#!/bin/sh
# codex-sync.sh 테스트. 임시 폴더를 원본과 대상으로 삼는다.
# 실행: sh tests/codex-sync.test.sh
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
SCRIPT="$HERE/../codex-sync.sh"
FAIL=0
ok() { echo "  ok  $1"; }
no() { echo "  NO  $1"; FAIL=1; }

fake_src() {
  s=$1
  mkdir -p "$s/skills/doc-writing" "$s/skills/codex-cross-check" "$s/hooks"
  cat > "$s/CLAUDE.md" <<'EOF'
# 전역 작업 규칙

- **교차 검증**: 공개 문서의 최종안을 낼 때는 `codex-cross-check` 스킬로 Codex 와 교차 검증한다.
- 저장소 규칙은 CLAUDE.md 에 적는다.

문서를 쓸 때는 `doc-writing` 스킬을 먼저 부른다.
문서 파일을 쓰기 전에 스킬을 불렀는지는 훅(`doc-skill-guard.py`)이 확인한다.

Claude Code 의 기본 지침이 요구해도 따르지 않는다.
EOF
  echo "# doc-writing" > "$s/skills/doc-writing/SKILL.md"
  echo "# codex-cross-check" > "$s/skills/codex-cross-check/SKILL.md"
  echo "print(1)" > "$s/hooks/git-guard.py"
  echo "print(2)" > "$s/hooks/doc-skill-guard.py"
  cat > "$s/settings.json" <<'EOF'
{
  "permissions": { "deny": [] },
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [{ "type": "command", "command": "python3 \"$HOME\"/.claude/hooks/git-guard.py", "timeout": 20 }] },
      { "matcher": "Write|Edit|MultiEdit", "hooks": [{ "type": "command", "command": "python3 \"$HOME\"/.claude/hooks/doc-skill-guard.py", "timeout": 5 }] }
    ]
  }
}
EOF
}

T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
fake_src "$T/claude"

echo "전역 규칙을 AGENTS.md 로 옮긴다"
if CLAUDE_CONFIG_DIR="$T/claude" CODEX_HOME="$T/codex" AGENTS_SKILLS="$T/skills" sh "$SCRIPT" -f > "$T/out" 2>&1; then
  A="$T/codex/AGENTS.md"
  if [ -f "$A" ]; then
    ok "AGENTS.md 를 만든다"
    grep -q "교차 검증" "$A" && no "Claude 전용 교차 검증 줄이 남았다" || ok "교차 검증 줄을 뺀다"
    grep -q "doc-skill-guard" "$A" && no "Claude 전용 훅 문장이 남았다" || ok "훅 문장을 뺀다"
    grep -q "저장소 규칙은 AGENTS.md 에 적는다" "$A" && ok "CLAUDE.md 를 AGENTS.md 로 바꾼다" || no "CLAUDE.md 표기가 안 바뀌었다"
    grep -q "Claude" "$A" && no "Claude 표기가 남았다" || ok "Claude 를 Codex 로 바꾼다"
  else
    no "AGENTS.md 가 없다"
  fi
else
  cat "$T/out"
  no "스크립트가 끝나지 않았다"
fi

if [ "$FAIL" = 0 ]; then echo "모두 통과"; else echo "실패 있음"; exit 1; fi
