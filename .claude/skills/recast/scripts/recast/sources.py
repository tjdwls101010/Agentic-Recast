"""명령줄 경로 → 처리할 원문과 그 출력 경로.

폴더는 바로 아래 .md만(하위 폴더·숨김 파일 제외) 원문으로 본다. Recast_*와 옛 Reconstruct_*는 출력이라 원문에서 거른다. 완료 판정은 Recast_만 본다.
"""

import os
from dataclasses import dataclass
from pathlib import Path

OUTPUT_PREFIX = "Recast_"
OUTPUT_PREFIXES = (OUTPUT_PREFIX, "Reconstruct_")


class UsageError(Exception):
    pass


@dataclass(frozen=True)
class Target:
    source: Path
    output: Path
    skip: str | None  # 건너뛰는 이유, 처리할 것이면 None


def output_path(source: Path) -> Path:
    return source.with_name(OUTPUT_PREFIX + source.name)


def _is_source(p: Path) -> bool:
    return p.is_file() and p.suffix == ".md" and not p.name.startswith((".", *OUTPUT_PREFIXES))


def _expand(raw: str) -> list[Path]:
    # 심볼릭 링크를 풀지 않는다 — 출력은 사용자가 준 자리 옆에 놓인다
    p = Path(os.path.abspath(Path(raw).expanduser()))
    if not p.exists():
        raise UsageError(f"경로가 없다: {raw}")
    if p.is_dir():
        found = sorted(c for c in p.iterdir() if _is_source(c))
        if not found:
            raise UsageError(f"처리할 .md 원문이 없다: {raw} (하위 폴더, 숨김 파일, Recast_*·Reconstruct_*는 제외된다)")
        return found
    if p.suffix != ".md":
        raise UsageError(f".md 파일이 아니다: {raw}")
    if p.name.startswith(OUTPUT_PREFIXES):
        raise UsageError(f"재구조화 출력 파일이다: {raw} — 원문 파일을 준다")
    return [p]


def targets(paths: list[str], force: bool) -> list[Target]:
    """경로들을 원문 목록으로 푼다. 같은 원문은 처음 나온 자리에서 한 번만. 잘못된 경로가 하나라도 있으면 UsageError."""
    seen: dict[Path, None] = {}
    for raw in paths:
        seen.update(dict.fromkeys(_expand(raw)))
    result = []
    for source in seen:
        output = output_path(source)
        skip = None if force or not output.exists() else f"이미 있다: {output.name} (다시 쓰려면 --force)"
        result.append(Target(source, output, skip))
    return result
