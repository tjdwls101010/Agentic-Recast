"""seam ③: recast.sources — 경로 → 원문, 출력 이름, 건너뜀, 사용법 오류."""

import pytest

from recast import sources


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "vault"
    (v / "sub").mkdir(parents=True)
    for name in ["b.md", "a.md", "Recast_a.md", "Reconstruct_b.md", ".hidden.md", "notes.txt", "끝에 마침표.md"]:
        (v / name).write_text("x", encoding="utf-8")
    (v / "sub" / "deep.md").write_text("x", encoding="utf-8")
    return v


def names(ts):
    return [t.source.name for t in ts]


def test_a_folder_gives_its_direct_markdown_sources_in_name_order(vault):
    ts = sources.targets([str(vault)], force=False)
    assert names(ts) == sorted(["a.md", "b.md", "끝에 마침표.md"])
    assert all(t.source.parent == vault for t in ts)


def test_output_sits_beside_the_source_with_the_recast_prefix(tmp_path):
    src = tmp_path / "📰Claude Opus 5.5 is built with that in mind..md"
    assert sources.output_path(src) == tmp_path / "Recast_📰Claude Opus 5.5 is built with that in mind..md"


def test_files_and_folders_mix_and_each_source_is_taken_once(vault):
    ts = sources.targets([str(vault / "b.md"), str(vault), str(vault / "b.md"), str(vault / "sub" / "deep.md")], force=False)
    assert names(ts) == ["b.md", "a.md", "끝에 마침표.md", "deep.md"]


def test_only_an_existing_recast_output_skips_and_force_redoes_it(vault):
    by_name = {t.source.name: t for t in sources.targets([str(vault)], force=False)}
    assert by_name["a.md"].skip and "Recast_a.md" in by_name["a.md"].skip
    assert by_name["b.md"].skip is None  # 옛 Reconstruct_b.md는 완료로 보지 않는다
    assert all(t.skip is None for t in sources.targets([str(vault)], force=True))


@pytest.mark.parametrize("make, needle", [
    (lambda v: v / "missing.md", "없다"),
    (lambda v: v / "notes.txt", ".md"),
    (lambda v: v / "Recast_a.md", "출력"),
    (lambda v: v / "Reconstruct_b.md", "출력"),
    (lambda v: v / "sub" / "empty", "원문이 없다"),
])
def test_usage_errors_say_what_is_wrong(vault, make, needle):
    (vault / "sub" / "empty").mkdir()
    with pytest.raises(sources.UsageError, match=needle):
        sources.targets([str(make(vault))], force=False)
