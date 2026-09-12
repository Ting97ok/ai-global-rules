#!/bin/sh
# 로컬 원본(~/.claude)을 이 저장소로 복사한다. 커밋 전에 돌린다.
# settings.json 은 공개해도 되는 키만 옮긴다. 나중에 토큰 같은 값이 생겨도 올라가지 않는다.
set -eu
cd "$(dirname "$0")"
SRC="$HOME/.claude"
SKILLS="spring-conventions doc-writing codex-cross-check"

mkdir -p claude/hooks claude/skills
cp "$SRC/CLAUDE.md" claude/CLAUDE.md
rsync -a --delete --exclude '__pycache__' "$SRC/hooks/" claude/hooks/
jq '{permissions, hooks, enabledPlugins, extraKnownMarketplaces}' "$SRC/settings.json" > claude/settings.json
for s in $SKILLS; do
  rsync -a --delete "$SRC/skills/$s/" "claude/skills/$s/"
done

git status --short
