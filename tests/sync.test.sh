#!/bin/sh
# sync.sh 테스트. 임시 폴더를 원본(HOME/.claude)과 대상 저장소로 삼는다.
# 실행: sh tests/sync.test.sh
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
FAIL=0
ok() { echo "  ok  $1"; }
no() { echo "  NO  $1"; FAIL=1; }

T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
C="$T/home/.claude"
for d in hooks/__pycache__ skills/spring-conventions skills/doc-writing skills/codex-cross-check/__pycache__; do
  mkdir -p "$C/$d"
done
echo "# 전역 작업 규칙" > "$C/CLAUDE.md"
echo "print(1)" > "$C/hooks/git-guard.py"
echo "cache" > "$C/hooks/__pycache__/git-guard.cpython-314.pyc"
for s in spring-conventions doc-writing codex-cross-check; do echo "# $s" > "$C/skills/$s/SKILL.md"; done
echo "cache" > "$C/skills/codex-cross-check/__pycache__/usage.cpython-314.pyc"
echo '{"permissions": {}, "hooks": {}, "enabledPlugins": {}, "extraKnownMarketplaces": {}}' > "$C/settings.json"

# sync.sh 는 자기 폴더를 저장소로 보고 복사한다. 임시 저장소에 복사해 실행한다
R="$T/repo"
mkdir -p "$R" && cp "$HERE/../sync.sh" "$R/" && git -C "$R" init -q

echo "원본을 저장소로 복사한다"
if HOME="$T/home" sh "$R/sync.sh" > "$T/out" 2>&1; then
  [ -f "$R/claude/hooks/git-guard.py" ] && ok "훅을 복사한다" || no "훅을 복사하지 않았다"
  [ -f "$R/claude/skills/codex-cross-check/SKILL.md" ] && ok "스킬을 복사한다" || no "스킬을 복사하지 않았다"
else
  cat "$T/out"
  no "스크립트가 끝나지 않았다"
fi

echo "파이썬 캐시 폴더는 복사하지 않는다"
[ -e "$R/claude/hooks/__pycache__" ] && no "훅의 캐시 폴더를 복사했다" || ok "훅의 캐시 폴더는 복사하지 않는다"
[ -e "$R/claude/skills/codex-cross-check/__pycache__" ] && no "스킬의 캐시 폴더를 복사했다" || ok "스킬의 캐시 폴더는 복사하지 않는다"

if [ "$FAIL" = 0 ]; then echo "모두 통과"; else echo "실패 있음"; exit 1; fi
