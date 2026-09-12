#!/bin/sh
# 로컬 원본(~/.claude)의 전역 규칙을 Codex 가 읽는 자리로 옮긴다.
# Codex 앱의 가져오기 자동 업데이트(전역 규칙·스킬·훅)는 끄고 이 스크립트로만 옮긴다.
#
# 경로는 테스트에서만 바꾼다. CLAUDE_CONFIG_DIR(원본), CODEX_HOME·AGENTS_SKILLS(대상).
set -eu
SRC="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CODEX="${CODEX_HOME:-$HOME/.codex}"
SKILLS="${AGENTS_SKILLS:-$HOME/.agents/skills}"

# Codex 에 옮기지 않는 스킬. Codex 가 자기 자신과 교차 검증하게 된다
NOT_SKILLS="codex-cross-check"

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

# 스킬은 이름을 바꾸지 않고 폴더째 옮긴다. 가져오기가 넣은 치환이 틀린 문장을 만들었고,
# 저장소 규칙의 원본은 그 저장소의 CLAUDE.md 라 Codex 가 그 파일을 읽어도 된다.
# Codex 에만 있는 폴더(find-skills, source-command-*)는 목록에 없어서 건드리지 않는다.
mkdir -p "$SKILLS"
for d in "$SRC"/skills/*/; do
  s=$(basename "$d")
  case " $NOT_SKILLS " in *" $s "*) continue ;; esac
  rsync -a --delete --exclude __pycache__ "$d" "$SKILLS/$s/"
done

# 훅은 스크립트를 옮기고 등록은 settings.json 에서 만든다.
# doc-skill-guard 는 Codex 에 붙이지 않는다. Claude 의 Skill 도구 호출을 찾는 훅이라
# Codex 에서는 하는 일 없이 신뢰 승인만 요구한다.
NOT_HOOKS="doc-skill-guard.py"
mkdir -p "$CODEX/hooks"
rsync -a --delete --exclude __pycache__ --exclude tests "$SRC/hooks/" "$CODEX/hooks/"
for h in $NOT_HOOKS; do rm -f "$CODEX/hooks/$h"; done

# 이벤트 순서와 명령 꼴을 지금 hooks.json 과 같게 둔다. 훅 신뢰 승인이 그대로 유지된다.
jq --arg dir "$CODEX/hooks/" --arg q "'" --arg not "$NOT_HOOKS" '
  def pat: "^python3 \"\\$HOME\"/\\.claude/hooks/(?<f>[^/]+)$";
  ($not | split(" ") | map(select(length > 0))) as $not
  | .hooks as $h
  | ({PreToolUse: $h.PreToolUse, PostToolUse: $h.PostToolUse, Stop: $h.Stop} + $h)
  | with_entries(select(.value != null))
  | map_values(map(.hooks |= map(select(.command as $c | all($not[]; . as $n | $c | contains($n) | not))))
               | map(select(.hooks | length > 0)))
  | with_entries(select(.value | length > 0))
  | walk(if type == "object" and has("command") then
           if (.command | test(pat)) then .command |= sub(pat; "python3 \($q)\($dir)\(.f)\($q)")
           else error("codex-sync: 모르는 훅 명령 형식 \(.command)") end
         else . end)
  | {hooks: .}' "$SRC/settings.json" > "$CODEX/hooks.json"
