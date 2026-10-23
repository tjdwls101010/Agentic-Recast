"""스킬이 읽고 쓰는 파일의 자리."""

import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SYSTEM_PROMPT = Path(__file__).resolve().with_name("system_prompt.md")


def runs_dir() -> Path:
    """실행 기록 폴더. RECAST_DATA_DIR은 테스트가 기록을 임시 폴더로 돌리는 데만 쓴다."""
    return Path(os.environ.get("RECAST_DATA_DIR") or SKILL_DIR / "data") / "runs"
