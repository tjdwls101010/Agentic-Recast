"""출력을 원문 옆에 원자적으로 게시한다.

내용은 목적지와 같은 폴더에 호출마다 고유하게 만든 임시 파일에 다 쓴 뒤 옮긴다 — 같은 폴더라 외장 볼륨에서도 원자적이다. force가 없으면 os.link로 "목적지가 없을 때만" 게시해, 다른 실행이 먼저 쓴 출력이나 사용자가 고친 출력을 덮지 않는다. 하드 링크가 없는 볼륨에서는 부분 파일을 남길 수 있는 대안을 쓰지 않고 실패한다.
"""

import errno
import os
import tempfile
from pathlib import Path

_NO_LINKS = {errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EXDEV, errno.EMLINK, errno.ENOSYS}


class Exists(Exception):
    """force 없이 게시하려는데 목적지가 이미 있다."""


class PublishError(Exception):
    pass


def publish(dest: Path, data: bytes, force: bool) -> None:
    dest = Path(dest)
    try:
        fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=".Recast_", suffix=".tmp")
    except OSError as e:
        raise PublishError(f"{dest.parent}에 쓸 수 없다: {e.strerror or e}") from e
    try:
        with os.fdopen(fd, "wb") as f:
            os.fchmod(f.fileno(), 0o644)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if force:
            os.replace(tmp, dest)
            return
        try:
            os.link(tmp, dest)
        except FileExistsError:
            raise Exists(str(dest)) from None
        except OSError as e:
            if e.errno in _NO_LINKS:
                raise PublishError(f"이 볼륨은 하드 링크를 지원하지 않아 덮어쓰기 없는 원자적 게시를 할 수 없다: {dest.parent} "
                                   "(--force면 교체로 게시한다)") from e
            raise PublishError(f"{dest}에 게시할 수 없다: {e.strerror or e}") from e
    except OSError as e:
        raise PublishError(f"{dest}에 게시할 수 없다: {e.strerror or e}") from e
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
