#!/bin/sh
# Codex 권한 차단 규칙을 codex execpolicy check 로 확인한다.
# 막아야 할 명령과 통과해야 할 명령을 모두 본다.
set -eu
cd "$(dirname "$0")/.."
RULES="codex/claude-deny.rules"
FAIL=0
ok() { echo "  ok  $1"; }
no() { echo "  NO  $1"; FAIL=1; }

decision() {
  out=$(codex execpolicy check --rules "$RULES" -- "$@" 2>/dev/null) || { echo "확인못함"; return; }
  printf '%s' "$out" | python3 -c "import json,sys
try:
    print(json.load(sys.stdin).get('decision', '없음'))
except Exception:
    print('확인못함')"
}

echo "막아야 하는 것 — 규칙 아홉 개를 하나씩"
for c in "git rebase main" "git push --force origin" "git reset --hard" "git checkout -- a.py" \
         "git restore a.py" "git clean -fd" "git stash drop" "git branch -D old" "rm -rf build"; do
  [ "$(decision $c)" = "forbidden" ] && ok "$c" || no "$c"
done

echo "통과해야 하는 것"
for c in "git status --short" "git commit -m x" "git stash list" "rm a.txt"; do
  [ "$(decision $c)" = "없음" ] && ok "$c" || no "$c"
done

echo "못 막는 것 — 규칙 파일 끝에 적은 한계"
for c in "git push origin --force" "rm -f -r build"; do
  [ "$(decision $c)" = "없음" ] && ok "$c" || no "$c 를 막았다. 한계 설명을 고친다"
done

if [ "$FAIL" = 0 ]; then echo "모두 통과"; else echo "실패 있음"; exit 1; fi
