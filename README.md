# AI 전역 작업 규칙

Claude Code 와 Codex 를 쓰며 정한 개인 작업 규칙과, 그 규칙이 실제로 돌아간 공개 기록을 모았다.
2025년 9월부터 계획을 세워 이 방식으로 일해 왔고, 규칙을 정리해 공개한 것은 2026년 9월이다.

## [회고 읽기: AI와 일하며 가장 많이 고친 건 문서였다](https://ting97ok.github.io/ai-global-rules/) · 약 8분

- **원칙**: AI 가 세운 구현 계획을 온전히 이해한 뒤에 구현을 시작한다.
- **문제**: 계획 문서를 읽는 일이 병목이어서 문서 형식과 작성 규칙을 계속 바꿨다.
- **한계**: 읽는 부담은 줄었다고 느끼지만 되묻는 일은 늘었고 효과를 수치로 재지는 못했다.

## 검증 기록

| 규칙 | 공개 기록 |
|---|---|
| 테스트 하나와 구현 하나를 번갈아 커밋한다 | 이 저장소 [PR #4](https://github.com/Ting97ok/ai-global-rules/pull/4) 의 커밋 목록<br>`hotdeal-commerce` [82a62aa](https://github.com/Ting97ok/hotdeal-commerce/commit/82a62aaf5ecbe69c62ccef263f0d05f2326b6aac) → [78982d6](https://github.com/Ting97ok/hotdeal-commerce/commit/78982d6912fff9c3fa9ee1e7f9ad643d5741c8a1) |
| 작업 단위가 끝나면 앱을 띄워 밖에서 호출한다 | `hotdeal-commerce` [PR #6](https://github.com/Ting97ok/hotdeal-commerce/pull/6) 본문의 「인수 확인」 |
| 교차 검증이 잡은 사실 오류를 댓글로 남긴다 | 이 저장소 [PR #4 댓글](https://github.com/Ting97ok/ai-global-rules/pull/4#issuecomment-5645600619) |

두 커밋은 `confirm` 응답에서 결제 완료(`DONE`)와 결과 미확정(`IN_DOUBT`)을 구분한 변경이다. 테스트가 단언을 먼저 잡고 구현이 `ConfirmPaymentResponse` 에 `status` 필드를 더했다.

리뷰로 방향이 바뀌면 댓글을 먼저 남기고 커밋한다는 규칙은 아직 공개 사례로 제시하지 못했다.

이 저장소 자체의 검사도 공개한다. [훅 테스트](claude/hooks/tests/)가 문서 작성 스킬 호출 누락과 테스트가 실패한 상태의 커밋 명령을 검사하고, [Codex 연결 테스트](tests/codex-sync.test.sh)가 링크와 덮어쓰기 방지를, [권한 규칙 테스트](tests/codex-rules.test.sh)가 Codex 에서 막아야 하는 명령을 검사한다.

[이 작업 방식이 만들어진 과정과 남은 고민 읽기](https://ting97ok.github.io/ai-global-rules/)

## 자동 검사 범위

규칙 문서의 지시는 권고다. 훅은 정해진 조건에서 실행된다. 그래서 되돌리기 어려운 동작은 훅으로 검사한다.

| 훅 | 검사하는 것 |
|---|---|
| `git-guard.py` | `git add -A`, 커밋 접두사, 도구 서명, 병합 방식, PR 본문 항목 |
| `commit-checkpoint.py` | 테스트가 통과했는데 커밋하지 않은 변경이 남은 상태 |
| `stop-check.py` | 조회 명령 시키기, 상태 확인 없는 커밋 명령, 테스트가 실패한 상태의 커밋 명령 |
| `prose-check.py` | 문서의 전각 대시 문장 연결, 질문형 제목, 제목 속 개수 |
| `doc-skill-guard.py` | README 와 `docs/` 의 문서를 쓰기 전에 `doc-writing` 스킬을 불렀는지 |
| `memory-note.py` | 메모리에 둘 내용인지 다시 보게 한다 |
| `agent-guard.py` | 서브에이전트 호출에 모델을 지정하는 것 |

훅은 정해진 입력과 패턴을 검사한다. PR 에 「인수 확인」 항목이 있는지는 보지만 적힌 결과가 맞는지까지 판단하지는 않는다. 설계의 타당성과 검증 결과는 내가 직접 검토한다.

<details>
<summary>Codex 적용 범위와 테스트 실행</summary>

전역 규칙과 스킬, 훅은 `~/.claude` 에 한 벌만 둔다. Codex 가 읽는 자리에는 그 원본을 가리키는 링크를 건다. [codex-sync.sh](codex-sync.sh) 가 `~/.codex/AGENTS.md`, `~/.agents/skills/`, `~/.codex/hooks/` 에 링크를 만든다. 사본이 없으니 원본을 고치면 Codex 쪽도 같이 바뀐다.

처음에는 복사했다. 저장소마다 둔 `AGENTS.md` 사본에서 치환이 틀려 `~/.Codex/` 라는 없는 경로를 가리키는 것을 발견하고 링크로 바꿨다.

훅은 자리를 지키고 파일만 링크다. Codex 는 훅 명령 문자열로 신뢰 승인을 잡아서, `hooks.json` 의 경로를 바꾸면 승인이 풀리고 훅이 조용히 멈춘다.

사본으로 남는 것은 둘이다. 훅 등록 파일 `hooks.json` 은 `settings.json` 에서 생성하고, 권한 규칙은 이 저장소의 [codex/claude-deny.rules](codex/claude-deny.rules) 가 원본이다. 이 둘만 Codex 쪽에서 고쳤는지 확인하고, 고친 것이 있으면 바뀔 목록을 보여 주고 멈춘다. 확인한 뒤 `-f` 를 주면 덮는다.

`codex-cross-check` 스킬은 링크하지 않는다. Codex 가 자기 자신에게 교차 검증을 요청하게 된다.

전역 규칙이 링크라 Claude 전용 문장을 뺄 수 없다. 교차 검증과 `doc-skill-guard` 두 줄이 그렇다. `config.toml` 의 `developer_instructions` 에 Codex 에는 해당하지 않는다고 적어 바로잡는다.

`git-guard.py` 는 훅 입력의 셸 명령을 그대로 검사한다. Codex 도 명령을 그대로 넘겨서 처음부터 동작했다. `stop-check.py` 는 대화 기록에서 명령을 꺼내는데, Codex 는 `exec_command({cmd:"…"})` 로 감싸 둔다. `prose-check.py` 와 `memory-note.py` 는 훅 입력의 패치에서 편집한 경로를 꺼내고, Codex 는 그 경로를 `*** Update File:` 줄에 적는다.

| 훅 | Codex |
|---|---|
| `git-guard.py` | 동작한다 |
| `stop-check.py` | 동작한다 |
| `prose-check.py` | 동작한다 |
| `memory-note.py` | 동작한다 |
| `commit-checkpoint.py` | 동작한다 |
| `agent-guard.py` | Claude 의 `Agent` 도구를 검사하는 훅이다 |
| `doc-skill-guard.py` | 등록하지 않는다.<br>Claude 의 스킬 호출 기록에 기대는 훅이다 |

표의 「동작한다」는 실제 Codex 세션을 돌려 확인한 것이다. 테스트만으로는 훅이 불리는지까지 알 수 없다.

Codex 에서는 AGENTS.md 가 문서 작업에 스킬을 먼저 부르라고 지시한다. 누락을 자동으로 막지는 않는다.

되돌리기 어려운 명령은 훅이 아니라 권한 규칙으로 막는다. [codex/claude-deny.rules](codex/claude-deny.rules) 가 `~/.codex/rules/` 로 들어가 `git reset`·`git clean`·`rm -rf` 등 열한 가지를 거절하고, 거절할 때 규칙에 적은 이유를 그대로 보여 준다. 인자를 앞에서부터 맞추는 방식이라 깃발이 올 수 있는 자리를 하나씩 적어야 한다. `git push mirror --force` 처럼 원격 이름이 다른 것은 여전히 못 막는다. 못 막는 것은 규칙 파일 끝에 적었다.

저장소마다 정한 규칙은 사본을 만들지 않는다. `config.toml` 에 `project_doc_fallback_filenames = ["CLAUDE.md"]` 를 두면 Codex 가 그 저장소의 `CLAUDE.md` 를 직접 읽는다. 사본을 두면 원본을 고쳐도 사본은 그대로 남는다. 설정이 빠졌는지는 `codex-sync.sh` 가 확인한다.

테스트는 파일을 하나씩 직접 돌린다. 훅은 `claude/hooks/tests/test_*.py` 여섯 개를 `python3 claude/hooks/tests/test_stop_check.py` 처럼 돌리고, Codex 연결은 `sh tests/codex-sync.test.sh`, 권한 규칙은 `sh tests/codex-rules.test.sh` 다.

</details>

## 공개 파일

규칙 문서와 스킬, 규칙을 검사하는 훅과 테스트, 두 도구가 같은 원본을 보게 하는 스크립트가 들어 있다.

| 파일 | 내용 |
|---|---|
| [claude/CLAUDE.md](claude/CLAUDE.md) | 전역 규칙. 모든 세션에 들어간다 |
| [claude/skills/doc-writing/](claude/skills/doc-writing/SKILL.md) | 문서 작성 규칙. 문서 작업이면 이름을 부르지 않아도 불린다 |
| [claude/skills/codex-cross-check/](claude/skills/codex-cross-check/SKILL.md) | Codex 와 교차 검증하는 절차 |
| [claude/skills/spring-conventions/](claude/skills/spring-conventions/SKILL.md) | Spring·JPA 계층별 코드와 테스트 규칙 |
| [claude/hooks/](claude/hooks/) | 규칙을 검사하는 훅과 그 테스트 |
| [claude/settings.json](claude/settings.json) | 훅 등록과 차단 명령 목록. 네 항목만 발췌한다 |
| [codex/claude-deny.rules](codex/claude-deny.rules) | Codex 가 거절할 명령 목록 |
| [sync.sh](sync.sh) | 로컬 원본을 이 저장소로 복사한다 |
| [codex-sync.sh](codex-sync.sh) | Codex 가 읽는 자리에서 로컬 원본으로 링크를 건다 |

## 공개 범위

- 문서 초안은 AI 가 쓰고 내가 검토한다. 채택한 설계와 변경 내용은 내가 책임지고 커밋과 푸시도 직접 한다.
- 설정은 `permissions`, `hooks`, `enabledPlugins`, `extraKnownMarketplaces` 네 항목만 발췌한다. 인증 정보와 대화 기록, 메모리는 공개하지 않는다.
- 외부에서 가져온 스킬은 이 저장소에 올리지 않고 출처로 연결한다. [mattpocock/skills](https://github.com/mattpocock/skills), IntelliJ 의 `ij-debugger`.
- 회사 업무용 규칙과 사내 저장소 내용은 넣지 않는다.
- 작업 시간이나 결함이 얼마나 줄었는지는 측정하지 않았다. 수치로 제시하지 않는다.
