#!/bin/sh
# 로컬 원본(~/.claude)의 전역 규칙을 Codex 가 읽는 자리로 옮긴다.
# Codex 앱의 가져오기 자동 업데이트(전역 규칙·스킬·훅)는 끄고 이 스크립트로만 옮긴다.
#
# 경로는 테스트에서만 바꾼다. CLAUDE_CONFIG_DIR(원본), CODEX_HOME(대상).
set -eu
SRC="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CODEX="${CODEX_HOME:-$HOME/.codex}"

# Claude 에만 맞는 줄의 첫머리. 원본에서 한 번씩만 걸려야 한다.
# 규칙 문장이 바뀌면 여기서 멈춘다. 조용히 새는 것보다 낫다.
DROP='- **교차 검증**:
문서 파일을 쓰기 전에 스킬을 불렀는지는 훅(`doc-skill-guard.py`)이 확인한다.'

T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT

DROP="$DROP" awk '
  BEGIN { n = split(ENVIRON["DROP"], p, "\n") }
  { for (i = 1; i <= n; i++) if (index($0, p[i]) == 1) { c[i]++; next } print }
  END {
    for (i = 1; i <= n; i++)
      if (c[i] != 1) {
        printf "codex-sync: 뺄 줄이 %d번 걸린다: %s\n", c[i], p[i] > "/dev/stderr"
        bad = 1
      }
    exit bad
  }' "$SRC/CLAUDE.md" > "$T/rules.md"

mkdir -p "$CODEX"
sed -e 's/CLAUDE\.md/AGENTS.md/g' -e 's/Claude Code/Codex/g' -e 's/Claude/Codex/g' \
  "$T/rules.md" > "$CODEX/AGENTS.md"
