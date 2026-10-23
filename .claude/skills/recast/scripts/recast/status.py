"""status 명령: 실행 기록 → 파일별 진행 요약. 기록을 남긴 프로세스가 사라졌으면 끝나지 않은 파일을 interrupted로 보인다."""

import time

from . import runs

GONE = "실행 프로세스가 끝 기록 없이 사라졌다(강제 종료·재부팅 등)"


class NotFound(Exception):
    pass


def report(run_id: str | None = None) -> dict:
    run_id = run_id or runs.latest()
    record = runs.load(run_id) if run_id else None
    if record is None:
        raise NotFound(f"실행 기록이 없다: {run_id}" if run_id else "실행 기록이 하나도 없다")
    now = time.time()
    state = record["state"]
    gone = state == "running" and not runs.alive(record)
    if gone:
        state = "interrupted"
    files = []
    for e in record["files"]:
        status = e["status"]
        f = {"source": e["source"]}
        if gone and status in ("queued", "running"):
            f.update(status="interrupted", reason=GONE)
        elif status == "running":
            f.update(status=status, phase=e.get("phase"), phase_seconds=round(now - e.get("phase_since", now)),
                     written_chars=e.get("written_chars", 0), elapsed_seconds=round(now - e.get("started_at", now)),
                     last_signal_seconds_ago=round(now - e.get("last_signal_at", now)))
        else:
            f["status"] = status
            if status == "done":
                f.update(output=e["output"], seconds=e.get("seconds"))
            elif e.get("reason"):
                f["reason"] = e["reason"]
        files.append(f)
    counts = {s: sum(1 for f in files if f["status"] == s)
              for s in ("queued", "running", "done", "failed", "skipped", "interrupted")}
    return {"run": run_id, "state": state, "summary": {"total": len(files), **counts}, "files": files}
