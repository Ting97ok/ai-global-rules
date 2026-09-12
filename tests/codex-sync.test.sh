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

echo "전역 규칙을 링크로 둔다"
if CLAUDE_CONFIG_DIR="$T/claude" CODEX_HOME="$T/codex" AGENTS_SKILLS="$T/skills" sh "$SCRIPT" -f > "$T/out" 2>&1; then
  A="$T/codex/AGENTS.md"
  if [ -L "$A" ]; then
    ok "AGENTS.md 가 링크다"
    [ "$(readlink "$A")" = "$T/claude/CLAUDE.md" ] && ok "원본을 가리킨다" || no "원본을 안 가리킨다"
    printf '나중에 더한 줄\n' >> "$T/claude/CLAUDE.md"
    grep -q "나중에 더한 줄" "$A" && ok "원본을 고치면 그대로 보인다" || no "원본 수정이 안 보인다"
  else
    no "AGENTS.md 가 링크가 아니다"
  fi
else
  cat "$T/out"
  no "스크립트가 끝나지 않았다"
fi

echo "스킬을 링크로 둔다"
S="$T/skills"
[ -L "$S/doc-writing" ] && ok "doc-writing 이 링크다" || no "doc-writing 이 링크가 아니다"
[ "$(readlink "$S/doc-writing")" = "$T/claude/skills/doc-writing" ] && ok "원본 폴더를 가리킨다" || no "원본 폴더를 안 가리킨다"
[ -e "$S/codex-cross-check" ] && no "codex-cross-check 를 옮겼다" || ok "codex-cross-check 는 옮기지 않는다"
[ -f "$S/find-skills/SKILL.md" ] && ok "Codex 에만 있는 스킬은 그대로 둔다" || no "Codex 에만 있는 스킬이 사라졌다"

echo "훅은 원본을 그대로 가리킨다"
[ -d "$T/codex/hooks" ] && no "훅 사본을 만들었다" || ok "훅 사본을 만들지 않는다"
J="$T/codex/hooks.json"
if [ -f "$J" ]; then
  ok "hooks.json 을 만든다"
  grep -q "'$T/claude/hooks/git-guard.py'" "$J" && ok "원본 경로를 가리킨다" || no "원본 경로가 아니다"
  grep -q "doc-skill-guard" "$J" && no "hooks.json 에 doc-skill-guard 가 남았다" || ok "hooks.json 에서 doc-skill-guard 를 뺀다"
else
  no "hooks.json 이 없다"
fi

echo "스킬은 링크라 고치면 원본이 바뀐다"
echo "# Codex 쪽에서 고쳤다" >> "$S/doc-writing/SKILL.md"
grep -q "Codex 쪽에서 고쳤다" "$T/claude/skills/doc-writing/SKILL.md" \
  && ok "원본이 같이 바뀐다" || no "원본이 안 바뀌었다"

echo "사본으로 남는 것은 Codex 쪽 수정을 덮지 않는다"
echo "# 손으로 고쳤다" >> "$T/codex/rules/claude-deny.rules"
if CLAUDE_CONFIG_DIR="$T/claude" CODEX_HOME="$T/codex" AGENTS_SKILLS="$T/skills" \
   sh "$SCRIPT" > "$T/out2" 2>&1; then
  no "-f 없이 덮었다"
else
  ok "덮지 않고 멈춘다"
  grep -q "claude-deny" "$T/out2" && ok "바뀐 파일을 알려 준다" || no "바뀐 파일을 알려 주지 않는다"
  grep -q "손으로 고쳤다" "$T/codex/rules/claude-deny.rules" \
    && ok "Codex 쪽 수정이 그대로 있다" || no "Codex 쪽 수정이 사라졌다"
fi

echo "권한 규칙을 옮긴다"
R="$T/codex/rules/claude-deny.rules"
[ -f "$R" ] && ok "claude-deny.rules 를 옮긴다" || no "권한 규칙이 없다"
grep -q 'prefix_rule' "$R" 2>/dev/null && ok "규칙 내용이 그대로다" || no "규칙 내용이 비었다"

echo "저장소 규칙을 읽는 설정을 확인한다"
grep -q 'project_doc_fallback_filenames' "$T/out" && ok "설정이 없으면 알려 준다" || no "설정 안내가 없다"
printf 'project_doc_fallback_filenames = ["CLAUDE.md"]\n' > "$T/codex/config.toml"
if CLAUDE_CONFIG_DIR="$T/claude" CODEX_HOME="$T/codex" AGENTS_SKILLS="$T/skills" \
   sh "$SCRIPT" -f > "$T/out3" 2>&1; then
  grep -q 'project_doc_fallback_filenames' "$T/out3" && no "설정이 있는데도 알려 준다" || ok "설정이 있으면 잠잠하다"
else
  cat "$T/out3"
  no "설정을 넣은 뒤 스크립트가 끝나지 않았다"
fi
printf '# project_doc_fallback_filenames = ["CLAUDE.md"]\n' > "$T/codex/config.toml"
CLAUDE_CONFIG_DIR="$T/claude" CODEX_HOME="$T/codex" AGENTS_SKILLS="$T/skills" \
  sh "$SCRIPT" -f > "$T/out4" 2>&1 || true
grep -q 'project_doc_fallback_filenames' "$T/out4" && ok "주석 처리된 설정은 없는 것으로 본다" || no "주석을 설정으로 셌다"

echo "Claude 전용 규칙을 바로잡는 설정을 확인한다"
grep -q 'developer_instructions' "$T/out" && ok "설정이 없으면 알려 준다" || no "설정 안내가 없다"
printf 'developer_instructions = "교차 검증과 doc-skill-guard 는 Claude 전용이다"\n' >> "$T/codex/config.toml"
CLAUDE_CONFIG_DIR="$T/claude" CODEX_HOME="$T/codex" AGENTS_SKILLS="$T/skills" \
  sh "$SCRIPT" -f > "$T/out5" 2>&1 || true
grep -q 'developer_instructions' "$T/out5" && no "설정이 있는데도 알려 준다" || ok "설정이 있으면 잠잠하다"

if [ "$FAIL" = 0 ]; then echo "모두 통과"; else echo "실패 있음"; exit 1; fi
