#!/usr/bin/env python3
"""Stop — 답변을 끝내기 전에 마지막 답변의 bash 블록을 검사한다. ~/.claude/CLAUDE.md 「작업 성향 · 보여주기와 명령」.

막는 것 (decision: block 으로 되돌려 답변을 고치게 한다):
  1. 사용자에게 시키는 조회 명령. cat·less·head·tail·sed -n·grep 만으로 된 블록.
     봐야 할 내용은 답변에 직접 싣는다.
  2. 커밋·푸시·PR 명령(git add/commit/push, gh pr create/edit/ready/merge/comment)을 주면서
     이번 턴에 상태 확인(git status / git log / git diff / git branch / gh pr view|list)을 실제로 돌리지 않은 것.
이미 이 훅으로 되돌아온 턴(stop_hook_active)은 다시 막지 않는다. 무한 루프 방지.
"""
import json
import re
import sys

VIEW_ONLY = re.compile(r"^\s*(cat|less|more|head|tail|bat)\s|^\s*sed\s+-n\s|^\s*grep\s")
GIT_ACTION = re.compile(r"\bgit\s+(add|commit|push)\b|\bgh\s+pr\s+(create|edit|ready|merge|comment)\b")
STATE_CHECK = re.compile(r"\bgit\s+(status|log|diff|branch|rev-parse)\b|\bgh\s+pr\s+(view|list|status)\b")


def load_transcript(path):
    rows = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows


def content_blocks(row):
    msg = row.get("message") or {}
    c = msg.get("content")
    if isinstance(c, str):
        return [{"type": "text", "text": c}]
    return c if isinstance(c, list) else []


def is_human_turn(row):
    if row.get("type") != "user":
        return False
    blocks = content_blocks(row)
    return any(b.get("type") == "text" and b.get("text", "").strip() for b in blocks) \
        and not any(b.get("type") == "tool_result" for b in blocks)


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    if payload.get("stop_hook_active"):
        return
    rows = load_transcript(payload.get("transcript_path", ""))
    if not rows:
        return

    # 마지막 사람 발화 이후의 턴만 본다
    start = 0
    for i, r in enumerate(rows):
        if is_human_turn(r):
            start = i
    turn = rows[start + 1:]

    ran_commands, last_text = [], ""
    for r in turn:
        if r.get("type") != "assistant":
            continue
        texts = []
        for b in content_blocks(r):
            if b.get("type") == "tool_use" and b.get("name") == "Bash":
                ran_commands.append((b.get("input") or {}).get("command", "") or "")
            elif b.get("type") == "text":
                texts.append(b.get("text", ""))
        if texts:
            last_text = "\n".join(texts)

    blocks = re.findall(r"```(?:bash|sh|zsh|shell)\s*\n(.*?)```", last_text, re.S)
    if not blocks:
        return

    problems = []
    for b in blocks:
        first = b.strip().split("\n", 1)[0]
        # 앞의 cd … && 는 건너뛰고 실제 명령을 본다
        core = re.sub(r"^\s*cd\s+\S+\s*&&\s*", "", first)
        if VIEW_ONLY.match(core) and not GIT_ACTION.search(b):
            problems.append("조회 명령을 사용자에게 시키지 않는다. 그 내용을 답변에 직접 싣는다: " + core[:60])
    if any(GIT_ACTION.search(b) for b in blocks):
        if not any(STATE_CHECK.search(c) for c in ran_commands):
            problems.append("커밋·푸시·PR 명령을 주기 전에 이번 턴에서 상태를 확인한다 (git status / git log / gh pr view). "
                            "확인을 실제로 돌리고, 그 결과에 맞춰 명령을 다시 낸다")
    if problems:
        print(json.dumps({"decision": "block",
                          "reason": "[stop-check] " + " / ".join(problems)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
