"""recast.run 인터페이스: 중단 요청이 어느 순간에 와도 워커를 새로 띄우지 않고 요약을 낸다(신호 처리기는 cli.py가 이 이벤트에 잇는다)."""

import threading

from recast import run

SOURCE = "# 강변 마을\n\nThe river town had 1,400 residents in 2019.\n"


def test_a_stop_requested_before_any_worker_starts_leaves_every_file_interrupted(fake, tmp_path, monkeypatch):
    monkeypatch.setenv("RECAST_DATA_DIR", str(tmp_path / "data"))
    vault = tmp_path / "vault"
    vault.mkdir()
    for name in ["a.md", "b.md", "c.md"]:
        (vault / name).write_text(SOURCE, encoding="utf-8")
    stop = threading.Event()
    stop.set()
    result = run.execute([str(vault)], run.Options(jobs=1), stop=stop)
    assert result["state"] == "interrupted" and result["summary"]["interrupted"] == 3
    assert fake.calls() == []
    assert not list(vault.glob("Recast_*"))
