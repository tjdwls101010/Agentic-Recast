"""seam ⑤: 실제 claude가 recast.claude의 가정대로 동작하는지 확인한다. 돈이 들어 RECAST_LIVE=1일 때만 돈다(합성 원문, effort low).

RECAST_LIVE=1 uv run pytest -m live tests/test_live_contract.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from recast import claude

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.environ.get("RECAST_LIVE") != "1", reason="RECAST_LIVE=1일 때만 실제 claude를 부른다")]

CLI = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "recast" / "scripts" / "cli.py"
SOURCE = "# Synthetic Note\n\nThe river town had 1,400 residents in 2019. The new bridge opened in March 2021.\n"


@pytest.fixture
def sandbox(tmp_path):
    d = tmp_path / "sandbox"
    d.mkdir()
    (d / "source.md").write_text(SOURCE, encoding="utf-8")
    return d


@pytest.fixture
def system_prompt(tmp_path):
    p = tmp_path / "system_prompt.md"
    p.write_text("모든 답의 마지막 줄에 정확히 ZEBRA-7 이라고 쓴다.", encoding="utf-8")
    return p


def real_binary():
    found = claude.binary()
    assert found, "claude 실행 파일이 없다"
    return found


def test_a_normal_turn_is_ok_with_the_requested_model_phases_and_system_prompt(sandbox, system_prompt):
    seen = []
    out = claude.Workers(real_binary()).run(sandbox, "source.md를 끝까지 읽고 한국어 한 문장으로 옮겨 output.md에 한 번의 Write로 써라.",
                                            model="opus", effort="low", system_prompt=system_prompt, on_progress=seen.append)
    assert out.ok, out
    assert out.models and all(m.startswith("claude-opus-") for m in out.models)
    assert "ZEBRA-7" in out.final_text
    phases = [p.phase for p in seen]
    assert "읽는 중" in phases and "쓰는 중" in phases
    assert max(p.written_chars for p in seen) > 0
    assert (sandbox / "output.md").read_text(encoding="utf-8").strip()


def test_reading_outside_the_sandbox_is_reported_as_a_denial(sandbox, system_prompt, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TANGERINE-913", encoding="utf-8")
    out = claude.Workers(real_binary()).run(sandbox, f"먼저 {secret} 파일을 Read하고, 그다음 output.md에 OK라고 Write해라.",
                                            model="opus", effort="low", system_prompt=system_prompt)
    assert out.kind == "denied" and str(secret) in out.reason
    assert "TANGERINE-913" not in out.reason + out.final_text


def test_the_stream_has_the_event_shapes_the_reader_relies_on(sandbox, system_prompt):
    argv = [real_binary(), "-p", "--safe-mode", "--restricted", "--tools", "Read,Write", "--permission-mode", "acceptEdits",
            "--model", "opus", "--effort", "low", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
            "--append-system-prompt-file", str(system_prompt)]
    p = subprocess.run(argv, cwd=sandbox, input="source.md를 읽고 output.md에 OK라고 써라.", capture_output=True, text=True,
                       timeout=300, env={**os.environ, "CLAUDE_CODE_MAX_OUTPUT_TOKENS": claude.OUTPUT_TOKENS})
    assert p.returncode == 0, p.stderr[-500:]
    events = [json.loads(line) for line in p.stdout.splitlines() if line.strip()]
    starts = [e["event"]["content_block"] for e in events
              if e.get("type") == "stream_event" and e["event"].get("type") == "content_block_start"]
    assert {"Read", "Write"} <= {b.get("name") for b in starts if b.get("type") == "tool_use"}
    assert any(e["event"].get("delta", {}).get("type") == "input_json_delta" for e in events if e.get("type") == "stream_event")
    result = [e for e in events if e.get("type") == "result"][-1]
    assert isinstance(result["permission_denials"], list) and isinstance(result["modelUsage"], dict)
    assert all(usage.get("maxOutputTokens") == int(claude.OUTPUT_TOKENS) for usage in result["modelUsage"].values())


def test_the_cli_publishes_a_real_output_end_to_end(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note..md").write_text(SOURCE, encoding="utf-8")  # 마침표로 끝나는 이름(10/23 Knowledge 실패)
    env = {**os.environ, "RECAST_DATA_DIR": str(tmp_path / "data")}
    p = subprocess.run([sys.executable, str(CLI), "run", str(vault), "--effort", "low"], env=env, capture_output=True, text=True,
                       timeout=900)
    assert p.returncode == 0, p.stderr
    result = json.loads(p.stdout)
    f = result["files"][0]
    assert f["status"] == "done" and all(m.startswith("claude-opus-") for m in f["models"])
    assert (vault / "Recast_note..md").read_text(encoding="utf-8").strip()
