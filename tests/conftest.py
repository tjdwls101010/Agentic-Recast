import json
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
FAKE = TESTS / "fake_claude.py"
FIXTURES = TESTS / "fixtures"


class Fake:
    """가짜 claude의 시나리오와 호출 기록."""

    def __init__(self, home: Path):
        home.mkdir()
        self.home = home
        self.scenario_path = home / "scenario.json"
        self.calls_path = home / "calls.jsonl"
        self.scenario()

    def scenario(self, default: dict | None = None, **by_name: dict):
        """원래 파일 이름별 행동. 이름에 없는 파일은 default를 쓴다."""
        self.scenario_path.write_text(json.dumps({"*": default or {}, **by_name}, ensure_ascii=False), encoding="utf-8")

    def calls(self) -> list[dict]:
        if not self.calls_path.exists():
            return []
        return [json.loads(line) for line in self.calls_path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def fake(tmp_path, monkeypatch):
    f = Fake(tmp_path / "fake_home")
    monkeypatch.setenv("RECAST_CLAUDE_BIN", str(FAKE))
    monkeypatch.setenv("FAKE_CLAUDE_SCENARIO", str(f.scenario_path))
    monkeypatch.setenv("FAKE_CLAUDE_CALLS", str(f.calls_path))
    return f
