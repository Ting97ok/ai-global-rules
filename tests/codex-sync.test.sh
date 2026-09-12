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
# Codex 에만 있는 스킬. 복사 뒤에도 그대로 있어야 한다
mkdir -p "$T/skills/find-skills" && echo "# find-skills" > "$T/skills/find-skills/SKILL.md"

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

echo "스킬을 옮긴다"
S="$T/skills"
[ -f "$S/doc-writing/SKILL.md" ] && ok "doc-writing 을 옮긴다" || no "doc-writing 이 없다"
[ -d "$S/codex-cross-check" ] && no "codex-cross-check 를 옮겼다" || ok "codex-cross-check 는 옮기지 않는다"
[ -f "$S/find-skills/SKILL.md" ] && ok "Codex 에만 있는 스킬은 그대로 둔다" || no "Codex 에만 있는 스킬이 사라졌다"

echo "훅을 옮긴다"
H="$T/codex/hooks"
[ -f "$H/git-guard.py" ] && ok "훅 스크립트를 옮긴다" || no "git-guard.py 가 없다"
[ -f "$H/doc-skill-guard.py" ] && no "doc-skill-guard.py 를 옮겼다" || ok "doc-skill-guard 는 옮기지 않는다"
J="$T/codex/hooks.json"
if [ -f "$J" ]; then
  ok "hooks.json 을 만든다"
  grep -q "'$H/git-guard.py'" "$J" && ok "훅 경로를 Codex 자리로 바꾼다" || no "훅 경로가 Codex 자리가 아니다"
  grep -q "doc-skill-guard" "$J" && no "hooks.json 에 doc-skill-guard 가 남았다" || ok "hooks.json 에서 doc-skill-guard 를 뺀다"
else
  no "hooks.json 이 없다"
fi

echo "Codex 쪽에서 고친 파일은 덮지 않는다"
echo "# Codex 쪽에서 고쳤다" >> "$S/doc-writing/SKILL.md"
if CLAUDE_CONFIG_DIR="$T/claude" CODEX_HOME="$T/codex" AGENTS_SKILLS="$T/skills" \
   sh "$SCRIPT" > "$T/out2" 2>&1; then
  no "-f 없이 덮었다"
else
  ok "덮지 않고 멈춘다"
  grep -q "doc-writing" "$T/out2" && ok "바뀐 파일을 알려 준다" || no "바뀐 파일을 알려 주지 않는다"
  grep -q "Codex 쪽에서 고쳤다" "$S/doc-writing/SKILL.md" \
    && ok "Codex 쪽 수정이 그대로 있다" || no "Codex 쪽 수정이 사라졌다"
fi

if [ "$FAIL" = 0 ]; then echo "모두 통과"; else echo "실패 있음"; exit 1; fi
