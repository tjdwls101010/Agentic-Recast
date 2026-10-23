"""실행 기록(data/runs/<run-id>.json): 실행 하나의 파일별 상태. 쓰기는 원자적이고, 원문·출력 본문은 담지 않는다."""

import json
import os
import re
import secrets
import subprocess
import tempfile
import time
from pathlib import Path

from . import paths

_ID = re.compile(r"\d{8}-\d{6}-[0-9a-f]{4}")
HEARTBEAT_SECONDS = 30
STALE_SECONDS = 120


class Unavailable(Exception):
    """ps를 쓸 수 없어 프로세스를 확인할 수 없다."""


def new_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


def save(run_id: str, record: dict) -> None:
    folder = paths.runs_dir()
    folder.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=f".{run_id}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=1)
        os.replace(tmp, folder / f"{run_id}.json")
    finally:
        Path(tmp).unlink(missing_ok=True)


def load(run_id: str) -> dict | None:
    if not _ID.fullmatch(run_id):
        return None
    try:
        return json.loads((paths.runs_dir() / f"{run_id}.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def latest() -> str | None:
    """가장 늦게 시작한 실행의 id. id의 꼬리는 무작위라 같은 초에 시작한 실행끼리는 이름 순서가 시작 순서가 아니다."""
    folder = paths.runs_dir()
    found = []
    for p in folder.glob("*.json") if folder.is_dir() else []:
        record = load(p.stem)
        if record is not None:
            found.append((record.get("started_at", 0.0), p.stem))
    return max(found)[1] if found else None


def process_identity(pid: int) -> str | None:
    """pid의 프로세스 시작 시각(`ps -o lstart=`). 그 pid의 프로세스가 없으면 None, ps를 쓸 수 없으면 Unavailable."""
    try:
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Unavailable(str(e)) from e
    return out.stdout.strip() or None


def alive(record: dict) -> bool:
    """기록을 남긴 실행 프로세스가 아직 살아 있는가.

    pid와 그 시작 시각이 둘 다 맞으면 산 것이다 — pid 재사용·재부팅·강제 종료에 안전하고, 잠자기에서 깨어난 실행은 산 것으로 본다. ps를 쓸 수 없으면(샌드박스 등) 실행이 HEARTBEAT_SECONDS마다 갱신하는 updated_at이 STALE_SECONDS 안이면 산 것으로 본다.
    """
    started = record.get("process_start")
    if started:
        try:
            return process_identity(int(record.get("pid", 0))) == started
        except Unavailable:
            pass
    return time.time() - float(record.get("updated_at", 0)) <= STALE_SECONDS
