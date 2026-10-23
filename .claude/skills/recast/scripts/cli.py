#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""recast CLI 진입점: 파서·도움말·디스패치·종료 코드. 인자와 출력은 --help가 설명한다."""

import argparse
import json
import signal
import sys

from recast import run, sources, status

DESCRIPTION = """원문(.md)을, 원문을 다시 볼 필요 없는 한국어 글로 재구조화해 원문 옆에 Recast_<원문 파일명>으로 쓴다.
원문마다 깨끗한 헤드리스 claude 세션(기본 Opus·xhigh) 하나가 원문 전체를 읽고 한 번에 쓴다.
명령마다 --help가 인자·출력·종료 코드를 설명한다."""

RUN_HELP = """원문을 재구조화한다. 파일 수에 비례해 오래 걸리는 블로킹 명령이다(파일 하나에 수 분~십여 분, 파일끼리는 --jobs개씩 병렬).

원문 고르기: 경로는 .md 파일이나 폴더를 하나 이상, 섞어서 준다. 폴더는 바로 아래 .md만 원문으로 보고, 하위 폴더·숨김 파일·출력(Recast_*, 옛 Reconstruct_*)은 뺀다. 같은 원문은 한 번만 처리한다. 원문 옆에 Recast_<원문 파일명>이 이미 있으면 건너뛴다(옛 Reconstruct_*는 완료로 보지 않고 건드리지도 않는다).

워커: 원문마다 임시 폴더에 원문 사본만 두고 claude -p --safe-mode --restricted를 띄운다 — CLAUDE.md·스킬·훅·설정 없이, 파일 도구는 그 폴더 안에서만 쓴다. 워커에게서 20분 동안 아무 신호도 오지 않으면 멈춘 것으로 보고 그 파일만 끝낸다. 작업 시간 한도는 없다(일하는 워커는 생각하는 중에도 1~2초마다 신호를 보낸다).

판정 — 하나라도 걸리면 그 파일은 실패이고 출력을 게시하지 않는다: 원문을 읽을 수 없음(UTF-8 아님 포함) / 멈춤 / 워커 비정상 종료·결과 없음 / 워커 오류 결과 / 권한 거부 / 요청한 모델이 아닌 모델이 돎 / output.md 없음(워커의 답이 worker_said로 온다) / 작업 도중 원문이 바뀜 / 게시 실패. 처리 도중 다른 실행이 먼저 Recast_를 쓰면 덮지 않고 건너뛴다.

출력: 파일이 끝날 때마다 stderr에 한 줄(✅ ❌ ⏭️ ⏹️). 끝나면(중단돼도) stdout에 JSON 하나:
  {"run": 실행 id, "state": finished|interrupted,
   "summary": {total, done, failed, skipped, interrupted, seconds},
   "files": [{source, status: done|failed|skipped|interrupted, output, source_chars, output_chars, seconds, models, reason, next, worker_said}],
   "next": 다음 행동}
원문·출력 본문은 stdout·stderr·실행 기록에 싣지 않는다. 도는 동안의 진행은 status <실행 id>로 본다.

종료 코드: 0 실패 없음(건너뜀 포함), 1 실패가 하나라도 있음, 2 사용법 오류, 3 환경 오류(claude 실행 파일이나 워커 지시문이 없다 — 아무것도 시작하지 않는다), 130 중단(SIGINT·SIGTERM — 대기 중인 파일은 시작하지 않고 돌던 워커는 끝낸다)."""

STATUS_HELP = """실행 하나의 파일별 진행을 본다. RUN_ID를 빼면 가장 최근 실행.

stdout JSON:
  {"run", "state": running|finished|interrupted,
   "summary": {total, queued, running, done, failed, skipped, interrupted},
   "files": [{source, status: queued|running|done|failed|skipped|interrupted,
              phase: 시작|읽는 중|생각하는 중|쓰는 중|속도 제한 대기, phase_seconds(지금 단계에 머문 초),
              written_chars(쓴 글자 수, 대략), elapsed_seconds, last_signal_seconds_ago, output, seconds, reason}]}
신호가 계속 오는데 같은 단계에 지나치게 오래 머물거나 쓰는 중인데 written_chars가 늘지 않으면 진척 없이 멈춘 것일 수 있다(20분 무신호는 run이 스스로 끝낸다).
실행 프로세스가 끝 기록 없이 사라졌으면(강제 종료·재부팅) state와 끝나지 않은 파일이 interrupted로 보인다. 잠자기에서 깨어난 직후처럼 늦을 뿐인 실행은 running이다.

종료 코드: 0, 2(RUN_ID의 기록이 없거나 실행 기록이 하나도 없다)."""


def _model(value: str) -> str:
    if not run.valid_model(value):
        raise argparse.ArgumentTypeError(f"모델은 {'·'.join(run.MODELS)} 별칭이나 claude-로 시작하는 전체 ID다: {value}")
    return value


def _jobs(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("--jobs는 1 이상이다")
    return n


def parser() -> argparse.ArgumentParser:
    fmt = argparse.RawTextHelpFormatter  # 설명과 인자 도움말을 접지 않는다 — 줄 단위로 읽고 grep한다
    ap = argparse.ArgumentParser(prog="cli.py", description=DESCRIPTION, formatter_class=fmt)
    sub = ap.add_subparsers(dest="command", required=True, metavar="{run,status}")

    r = sub.add_parser("run", help="원문을 재구조화한다(블로킹)", description=RUN_HELP, formatter_class=fmt)
    r.add_argument("paths", nargs="+", metavar="경로", help="원문 .md 파일이나 폴더(여러 개, 섞어도 된다)")
    r.add_argument("--instructions", metavar="지시", help='워커에게 전할 추가 지시(예: "경제 개념 설명을 자세히"). 모든 파일에 같이 간다.')
    r.add_argument("--force", action="store_true", help="원문 옆의 기존 Recast_를 다시 써서 덮는다. 되돌릴 수 없다.")
    r.add_argument("--jobs", type=_jobs, default=8, metavar="N", help="동시에 처리할 파일 수(기본 8). 속도 제한에 걸리면 낮춘다.")
    r.add_argument("--model", type=_model, default="opus", metavar="모델",
                   help=f"워커 모델: {'·'.join(run.MODELS)} 별칭이나 claude-로 시작하는 전체 ID(기본 opus). 실제로 이 모델이 돌았는지 판정한다.")
    r.add_argument("--effort", choices=run.EFFORTS, default="xhigh",
                   help="워커 effort(기본 xhigh). 모델마다 받는 값이 다를 수 있고, 거부되면 워커 오류로 보고된다.")

    s = sub.add_parser("status", help="실행의 파일별 진행을 본다", description=STATUS_HELP, formatter_class=fmt)
    s.add_argument("run_id", nargs="?", metavar="RUN_ID", help="run이 낸 실행 id(빼면 가장 최근 실행)")
    return ap


def _interrupt(signum, frame):
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "status":
        try:
            print(json.dumps(status.report(args.run_id), ensure_ascii=False, indent=1))
        except status.NotFound as e:
            print(f"cli.py status: {e}", file=sys.stderr)
            return 2
        return 0

    signal.signal(signal.SIGTERM, _interrupt)  # 백그라운드 실행을 멈추는 신호도 Ctrl+C처럼 다룬다
    options = run.Options(instructions=args.instructions, force=args.force, jobs=args.jobs, model=args.model, effort=args.effort)
    try:
        result = run.execute(args.paths, options, on_line=lambda line: print(line, file=sys.stderr, flush=True))
    except sources.UsageError as e:
        print(f"cli.py run: {e}", file=sys.stderr)
        return 2
    except run.SetupError as e:
        print(f"cli.py run: {e}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        return 130
    print(json.dumps(result, ensure_ascii=False, indent=1))
    if result["state"] == "interrupted":
        return 130
    return 1 if result["summary"]["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
