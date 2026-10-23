"""run 명령: 원문마다 깨끗한 헤드리스 워커 하나로 재구조화하고, 판정을 통과한 출력만 원문 옆에 게시한다."""

import hashlib
import os
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import claude, paths, publish, runs, sources

MODELS = claude.MODEL_ALIASES
EFFORTS = ("low", "medium", "high", "xhigh", "max")
valid_model = claude.valid_model
SAVE_EVERY = 2.0  # 진행 이벤트로 실행 기록을 다시 쓰는 최소 간격(초)

RETRY = "같은 명령을 다시 실행하면 끝난 파일은 건너뛰고 이 파일만 다시 한다"
NEXT = {
    "stalled": RETRY,
    "crashed": RETRY,
    "error": RETRY,
    "model": RETRY,
    "denied": "워커가 원문 사본 밖을 건드리려 했다 — reason의 도구와 경로를 확인하고 다시 실행한다",
    "no_output": "worker_said를 확인한다 — 원문이 망가졌거나 재구조화할 지식이 없다고 판단했을 수 있다",
    "utf8": "원문을 UTF-8로 저장한 뒤 다시 실행한다",
    "unreadable": "원문 파일을 확인한 뒤 다시 실행한다",
    "changed": "다시 실행하면 바뀐 원문으로 처음부터 한다",
    "publish": "원문 폴더의 쓰기 권한과 볼륨을 확인한다",
    "internal": "같은 명령을 다시 실행하고, 되풀이되면 알린다 — 버그일 수 있다",
}


class SetupError(Exception):
    """claude 실행 파일이나 워커 지시문이 없어 아무 파일도 시작할 수 없다."""


@dataclass(frozen=True)
class Options:
    instructions: str | None = None
    force: bool = False
    jobs: int = 8
    model: str = "opus"
    effort: str = "xhigh"


def prompt(name: str, lines: int, instructions: str | None) -> str:
    """워커 프롬프트 — 읽을 것, 쓸 것, 쓸 수 없을 때. 재구조화 원칙은 시스템 프롬프트(system_prompt.md)가 갖는다."""
    text = (f"원래 파일 이름: {name}\n\n"
            f"원문은 이 폴더의 source.md다({lines}줄). 처음부터 끝까지 읽는다 — Read 결과가 중간에서 끊기면 offset으로 이어 읽어 {lines}번째 줄까지 읽는다.\n"
            "다 읽었으면 재구조화한 글 전체를 output.md에 한 번의 Write로 쓴다.\n"
            "원문에서 재구조화할 지식을 찾을 수 없으면 output.md를 쓰지 않고 그 이유를 답한다.")
    if instructions:
        text += f"\n\n사용자 지시(이 원문에 적용한다): {instructions}"
    return text


def execute(paths_: list[str], options: Options, on_line: Callable[[str], None] | None = None,
            stop: threading.Event | None = None) -> dict:
    """원문을 고르고, 실행 기록을 열고, 파일마다 워커를 돌려 요약을 돌려준다. 잘못된 경로는 sources.UsageError, 환경 문제는 SetupError(둘 다 아무것도 시작하기 전).

    stop이 켜지면(언제든) 돌던 워커를 끝내고 아직 시작하지 않은 파일은 띄우지 않으며, 그래도 요약을 돌려준다.
    """
    targets = sources.targets(paths_, options.force)
    binary = claude.binary()
    if not binary:
        raise SetupError("claude 실행 파일을 찾을 수 없다: Claude Code CLI를 설치하거나 PATH에 넣는다")
    if not paths.SYSTEM_PROMPT.is_file():
        raise SetupError(f"워커 지시문이 없다: {paths.SYSTEM_PROMPT}")
    return _Batch(targets, options, binary, on_line or (lambda line: None), stop or threading.Event()).go()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _duration(seconds: float) -> str:
    minutes, sec = divmod(int(round(seconds)), 60)
    return f"{minutes}분 {sec}초" if minutes else f"{sec}초"


class _Batch:
    def __init__(self, targets: list[sources.Target], options: Options, binary: str, on_line: Callable[[str], None],
                 stop: threading.Event):
        self.targets, self.options, self.on_line, self.stop = targets, options, on_line, stop
        self.record_error = None
        self.workers = claude.Workers(binary)
        self.lock = threading.Lock()
        self.id = runs.new_id()
        self.last_save = 0.0
        now = time.time()
        files = [{"source": str(t.source), "output": str(t.output), "status": "skipped" if t.skip else "queued",
                  **({"reason": t.skip} if t.skip else {})} for t in targets]
        try:
            identity = runs.process_identity(os.getpid())
        except runs.Unavailable:
            identity = None  # status는 하트비트로 판정한다
        self.record = {"run": self.id, "pid": os.getpid(), "process_start": identity,
                       "state": "running", "started_at": now, "updated_at": now, "finished_at": None,
                       "options": {"model": options.model, "effort": options.effort, "jobs": options.jobs,
                                   "force": options.force, "instructions": options.instructions},
                       "files": files}

    # ── 기록 ──────────────────────────────────────────────────────────
    def save(self, throttle: bool = False) -> None:
        """기록을 쓴다. 쓰지 못해도 작업은 계속하고, 첫 오류를 요약의 warning으로 남긴다."""
        with self.lock:
            now = time.time()
            if throttle and now - self.last_save < SAVE_EVERY:
                return
            self.last_save = now
            self.record["updated_at"] = now
            try:
                runs.save(self.id, self.record)
            except OSError as e:
                self.record_error = self.record_error or f"실행 기록을 쓸 수 없다({e.strerror or e}) — status로 진행을 볼 수 없다"

    def heartbeat(self, done: threading.Event) -> None:
        while not done.wait(runs.HEARTBEAT_SECONDS):
            self.save()

    def progress(self, i: int, p: claude.Progress) -> None:
        with self.lock:
            entry, now = self.record["files"][i], time.time()
            if entry.get("phase") != p.phase:
                entry["phase"], entry["phase_since"] = p.phase, now
            entry["written_chars"] = p.written_chars
            entry["last_signal_at"] = now
        self.save(throttle=True)

    def finish(self, i: int, status: str, **fields) -> None:
        with self.lock:
            entry, now = self.record["files"][i], time.time()
            for key in ("phase", "phase_since", "written_chars", "last_signal_at"):
                entry.pop(key, None)
            entry.update(status=status, finished_at=now, seconds=round(now - entry.get("started_at", now), 1),
                         **{k: v for k, v in fields.items() if v not in (None, "")})
            line = self._line(entry)
        self.save()
        self.on_line(line)

    @staticmethod
    def _line(e: dict) -> str:
        name = Path(e["source"]).name
        if e["status"] == "done":
            return f"✅ {name} — 원문 {e['source_chars']:,}자 → 출력 {e['output_chars']:,}자, {_duration(e['seconds'])}"
        mark = {"failed": "❌", "skipped": "⏭️", "interrupted": "⏹️"}[e["status"]]
        return f"{mark} {name} — {e.get('reason', '')}"

    # ── 실행 ──────────────────────────────────────────────────────────
    def go(self) -> dict:
        self.save()
        for entry in self.record["files"]:
            if entry["status"] == "skipped":
                self.on_line(self._line(entry))
        done = threading.Event()
        threading.Thread(target=self.heartbeat, args=(done,), daemon=True).start()
        pool = ThreadPoolExecutor(max_workers=self.options.jobs)
        try:
            pending = {pool.submit(self.one, i) for i, t in enumerate(self.targets) if not t.skip}
            stopping = False
            while pending:
                finished, pending = wait(pending, timeout=0.2)
                for f in finished:
                    f.result()
                if self.stop.is_set() and not stopping:
                    stopping = True
                    self.workers.stop()  # 돌던 워커는 끝나고, 대기 중인 파일은 one()이 시작하지 않는다
        finally:
            pool.shutdown(wait=True)
            done.set()
        with self.lock:
            files = self.record["files"]
            self.record["state"] = "interrupted" if any(f["status"] == "interrupted" for f in files) else "finished"
            self.record["finished_at"] = time.time()
        self.save()
        return self.summary()

    def one(self, i: int) -> None:
        if self.stop.is_set():
            return self.finish(i, "interrupted", reason="시작하기 전에 멈췄다")
        target, now = self.targets[i], time.time()
        with self.lock:
            self.record["files"][i].update(status="running", started_at=now, phase=claude.STARTING, phase_since=now,
                                           written_chars=0, last_signal_at=now)
        self.save()
        sandbox = None
        try:
            try:
                raw = target.source.read_bytes()
            except OSError as e:
                return self.finish(i, "failed", reason=f"원문을 읽을 수 없다: {e.strerror or e}", next=NEXT["unreadable"])
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                return self.finish(i, "failed", reason="원문을 UTF-8로 읽을 수 없다", next=NEXT["utf8"])
            with self.lock:
                self.record["files"][i]["source_chars"] = len(text)
            sandbox = Path(tempfile.mkdtemp(prefix="recast-"))
            (sandbox / "source.md").write_bytes(raw)
            out = self.workers.run(sandbox, prompt(target.source.name, len(text.splitlines()), self.options.instructions),
                                   model=self.options.model, effort=self.options.effort, system_prompt=paths.SYSTEM_PROMPT,
                                   on_progress=lambda p: self.progress(i, p))
            seen = {"models": list(out.models), "longest_silence": round(out.longest_silence, 1)}
            if out.kind == "stopped":
                return self.finish(i, "interrupted", reason=out.reason, **seen)
            if not out.ok:
                return self.finish(i, "failed", reason=out.reason, next=NEXT[out.kind], worker_said=out.final_text, **seen)
            produced = sandbox / "output.md"
            data = produced.read_bytes() if produced.is_file() else b""
            if not data.strip():
                return self.finish(i, "failed", reason="워커가 output.md를 쓰지 않았다", next=NEXT["no_output"],
                                   worker_said=out.final_text or "(답 없음)", **seen)
            try:
                current = target.source.read_bytes()
            except OSError:
                current = None
            if current is None or _sha(current) != _sha(raw):
                return self.finish(i, "failed", reason="작업 도중 원문이 바뀌었다", next=NEXT["changed"], **seen)
            try:
                publish.publish(target.output, data, force=self.options.force)
            except publish.Exists:
                return self.finish(i, "skipped", reason=f"처리 도중 다른 실행이 먼저 {target.output.name}을 썼다(덮지 않았다)", **seen)
            except publish.PublishError as e:
                return self.finish(i, "failed", reason=f"게시하지 못했다: {e}", next=NEXT["publish"], **seen)
            return self.finish(i, "done", output_chars=len(data.decode("utf-8", errors="replace")), **seen)
        except Exception as e:  # 한 파일의 버그가 배치 전체를 멈추지 않게 한다
            return self.finish(i, "failed", reason=f"내부 오류: {type(e).__name__}: {e}"[:500], next=NEXT["internal"])
        finally:
            if sandbox:
                shutil.rmtree(sandbox, ignore_errors=True)

    # ── 요약 ──────────────────────────────────────────────────────────
    def summary(self) -> dict:
        keys = ("source", "status", "output", "source_chars", "output_chars", "seconds", "models", "reason", "next", "worker_said")
        with self.lock:
            files = self.record["files"]
            counts = {s: sum(1 for f in files if f["status"] == s) for s in ("done", "failed", "skipped", "interrupted")}
            state = self.record["state"]
            seconds = round(self.record["finished_at"] - self.record["started_at"], 1)
            listed = [{k: f[k] for k in keys if k in f and not (k == "output" and f["status"] != "done")} for f in files]
        if state == "interrupted":
            next_step = "같은 명령을 다시 실행하면 끝난 파일은 건너뛰고 나머지를 한다"
        elif counts["failed"]:
            next_step = "실패한 파일은 reason과 next를 본다 — 같은 명령을 다시 실행하면 끝난 파일은 건너뛰고 실패한 파일만 다시 한다"
        else:
            next_step = "끝났다 — 출력은 각 원문 옆의 Recast_ 파일이다"
        result = {"run": self.id, "state": state, "summary": {"total": len(files), **counts, "seconds": seconds},
                  "files": listed, "next": next_step}
        if self.record_error:
            result["warning"] = self.record_error
        return result
