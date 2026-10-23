"""seam ③: recast.publish — 같은 폴더 임시 파일을 거친 원자적 게시, 덮어쓰기 금지, 정리."""

import errno
import os
import stat
import threading

import pytest

from recast import publish


def leftovers(folder):
    return sorted(p.name for p in folder.iterdir() if p.name.startswith(".Recast_"))


def test_a_new_output_is_published_whole_and_readable(tmp_path):
    dest = tmp_path / "Recast_a.md"
    publish.publish(dest, "# 🖇️제목\n본문\n".encode(), force=False)
    assert dest.read_text(encoding="utf-8") == "# 🖇️제목\n본문\n"
    assert stat.S_IMODE(dest.stat().st_mode) == 0o644
    assert leftovers(tmp_path) == []


def test_an_existing_output_is_never_overwritten_without_force(tmp_path):
    dest = tmp_path / "Recast_a.md"
    dest.write_text("성진이 고친 글", encoding="utf-8")
    with pytest.raises(publish.Exists):
        publish.publish(dest, b"new", force=False)
    assert dest.read_text(encoding="utf-8") == "성진이 고친 글"
    assert leftovers(tmp_path) == []


def test_force_replaces_the_existing_output(tmp_path):
    dest = tmp_path / "Recast_a.md"
    dest.write_text("old", encoding="utf-8")
    publish.publish(dest, b"new", force=True)
    assert dest.read_bytes() == b"new"
    assert leftovers(tmp_path) == []


def test_a_volume_without_hard_links_fails_without_leaving_a_partial_file(tmp_path, monkeypatch):
    # 하드 링크가 없는 볼륨은 실제 볼륨 없이 재현할 수 없어 os.link 경계만 대역으로 바꾼다
    def no_links(*args, **kwargs):
        raise OSError(errno.ENOTSUP, "Operation not supported")

    monkeypatch.setattr(os, "link", no_links)
    dest = tmp_path / "Recast_a.md"
    with pytest.raises(publish.PublishError, match="하드 링크"):
        publish.publish(dest, b"body", force=False)
    assert not dest.exists() and leftovers(tmp_path) == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root는 권한을 무시한다")
def test_an_unwritable_folder_is_a_publish_error(tmp_path):
    folder = tmp_path / "locked"
    folder.mkdir()
    folder.chmod(0o500)
    try:
        with pytest.raises(publish.PublishError):
            publish.publish(folder / "Recast_a.md", b"body", force=False)
    finally:
        folder.chmod(0o700)


def test_racing_publishers_leave_exactly_one_whole_output(tmp_path):
    dest = tmp_path / "Recast_a.md"
    bodies = [f"writer {i} ".encode() * 5000 for i in range(8)]
    results = [None] * len(bodies)

    def go(i):
        try:
            publish.publish(dest, bodies[i], force=False)
            results[i] = "won"
        except publish.Exists:
            results[i] = "exists"

    threads = [threading.Thread(target=go, args=(i,)) for i in range(len(bodies))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("won") == 1 and results.count("exists") == len(bodies) - 1
    assert dest.read_bytes() == bodies[results.index("won")]
    assert leftovers(tmp_path) == []
