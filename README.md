# AI 전역 작업 규칙

Claude Code 와 Codex 가 모든 저장소에서 따르는 작업 규칙이다. 규칙 문서와, 그 규칙을 도구 실행 전후에 검사하는 훅(hook) 스크립트가 들어 있다.

| 파일 | 내용 | 위치 |
|---|---|---|
| `claude/CLAUDE.md` | 전역 규칙. 모든 세션에 들어간다 | `~/.claude/CLAUDE.md` |
| `claude/hooks/` | 규칙을 검사하는 훅 | `~/.claude/hooks/` |
| `claude/settings.json` | 훅 연결과 차단 명령 목록(발췌) | `~/.claude/settings.json` |
| `claude/skills/spring-conventions/` | Spring·JPA 코드 규칙 | `~/.claude/skills/` |
| `sync.sh` | 로컬 파일을 이 저장소로 복사한다 | |
