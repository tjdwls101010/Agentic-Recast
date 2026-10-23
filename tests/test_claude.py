"""seam ②: recast.claude — 헤드리스 워커 호출, stream-json 이벤트 → 단계·글자 수, 결과 판정, 멈춤과 중단."""

import json
import os
import threading
import time

import pytest

from conftest import FAKE, FIXTURES
from recast import claude

PROMPT = "원래 파일 이름: a.md\n원문을 끝까지 읽고 output.md에 쓴다."


@pytest.fixture
def sandbox(tmp_path):
    d = tmp_path / "sandbox"
    d.mkdir()
    (d / "source.md").write_text("The river town had 1,400 residents in 2019.\n", encoding="utf-8")
    return d


@pytest.fixture
def system_prompt(tmp_path):
    p = tmp_path / "system_prompt.md"
    p.write_text("원칙", encoding="utf-8")
    return p


def run(sandbox, system_prompt, model="opus", effort="xhigh", grace=1.0, **kw):
    seen = []
    out = claude.Workers(str(FAKE), grace=grace).run(sandbox, PROMPT, model=model, effort=effort, system_prompt=system_prompt,
                                                     on_progress=seen.append, **kw)
    return out, seen


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_binary_prefers_the_env_override_then_path_and_needs_an_executable(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "claude"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    override = tmp_path / "override-claude"
    override.write_text("#!/bin/sh\n")
    override.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("RECAST_CLAUDE_BIN", str(override))
    assert claude.binary() == str(override)
    monkeypatch.setenv("RECAST_CLAUDE_BIN", str(tmp_path / "missing-claude"))
    assert claude.binary() is None
    monkeypatch.delenv("RECAST_CLAUDE_BIN")
    assert claude.binary() == str(exe)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert claude.binary() is None


def test_worker_gets_the_fixed_flags_the_model_effort_cwd_prompt_and_output_cap(fake, sandbox, system_prompt):
    out, _ = run(sandbox, system_prompt, model="sonnet", effort="high", )
    call = fake.calls()[0]
    assert call["argv"] == ["-p", "--safe-mode", "--restricted", "--tools", "Read,Write", "--permission-mode", "acceptEdits",
                            "--model", "sonnet", "--effort", "high", "--output-format", "stream-json", "--verbose",
                            "--include-partial-messages", "--append-system-prompt-file", str(system_prompt)]
    assert call["cwd"] == str(sandbox)
    assert call["prompt"] == PROMPT
    assert call["env"]["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "128000"


def test_real_stream_succeeds_with_read_then_write_phases(fake, sandbox, system_prompt):
    fixture = FIXTURES / "stream_ok.jsonl"
    fake.scenario({"replay": str(fixture)})
    events = [json.loads(line) for line in fixture.read_text(encoding="utf-8").splitlines()]
    written = next(c["input"]["content"] for e in events if e["type"] == "assistant"
                   for c in e["message"]["content"] if c.get("name") == "Write")
    final = next(e["result"] for e in events if e["type"] == "result")
    out, seen = run(sandbox, system_prompt)
    assert out.ok and out.kind is None, out
    assert out.models == ("claude-opus-5-5",)
    assert out.final_text == final
    phases = [p.phase for p in seen]
    assert phases[0] == "시작"
    assert phases.index("읽는 중") < phases.index("쓰는 중")
    assert abs(max(p.written_chars for p in seen) - len(written)) <= 3


def test_real_denied_stream_fails_naming_only_the_tool_and_path(fake, sandbox, system_prompt):
    fake.scenario({"replay": str(FIXTURES / "stream_denied.jsonl")})
    out, _ = run(sandbox, system_prompt)
    assert not out.ok and out.kind == "denied"
    assert "Read" in out.reason and "/outside/secret.txt" in out.reason


def test_denied_write_reports_no_body(fake, sandbox, system_prompt):
    fake.scenario({"deny_write": True, "marker": "MARKER-7Q"})
    out, _ = run(sandbox, system_prompt)
    assert out.kind == "denied" and "Write" in out.reason
    assert "MARKER-7Q" not in out.reason + out.final_text


def test_nonzero_exit_reports_the_end_of_stderr_capped(fake, sandbox, system_prompt):
    fake.scenario({"exit": 3, "stderr": "E" * 2000 + "TAIL-OF-STDERR"})
    out, _ = run(sandbox, system_prompt)
    assert out.kind == "crashed" and "3" in out.reason and "TAIL-OF-STDERR" in out.reason
    assert len(out.reason) <= 600


def test_ending_without_a_result_event_is_crashed(fake, sandbox, system_prompt):
    fake.scenario({"no_result": True})
    out, _ = run(sandbox, system_prompt)
    assert out.kind == "crashed"


def test_error_result_carries_the_worker_text_capped(fake, sandbox, system_prompt):
    fake.scenario({"is_error": True, "result_text": "X" * 1000})
    out, _ = run(sandbox, system_prompt)
    assert out.kind == "error" and len(out.final_text) <= 500


@pytest.mark.parametrize("requested, models, ok", [
    ("opus", ["claude-opus-5-5"], True),
    ("opus", ["claude-sonnet-5-5"], False),
    ("opus", ["claude-opus-5-5", "claude-haiku-5-5"], False),
    ("opus", [], False),
    ("sonnet", ["claude-sonnet-5-5"], True),
    ("claude-opus-5-5", ["claude-opus-5-5"], True),
    ("claude-opus-5", ["claude-opus-5-5"], False),
])
def test_model_is_judged_against_the_requested_model(fake, sandbox, system_prompt, requested, models, ok):
    fake.scenario({"models": models})
    out, _ = run(sandbox, system_prompt, model=requested)
    assert out.ok is ok
    if not ok:
        assert out.kind == "model"


@pytest.mark.parametrize("name, ok", [("opus", True), ("fable", True), ("claude-opus-5-5", True),
                                      ("Opus", False), ("gpt-6", False), ("", False)])
def test_valid_model_names(name, ok):
    assert claude.valid_model(name) is ok


def test_silence_past_the_stall_limit_ends_the_worker_and_its_children(fake, sandbox, system_prompt, tmp_path):
    pid_file = tmp_path / "child.pid"
    fake.scenario({"silent": 60, "child_pid_file": str(pid_file)})
    start = time.monotonic()
    out, _ = run(sandbox, system_prompt, stall_seconds=1)
    assert out.kind == "stalled" and time.monotonic() - start < 15
    child = int(pid_file.read_text())
    deadline = time.monotonic() + 5
    while alive(child) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not alive(child)


def test_stall_also_ends_a_worker_that_ignores_sigterm(fake, sandbox, system_prompt):
    fake.scenario({"silent": 60, "ignore_term": True})
    start = time.monotonic()
    out, _ = run(sandbox, system_prompt, stall_seconds=1, grace=1)
    assert out.kind == "stalled" and time.monotonic() - start < 15
    assert not alive(fake.calls()[0]["pid"])


def test_stop_ends_a_running_worker_and_refuses_new_ones(fake, sandbox, system_prompt):
    fake.scenario({"silent": 60})
    workers = claude.Workers(str(FAKE), grace=1)
    result = {}
    t = threading.Thread(target=lambda: result.update(out=workers.run(sandbox, PROMPT, model="opus", effort="xhigh",
                                                                       system_prompt=system_prompt)))
    t.start()
    deadline = time.monotonic() + 10
    while not fake.calls() and time.monotonic() < deadline:
        time.sleep(0.05)
    workers.stop()
    t.join(15)
    assert result["out"].kind == "stopped"
    assert not alive(fake.calls()[0]["pid"])
    again = workers.run(sandbox, PROMPT, model="opus", effort="xhigh", system_prompt=system_prompt)
    assert again.kind == "stopped" and len(fake.calls()) == 1


def test_rejected_rate_limit_shows_a_waiting_phase(fake, sandbox, system_prompt):
    fake.scenario({"rate_limited": True})
    out, seen = run(sandbox, system_prompt)
    assert out.ok and "속도 제한 대기" in [p.phase for p in seen]


def test_longest_silence_is_measured(fake, sandbox, system_prompt):
    fake.scenario({"delay": 0.3})
    out, _ = run(sandbox, system_prompt)
    assert out.ok and 0.3 <= out.longest_silence < 5


def test_a_missing_binary_fails_the_worker_without_raising(sandbox, system_prompt):
    out = claude.Workers("/nonexistent/claude").run(sandbox, PROMPT, model="opus", effort="xhigh", system_prompt=system_prompt)
    assert out.kind == "crashed" and "claude" in out.reason


def test_a_failing_progress_callback_does_not_orphan_the_worker(fake, sandbox, system_prompt):
    fake.scenario({"delay": 0.2})

    def explode(progress):
        if progress.phase != claude.STARTING:
            raise RuntimeError("기록을 쓸 수 없다")

    with pytest.raises(RuntimeError):
        claude.Workers(str(FAKE), grace=1).run(sandbox, PROMPT, model="opus", effort="xhigh", system_prompt=system_prompt,
                                               on_progress=explode)
    assert not alive(fake.calls()[0]["pid"])
