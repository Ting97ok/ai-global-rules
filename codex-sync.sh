#!/bin/sh
# 로컬 원본(~/.claude)의 전역 규칙·스킬·훅을 Codex 가 읽는 자리로 옮긴다.
# Codex 앱의 가져오기 자동 업데이트(전역 규칙·스킬·훅)는 끄고 이 스크립트로만 옮긴다.
#
# 결과를 임시 폴더에 먼저 만들고, 지금 대상·지난 복사 기록과 비교한 뒤에만 옮긴다.
# 첫 실행이거나 Codex 쪽에서 고친 파일이 있으면 바뀔 파일을 보여 주고 멈춘다. -f 로만 진행한다.
# 부분 반영을 막는 장치는 아니다. 실패를 알아채고 백업에서 손으로 되돌리게 하는 방식이다.
#
# 경로는 테스트에서만 바꾼다. CLAUDE_CONFIG_DIR(원본), CODEX_HOME·AGENTS_SKILLS(대상).
set -eu
SRC="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CODEX="${CODEX_HOME:-$HOME/.codex}"
SKILLS="${AGENTS_SKILLS:-$HOME/.agents/skills}"
STATE="$CODEX/claude-sync.sha256"
RULES="$(dirname "$0")/codex/claude-deny.rules"   # 이 저장소가 원본이다
FORCE=0
[ "${1:-}" = "-f" ] && FORCE=1

# 저장소 규칙은 옮기지 않는다. Codex 가 그 저장소의 CLAUDE.md 를 직접 읽게 두고 설정만 확인한다.
# 이 키가 없으면 저장소가 정한 것이 Codex 에 하나도 안 간다.
grep -q '^[^#]*project_doc_fallback_filenames.*CLAUDE\.md' "$CODEX/config.toml" 2>/dev/null ||
  echo "codex-sync: config.toml 에 project_doc_fallback_filenames = [\"CLAUDE.md\"] 가 없다. 저장소 CLAUDE.md 를 Codex 가 읽지 않는다"

# 전역 규칙이 링크라 Claude 전용 줄을 뺄 수 없다. Codex 쪽에서 그 두 줄을 바로잡는다.
grep -q '^[^#]*developer_instructions' "$CODEX/config.toml" 2>/dev/null ||
  echo "codex-sync: config.toml 에 developer_instructions 가 없다. 교차 검증과 doc-skill-guard 는 Claude 전용인데 전역 규칙에 그대로 남아 있다"

# Codex 에 옮기지 않는 스킬. Codex 가 자기 자신과 교차 검증하게 된다
NOT_SKILLS="codex-cross-check"
# Codex 에 붙이지 않는 훅. Claude 의 Skill 도구 호출을 찾는 훅이라
# Codex 에서는 하는 일 없이 신뢰 승인만 요구한다
NOT_HOOKS="doc-skill-guard.py"
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
STAGE="$T/stage"
mkdir -p "$STAGE/codex/rules"

# 1. 전역 규칙은 링크다. 사본이 없으니 원본과 어긋날 수 없다.
#    링크는 덮어써도 잃을 것이 없어 비교 대상에서 뺀다.
mkdir -p "$CODEX"
ln -sfn "$SRC/CLAUDE.md" "$CODEX/AGENTS.md"

# 2. 스킬은 이름을 바꾸지 않고 폴더째 옮긴다. 가져오기가 넣은 치환이 틀린 문장을 만들었고,
#    저장소 규칙의 원본은 그 저장소의 CLAUDE.md 라 Codex 가 그 파일을 읽어도 된다.
#    Codex 에만 있는 폴더(find-skills, source-command-*)는 목록에 없어서 건드리지 않는다.
mkdir -p "$SKILLS"
for d in "$SRC"/skills/*/; do
  s=$(basename "$d")
  case " $NOT_SKILLS " in *" $s "*) continue ;; esac
  rm -rf "${SKILLS:?}/$s"          # 예전 사본이 있으면 그 안에 링크가 생긴다
  ln -sfn "${d%/}" "$SKILLS/$s"
done
# 원본에서 사라진 스킬은 끊어진 링크로 남는다. 그것만 치운다
for l in "$SKILLS"/*; do
  [ -L "$l" ] && [ ! -e "$l" ] && rm -f "$l"
done

# 3. 훅은 사본을 두지 않는다. hooks.json 이 원본 경로를 그대로 가리킨다.
#    등록만 settings.json 에서 만들고 이벤트 순서는 지금 hooks.json 과 같게 둔다.
# 4. 권한 차단 규칙. settings.json 의 deny 에 해당하는 것을 손으로 옮겨 둔 파일이다
[ -f "$RULES" ] && cp "$RULES" "$STAGE/codex/rules/"

jq --arg dir "$SRC/hooks/" --arg q "'" --arg not "$NOT_HOOKS" '
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
  | {hooks: .}' "$SRC/settings.json" > "$STAGE/codex/hooks.json"

# 4. 새로 만든 것 / 지금 대상 / 지난 복사 기록을 비교한다
sums() {  # sums <codex 뿌리>
  c=$1
  # rules 는 폴더가 아니라 우리가 옮기는 파일 하나만 본다. 손으로 넣은 규칙까지 감시하면 매번 걸린다
  for f in hooks.json rules/claude-deny.rules; do
    [ -e "$c/$f" ] || continue
    (cd "$c" && find "$f" -type f ! -path '*/__pycache__/*' -exec shasum -a 256 {} +) |
      sed 's|  |  codex/|'
  done
}
changed() { diff "$1" "$2" | sed -n 's/^[<>] [0-9a-f]*  //p' | sort -u; }

sums "$STAGE/codex" | sort -k2 > "$T/new.sha256"
sums "$CODEX" | sort -k2 > "$T/now.sha256"

if cmp -s "$T/new.sha256" "$T/now.sha256"; then
  echo "codex-sync: Codex 쪽이 이미 원본과 같다"
  exit 0
fi
if [ ! -f "$STATE" ]; then
  echo "codex-sync: 첫 실행이다. 덮으면 바뀌는 파일:"
  changed "$T/now.sha256" "$T/new.sha256"
  [ "$FORCE" = 1 ] || { echo "codex-sync: 확인했으면 -f 로 다시 돌린다" >&2; exit 1; }
elif ! cmp -s "$STATE" "$T/now.sha256"; then
  echo "codex-sync: 지난 복사 뒤 Codex 쪽에서 바뀐 파일:"
  changed "$STATE" "$T/now.sha256"
  [ "$FORCE" = 1 ] || {
    echo "codex-sync: 살릴 것은 원본에 옮기고, 확인했으면 -f 로 다시 돌린다" >&2
    exit 1
  }
fi

# 5. 백업하고 옮긴다. 해시 기록은 모두 끝난 뒤에 쓴다
B="$CODEX/claude-sync-backup/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$B/codex"
for f in hooks.json rules; do
  [ -e "$CODEX/$f" ] && cp -R "$CODEX/$f" "$B/codex/" || true
done

cp "$STAGE/codex/hooks.json" "$CODEX/"
mkdir -p "$CODEX/rules"
rsync -a "$STAGE/codex/rules/" "$CODEX/rules/"

cp "$T/new.sha256" "$STATE"
echo "codex-sync: 옮겼다. 이전 상태는 $B 에 있다"
