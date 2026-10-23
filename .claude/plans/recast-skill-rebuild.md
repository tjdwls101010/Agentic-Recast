# recast 스킬 재작성 — `.tmp/Knowledge` → `.claude/skills/recast`

> 파일 이름: plan 모드의 `ExitPlanMode`는 지정 경로(`tmp-knowledge-enumerated-kitten.md`)만 읽어서, 계획 승인 직후(2026-10-23 14:02)에 `.claude/plans/recast-skill-rebuild.md`로 옮겼다(Agentic-* 레포 관례 `<스킬>-<주제>.md`, 예: Agentic SNS `twitter-skill-rebuild.md`). 0단계는 끝났고, 구현 세션은 1단계부터 시작한다. 계획 세션의 codex 검토 기록은 프로젝트 루트의 `.codex-runs/`에 있다(1단계 `.gitignore` 대상).

## Context

recast는 주로 영어인 강의·팟캐스트 전사, 기사·에세이, 책 장 같은 `.md` 원문을 **원문을 다시 볼 필요 없는 한국어 글**로 다시 짓는 스킬이다. 번역처럼 원문의 순서와 포장까지 옮기지도, 요약처럼 실질을 줄이지도 않는다. 성공 기준은 산출물의 품질 하나다.

계보는 둘이다. `.tmp/old`(서브에이전트 `Reconstructor`, 4~7월에 볼트 산출물 347쌍을 만든 것)와 `.tmp/Knowledge`(9월 헤드리스 CLI 파이프라인, 실제로 4번 돌았다). Knowledge는 old의 실패(모델 이탈, 긴 원문 중단, 머리 삭제)를 막으려고 블록 번호·개요·숫자 힌트·형식 검사·고침 턴·턴 단위 재개를 쌓았다. 실제 기록을 보면 숫자 힌트 3건은 모두 오탐이었고, ⚠️ 작업 폴더는 한 달째 방치됐으며, 오늘(10/23) 실패는 지식이 아니라 작업 폴더 이름(마침표로 끝남)이 권한 검사에 걸린 실행 실패였다. 성진은 Knowledge가 지나치게 복잡하다고 판단했고, 이 계획은 그 판단을 근거와 함께 따른다.

결과물:

1. **얇은 헤드리스 CLI** — 파일마다 `claude -p`(기본 Opus·xhigh, 깨끗한 환경) 세션 하나를 띄워 원문 전체를 읽고 한 번에 쓰게 한다. 워커의 활동을 실시간으로 받아 진행 상황을 보여 주고, 신호가 오래 끊긴 워커는 멈춤으로 끝낸다. 결과로 성공·실패를 판정해 `Recast_<원문>`을 원문 옆에 게시한다. skill-maker의 코드 트리를 그대로 따른다.
2. **`scripts/recast/system_prompt.md`** — 워커의 시스템 프롬프트. old의 Reconstructor를 바탕으로, 9월 대조 실험이 실제로 잡은 교정만 더해 원칙 중심으로 다시 쓴다.
3. **`SKILL.md`** — 볼트 세션의 메인 Claude가 읽는 짧은 문서(실행·진행·결과 전달).
4. 레포 골격 — git, 공개 저장소 `tjdwls101010/Agentic-Recast`, 개발용 `pyproject.toml`, 레포 `tests/`(구조 테스트 포함).

Knowledge에서 버리는 것: 블록 번호와 개요(`outline.json`), 배정 완결성 검사, 숫자 힌트·판정 파일·⚠️ 상태, 형식 위반 검사와 고침 턴, 턴 단위 재개와 세션 소실 복구, `state.json`·잠금·영속 작업 폴더, 노트 머리(frontmatter·h1·cite 콜아웃) 보존 코드, 전체 시간 제한.

## 장부

### 사실·실측 (2026-10-23, 이 Mac)

- **기존 스킬의 정체:** `.tmp/Knowledge`는 9월 25일 재작성본(볼트 레포 커밋 `e5dcb1b`, PR #8, 계획 `~/💎Obsidian/.claude/plans/knowledge-skill-rebuild.md`)이다. 그 계획이 대조 실험(무스킬 A / 현행 지시문 B, For-Profit Presidency 47K자, Opus 5.5 xhigh), codex 계획 리뷰 13건, 네 프레임 감사를 거쳤다. 지금의 skill-maker와 어긋나는 곳은 코드 트리(`scripts/knowledge.py` + `scripts/recon/` + 스킬 안 `tests/` + `sys.path.insert` + `allowed-tools: Bash(python3 *knowledge.py*)`)와, 9월 프레임에 없던 다섯째 성질(colleague over autopilot)이다.
- **계보:** `.tmp/old`(오케스트레이션 `SKILL.md` 4.3K자 + 서브에이전트 `Reconstructor.md` 17K자, v1.2.0 2026-07-18) → `.tmp/Knowledge`(9월 헤드리스 CLI). 9월 계획이 적은 old의 실패: 워커 모델 이탈(`model: opus`인데 Opus 4.8·Sonnet 5·Opus 5.5가 섞임), 누락 판별 수단이 글자 수뿐, 규칙 7(`# 🖇️`로 시작) 때문에 cite 콜아웃 삭제, 9만~19만 자 원문에서 Write 없이 멈추거나 13~17분 끌다 중단, 12만 자 이상에서 출력 비율 0.47→0.26.
- **9월 대조 실험에서 무스킬 Opus(A)가 한 것:** 목록·표·번호 절, 요약 표·용어 부록·전사 오류 목록 추가, 원문 밖 지식으로 교정("OLC는 실은 법무부 소속"), 이모지 없음. 현행 지시문(B)은 전부 산문·이모지 헤딩·한국어 제목·추가 없음이었지만 화자 중계체("콜드웰이 물었다 / 골드스미스가 답했다")가 남았다. 출처: 9월 계획의 원장.
- **코드 규모:** `recon/` 10모듈 1,481줄, 테스트 9파일 + 가짜 claude 1,165줄.
- **설치 형태:** 볼트 `~/💎Obsidian/.claude/skills/recast` → `~/Coding/Agentic Recast/.claude/skills/recast` 심볼릭 링크가 이미 있다(대상 폴더는 비어 있음). 볼트의 옛 `.claude/skills/Knowledge`는 그대로 있다.
- **저장소:** `https://github.com/tjdwls101010/Agentic-Recast.git` — PUBLIC, 비어 있음(2026-10-23 생성). 로컬 `~/Coding/Agentic Recast`는 아직 git 레포가 아니다. 공개 레포이므로 원문 사본·실제 기사·책 본문이 커밋되면 안 된다(`.tmp/`의 예시 원문 포함).
- **실사용 분포(볼트 실측):** `Reconstruct_*.md` 372개, 원문과 짝이 맞는 것 349쌍. 그중 329쌍(94%)이 `🧷Attachments/📖Books/📕…/` 책 장, 18쌍 `📥Articles`, 2쌍 `📂Inbox`. 원문 크기 중앙값 44,682자, p90 80K, 최대 312,190자, 10만 자 초과 19개.
- **책 장의 모양:** frontmatter(`date_created`) → `# 2 Rawls and Beyond` → 본문. 329개 중 52개에 PDF 합자 깨짐(`di�er`, `�rst` — U+FFFD)이 있고, 일부(Idea of Justice)는 PDF 줄마다 빈 줄이 끼어 있다(장당 약 1,900줄).
- **노트 머리 모양:** `📥Articles` — `fm+h1+[!cite]` 883, `fm+[!cite]` 329, `fm+[!success]` 18, `fm+[!todo]` 17. 책 장 — `fm+h1` 1,100, 머리 없음 171. `📰아프면 쉴 권리.md`는 frontmatter → `> [!success] 요약`(성진이 쓴 요약) → `# 🖇️제목` → `> [!cite]+ 원본` 순이다.
- **CLI 시대 실행 기록(`runs.jsonl` 전부):** 9/25 E2E 3건 모두 ⚠️(숫자 힌트 14·52·2건, 판정 0), 10/23 1건 ❌. 숫자 힌트 14건은 전부 mermaid `classDef`의 색상 코드에서, For-Profit 2건은 `1. 4 billion`의 `1`과 `50, 60, 70 years`의 `60`에서 나왔다.
- **오늘의 ❌ 원인(`worker.log`):** 원문 stem이 마침표로 끝나(`📰Claude Opus 5.5 is built with that in mind.`) 작업 폴더 경로가 Claude Code 권한 검사에서 "의심스러운 Windows 경로"로 분류됐고, 헤드리스 워커는 승인받을 수 없어 Read가 막혔다. 파이프라인은 이를 개요 오류로 보고 같은 `outline-fix` 프롬프트를 두 번 더 보냈다(턴은 모두 `ok=True`, 결과 JSON의 거부는 보지 않음).
- **`.tmp/examples`(성진 제공 재료, 공개 레포에 올리지 않음):** `📰Bill Gates A.I. ‘Makes Nuclear Weapons Look Like Nothing’.md` 78,633자(Ezra Klein Show, JSON 발화 252개 — Gates 148·Klein 96·도입 클립 화자 6, h1+cite) / `📰Why Are We Sprinting Off the A.I. Cliff?.md` 35,606자(Klein 단독 에세이형 + 도입 뉴스 클립 몽타주, h1+cite) / `📰Claude Opus 5.5 is built with that in mind..md` 8,198자(블로그, 통계 불릿·이미지·링크, 오늘 ❌의 그 파일).
- **Claude Code 2.1.309:** `--effort`(low·medium·high·xhigh·max), `--restricted`(Bash 등 코드 실행 도구와 WebFetch 제거, 사용자·프로젝트·로컬 설정 파일 무시, 파일 도구를 작업 디렉터리에 가둠, 설정·git·도구 설정 파일 쓰기는 사람만 승인), `--safe-mode`(CLAUDE.md·스킬·플러그인·훅·MCP 서버·에이전트 등 비활성, 인증·모델 선택·내장 도구·권한은 정상), `--append-system-prompt-file`, `--tools`, `--permission-mode`, `--output-format stream-json`(실시간 이벤트, `--print` 전용), `--include-partial-messages`(부분 메시지 조각을 도착하는 대로), `--verbose`가 있다. 9월 실측: `--restricted`에서 cwd 안 쓰기 성공·cwd 밖 읽기 거부, `--append-system-prompt-file` 반영, `modelUsage`로 실제 모델 확인 가능.
- **출력 한도(공식 문서):** Opus 5.5 — 컨텍스트 1M, 최대 출력 128K 토큰, 적응형 사고 항상 켜짐, 기본 effort `medium`(platform.claude.com/docs/en/models/opus-5-5/overview). Claude Code — `CLAUDE_CODE_MAX_OUTPUT_TOKENS`가 요청당 최대 출력을 정하고, 기본값과 상한은 모델마다 다르며 상한을 넘는 값은 상한으로 낮춘다(code.claude.com/docs/en/env-vars). 사고 토큰은 같은 요청의 최대 출력 안에서 쓰인다(`MAX_THINKING_TOKENS`는 최대 출력 − 1로 묶임). Opus 5.5에서 Claude Code의 기본값은 이 문서들에 숫자로 적혀 있지 않다.
- **stream-json 실측(2026-10-23, `claude -p --safe-mode --restricted --tools Read --model opus --effort xhigh --output-format stream-json --verbose --include-partial-messages`, 도구가 필요 없는 계산 문제 하나):** 20.5초 동안 이벤트 47개. 종류: `system/init` 1, `system/status` 1, `system/thinking_tokens` 15, `stream_event`(`message_start`, `content_block_start` thinking·text, `thinking_delta` 16, `signature_delta`, `text_delta`, `content_block_stop`, `message_delta`, `message_stop`), `assistant` 2, `rate_limit_event` 1, `result/success` 1. 사고 중에도 `system/thinking_tokens`·`thinking_delta`가 1~1.5초 간격으로 와서 가장 긴 끊김은 1.5초. 결과의 `modelUsage` 키는 `claude-opus-5-5` 하나, `permission_denials`는 빈 목록 `[]`, `is_error` 거짓. 확인하지 못한 것: 도구 호출(Read·Write) 이벤트의 모양, API 재시도 대기 중의 이벤트, 수만 자 출력을 쓰는 동안의 간격 — 6·8단계.
- **위임 충돌:** 성진의 전역 `~/.claude/CLAUDE.md`는 "위임 또는 검증의 기본값은 `Agent`·`Workflow`가 아니라 `codex`", "그럼에도 `Agent`를 쓴다면 `sonnet`"이라고 지시한다. 메인이 서브에이전트를 그때그때 정의하는 설계는 볼트 세션마다 이 지시와 부딪혀 집필이 GPT나 Sonnet으로 갈 수 있다. 헤드리스 `--safe-mode --restricted`는 CLAUDE.md·스킬·훅·설정을 싣지 않으므로 구조적으로 피한다. (Agent 도구는 이제 `model`·`effort` 인자를 받지만, 이 충돌과 메인이 위임 지시문을 매번 새로 쓰는 문제는 남는다.)
- **도구:** uv 0.8.0, Python 3.14.8(3.12·3.13도 설치됨), `claude plugin validate`, 전역 스킬 `codex`·`coding`·`skill-maker`.
- **형제 레포 관례:** Agentic Invest — `tests/test_skill_layout.py`(구조 테스트: `scripts/`에 `cli.py`와 패키지 하나, 표준 라이브러리 이름 가림 금지, `sys.path` 편집 금지, PEP 723, `allowed-tools`와 SKILL.md 본문의 호출 구문, 단위 종류별 import 방향), `pyproject.toml`(pytest `pythonpath`, ruff line-length 120). Naver-News(공개) — PR 템플릿 무엇을 바꿨나/왜/영향/검증.

### 결정 원장 (성진, 2026-10-23)

- 스킬 이름 `recast`, 위치 `.claude/skills/recast`, 저장소 `tjdwls101010/Agentic-Recast`.
- Knowledge는 지나치게 복잡하다 — 재구조화에는 정답이 없고, 검증 장치를 이만큼 둘 이유가 약하다.
- 코드가 필요하다면 헤드리스 Claude를 띄우는 얇은 CLI 정도. 서브에이전트를 그때그때 Claude가 정의해 돌리는 방식은 피한다. old가 서브에이전트를 쓴 이유는 폴더 단위 여러 파일을 서로 독립적으로 처리하기 위해서였고, 헤드리스가 그 자리를 맡는다. CLI는 폴더 경로와 파일 경로를 모두 받는다.
- CLI는 skill-maker 프레임을 철저히 따르고, 진행 상황과 완료 요약을 볼 수 있어야 한다. 헤드리스가 자체 오류로 멈추는 경우가 있으니 멈췄는지 진행 중인지 보여야 한다.
- 워커가 신호 없이 오래 멈추면 CLI가 그 파일만 자동으로 끝내고 '멈춤' 실패로 처리한다. 일하는 워커를 자르는 전체 시간 제한(`--timeout`)은 두지 않는다.
- 멈춤 판단은 둘을 겸한다: 코드는 20분 무신호를 하한으로 자동 종료하고(run이 반드시 끝나 완료 알림이 오게), 신호는 오는데 진척이 없는 경우(같은 단계에 오래 머묾, 속도 제한만 반복)는 사용자가 물을 때 Claude가 `status`를 보고 판단해 알리고 멈출지 묻는다.
- 모델과 effort는 기본 `opus`·`xhigh`, 파라미터(`--model`, `--effort`)로 바꿀 수 있다.
- 헤드리스 워커의 프롬프트는 `references/`가 아니라 스크립트 코드 폴더에 둔다.
- cite 콜아웃 같은 노트 장치가 출력에 남지 않아도 큰 문제가 아니다. 중요한 것은 내용이고, 형식적인 것은 성진이 나중에 알아서 더한다 → 노트 머리 보존은 요구 사항이 아니다(코드에도 지시문에도 두지 않는다).
- 나눠 쓰기는 고려 대상이 아니다. 출력이 한 응답의 최대 출력(성진 추산 약 6만 자)을 넘는 원문은 다루지 않는다. 출력 한도는 실측이 아니라 문서로 확인한다(위 사실 참고).
- 실측은 지금 하지 않는다. 실행 계약·지시문 효과는 구현 세션의 실제 계약 테스트와 E2E가 확인한다.
- 워커 지시문의 바탕은 `.tmp/old/Reconstructor.md`(성진이 오래 다듬은 정의). 꼭 지킬 것: 원문의 중요 내용을 유지한다 — 축약도 아니고 잡담·기침까지 옮기는 것도 아니다. 순서는 재구조화에 필요하면 바뀔 수 있지만 "바꿔도 된다"를 레일로 깔지 않는다.
- 화자·목소리: "화자 언급을 지웠을 때 잃는 지식이 있으면 남긴다"를 Knowledge 판으로 — 대담이어도 사실·제도·개념 설명은 명제로, 화자는 판단·예측·확신의 정도·이견·질문의 틀이 답을 바꾼 곳에만, 저자 자신의 경험은 1인칭 '나는'(Gates 전사 장면 5개로 판정 확인: ① 회사 역사 설명 → 명제 ② 10년 예측 → 화자 ③ 질문의 틀에 대한 반박 → 화자 ④ 자기 재단 경험 → '나는' ⑤ 도입 뉴스 클립 → 화자 없이 '당시 보도는' 정도).
- 서식 관례 1~8: ① 평어체 ② 외국어 고유명사 첫 등장 `한글(원어)`, 이후 한글, 한국 고유명사는 그대로 ③ 맨 위 `# 🖇️한국어 제목`, 본문 `##` 이하, 모든 헤딩 앞에 내용에 맞는 이모지 ④ 산문 중심, 목록·표는 서사 없이 나란히 놓인 항목일 때만 ⑤ 짧은 인용은 `" "`로 녹이고 `>`는 핵심 인용에만, 외국어 인용은 한국어로 ⑥ 관련 이미지는 `![[파일명]]`, 장식 이미지는 버림 ⑦ 굵게는 재량 ⑧ 번역투 금지(BAD/GOOD 한 쌍).
- 문서·CLI 언어: 전부 한국어 — SKILL.md, `system_prompt.md`, `--help`·메시지.
- 출력 이름: `Recast_<원문 파일명>`. 폴더를 처리할 때 `Recast_*`와 옛 `Reconstruct_*`를 모두 원문에서 거른다.
- 완료 판정은 `Recast_`만 본다. 옛 `Reconstruct_`가 있어도 `Recast_`가 없으면 처리한다. 옛 `Reconstruct_` 파일은 지우거나 덮지 않는다.
- `.claude/plans`는 공개 저장소에 커밋한다.
- 볼트는 손대지 않는다 — 옛 `.claude/skills/Knowledge`와 `.knowledge/` 작업 폴더 4개를 그대로 둔다.

### 9월 결정 중 그대로 잇는 것 (성진이 9월에 정함)

- 집필은 Claude만(기본 Opus), codex는 개발 리뷰에만.
- 직접 호출 전용(`disable-model-invocation: true`).
- 경로 뒤에 덧붙인 말은 워커에게 가는 추가 지시(`--instructions`).
- 완료분 건너뜀, `--force`로 다시 씀. 파일 간 병렬 기본 8.
- 화자 원칙, 덧붙임의 경계(전사 오류는 조용히 바로잡고 바깥 지식으로 고치거나 보태지 않음), 요약 절·요약 표·용어 부록 없음, 망가진 원문은 지어내지 않음.

### Claude가 정한 것 (근거)

- **계획 파일 이름** `recast-skill-rebuild.md` — 머리말.
- **워커 프롬프트의 위치와 형식:** `scripts/recast/system_prompt.md`. 메인 Claude가 읽는 참고 문서가 아니라 코드가 워커에게 그대로 넘기는 시스템 프롬프트라, 그것을 보내는 패키지 안에 둔다. 형식은 md — 성진이 전문을 읽고 승인하고, 헤딩 구조가 그대로 모델에게 간다. Python 문자열 상수로 두면 읽고 고치기만 어려워진다. `references/`는 만들지 않는다.
- **워커 샌드박스:** 파일마다 시스템 임시 폴더(`tempfile.mkdtemp(prefix="recast-")`)를 만들어 원문을 `source.md`로 복사하고, 워커는 `output.md`를 쓴다. 근거: 오늘 ❌는 원문 이름에서 만든 작업 경로가 권한 검사에 걸린 것이고, 샌드박스는 ASCII 이름만 쓰므로 이 부류를 없앤다. 워커가 볼트를 보지 않는다. 판정을 통과한 출력만 볼트에 놓인다. 스킬 `data/` 아래(`.claude/` 경로)는 `--restricted`의 "도구 설정 파일" 승인 규칙에 걸릴 위험이 있어 쓰지 않는다. 샌드박스는 실행 동안만 사는 임시물이지 상태가 아니므로 `data/` 규칙과 어긋나지 않는다. 끝나면 항상 지운다.
- **게시(codex ①1·2·3, ②1·2):** 게시는 `recast/publish.py` 한 곳이 맡는다. 게시 직전에 원문을 다시 읽어 복사할 때의 sha256과 비교하고, 다르면 게시하지 않는다. 출력은 원문과 같은 폴더에 실행마다 고유하게 배타적으로 만든 숨은 임시 파일(`tempfile.mkstemp(dir=원문 폴더, prefix=".Recast_", suffix=".tmp")`)에 먼저 다 쓰고 `fsync`한 뒤, `--force`가 없으면 `os.link(임시, 목적지)`(목적지가 있으면 실패하는 원자적 no-clobber), `--force`면 `os.replace`로 게시한다. 임시 파일은 그 실행이 만든 것만 지운다(성공·실패 모두). 같은 폴더 안에서만 옮기므로 외장 볼륨에서도 되고, 하드 링크를 지원하지 않는 볼륨(exFAT 등)에서는 부분 파일을 만들 수 있는 대안을 쓰지 않고 `--force` 없는 게시를 '게시 실패'로 끝낸다. 다른 실행이 먼저 `Recast_`를 썼으면 덮지 않고 건너뜀으로 보고한다.
- **한 턴, 세션 재개 없음:** `--session-id`/`--resume`을 쓰지 않는다. 실패한 파일은 같은 명령을 다시 실행하면 처음부터 다시 한다(파일 하나가 수 분~십여 분).
- **출력 한도:** 워커 환경에 `CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000`을 명시한다 — Claude Code의 Opus 5.5 기본값이 문서에 없고, xhigh의 사고가 같은 한도를 나눠 쓰기 때문이다(다른 모델은 Claude Code가 그 모델의 상한으로 낮춘다). 출력이 한도를 넘으면 Write가 실행되지 않아 `output.md`가 없고, "출력 없음" 실패로 잡힌다.
- **긴 원문 읽기:** 프롬프트에 원문 줄 수를 알리고 "Read가 끊기면 offset으로 이어 끝까지 읽는다"를 준다(Read 기본 2,000줄·25K 토큰 — 줄마다 빈 줄이 낀 책 장은 1,900줄 안팎).
- **실시간 모니터링과 멈춤:** 워커를 `--output-format stream-json --verbose --include-partial-messages`로 띄워 stdout 이벤트를 한 줄씩 읽는다. `claude.py`가 이벤트를 우리 말(단계: 읽는 중·생각하는 중·쓰는 중, 쓴 글자 수, 마지막 신호 시각)로 바꿔 넘긴다. 마지막 이벤트 뒤로 `STALL` 동안 아무 줄도 오지 않으면 프로세스 그룹을 끝내고 '멈춤' 실패로 처리한다. 실측에서 xhigh 사고 중에도 이벤트가 1~1.5초 간격으로 왔으므로(사실 절), 무신호 기준은 작업 시간과 무관하고 일하는 워커를 자르지 않는다. `STALL`은 성진이 정한 하한 20분, 상수로 둔다(`성진:` 주석에 근거와 함께). 실행 기록에 파일별 "이벤트가 가장 오래 끊긴 시간"을 남기고, 8단계에서 그 값이 7분(20분의 1/3)을 넘으면 기준을 성진에게 다시 묻는다. 도구 호출·속도 제한 이벤트의 모양은 6단계 실제 계약에서 확인하고, 속도 제한 대기를 뜻하는 이벤트는 단계 '속도 제한 대기'로 옮긴다.
- **본문은 CLI 밖으로 나가지 않는다(성진의 질문, 2026-10-23):** 워커 이벤트에는 Read 결과(원문 본문)와 써 내려가는 출력 조각이 들어 있다. 이벤트는 CLI 프로세스 안에서 단계·글자 수·마지막 신호 시각으로 줄이고 버린다. 메인 Claude가 보는 stdout JSON·stderr 진행 줄·`status` JSON·실행 기록에는 원문·출력 본문이 들어가지 않고, 이벤트 원본도 저장하지 않는다. 예외인 텍스트 둘 — 출력이 없을 때나 오류 결과일 때 워커의 마지막 답(`worker_said`)과 비정상 종료 때 stderr 끝부분 — 은 각각 500자에서 자른다. 권한 거부는 `permission_denials`의 `tool_input`을 싣지 않고 도구 이름과 파일 경로(200자 이하)만 보고한다 — 거부된 Write의 입력에는 쓰려던 본문이 통째로 들어 있다(codex ②4). 이벤트 파싱에 실패해도 원래 줄을 진단에 옮기지 않는다. 메인 컨텍스트가 원문으로 차는 것을 막고, 공개 레포 밖 `data/`에도 원문 사본이 쌓이지 않게 한다.
- **진행·요약·생존(codex ①5·6, ②3):** 실행 기록을 `data/runs/<run-id>.json`에 두고, 이벤트가 올 때(몇 초 간격으로 묶어서)와 30초마다 하트비트를 원자적으로 갱신한다. 기록에는 실행 프로세스의 PID와 그 프로세스의 시작 시각(`ps -o lstart= -p <pid>`)을 함께 남긴다. `status`는 끝 기록이 없을 때 하트비트가 신선하면 `running`, 하트비트가 2분 넘게 멈췄으면 PID와 시작 시각으로 실행 동일성을 확인해 같은 프로세스가 살아 있으면 `running`(응답 지연 — Mac 잠자기 복귀 등), 프로세스가 없거나 시작 시각이 다르면 `interrupted`로 본다(PID 재사용·재부팅·SIGKILL에 안전하고, 잠자기를 중단으로 오판하지 않는다). `run`은 끝에(중단 때도) stdout으로 요약 JSON 하나를 내고, 진행은 stderr로 파일마다 한 줄.
- **모델 증거(codex 8):** 결과의 `modelUsage` 키를 파일별 `models`로 실행 기록과 stdout JSON에 남긴다.
- **모델 판정:** 요청한 모델이 실제로 돌았는지를 본다 — 별칭(`opus`·`sonnet`·`haiku`·`fable`)은 `claude-<별칭>-`로 시작하는지, 전체 ID는 같은지. `modelUsage`가 비었거나 다른 모델 키가 섞이면 실패. 보조 모델이 섞이는지는 6단계에서 확인한다(남은 위험).
- **노트 장치 문장은 지시문에 두지 않는다:** 성진의 결정(내용만 중요). 성진이 직접 쓴 `[!success] 요약` 같은 메모가 본문에 섞이는지는 E2E에서 보고, 섞이면 그때 한 줄을 더할지 성진에게 묻는다.

### 열린 질문

없음. 구현 중 계획과 다른 판단이 필요하면 구현 기록에 적고, 성진의 결정을 바꾸는 것은 묻는다.

## 디렉터리 (구현 후)

```
Agentic Recast/
├── .gitignore                  # .DS_Store, __pycache__/, .pytest_cache/, .venv/, .tmp/, .claude/histories,
│                               # .claude/skills/recast/data/, .ultra-search/, .codex-runs/
├── pyproject.toml              # 개발 전용: pytest·ruff 설정, dev 의존성(pytest)
├── .claude/
│   ├── plans/recast-skill-rebuild.md
│   └── skills/recast/
│       ├── SKILL.md
│       ├── data/               # runs/<run-id>.json — gitignore
│       └── scripts/
│           ├── cli.py          # 유일한 진입점: 파서·도움말·디스패치·종료 코드. PEP 723 헤더(requires-python >=3.11, 의존성 없음)
│           └── recast/
│               ├── __init__.py
│               ├── system_prompt.md  # 워커의 시스템 프롬프트(--append-system-prompt-file)
│               ├── paths.py    # common: 스킬 폴더·data/·system_prompt.md 경로
│               ├── sources.py  # common: 경로 → 대상 파일, Recast_ 이름, 거를 접두사, 건너뜀 판정
│               ├── publish.py  # common: 같은 폴더 고유 임시 파일 → no-clobber(os.link)·--force(os.replace) 원자적 게시, 자기 임시 파일 정리
│               ├── claude.py   # system: 헤드리스 Claude Code — argv·env, stream-json 이벤트 → 진행(우리 말), 멈춤 감시, 프로세스 그룹 종료, 결과 판정
│               ├── runs.py     # store: data/runs/<run-id>.json 원자적 쓰기·읽기·최근 실행·하트비트
│               ├── run.py      # feature: 파일 하나(샌드박스→워커→판정→게시)와 병렬 배치, 중단 처리
│               └── status.py   # feature: 실행 기록 → 진행 요약(단계, 경과, 마지막 신호, 생존)
└── tests/
    ├── fake_claude.py          # 가짜 claude: argv·cwd·프롬프트 기록, 시나리오대로 stream-json 이벤트·output.md·결과
    ├── fixtures/               # 합성 원문(실제 기사·책 본문 금지), 실제 이벤트 모양(6단계에서 합성 원문으로 받음)
    ├── test_structure.py       # Invest test_skill_layout.py를 recast 하나로 줄여 옮김
    ├── test_claude.py
    ├── test_sources.py
    ├── test_publish.py
    ├── test_cli.py             # run·status를 cli.py 서브프로세스로
    └── test_live_contract.py   # RECAST_LIVE=1일 때만 실제 claude
```

단위 종류와 import 방향(구조 테스트가 지킨다): common = `paths`, `sources`, `publish` / system = `claude` / store = `runs` / feature = `run`, `status` / `cli.py`는 common과 feature만. feature는 system·store·common을, system·store는 common을 import한다. 두 번째 바뀔 이유가 생기기 전까지 모듈은 패키지 바로 아래 둔다.

## CLI 계약

호출: `uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" <명령> …`. 모든 도움말·메시지는 한국어.

### `run <경로>... [--instructions 지시] [--force] [--jobs N] [--model {opus,sonnet,haiku,fable} | ID] [--effort {low,medium,high,xhigh,max}]`

- 경로: `.md` 파일이나 폴더를 하나 이상, 섞어서. 폴더는 바로 아래 `.md`만(하위 폴더·숨김 파일 제외), `Recast_*`·`Reconstruct_*`는 출력이라 제외. 여러 경로에 같은 파일이 있으면 한 번만. 없는 경로, `.md`가 아닌 파일, 출력 파일을 직접 준 경우, 처리할 원문이 없는 폴더는 사용법 오류(종료 2).
- 건너뜀: 원문 옆에 `Recast_<원문 파일명>`이 있으면 건너뛴다. `--force`면 다시 쓰고 기존 `Recast_`를 덮는다(되돌릴 수 없음). 옛 `Reconstruct_`는 판정에 쓰지 않고 건드리지도 않는다.
- 기본값: `--jobs 8`, `--model opus`, `--effort xhigh`. 모델마다 받는 effort가 다를 수 있다는 것을 도움말에 적는다(거부되면 워커 오류로 보고된다).
- 시작 전 확인: `claude` 실행 파일이 없으면 아무 파일도 시작하지 않고 종료 3(환경 오류). 실행 파일은 `RECAST_CLAUDE_BIN` 환경 변수가 있으면 그것(테스트용), 없으면 PATH의 `claude`.
- 워커 호출(고정 부분): `claude -p --safe-mode --restricted --tools Read,Write --permission-mode acceptEdits --model <model> --effort <effort> --output-format stream-json --verbose --include-partial-messages --append-system-prompt-file <스킬>/scripts/recast/system_prompt.md`, cwd = 샌드박스, env에 `CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000`, 프롬프트는 stdin, 자기 프로세스 그룹(`start_new_session`).
- 워커 프롬프트(프로토콜만, 원칙은 시스템 프롬프트가 가짐): 원문은 `source.md`(원래 파일 이름, 줄 수), 끝까지 읽기(Read가 끊기면 offset으로 이어 읽기), 재구조화한 글 전체를 `output.md`에 한 번의 Write로 쓰기, 재구조화할 지식을 찾을 수 없으면 `output.md`를 쓰지 않고 이유를 답하기, 사용자 지시(있으면).
- 파일 판정(하나라도 걸리면 실패, 출력은 게시하지 않음, 다른 파일은 계속):

| 판정 | 근거 | 보고할 다음 행동 |
|---|---|---|
| 원문 읽기 실패 | 원문이 UTF-8이 아니거나 읽을 수 없음(복사 전) | 원문을 UTF-8로 저장 |
| 멈춤 | 워커에게서 `STALL` 동안 아무 이벤트도 없음 → 프로세스 그룹 SIGTERM→SIGKILL, 종료 확인 | 다시 실행 |
| 비정상 종료·결과 없음 | 종료 코드 ≠ 0이거나 마지막 `result` 이벤트가 없음 | stderr 끝부분과 함께, 다시 실행 |
| 오류 결과 | `result`의 `is_error` 참 | 결과 문구와 함께, 다시 실행 |
| 권한 거부 | `permission_denials`가 비어 있지 않음 | 거부된 도구 이름과 경로만 보여 준다(입력 본문은 싣지 않음) |
| 모델 불일치 | `modelUsage`가 비었거나 요청한 모델이 아닌 키가 있음 | 돈 모델 이름과 함께, 다시 실행 |
| 출력 없음 | `output.md`가 없거나 비어 있음 | 워커의 마지막 응답(원문이 망가졌다는 판단 등)을 그대로 보여 준다 |
| 원문이 바뀜 | 게시 직전 원문의 sha256이 복사할 때와 다름 | 다시 실행 |
| 게시 실패 | 원문 폴더에 쓸 수 없음, 하드 링크를 지원하지 않는 볼륨(`--force` 없을 때) 등 | 오류 문구와 권한·볼륨 확인 |

  건너뜀 사유는 둘이다: `Recast_`가 이미 있음 / 처리 도중 다른 실행이 먼저 `Recast_`를 씀(덮지 않음).
- stdout(끝에 한 번, 중단 때도, JSON 하나): 싼 신호 먼저 — `{"run": id, "state": finished|interrupted, "summary": {"total", "done", "failed", "skipped", "interrupted", "seconds"}, "files": [{"source", "status": done|failed|skipped|interrupted, "output", "source_chars", "output_chars", "seconds", "models", "reason", "next", "worker_said"}], "next": "…"}`. stderr: 파일이 끝날 때마다 한 줄(✅·❌·⏭️).
- 중단(SIGINT·SIGTERM): 대기 중인 파일은 시작하지 않고(`interrupted`), 돌고 있는 워커 프로세스 그룹을 끝내고(`interrupted`), 샌드박스를 지우고, 기록과 stdout JSON을 `interrupted`로 남긴다.
- 종료 코드: 0 실패 없음(건너뜀 포함), 1 실패가 하나라도 있음, 2 사용법 오류, 3 `claude` 실행 파일 없음, 130 중단.

### `status [RUN_ID]`

- 인자가 없으면 가장 최근 실행. stdout JSON: `{"run", "state": running|finished|interrupted, "summary": {...}, "files": [{"source", "status": queued|running|done|failed|skipped|interrupted, "phase": 읽는 중|생각하는 중|쓰는 중|속도 제한 대기, "phase_seconds", "written_chars", "elapsed_seconds", "last_signal_seconds_ago", "output", "reason"}]}` — `phase_seconds`(지금 단계에 머문 시간)는 신호는 오는데 진척이 없는지를 Claude가 판단하는 근거다. 끝 기록이 없을 때의 생존 판정은 'Claude가 정한 것 → 진행·요약·생존'대로(하트비트, 멈췄으면 PID와 시작 시각).
- 종료 코드: 0, 2(없는 RUN_ID·기록 없음).

## 문서 섹션 구조

### `SKILL.md` (한국어, 독자: 볼트 세션의 메인 Claude)

frontmatter: `name: recast` / `description`(직접 호출용으로 짧게 — 무엇을 하는지, 출력 `Recast_<원문>.md`, 인자는 파일·폴더 경로와 덧붙인 지시) / `argument-hint: <경로>... [지시]` / `disable-model-invocation: true` / `allowed-tools: Bash(uv run "${CLAUDE_SKILL_DIR}/scripts/cli.py" *)`. 인자·출력 형식·실패 종류는 `--help`가 소유하고 SKILL.md는 사본을 두지 않는다.

1. **무엇을 하나** — 재구조화의 한 줄 정의. CLI가 파일마다 깨끗한 헤드리스 세션 하나를 띄워 원문 전체를 읽고 한 번에 쓴다. 메인이 원문이나 출력 본문을 읽지 않는 이유(여러 파일의 본문이 메인 컨텍스트에 쌓이면 조율할 자리가 사라지고, 집필 판단은 워커의 시스템 프롬프트가 갖는다). 메인이 직접 쓰거나 다른 모델·서브에이전트로 넘기지 않는 이유(이 세션의 위임 기본값과 무관하게 모든 파일이 같은 모델·같은 지시문으로 쓰여야 한다). 모델·effort는 사용자가 정할 때만 바꾼다.
2. **실행** — `run`은 파일 수에 비례해 오래 걸리는 블로킹 명령이라 Bash `run_in_background`로 돌리고 완료 알림을 기다린다. 경로 뒤에 덧붙인 말은 `--instructions`로 넘긴다. 사용자가 진행이나 멈춤 여부를 물을 때 `status`를 본다. 신호가 20분 끊긴 워커는 CLI가 스스로 끝내므로, Claude가 판단할 것은 신호는 오는데 진척이 없는 경우다 — 단계에 머문 시간이 그 원문 길이에 비해 지나치게 길거나, 쓰는 중인데 글자 수가 늘지 않거나, 속도 제한 대기만 이어진다. 그렇게 보이면 근거(단계·머문 시간·글자 수)와 함께 알리고 멈출지 묻는다. 멈추는 방법은 그 백그라운드 작업을 멈추는 것이고(기록은 `interrupted`), 같은 명령을 다시 실행하면 끝난 파일은 건너뛴다. `--force`는 기존 `Recast_`를 덮어 되돌릴 수 없으므로 사용자가 다시 쓰라고 했을 때만 쓴다.
3. **결과를 전하기** — 요약과 파일별 결과를 전하고, 실패는 이유와 다음 행동을 붙인다. 결과가 보여 주지 않는 것: 충실도는 아무도 자동으로 검사하지 않았다 — 글자 수 비율은 척도가 아니다(포장이 많은 대담은 크게 줄고 밀도 높은 글은 거의 줄지 않는다). 사용자가 품질을 물을 때만 원문과 출력의 해당 대목을 함께 읽는다. 출력이 왜 그렇게 쓰였는지 묻거나 원칙을 바꾸려 하면 `scripts/recast/system_prompt.md`를 연다.

### `scripts/recast/system_prompt.md` (한국어, 독자: 헤드리스 워커 — 시스템 프롬프트)

바탕은 `.tmp/old/Reconstructor.md`. 운영 부분(입력 명세, 도구 사용법, `Bash cat`, 글자 수 보고, 워크플로 단계, 페르소나 이름)은 CLI의 프롬프트와 판정이 맡으므로 옮기지 않는다. 9월 대조 실험이 잡은 교정(바깥 지식 금지, 요약 절·부록 금지, 화자 중계체, 망가진 원문)은 Knowledge의 `reconstruct.md`에서 가져온다. 각 절은 원칙과 그 이유, 결론이 갈리는 경계 사례로 쓰고, 예시는 비슷한 두 경우가 왜 갈리는지 보여 줄 때만 쓴다.

1. **목표** — 독자가 원문을 다시 볼 필요 없는 한국어 글. 번역(순서와 포장까지 옮김)도 요약(실질을 줄임)도 아니다. 글의 구조는 원문이 전달된 순서가 아니라 지식을 따르고, 말하는 동안 암묵적이던 논리 연결(이 사례가 왜 이 주장의 근거인지, 두 논점이 어떻게 맞서는지)을 문장으로 드러내며, 헤딩만 읽어도 논증의 뼈대가 보인다. 출력은 글 자체다(인사·안내·메타 설명 없음). 분량은 충실도의 척도가 아니다.
2. **실질과 포장** — 판단 질문 하나: 이것은 지식인가, 지식이 담겨 온 포장인가. 실질: 개념, 주장과 근거, 사례, 구분, 단서 조건, 확신의 정도, 나열된 항목 전부, 시간·빈도 표현, 대비 구조(old의 점검 목록이 잡던 누락을 원칙으로). 포장: 잡담, 기침, 광고, 의례적 인사, "좋은 질문입니다", 말로 한 강조 반복, 클리퍼 잔재. 경계 사례: 한 발화에 소개와 인사가 섞이면 소개만 옮긴다 / 같은 요점을 말로 두 번 강조한 것은 한 번, 다른 사례로 되풀이했다면 그 사례는 실질. 사례는 조회표가 아니라 원리의 예다.
3. **화자와 목소리** — 판정: 화자 언급을 지웠을 때 잃는 지식이 있나. 사실·제도·개념 설명은 누가 말했든 명제로. 화자를 남기는 곳: 판단·예측·확신의 정도·화자 사이의 이견, 질문의 틀이 답을 바꾼 곳. 저자 자신의 경험은 원문대로 1인칭 '나는'("저자는"으로 바꾸면 경험이 논증에 싣는 무게가 빠진다). 대담을 발언 순서대로 중계하면 속기록이 된다. 예시: 같은 대목을 중계와 재구조화로 쓴 한 쌍(Knowledge의 골드스미스 대목)과 왜 갈리는지 한 줄.
4. **덧붙임의 경계** — 원문 문맥으로 복원되는 표기 오류(잘못 붙은 화자 라벨, 고유명사 철자, 끊긴 문장, PDF 합자 깨짐)는 조용히 바로잡고 고친 목록을 남기지 않는다. 원문이 전제한 용어·배경은 본문 흐름 안에서 짧게 풀어도 된다. 원문의 주장 자체를 바깥 지식으로 고치거나 보태지 않는다(독자는 원문이 무엇을 말했는지 읽으러 왔고, 섞이면 어디까지가 원문인지 가릴 수 없다). 요약 절·요약 표·용어 부록을 두지 않는다(본문을 두 번 말할 뿐이다).
5. **산문과 한국어** — 완결된 문장과 문단으로 쓴다(목록으로 쪼개면 원문이 갖던 연결 논리를 독자가 다시 짜 맞춰야 하고, 그 일을 대신하는 것이 이 글이다). 목록·표는 서사 없이 나란히 놓인 항목일 때만. 의미에 충실하되 문장 구조는 옮기지 않는다 — 한국어로 처음 쓴 글처럼(BAD/GOOD 한 쌍).
6. **서식 관례** — 결정 원장의 1~8을 그대로(평어체, 고유명사 표기, `# 🖇️` 제목과 이모지 헤딩, 산문 기준의 목록·표, 인용 규칙, 이미지, 굵게 재량, 번역투). 관례라 이유는 붙이지 않는다.
7. **원문이 망가졌을 때** — 복원할 지식이 없으면(문장이 성립하지 않는 전사, 본문 대신 오류 페이지만 저장된 클립) 지어내지 않고 `output.md`를 쓰지 않은 채 이유를 답한다(그 답이 사용자에게 실패 이유로 간다). 일부만 깨졌으면 복원되는 실질은 살린다.

## 테스트 (seam)

`coding` 스킬 기준으로 seam을 다섯으로 정한다. 기대값은 구현이 닿지 않는 곳에서 온다 — 합성 원문의 내용, 실제 claude에서 받은 이벤트·결과의 모양, `--help` 문구가 아니라 실제 동작. 멈춤 기준 시간은 테스트에서 짧게 바꿀 수 있어야 하므로 `RECAST_STALL_SECONDS` 환경 변수로만 덮어쓸 수 있게 한다(코드 주석에 테스트용이라고 적는다).

| seam | 무엇을 검증 | 무엇이 남는가(미검증) |
|---|---|---|
| ① `cli.py` 서브프로세스 + 가짜 claude(`RECAST_CLAUDE_BIN`) | run·status의 프로토콜: stdout JSON 모양과 상태 집합, 종료 코드 0·1·2·3·130, 게시·건너뜀·`--force`, 판정 표의 실패 9종이 각각 보고되고 출력이 게시되지 않음(원문이 바뀜은 가짜가 실행 도중 원문을 고쳐 재현), 경합(가짜가 실행 도중 `Recast_`를 만들면 덮지 않고 건너뜀), 옛 `Reconstruct_`는 판정에 쓰이지 않고 그대로 남음, 중단(SIGINT·SIGTERM 각각 — 대기 파일 미시작·워커 회수·샌드박스 삭제·최종 JSON `interrupted`·exit 130), `status`의 여섯 상태·단계·단계에 머문 시간·쓴 글자 수·마지막 신호, 멈춤(가짜가 신호를 끊으면 `RECAST_STALL_SECONDS` 뒤 그 파일만 '멈춤'으로 끝나고 나머지는 계속), 생존 판정(하트비트 신선 → running / 멈췄지만 같은 PID·시작 시각의 프로세스가 살아 있음 → running / 프로세스 없음 → interrupted / PID는 살아 있으나 시작 시각이 다름 → interrupted), 같은 원문에 실제 CLI 두 개를 동시에 돌려도 `Recast_`가 하나만 게시되고 진 쪽은 건너뜀·임시 파일이 남지 않음, `--model`·`--effort`가 워커 argv로 가고 모델 판정이 요청한 모델을 기준으로 함, 본문 차단(가짜가 표식 문자열을 큰 Read 결과·출력 조각·거부된 Write의 `tool_input.content`·오류 결과 문구에 담아 흘려도 stdout·stderr·실행 기록 어디에도 500자를 넘는 본문이나 표식이 없고, `worker_said`·stderr 끝부분은 500자 이하) | 실제 Claude Code의 이벤트·결과 모양(→⑤) |
| ② `recast.claude` 인터페이스 | argv·env 조립(플래그 전부, cwd, `CLAUDE_CODE_MAX_OUTPUT_TOKENS`), stream-json 이벤트 → 단계·글자 수(실제 모양 픽스처로), 결과 판정, 멈춤 감시가 프로세스 그룹 종료를 확인 | 같음(→⑤) |
| ③ `recast.sources`·`recast.publish` 인터페이스 | sources: 폴더·파일·섞어 주기·중복, 숨김·하위 폴더·두 접두사 제외, 건너뜀 판정, 사용법 오류. publish: 목적지가 없으면 게시, 있으면 덮지 않고 '이미 있음', `--force`면 원자적 교체, 호출마다 고유 임시 파일과 그 정리, 하드 링크 불가(`os.link`가 `OSError`를 내는 경계 — 실제 볼륨 없이 재현할 다른 방법이 없어 여기만 대역을 쓴다) 시 부분 파일 없이 실패 | 실제 exFAT 볼륨에서의 동작 |
| ④ 구조 테스트 | 트리 두 이름, PEP 723, `allowed-tools`와 SKILL.md 본문의 호출 구문, `sys.path` 편집 없음, 단위 종류별 import 방향 | — |
| ⑤ 실제 계약(`RECAST_LIVE=1`, 합성 원문, effort low) | `--restricted`에서 cwd 안 쓰기 성공·cwd 밖 읽기가 `permission_denials`로 나타남(필드 이름·모양), `--append-system-prompt-file` 반영, `modelUsage` 키, stream-json 이벤트 종류와 모양(읽기·쓰기·부분 메시지·결과), `--verbose` 필요 여부, `CLAUDE_CODE_MAX_OUTPUT_TOKENS` 지정이 오류 없이 통함 | 집필 품질(→E2E와 성진의 판단), xhigh에서의 끊김 시간(→8단계) |

## 작업 단계 (구현 세션 시작 시 `TaskCreate`로 트래커를 열고, 각 description에 판정을 그대로 적는다)

0. **계획 파일 이름** — 이 계획 승인 직후(이 세션)에 `mv`로 `.claude/plans/recast-skill-rebuild.md`로 옮긴다(아직 git 레포가 아니므로 `git mv`가 아니다). 판정: 새 경로에 파일이 있고 옛 경로에는 없음.
1. **레포 초기화(main)** — `git init -b main`, `.gitignore`(디렉터리 절의 목록), `git remote add origin https://github.com/tjdwls101010/Agentic-Recast.git`, 첫 커밋 `chore: 레포를 초기화한다`(`.gitignore` + 계획 파일만 — 커밋 전에 `git status --short`로 그 둘뿐인지 본다), 푸시. 판정: `git ls-remote origin`에 main이 보임, `git check-ignore -v .tmp/examples .claude/histories .claude/skills/recast/data/x .codex-runs .DS_Store`가 다섯 다 무시됨(계획 세션의 codex 검토 기록 `.codex-runs/`가 이미 있다), `git status` 깨끗함.
2. **브랜치·골격** — `feat/recast-skill`. `pyproject.toml`(개발 전용, `[tool.pytest.ini_options] testpaths=["tests"]`, `pythonpath=[".claude/skills/recast/scripts", "tests"]`, `markers=["live: 실제 claude를 부른다"]`, `addopts="-m 'not live'"`, ruff line-length 120, `[dependency-groups] dev=["pytest>=8"]`). 구조 테스트를 먼저 쓰고 빨강을 본 뒤, `cli.py`(PEP 723 헤더), 빈 단위 모듈, SKILL.md 골격(frontmatter와 호출 구문 한 줄 — 전문은 7단계)으로 초록. 판정: `uv run pytest tests/test_structure.py`가 빨강(트리 없음)→초록.
3. **`claude.py`(system)** — seam ②. 판정: argv·env·cwd 조립, 이벤트 → 단계·글자 수, 판정(비정상 종료·결과 없음, 오류 결과, 권한 거부, 모델 불일치, 멈춤과 프로세스 그룹 종료 확인)이 각각 구분되어 나오는 테스트가 빨강→초록. 이벤트 픽스처는 우선 문서 기준 모양으로 쓰고 6단계에서 실제 모양으로 바꾼다.
4. **`sources.py`·`publish.py`(common)** — seam ③. 판정: 폴더 바로 아래만, 파일·폴더 섞어 주기, 숨김·`Recast_*`·`Reconstruct_*` 제외, 중복 제거, `Recast_`만 건너뜀 근거, 사용법 오류 네 가지, 그리고 publish의 다섯 경우(새로 게시, 이미 있음, `--force` 교체, 고유 임시 파일 정리, 하드 링크 불가 시 부분 파일 없는 실패)가 빨강→초록.
5. **`runs.py`·`run.py`·`status.py`·`cli.py`** — seam ①의 목록 전부가 빨강→초록. `--help`·`run --help`·`status --help`를 실제로 실행해 모든 인자·기본값·선택지·출력·종료 코드·되돌릴 수 없는 동작(`--force`)·멈춤 처리가 적혔는지 확인.
6. **실제 계약 테스트** — seam ⑤를 한 번 돌린다: `RECAST_LIVE=1 uv run pytest -m live tests/test_live_contract.py`. 합성 원문으로 받은 실제 이벤트·결과 모양(본문 없이)을 `tests/fixtures/`에 저장해 ②의 픽스처를 바꾼다. 판정: 통과, `permission_denials`·`modelUsage`·이벤트의 실제 모양이 판정·진행 코드와 일치(다르면 코드를 고치고 ②·①을 다시 초록으로).
7. **문서** — `SKILL.md` 전문과 `system_prompt.md`를 위 섹션 구조로 쓴다. codex(다른 모델군)가 skill-maker 다섯 성질 기준으로 읽고, 그 검토를 따져 반영한다. 판정: 성진이 두 문서 전문을 승인.
8. **E2E** — `.tmp/examples`의 원문 3개로 `uv run ".claude/skills/recast/scripts/cli.py" run .tmp/examples`를 백그라운드로 돌리고, 도중에 `status`, 끝난 뒤 요약 JSON·출력 파일을 확인한다. 실행 기록에 남은 파일별 "이벤트가 가장 오래 끊긴 시간"으로 `STALL`을 확정한다. 이어서 이 레포 세션에서 `/recast <예시 파일 하나>`로 SKILL.md 흐름도 한 번 확인한다. 판정: 3개 모두 `done`, stdout JSON의 `models`가 `claude-opus-*`뿐, 권한 거부 없음, `..md` 파일 통과, `status`가 도중에 단계·글자 수·마지막 신호를 보여 줌, 출력이 서식 관례 1~8을 따름(첫 줄 `# 🖇️…`, 이모지 헤딩, `한글(원어)`, 평어체), 성진이 출력을 읽고 품질을 승인. 성진의 `[!success]` 같은 메모가 본문에 섞였는지도 본다(섞였으면 지시문에 한 줄을 더할지 묻는다).
9. **마무리** — `claude plugin validate --strict "/Users/seongjin/Coding/Agentic Recast/.claude/skills"` exit 0, `uv run pytest` 전체 초록, codex 최종 코드 리뷰(평범한 실행에서 도달 가능한 결함 목록이 빌 때까지, 발견은 재현해 따지고 반영). 판정: 셋 다 통과.
10. **PR·머지** — 논리 단위 커밋(`feat:`/`test:`/`docs:` 한국어 제목), 푸시, PR(제목 `feat: recast 스킬을 얇은 헤드리스 CLI로 다시 짓는다`, 본문 `## 무엇을 바꿨나` / `## 왜` / `## 영향` / `## 검증`(실제 명령과 수치)), `gh pr merge --squash`. 계획 파일 끝에 `# 구현 기록`(계획 대비 바꾼 것, 단계 결과, codex 검토 처리, 남은 것)을 더해 같은 PR에 넣는다. 판정: main에 머지, 원격 main에 스킬·테스트·계획이 있음.

## 검증 (end-to-end)

- `uv run pytest`(라이브 제외) 전체 초록, 종료 코드로 판정.
- `RECAST_LIVE=1 uv run pytest -m live` 통과(6단계).
- `uv run ".claude/skills/recast/scripts/cli.py" --help` / `run --help` / `status --help`를 실행해 설명과 동작 일치.
- 8단계 E2E: 요약 JSON 수치(파일별 원문 자→출력 자, 초, models), `status` 중간 출력, 출력 3개의 서식 관례 확인, 성진의 품질 판단.
- `claude plugin validate --strict "/Users/seongjin/Coding/Agentic Recast/.claude/skills"` exit 0.

## skill-maker 조항 대조

| 조항 | 이 계획에서 |
|---|---|
| 기본 모델이 이미 하는 것은 빼고 차이만 | 9월 대조 실험이 확인한 기본 동작(주제별 재편, 잡담 제거, 평어체 기본, 전사 오류 교정)은 절을 따로 두지 않고, 차이를 만든 것(화자, 덧붙임, 요약 절·부록, 서식 관례)에 분량을 쓴다 |
| Principle over rail | "순서를 바꿔도 된다"·"cite 보존"·`>` 절대 금지·목록 절대 금지를 레일로 두지 않고 원칙(구조는 지식을 따른다, 산문의 이유)으로 |
| Interface over document | 인자·출력·실패는 `--help`와 CLI 판정이 소유, 워커 프로토콜은 CLI 프롬프트가 소유, 문서는 사본을 두지 않는다 |
| For the model | 출처·실측 이력·버린 대안은 문서가 아니라 PR 본문과 이 계획의 구현 기록에 |
| Colleague over autopilot | SKILL.md가 결과가 보여 주지 않는 것(충실도 미검사)과 되돌릴 수 없는 것(`--force`)을 말하고, 품질 확인은 사용자가 원할 때만 |
| 코드 트리 | `scripts/cli.py` + `scripts/recast/`, `uv run "${CLAUDE_SKILL_DIR}/…"`, PEP 723, stdout JSON(싼 신호 먼저, 실행 id가 상세의 손잡이), stderr 진행, 0/2 + `--help`가 정한 1·3·130, `data/`에 상태, 레포 `tests/`와 구조 테스트 |
| Split files by when they are needed | 메인이 읽는 것은 SKILL.md 하나, 워커가 읽는 것은 코드가 넘기는 `system_prompt.md` 하나 — 메인이 원칙을 들여다볼 때만 SKILL.md의 포인터로 연다 |
| 이웃 스킬 경쟁 | 직접 호출 전용이라 스킬 목록에서 경쟁하지 않는다 — `/skill-doctor`는 생략한다 |
| 완료 조건 | 성진의 전문 승인, `plugin validate --strict` exit 0, 다른 모델군(codex) 검토 |

## 남은 위험

- **기본 동작 교정의 근거가 오래됐다.** 실측을 하지 않기로 했으므로, 지시문의 교정 문장(화자, 덧붙임, 요약 절)이 지금 모델에게도 필요한지는 9월 대조 실험(같은 Opus 5.5)과 old를 다듬은 성진의 경험에 기댄다. 이 스킬은 성진만 쓰므로 그 경험 자체가 지식이다. E2E 출력과 성진의 판단이 남은 확인 수단이다.
- **충실도는 아무도 자동 검사하지 않는다.** 누락을 잡던 장치(블록 배정, 숫자 힌트)를 뺐다. 지시문의 실질 목록과 모델의 판단에 맡기고, SKILL.md가 이 사실을 결과 전달에서 말한다.
- **`modelUsage`의 보조 모델.** 헤드리스 실행이 보조 작업에 다른 모델(Haiku 등)을 쓰면 "모델 불일치"가 오탐이 된다. 9월 실행은 Opus뿐이었다. 6단계 실제 계약에서 확인하고, 보조 모델이 보이면 판정을 "집필 모델이 요청한 모델인가"로 좁힌다.
- **멈춤 기준 시간.** 사고 중 이벤트 간격은 실측으로 1~1.5초임을 확인했다(짧은 계산 문제 하나). 남은 불확실성은 API 재시도 대기처럼 Claude Code가 이벤트 없이 기다리는 구간이 있는지다. 하한 20분은 성진의 결정이고, 8단계에서 최장 끊김이 7분을 넘으면 다시 묻는다. 신호는 오는데 진척이 없는 정체는 코드가 잡지 않고 Claude가 `status`로 판단한다 — 아무도 묻지 않으면 그런 정체는 오래 이어질 수 있다.
- **동시 8개.** 구독의 속도 제한에 걸리면 실패가 늘 수 있다. 그 경우 실패 사유(오류 결과)로 드러나고 `--jobs`로 낮춘다.

## 독립 검토 (codex)

### ① 계획 검토 (gpt-6.1-sol high, read-only, run `20261023-134230-plan-review-634e`)

9건, 모두 반영했다. 판단: "방향을 바꿀 필요는 없지만 동시 게시와 원문 변경에서 결과를 잘못 확정하는 문제는 먼저 막아야 한다."

| # | 심각도 | 지적 | 처리 |
|---|---|---|---|
| 1 | 높음 | 두 실행이 같은 파일을 동시에 처리하면 `--force` 없이도 덮어쓴다(`os.replace`는 목적지를 덮음) | 원문 폴더의 임시 파일 + no-clobber 게시, 진 쪽은 건너뜀으로 보고, 경합 테스트 |
| 2 | 높음 | 처리 도중 원문이 바뀌면 옛 내용의 결과를 게시하고, 재실행은 건너뛴다 | 게시 직전 sha256 비교, 다르면 실패 |
| 3 | 중간 | 시스템 임시 폴더 → 외장 볼륨 `os.replace`는 `EXDEV` | 같은 폴더 임시 파일로 해결 |
| 4 | 중간 | 쓰기 권한 없음·UTF-8 아님·`claude` 없음의 계약이 없다 | 앞의 둘은 파일 실패, `claude` 없음은 시작 전 종료 3 |
| 5 | 중간 | PID 재사용 시 `status`가 죽은 실행을 살아 있다고 본다 | 하트비트로 생존 판정 |
| 6 | 중간 | 중단 결과를 `run`의 stdout 스키마로 표현할 수 없다 | `interrupted` 상태와 중단 때도 최종 JSON |
| 7 | 중간 | 2단계 구조 테스트가 SKILL.md 없이 초록이 될 수 없다 | 2단계에 SKILL.md 골격 |
| 8 | 중간 | E2E의 "Opus만" 판정을 확인할 증거가 출력에 없다 | 파일별 `models`를 기록·stdout에 |
| 9 | 중간·사용자 결정과 충돌 | `--effort` 공개 옵션이 xhigh 고정 결정과 어긋난다 | 검토 뒤 성진이 "기본 opus·xhigh, 파라미터로 설정 가능"으로 정해 옵션을 두고, 모델 판정을 요청한 모델 기준으로 바꿨다 |

검토 뒤 성진의 결정으로 바뀐 것: `--timeout` 제거, 워커 프롬프트를 `scripts/recast/system_prompt.md`로, 멈춤 자동 종료(stream-json 모니터링), `--model`·`--effort` 파라미터, 모니터링 이벤트의 본문이 메인으로 가지 않게 차단.

### ② 반영 확인 (같은 스레드, run `20261023-135222-plan-review-7eea`)

①의 9건이 본문·seam·단계에 반영된 것을 확인했다(①1·①5는 아래 ②1~3으로 불완전 지적). 새 발견 4건, 모두 반영했다. 판단: "보완하면 나머지 스트림 동작은 계획에 잡힌 실제 계약 테스트와 E2E에서 확인하는 조건으로 구현에 들어갈 수 있다."

| # | 심각도 | 지적 | 처리 |
|---|---|---|---|
| 1 | 높음 | 하드 링크가 안 될 때 배타적 생성으로 바꾸면 부분 파일이 남고 다음 실행이 완료분으로 건너뛴다 | 대안을 없애고 '게시 실패'로 끝낸다, `publish.py` 테스트 |
| 2 | 중간 | 게시용 임시 파일 이름이 실행마다 고유하지 않으면 링크된 inode를 다른 실행이 덮는다 | `mkstemp`로 고유·배타 생성, 자기 것만 정리, 실제 CLI 두 개 동시 실행 테스트 |
| 3 | 중간 | 오래된 하트비트만으로 중단을 확정하면 Mac 잠자기 복귀를 `interrupted`로 오판한다 | 하트비트 + PID·시작 시각 동일성 확인 |
| 4 | 중간·검증 공백 | 거부된 Write의 `permission_denials[].tool_input`에 본문이 들어 있어, 직렬화하면 표식 테스트를 통과하면서 새어 나간다 | `tool_input`을 싣지 않고 도구 이름·경로만, 표식 테스트에 거부된 Write·오류 결과 추가 |

남은 것(확인 불가로 남김): 정상 사고 중 이벤트 공백과 실제 이벤트 모양은 실제 헤드리스 실행 없이 확인할 수 없어 6·8단계에 둔다. 재시도나 반복 호출처럼 이벤트가 계속 오는 정체는 `STALL`의 탐지 대상이 아니다(성진이 고른 정책의 범위). 패키지 안 `system_prompt.md`는 구조 테스트·`uv run`과 충돌하지 않는다(codex 확인). 이 4건의 처리는 계획 수준의 수정이라 세 번째 검토 대신 구현의 테스트(seam ①·③)가 닫는다.

# 구현 기록 (2026-10-23)

## 단계 결과

| 단계 | 결과 |
|---|---|
| 0 | 계획 승인 직후 `recast-skill-rebuild.md`로 옮김 |
| 1 | `git init -b main`, 원격 연결, 첫 커밋 `f3cb14d` 푸시. `git check-ignore` 다섯 경로 모두 무시 |
| 2 | 구조 테스트 빨강(트리 없음 7건) → 골격으로 초록 9건. `sys.path` 편집·system→feature import·밑줄 이름 접근을 일부러 넣어 셋 다 잡히는 것을 확인 |
| 3 | 실제 claude로 정상·권한 거부 스트림을 먼저 받아(경로만 바꿔) 픽스처로 삼고, `claude.py` 테스트 27건 빨강→초록. 권한 거부 판정 제거·모델 판정 무력화·`killpg`→`kill` 변형을 테스트가 잡음 |
| 4 | `sources`·`publish` 15건 빨강→초록. no-clobber를 `os.replace`로 바꾸기·옛 접두사 제외 제거·`Reconstruct_`를 완료로 보기 변형을 잡음 |
| 5 | seam ① 33건. A 묶음은 빨강→초록, B~D는 구현과 함께 들어가 여섯 변형(원문 해시 비교 제거, 항상 force 게시, 글 상한 5000, 대기 파일 interrupted 표시 제거, 생존 항상 참, PID만으로 생존)으로 지키는지 확인. `uv run … --help`를 실제로 읽고, 인자 도움말이 접히지 않게 `RawTextHelpFormatter`로 바꿈 |
| 6 | `RECAST_LIVE=1 uv run pytest -m live` 4건 통과(37초, 수정 뒤 다시 4건 통과). `modelUsage`에 보조 모델 없음, `maxOutputTokens` 128000, `note..md` 끝에서 끝까지 통과 |
| 7 | 문서 초안 → codex 문서 검토 6건 반영 → 성진 전문 승인 |
| 8 | 아래 E2E 표. 성진 출력 품질 승인. `claude -p "/recast .tmp/examples"`로 SKILL.md 흐름(스킬 로드 → `allowed-tools` 사전 승인 → CLI → 결과 전달, 권한 거부 0)도 확인 |
| 9 | `claude plugin validate --strict` exit 0, `uv run pytest` 96 passed(라이브 4 제외), ruff 통과, codex 최종 검토 "없음" |

### E2E (`uv run .claude/skills/recast/scripts/cli.py run .tmp/examples`, 기본 opus·xhigh, 병렬 3)

| 원문 | 원문→출력 | 시간 | models | 최장 무신호 | worker_said |
|---|---|---|---|---|---|
| 📰Claude Opus 5.5 is built with that in mind..md | 8,198→3,564자 | 1분 39초 | claude-opus-5-5 | 1.7초 | 버린 대목 없음 |
| 📰Why Are We Sprinting Off the A.I. Cliff?.md | 35,606→14,883자 | 5분 13초 | claude-opus-5-5 | 3.0초 | 버린 대목 없음 |
| 📰Bill Gates A.I. ‘Makes Nuclear Weapons Look Like Nothing’.md | 78,633→25,762자 | 7분 18초 | claude-opus-5-5 | 1.7초 | 버린 대목 없음 |

전체 438초, exit 0. 도중 `status`가 파일마다 단계·머문 시간·글자 수·마지막 신호를 보여 줬다. 최장 무신호가 3초로 7분 기준에 한참 못 미쳐 `STALL` 20분을 그대로 둔다.

## 계획 대비 바꾼 것

- **생존 판정:** 계획은 "하트비트가 신선하면 running, 멈췄으면 PID·시작 시각 확인"이었다. 구현은 PID·시작 시각을 먼저 보고, `ps`를 쓸 수 없거나 조회가 stderr와 함께 실패할 때만 하트비트(30초 갱신, 2분 기준)로 본다. 하트비트를 먼저 보면 강제 종료된 실행이 최대 2분 동안 running으로 보이기 때문이다.
- **중단:** 신호 처리기가 `KeyboardInterrupt`를 던지지 않고 멈춤 이벤트만 켠다(codex 코드 1차 #1). 배치는 0.2초마다 이벤트를 보고 워커를 끝내며, 파일은 시작 전에 이벤트를 확인한다. 멈춤 요청을 받은 실행은 `interrupted`로 남는다.
- **성공 시 `worker_said`:** 워커 프롬프트가 마지막 답을 "버린 대목" 한 줄로 하게 하고, 성공한 파일에도 `worker_said`를 싣는다(codex 문서 #3). 깨져서 버린 대목이 성공 결과에서 사라지지 않게 하려는 것이다.
- **재시도 안내:** `--force`로 돈 실행 뒤의 `next`는 "실패하거나 중단된 원문만 경로로 주고 다시 실행"으로 안내한다(codex 문서 #1).
- **단계 이름:** `시작`을 더했다(첫 이벤트 전 상태).
- **출력 한도:** 실측에서 `CLAUDE_CODE_MAX_OUTPUT_TOKENS` 없이도 `modelUsage.maxOutputTokens`가 128000이었다. 문서에 숫자가 없어 명시는 그대로 둔다.
- **픽스처:** 계획은 6단계에서 실제 모양을 받기로 했지만, 가짜가 실제와 다른 모양을 흉내 내지 않도록 3단계 시작 전에 받았다.
- **커밋 이력:** `f0862ce`(코드 수정)에 문서 초안 `system_prompt.md`가 함께 들어갔다. 스쿼시 머지라 main에는 남지 않는다. `uv.lock`도 커밋한다.

## 독립 검토 (codex, gpt-6.1-sol high, read-only)

| 회차 | run | 결과와 처리 |
|---|---|---|
| 코드 1차 | `20261023-142154-code-review-cli-22e0` | 5건 모두 반영: 작업 제출 직후 신호에 대기 파일이 게시됨(높음) / 기록 저장 실패 시 워커 고아 / 같은 초의 id로 최근 실행 오판 / ps 불가 환경에서 생존 오판 / 심볼릭 링크로 같은 원문 두 번 처리 — 각각 재현 테스트를 먼저 쓰고 고침 |
| 문서 | `20261023-142510-doc-review-413d` | 6건 모두 반영: `--force` 재시도 안내 / 이름 없는 화자 규칙이 결정보다 넓음 / 깨져서 버린 대목의 보고 / 실질 목록과 광고 제거의 범위 / CLI 기본값의 사본 / 500자 상한과 "그대로" 표현 |
| 코드 2차 | `20261023-143111-code-review-cli-78bf` | 1차 5건 해소 확인, 새 3건 반영: 결과를 낸 뒤 멈춘 워커가 실패로 보고됨 / ps가 돌았지만 조회 실패 / 읽을 수 없는 과거 기록이 status를 막음 |
| 최종 | `20261023-144511-code-review-cli-b9db` | 없음(평범한 사용 흐름 전체, 96 passed) |

## 남은 것·한계

- **충실도는 자동으로 검사하지 않는다**(설계). SKILL.md가 결과 전달에서 이 사실을 말한다. 워커가 스스로 확인한 결손만 `worker_said`로 온다.
- **확인하지 못한 것:** 성진이 원문 안에 직접 쓴 `[!success] 요약` 같은 메모가 본문에 섞이는지(예시 원문에 없었다), 책 장(PDF 합자·각주·제사)에서의 출력, `rate_limit_event`의 `rejected` 모양(가짜에서만), Claude Code가 백그라운드 작업을 멈출 때 보내는 신호와의 연동(`/recast` 흐름은 `-p`로만 확인).
- **Gates 출력**에 "클라인은 … 물었다"식 질문 중계가 일부 남았다(성진 승인). 되풀이되면 화자 절의 예시를 손볼 후보다.
- **볼트**의 옛 `.claude/skills/Knowledge`와 `.knowledge/` 작업 폴더는 결정대로 그대로 두었다.
