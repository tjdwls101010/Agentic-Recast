"""헤드리스 Claude Code(`claude -p`) 워커 하나를 돌리고, 그 stream-json 출력을 이 스킬의 말(단계·글자 수·판정)로 바꾼다.

이벤트 모양은 claude 2.1.309에서 받은 실제 출력(레포 tests/fixtures/stream_*.jsonl)을 따른다. Claude Code가 이 모양을 바꾸면 고칠 곳은 이 모듈 하나다.
이벤트에는 원문(Read 결과)과 출력 본문(Write 입력)이 들어 있지만, 여기서 단계와 글자 수로 줄이고 버린다 — 밖으로 나가는 글은 워커의 마지막 답과 stderr 끝부분뿐이고 둘 다 TEXT_LIMIT에서 자른다.
"""

import json
import os
import queue
import re
import shutil
import signal
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# 성진: 무신호 하한 20분(2026-10-23 결정). 실측에서 xhigh 사고 중에도 이벤트가 1~1.5초 간격으로 와서 일하는 워커는 잘리지 않는다. RECAST_STALL_SECONDS는 테스트용으로만 덮어쓴다.
STALL_SECONDS = float(os.environ.get("RECAST_STALL_SECONDS", 20 * 60))
MODEL_ALIASES = ("opus", "sonnet", "haiku", "fable")
OUTPUT_TOKENS = "128000"
TEXT_LIMIT = 500

STARTING, READING, THINKING, WRITING, RATE_LIMITED = "시작", "읽는 중", "생각하는 중", "쓰는 중", "속도 제한 대기"
_EOF = object()


@dataclass(frozen=True)
class Progress:
    phase: str
    written_chars: int


@dataclass(frozen=True)
class Outcome:
    ok: bool
    kind: str | None  # None(성공) | stalled | stopped | crashed | error | denied | model
    reason: str
    models: tuple[str, ...]
    final_text: str
    longest_silence: float
    seconds: float


def binary() -> str | None:
    """워커로 띄울 claude 실행 파일. RECAST_CLAUDE_BIN이 있으면 그것(테스트용), 없으면 PATH의 claude. 실행할 수 없으면 None."""
    found = os.environ.get("RECAST_CLAUDE_BIN") or shutil.which("claude")
    return found if found and os.path.isfile(found) and os.access(found, os.X_OK) else None


def valid_model(name: str) -> bool:
    """별칭(opus·sonnet·haiku·fable)이나 claude- 로 시작하는 전체 모델 ID."""
    return name in MODEL_ALIASES or bool(re.fullmatch(r"claude-[a-z0-9][a-z0-9.-]*", name))


def _model_matches(requested: str, key: str) -> bool:
    if requested in MODEL_ALIASES:
        return key.startswith(f"claude-{requested}-")
    return key == requested or key.startswith(requested + "[")  # "[1m]" 같은 컨텍스트 꼬리표


def _cap(text: str) -> str:
    text = text.strip()
    return text if len(text) <= TEXT_LIMIT else text[: TEXT_LIMIT - 1] + "…"


def _tail(text: str) -> str:
    text = text.strip()
    return text if len(text) <= TEXT_LIMIT else "…" + text[-(TEXT_LIMIT - 1):]


class _Reader:
    """이벤트 한 줄씩 단계·글자 수·결과로 줄인다. 본문은 쓰는 중인 Write 입력만 글자 수를 세는 동안 잠깐 붙든다."""

    def __init__(self):
        self.phase = STARTING
        self.tool = None
        self.write_buffer = ""
        self.written = 0
        self.result = None
        self.denied = []  # (도구 이름, 경로)

    def feed(self, line: str) -> None:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return
        if not isinstance(event, dict):
            return
        kind = event.get("type")
        if kind == "stream_event":
            self._stream(event.get("event") or {})
        elif kind == "system":
            if event.get("subtype") == "thinking_tokens" and self.tool != "Write":
                self.phase = THINKING
        elif kind == "assistant":
            for block in (event.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    self.phase = WRITING if block.get("name") == "Write" else READING
        elif kind == "user":
            self.tool, self.write_buffer = None, ""
            self.phase = THINKING
        elif kind == "rate_limit_event":
            if (event.get("rate_limit_info") or {}).get("status") == "rejected":
                self.phase = RATE_LIMITED
        elif kind == "result":
            self.result = event
            for d in event.get("permission_denials") or []:
                if isinstance(d, dict):  # tool_input에는 거부된 Write의 본문이 통째로 있다 — 경로만 꺼낸다
                    tool_input = d.get("tool_input") if isinstance(d.get("tool_input"), dict) else {}
                    path = tool_input.get("file_path") or tool_input.get("path") or ""
                    self.denied.append((str(d.get("tool_name") or "?"), str(path)[:200]))

    def _stream(self, e: dict) -> None:
        if e.get("type") == "content_block_start":
            block = e.get("content_block") or {}
            if block.get("type") == "tool_use":
                self.tool, self.write_buffer = block.get("name"), ""
                self.phase = WRITING if self.tool == "Write" else READING
            elif block.get("type") in ("thinking", "text"):
                self.tool = None
                self.phase = THINKING
        elif e.get("type") == "content_block_delta":
            d = e.get("delta") or {}
            if d.get("type") == "input_json_delta" and self.tool == "Write":
                self.write_buffer += d.get("partial_json") or ""
                at = self.write_buffer.find('"content": "')
                if at < 0:
                    at = self.write_buffer.find('"content":"')
                    start = at + len('"content":"')
                else:
                    start = at + len('"content": "')
                if at >= 0:
                    self.written = max(0, len(self.write_buffer) - start - (2 if self.write_buffer.endswith('"}') else 0))
            elif d.get("type") == "thinking_delta" and self.tool is None:
                self.phase = THINKING


class Workers:
    """워커 프로세스들. stop()은 돌고 있는 워커를 끝내고 새 워커를 막는다."""

    def __init__(self, binary: str, grace: float = 10.0):
        self.binary = binary
        self.grace = grace
        self._live: set[subprocess.Popen] = set()
        self._lock = threading.Lock()
        self._stopping = threading.Event()

    def stop(self) -> None:
        self._stopping.set()
        with self._lock:
            live = list(self._live)
        for proc in live:
            self._kill(proc)

    def run(self, cwd: Path, prompt: str, *, model: str, effort: str, system_prompt: Path,
            on_progress: Callable[[Progress], None] | None = None, stall_seconds: float = STALL_SECONDS) -> Outcome:
        start = time.monotonic()
        argv = [self.binary, "-p", "--safe-mode", "--restricted", "--tools", "Read,Write", "--permission-mode", "acceptEdits",
                "--model", model, "--effort", effort, "--output-format", "stream-json", "--verbose",
                "--include-partial-messages", "--append-system-prompt-file", str(system_prompt)]
        env = {**os.environ, "CLAUDE_CODE_MAX_OUTPUT_TOKENS": OUTPUT_TOKENS}
        with self._lock:
            if self._stopping.is_set():
                return Outcome(False, "stopped", "사용자가 실행을 멈췄다", (), "", 0.0, 0.0)
            try:
                proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                        start_new_session=True)
            except OSError as e:
                return Outcome(False, "crashed", f"claude 실행 파일을 띄울 수 없다: {e}", (), "", 0.0, 0.0)
            self._live.add(proc)
        try:
            return self._follow(proc, prompt, model, on_progress, stall_seconds, start)
        finally:
            with self._lock:
                self._live.discard(proc)

    def _follow(self, proc, prompt, model, on_progress, stall_seconds, start) -> Outcome:
        lines: queue.Queue = queue.Queue()
        stderr_tail: deque[str] = deque(maxlen=4000)

        def pump_out():
            for line in proc.stdout:
                lines.put(line)
            lines.put(_EOF)

        def pump_err():
            for chunk in iter(lambda: proc.stderr.read(1024), ""):
                stderr_tail.extend(chunk)

        threads = [threading.Thread(target=pump_out, daemon=True), threading.Thread(target=pump_err, daemon=True)]
        for t in threads:
            t.start()
        try:
            proc.stdin.write(prompt)
            proc.stdin.close()
        except OSError:
            pass

        reader = _Reader()
        last = time.monotonic()
        longest = 0.0
        ended = None  # stalled | stopped
        if on_progress:
            on_progress(Progress(reader.phase, 0))
        while True:
            try:
                item = lines.get(timeout=0.2)
            except queue.Empty:
                if self._stopping.is_set():
                    ended = "stopped"
                elif time.monotonic() - last > stall_seconds:
                    ended = "stalled"
                if ended:
                    longest = max(longest, time.monotonic() - last)
                    self._kill(proc)
                    break
                continue
            if item is _EOF:
                break
            now = time.monotonic()
            longest = max(longest, now - last)
            last = now
            reader.feed(item)
            if on_progress:
                on_progress(Progress(reader.phase, reader.written))
        proc.wait()
        for t in threads:
            t.join(5)
        seconds = time.monotonic() - start
        return self._verdict(proc.returncode, reader, "".join(stderr_tail), model, ended, stall_seconds, longest, seconds)

    def _verdict(self, returncode, reader, stderr, model, ended, stall_seconds, longest, seconds) -> Outcome:
        result = reader.result or {}
        usage = result.get("modelUsage")
        models = tuple(sorted(usage)) if isinstance(usage, dict) else ()
        final = _cap(str(result.get("result") or ""))

        def fail(kind, reason):
            return Outcome(False, kind, reason, models, final, longest, seconds)

        if ended == "stopped" or (self._stopping.is_set() and reader.result is None):
            return fail("stopped", "사용자가 실행을 멈췄다")
        if ended == "stalled":
            return fail("stalled", f"워커에게서 {stall_seconds / 60:g}분 동안 신호가 없어 멈춘 것으로 보고 끝냈다")
        if returncode != 0:
            return fail("crashed", f"워커가 종료 코드 {returncode}로 끝났다: {_tail(stderr) or '(stderr 없음)'}")
        if reader.result is None:
            return fail("crashed", f"워커가 결과 없이 끝났다: {_tail(stderr) or '(stderr 없음)'}")
        if reader.denied:
            listed = ", ".join(f"{tool} {path}".strip() for tool, path in reader.denied)
            return fail("denied", f"권한이 거부됐다: {listed}")
        if not models:
            return fail("model", "결과에 modelUsage가 없어 실제 모델을 확인할 수 없다")
        others = [m for m in models if not _model_matches(model, m)]
        if others:
            return fail("model", f"요청한 모델({model})이 아닌 모델이 돌았다: {', '.join(others)}")
        if result.get("is_error"):
            return fail("error", f"워커가 오류로 끝났다: {final or result.get('subtype') or '(내용 없음)'}")
        return Outcome(True, None, "", models, final, longest, seconds)

    def _kill(self, proc: subprocess.Popen) -> None:
        """프로세스 그룹에 SIGTERM, grace 안에 끝나지 않으면 SIGKILL. 끝난 것을 확인한다."""
        for sig, wait in ((signal.SIGTERM, self.grace), (signal.SIGKILL, 30)):
            try:
                os.killpg(proc.pid, sig)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                proc.wait(timeout=wait)
                return
            except subprocess.TimeoutExpired:
                continue
