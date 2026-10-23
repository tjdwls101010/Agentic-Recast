"""recast.runs 인터페이스: 가장 최근 실행은 이름이 아니라 시작 시각으로 고른다."""

from recast import runs


def test_latest_is_the_run_that_started_last_even_when_ids_sort_the_other_way(tmp_path, monkeypatch):
    monkeypatch.setenv("RECAST_DATA_DIR", str(tmp_path / "data"))
    runs.save("20261023-142510-ffff", {"run": "20261023-142510-ffff", "started_at": 100.0, "state": "finished", "files": []})
    runs.save("20261023-142510-0000", {"run": "20261023-142510-0000", "started_at": 100.5, "state": "finished", "files": []})
    assert runs.latest() == "20261023-142510-0000"
