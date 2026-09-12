# AI 전역 작업 규칙

Claude Code 와 Codex 를 쓰며 정한 개인 작업 규칙과, 그 규칙이 실제로 돌아간 공개 기록을 모았다.

## [회고 읽기: AI와 일하며 가장 많이 고친 건 문서였다](https://ting97ok.github.io/ai-global-rules/) · 약 8분

- **원칙**: AI 가 세운 구현 계획을 온전히 이해한 뒤에 구현을 시작한다.
- **문제**: 계획 문서를 읽는 일이 병목이어서 문서 형식과 작성 규칙을 계속 바꿨다.
- **한계**: 읽는 부담은 줄었다고 느끼지만 되묻는 일은 늘었고 효과를 수치로 재지는 못했다.

## 검증 기록

| 규칙 | 공개 기록 |
|---|---|
| 테스트 하나와 구현 하나를 번갈아 커밋한다 | `hotdeal-commerce` [82a62aa](https://github.com/Ting97ok/hotdeal-commerce/commit/82a62aaf5ecbe69c62ccef263f0d05f2326b6aac) → [78982d6](https://github.com/Ting97ok/hotdeal-commerce/commit/78982d6912fff9c3fa9ee1e7f9ad643d5741c8a1) |
| 작업 단위가 끝나면 앱을 띄워 밖에서 호출한다 | `hotdeal-commerce` [PR #6](https://github.com/Ting97ok/hotdeal-commerce/pull/6) 본문의 「인수 확인」 |

두 커밋은 `confirm` 응답에서 결제 완료(`DONE`)와 결과 미확정(`IN_DOUBT`)을 구분한 변경이다. 테스트가 단언을 먼저 잡고 구현이 `ConfirmPaymentResponse` 에 `status` 필드를 더했다.

리뷰로 방향이 바뀌면 댓글을 먼저 남기고 커밋한다는 규칙은 아직 공개 사례로 제시하지 못했다.

이 저장소 자체의 검사도 공개한다. [훅 테스트](claude/hooks/tests/)와 [Codex 복사 테스트](tests/codex-sync.test.sh)가 문서 작성 스킬 호출 누락, 테스트가 실패한 상태의 커밋 명령, Codex 쪽 수정 덮어쓰기를 검사한다.

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

원본은 `~/.claude` 한 곳이다. [codex-sync.sh](codex-sync.sh) 가 전역 규칙에서 Claude 에만 맞는 줄을 빼고 이름을 바꿔 `~/.codex/AGENTS.md` 로 만들고, 스킬은 이름을 바꾸지 않고 폴더째 옮긴다. 옮기기 전에 지금 상태를 백업하고, Codex 쪽에서 따로 고친 파일이 있으면 덮지 않고 멈춘다.

`codex-cross-check` 스킬은 옮기지 않는다. Codex 가 자기 자신에게 교차 검증을 요청하게 된다.

| 훅 | Codex |
|---|---|
| `git-guard.py` | 동작한다 |
| `commit-checkpoint.py` | 확인하지 않았다 |
| `stop-check.py` | 기록 형식이 달라 검사하지 못한다 |
| `prose-check.py` | 입력 형식이 달라 검사하지 못한다 |
| `memory-note.py` | 입력 형식이 달라 검사하지 못한다 |
| `agent-guard.py` | 해당 도구가 없다 |
| `doc-skill-guard.py` | 등록하지 않는다. Claude 의 스킬 호출 기록에 기대는 훅이다 |

Codex 에서는 AGENTS.md 가 문서 작업에 스킬을 먼저 부르라고 지시한다. 누락을 자동으로 막지는 않는다.

훅 테스트는 `python3 claude/hooks/tests/test_stop_check.py` 처럼 파일을 직접 돌린다. Codex 복사 테스트는 `sh tests/codex-sync.test.sh` 다.

</details>

## 공개 파일

규칙 문서와 스킬, 규칙을 검사하는 훅과 테스트, 두 도구로 옮기는 복사 스크립트가 들어 있다.

| 파일 | 내용 |
|---|---|
| [claude/CLAUDE.md](claude/CLAUDE.md) | 전역 규칙. 모든 세션에 들어간다 |
| [claude/skills/doc-writing/](claude/skills/doc-writing/SKILL.md) | 문서 작성 규칙. 문서 작업이면 이름을 부르지 않아도 불린다 |
| [claude/skills/codex-cross-check/](claude/skills/codex-cross-check/SKILL.md) | Codex 와 교차 검증하는 절차 |
| [claude/skills/spring-conventions/](claude/skills/spring-conventions/SKILL.md) | Spring·JPA 계층별 코드와 테스트 규칙 |
| [claude/hooks/](claude/hooks/) | 규칙을 검사하는 훅과 그 테스트 |
| [claude/settings.json](claude/settings.json) | 훅 등록과 차단 명령 목록. 네 항목만 발췌한다 |
| [sync.sh](sync.sh) | 로컬 원본을 이 저장소로 복사한다 |
| [codex-sync.sh](codex-sync.sh) | 로컬 원본을 Codex 가 읽는 자리로 옮긴다 |

## 공개 범위

- 문서 초안은 AI 가 쓰고 내가 검토한다. 채택한 설계와 변경 내용은 내가 책임지고 커밋과 푸시도 직접 한다.
- 설정은 `permissions`, `hooks`, `enabledPlugins`, `extraKnownMarketplaces` 네 항목만 발췌한다. 인증 정보와 대화 기록, 메모리는 공개하지 않는다.
- 외부에서 가져온 스킬은 이 저장소에 올리지 않고 출처로 연결한다. [mattpocock/skills](https://github.com/mattpocock/skills), IntelliJ 의 `ij-debugger`.
- 회사 업무용 규칙과 사내 저장소 내용은 넣지 않는다.
- 작업 시간이나 결함이 얼마나 줄었는지는 측정하지 않았다. 수치로 제시하지 않는다.
