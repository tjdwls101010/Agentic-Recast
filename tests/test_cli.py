"""seam ①: cli.py를 서브프로세스로 돌린다 — run·status의 프로토콜(stdout JSON, stderr 진행, 종료 코드)과 게시 결과."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import FAKE

CLI = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "recast" / "scripts" / "cli.py"
SOURCE = "# 강변 마을\n\nThe river town had 1,400 residents in 2019. The bridge opened in March 2021.\n"


@pytest.fixture
def env(fake, tmp_path):
    e = {**os.environ, "RECAST_DATA_DIR": str(tmp_path / "data"), "RECAST_CLAUDE_BIN": str(FAKE),
         "FAKE_CLAUDE_SCENARIO": str(fake.scenario_path), "FAKE_CLAUDE_CALLS": str(fake.calls_path)}
    e.pop("RECAST_STALL_SECONDS", None)
    return e


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "vault"
    v.mkdir()
    for name in ["a.md", "b.md"]:
        (v / name).write_text(SOURCE, encoding="utf-8")
    return v


def cli(env, *args, timeout=60):
    return subprocess.run([sys.executable, str(CLI), *args], env=env, capture_output=True, text=True, timeout=timeout)


def run_json(env, *args):
    p = cli(env, "run", *args)
    return p, json.loads(p.stdout) if p.stdout.strip() else None


def by_source(result):
    return {Path(f["source"]).name: f for f in result["files"]}


def records(env):
    d = Path(env["RECAST_DATA_DIR"]) / "runs"
    return sorted(d.glob("*.json")) if d.exists() else []


# ── A. 정상 실행 ─────────────────────────────────────────────────────

def test_a_folder_run_publishes_each_output_beside_its_source(env, vault, fake):
    p, out = run_json(env, str(vault))
    assert p.returncode == 0, p.stderr
    assert out["state"] == "finished"
    assert out["summary"]["total"] == 2 and out["summary"]["done"] == 2
    for name in ["a.md", "b.md"]:
        f = by_source(out)[name]
        assert f["status"] == "done"
        assert f["output"] == str(vault / f"Recast_{name}")
        assert f["models"] == ["claude-opus-5-5"]
        assert f["source_chars"] == len(SOURCE)
        text = (vault / f"Recast_{name}").read_text(encoding="utf-8")
        assert text.startswith("# 🖇️") and f["output_chars"] == len(text)
    assert len(fake.calls()) == 2
    assert all(not Path(c["cwd"]).exists() for c in fake.calls())  # 샌드박스는 지운다


def test_the_worker_sees_only_a_copy_with_the_original_name_and_line_count(env, vault, fake):
    run_json(env, str(vault / "a.md"), "--instructions", "경제 개념을 자세히")
    call = fake.calls()[0]
    assert call["cwd"] != str(vault)
    assert "원래 파일 이름: a.md" in call["prompt"]
    assert f"{len(SOURCE.splitlines())}줄" in call["prompt"]
    assert "경제 개념을 자세히" in call["prompt"]
    assert "output.md" in call["prompt"]


def test_model_and_effort_default_to_opus_xhigh_and_can_be_set(env, vault, fake):
    run_json(env, str(vault / "a.md"))
    fake.scenario({"models": ["claude-sonnet-5-5"]})
    p, out = run_json(env, str(vault / "b.md"), "--model", "sonnet", "--effort", "high")
    argv = [c["argv"] for c in fake.calls()]
    assert argv[0][argv[0].index("--model") + 1] == "opus" and argv[0][argv[0].index("--effort") + 1] == "xhigh"
    assert argv[1][argv[1].index("--model") + 1] == "sonnet" and argv[1][argv[1].index("--effort") + 1] == "high"
    assert p.returncode == 0 and by_source(out)["b.md"]["status"] == "done"


def test_an_existing_recast_output_is_skipped_and_force_rewrites_it(env, vault, fake):
    (vault / "Recast_a.md").write_text("성진이 고친 글", encoding="utf-8")
    (vault / "Reconstruct_b.md").write_text("옛 출력", encoding="utf-8")
    p, out = run_json(env, str(vault))
    assert p.returncode == 0
    assert by_source(out)["a.md"]["status"] == "skipped" and "--force" in by_source(out)["a.md"]["reason"]
    assert by_source(out)["b.md"]["status"] == "done"  # 옛 Reconstruct_는 완료로 보지 않는다
    assert (vault / "Recast_a.md").read_text(encoding="utf-8") == "성진이 고친 글"
    assert (vault / "Reconstruct_b.md").read_text(encoding="utf-8") == "옛 출력"
    assert len(fake.calls()) == 1
    p, out = run_json(env, str(vault / "a.md"), "--force")
    assert by_source(out)["a.md"]["status"] == "done"
    assert (vault / "Recast_a.md").read_text(encoding="utf-8").startswith("# 🖇️")


def test_stderr_reports_one_line_per_file(env, vault):
    p, _ = run_json(env, str(vault))
    lines = [line for line in p.stderr.splitlines() if line.strip()]
    assert len([line for line in lines if line.startswith("✅")]) == 2


@pytest.mark.parametrize("args", [
    ["run"],
    ["run", "missing.md"],
    ["run", "a.md", "--jobs", "0"],
    ["run", "a.md", "--model", "gpt-6"],
    ["run", "a.md", "--effort", "extreme"],
    ["status", "no-such-run"],
])
def test_usage_errors_exit_2(env, vault, args):
    args = [str(vault / a) if a.endswith(".md") else a for a in args]
    p = cli(env, *args)
    assert p.returncode == 2, (p.stdout, p.stderr)


def test_a_missing_claude_refuses_before_starting(env, vault, tmp_path):
    env = {**env, "RECAST_CLAUDE_BIN": "", "PATH": str(tmp_path / "nowhere")}
    p = cli(env, "run", str(vault))
    assert p.returncode == 3 and "claude" in p.stderr
    assert not list(vault.glob("Recast_*")) and not records(env)


def test_help_describes_every_argument_default_and_exit_code(env):
    top = cli(env, "--help").stdout
    run = cli(env, "run", "--help").stdout
    status = cli(env, "status", "--help").stdout
    assert "run" in top and "status" in top
    for needle in ["--instructions", "--force", "--jobs", "--model", "--effort", "opus", "xhigh", "되돌릴 수 없", "20분",
                   "Recast_", "Reconstruct_", "130", " 3 "]:
        assert needle in run, needle
    for needle in ["RUN_ID", "running", "interrupted"]:
        assert needle in status, needle


# ── B. 실패 판정과 본문 차단 ─────────────────────────────────────────

@pytest.mark.parametrize("behavior, needle", [
    ({"exit": 3, "stderr": "boom"}, "종료 코드"),
    ({"no_result": True}, "결과 없이"),
    ({"is_error": True, "result_text": "API 오류"}, "오류"),
    ({"deny_write": True}, "권한"),
    ({"models": ["claude-sonnet-5-5"]}, "모델"),
    ({"output": None, "result_text": "원문이 깨져 재구조화할 수 없다"}, "output.md"),
])
def test_each_worker_failure_is_reported_and_nothing_is_published(env, vault, fake, behavior, needle):
    fake.scenario(behavior)
    p, out = run_json(env, str(vault / "a.md"))
    f = by_source(out)["a.md"]
    assert p.returncode == 1 and out["summary"]["failed"] == 1
    assert f["status"] == "failed" and needle in f["reason"] and f["next"]
    assert not (vault / "Recast_a.md").exists() and not list(vault.glob(".Recast_*"))


def test_a_missing_output_passes_the_worker_answer_through(env, vault, fake):
    fake.scenario({"output": None, "result_text": "원문이 깨져 재구조화할 수 없다"})
    _, out = run_json(env, str(vault / "a.md"))
    assert by_source(out)["a.md"]["worker_said"] == "원문이 깨져 재구조화할 수 없다"


def test_a_silent_worker_is_ended_and_only_its_file_fails(env, vault, fake):
    fake.scenario({}, **{"b.md": {"silent": 60}})
    start = time.monotonic()
    p, out = run_json({**env, "RECAST_STALL_SECONDS": "2"}, str(vault))
    assert time.monotonic() - start < 40
    assert p.returncode == 1
    assert by_source(out)["a.md"]["status"] == "done"
    assert by_source(out)["b.md"]["status"] == "failed" and "신호" in by_source(out)["b.md"]["reason"]


def test_a_source_that_is_not_utf8_fails_without_a_worker(env, vault, fake):
    (vault / "c.md").write_bytes(b"\xff\xfe broken \x80")
    p, out = run_json(env, str(vault))
    assert by_source(out)["c.md"]["status"] == "failed" and "UTF-8" in by_source(out)["c.md"]["reason"]
    assert sorted(Path(c["prompt"].split("\n")[0].split(": ")[1]).name for c in fake.calls()) == ["a.md", "b.md"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root는 권한을 무시한다")
def test_a_folder_that_cannot_be_written_fails_at_publish(env, vault):
    vault.chmod(0o555)
    try:
        p, out = run_json(env, str(vault / "a.md"))
    finally:
        vault.chmod(0o755)
    f = by_source(out)["a.md"]
    assert p.returncode == 1 and f["status"] == "failed" and "게시" in f["reason"]


def test_source_and_output_text_never_leave_the_cli(env, vault, fake):
    marker = "MARKER-" + "Q" * 24
    (vault / "c.md").write_text(SOURCE, encoding="utf-8")
    fake.scenario({"marker": marker}, **{"b.md": {"deny_write": True, "marker": marker},
                                         "c.md": {"is_error": True, "result_text": "X" * 600 + marker}})
    p, out = run_json(env, str(vault))
    assert marker in (vault / "Recast_a.md").read_text(encoding="utf-8")  # 표식은 실제로 흘렀다
    for text in [p.stdout, p.stderr, *(r.read_text(encoding="utf-8") for r in records(env))]:
        assert marker not in text
    assert all(len(f.get("worker_said", "")) <= 500 for f in out["files"])


# ── C. 원문 변경과 경합 ──────────────────────────────────────────────

def test_a_source_changed_mid_run_is_not_published(env, vault, fake):
    fake.scenario({"modify": str(vault / "a.md")})
    p, out = run_json(env, str(vault / "a.md"))
    assert p.returncode == 1 and "원문이 바뀌었다" in by_source(out)["a.md"]["reason"]
    assert not (vault / "Recast_a.md").exists()


def test_an_output_written_by_another_run_mid_run_is_kept(env, vault, fake):
    fake.scenario({"create": str(vault / "Recast_a.md")})
    p, out = run_json(env, str(vault / "a.md"))
    f = by_source(out)["a.md"]
    assert p.returncode == 0 and f["status"] == "skipped" and "먼저" in f["reason"]
    assert (vault / "Recast_a.md").read_text(encoding="utf-8") == "다른 실행이 먼저 쓴 글\n"


def test_two_cli_runs_on_one_source_publish_exactly_one_output(env, vault, fake):
    fake.scenario({"delay": 0.03})
    procs = [subprocess.Popen([sys.executable, str(CLI), "run", str(vault / "a.md")], env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True) for _ in range(2)]
    outs = [json.loads(p.communicate(timeout=60)[0]) for p in procs]
    assert sorted(by_source(o)["a.md"]["status"] for o in outs) == ["done", "skipped"]
    assert len(fake.calls()) == 2
    assert not list(vault.glob(".Recast_*"))


# ── D. 중단과 status ─────────────────────────────────────────────────

def start(env, *args):
    return subprocess.Popen([sys.executable, str(CLI), "run", *args], env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)


def wait_for(predicate, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError("기다린 상태가 오지 않았다")


def status_json(env, *args):
    p = cli(env, "status", *args)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def kill_workers(fake):
    for c in fake.calls():
        try:
            os.killpg(c["pid"], signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
def test_an_interrupt_ends_the_worker_leaves_queued_files_unstarted_and_still_reports(env, vault, fake, sig):
    (vault / "c.md").write_text(SOURCE, encoding="utf-8")
    fake.scenario({"silent": 60})
    proc = start(env, str(vault), "--jobs", "1")
    wait_for(fake.calls)
    proc.send_signal(sig)
    out, _ = proc.communicate(timeout=30)
    assert proc.returncode == 130
    result = json.loads(out)
    assert result["state"] == "interrupted" and result["summary"]["interrupted"] == 3
    assert {f["status"] for f in result["files"]} == {"interrupted"}
    assert len(fake.calls()) == 1
    worker = fake.calls()[0]
    with pytest.raises(ProcessLookupError):
        os.kill(worker["pid"], 0)
    assert not Path(worker["cwd"]).exists()
    assert status_json(env)["state"] == "interrupted"


def test_status_follows_a_running_file_through_its_phases(env, vault, fake):
    fake.scenario({"delay": 0.05, "output": "# 🖇️제목\n\n" + "가" * 4000})  # 쓰는 단계가 수 초 이어지게
    proc = start(env, str(vault / "a.md"))
    try:
        running = wait_for(lambda: records(env) and next((f for f in status_json(env)["files"] if f["status"] == "running"
                                                          and f.get("phase") == "쓰는 중" and f.get("written_chars")), None))
        assert {"phase_seconds", "elapsed_seconds", "last_signal_seconds_ago"} <= running.keys()
        assert running["last_signal_seconds_ago"] <= 5
        assert status_json(env)["state"] == "running"
    finally:
        proc.communicate(timeout=60)
    done = status_json(env)
    assert done["state"] == "finished" and done["files"][0]["status"] == "done"


def test_a_run_killed_without_a_trace_shows_as_interrupted(env, vault, fake):
    fake.scenario({"silent": 60})
    proc = start(env, str(vault))
    try:
        wait_for(fake.calls)
        wait_for(lambda: records(env))
        proc.kill()
        proc.wait(timeout=10)
        report = status_json(env)
        assert report["state"] == "interrupted"
        assert {f["status"] for f in report["files"]} == {"interrupted"}
    finally:
        kill_workers(fake)


def test_a_reused_pid_does_not_make_a_dead_run_look_alive(env, vault, fake):
    fake.scenario({"silent": 60})
    proc = start(env, str(vault / "a.md"))
    try:
        wait_for(fake.calls)
        record_path = wait_for(lambda: records(env))[0]
        proc.kill()
        proc.wait(timeout=10)
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["pid"] = os.getpid()  # 살아 있는 다른 프로세스가 같은 pid를 받은 상황
        record_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        assert status_json(env)["state"] == "interrupted"
    finally:
        kill_workers(fake)


def test_status_without_any_run_exits_2(env):
    p = cli(env, "status")
    assert p.returncode == 2 and "실행 기록" in p.stderr


# ── 코드 검토(codex) 뒤 더한 것 ──────────────────────────────────────

@pytest.mark.skipif(os.geteuid() == 0, reason="root는 권한을 무시한다")
def test_an_unwritable_run_record_does_not_stop_the_work(env, vault, tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o555)
    try:
        p, out = run_json({**env, "RECAST_DATA_DIR": str(locked / "data")}, str(vault / "a.md"))
    finally:
        locked.chmod(0o755)
    assert p.returncode == 0 and by_source(out)["a.md"]["status"] == "done"
    assert "실행 기록" in out["warning"]
    assert (vault / "Recast_a.md").exists()


def test_status_without_an_id_reads_the_run_that_started_last(env, vault):
    ids = [run_json(env, str(vault / "a.md"), "--force")[1]["run"] for _ in range(4)]
    assert status_json(env)["run"] == ids[-1]


def test_without_ps_a_fresh_record_is_running_and_a_stale_one_is_interrupted(env, vault, fake, tmp_path):
    fake.scenario({"silent": 60})
    proc = start(env, str(vault / "a.md"))
    no_ps = {**env, "PATH": str(tmp_path / "no-ps")}
    try:
        wait_for(fake.calls)
        record_path = wait_for(lambda: records(env))[0]
        assert status_json(no_ps)["state"] == "running"
        proc.kill()
        proc.wait(timeout=10)
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["updated_at"] -= 600  # 하트비트가 10분 멈춘 기록
        record_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        assert status_json(no_ps)["state"] == "interrupted"
    finally:
        kill_workers(fake)


def test_a_done_file_carries_what_the_worker_says_it_dropped(env, vault, fake):
    fake.scenario({"result_text": "3절의 표가 깨져 옮기지 못하고 버렸다"})
    _, out = run_json(env, str(vault / "a.md"))
    f = by_source(out)["a.md"]
    assert f["status"] == "done" and f["worker_said"] == "3절의 표가 깨져 옮기지 못하고 버렸다"
    assert "버린 대목" in fake.calls()[0]["prompt"]


def test_retry_advice_after_a_force_run_does_not_promise_to_skip_finished_files(env, vault, fake):
    fake.scenario({}, **{"b.md": {"exit": 3}})
    _, out = run_json(env, str(vault), "--force")
    assert "건너뛰" not in out["next"] and "원문만" in out["next"]
    assert "건너뛰" not in by_source(out)["b.md"]["next"]
    _, out = run_json(env, str(vault / "b.md"))
    assert "건너뛰" in out["next"]


def test_a_stop_after_the_worker_reported_but_before_it_exited_is_an_interruption(env, vault, fake):
    fake.scenario({"linger": 30})
    proc = start(env, str(vault / "a.md"))
    wait_for(fake.calls)
    wait_for(lambda: Path(fake.calls()[0]["cwd"], "output.md").exists())
    proc.send_signal(signal.SIGTERM)
    out, _ = proc.communicate(timeout=30)
    result = json.loads(out)
    assert proc.returncode == 130 and result["state"] == "interrupted"
    assert by_source(result)["a.md"]["status"] == "interrupted"
    assert not (vault / "Recast_a.md").exists()


def test_a_ps_that_runs_but_cannot_look_up_falls_back_to_the_heartbeat(env, vault, fake, tmp_path):
    bin_dir = tmp_path / "broken-ps"
    bin_dir.mkdir()
    ps = bin_dir / "ps"
    ps.write_text("#!/bin/sh\necho 'ps: permission denied' >&2\nexit 1\n")
    ps.chmod(0o755)
    fake.scenario({"silent": 60})
    proc = start(env, str(vault / "a.md"))
    try:
        wait_for(fake.calls)
        wait_for(lambda: records(env))
        assert status_json({**env, "PATH": str(bin_dir)})["state"] == "running"
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.communicate(timeout=30)


@pytest.mark.skipif(os.geteuid() == 0, reason="root는 권한을 무시한다")
def test_an_unreadable_old_record_does_not_hide_the_latest_run(env, vault):
    _, out = run_json(env, str(vault / "a.md"))
    folder = Path(env["RECAST_DATA_DIR"]) / "runs"
    (folder / "20000101-000000-0001.json").write_bytes(b"\xff\xfe not utf-8")
    locked = folder / "20000101-000000-0002.json"
    locked.write_text("{}", encoding="utf-8")
    locked.chmod(0o000)
    try:
        assert status_json(env)["run"] == out["run"]
    finally:
        locked.chmod(0o644)
