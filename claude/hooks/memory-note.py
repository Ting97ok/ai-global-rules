#!/usr/bin/env python3
"""PostToolUse(Write|Edit) — 메모리 디렉터리에 썼을 때 기록 위치 규칙을 되새긴다. 막지 않는다.

~/.claude/CLAUDE.md 「작업 성향 · 기록 위치」: 전역 규칙 → 저장소 규칙 → 메모리 순서.
이번 작업에서만 쓰고 끝날 것만 메모리에 둔다.
"""
import json
import sys


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    path = ((payload.get("tool_input") or {}).get("file_path") or "").replace("\\", "/")
    if "/.claude/projects/" in path and "/memory/" in path:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
              "additionalContext": "[기록 위치] 메모리에 적었다. 다른 저장소에서도 같은 판단을 할 내용이면 전역 CLAUDE.md, "
                                   "이 저장소의 사실·결정이면 저장소 문서가 먼저다. 이번 작업에서만 쓰는 것인지 한 번 본다."}},
              ensure_ascii=False))


if __name__ == "__main__":
    main()
