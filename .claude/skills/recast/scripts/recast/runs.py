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
    folder = paths.runs_dir()
    ids = sorted(p.stem for p in folder.glob("*.json") if _ID.fullmatch(p.stem)) if folder.is_dir() else []
    return ids[-1] if ids else None


def process_identity(pid: int) -> str | None:
    """pid의 프로세스 시작 시각(`ps -o lstart=`). 그 pid의 프로세스가 없으면 None."""
    try:
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() or None


def alive(record: dict) -> bool:
    """기록을 남긴 실행 프로세스가 아직 살아 있는가 — pid와 그 시작 시각이 둘 다 맞아야 한다(pid 재사용·재부팅에 안전, 잠자기 복귀는 살아 있음)."""
    started = record.get("process_start")
    return bool(started) and process_identity(int(record.get("pid", 0))) == started
