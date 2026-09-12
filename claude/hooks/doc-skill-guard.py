#!/usr/bin/env python3
"""PreToolUse(Write|Edit|MultiEdit) — 문서를 쓰기 전에 doc-writing 스킬을 불렀는지 확인한다.

전역 규칙 「문서 작성」이 스킬을 먼저 부르라고 한다. 그 호출이 대화 기록에 있는지만 본다.
종료 코드 2 + stderr 가 차단이다.
"""
import json
import sys

SKILL = "doc-writing"


def called(transcript_path):
    """대화 기록에 doc-writing 스킬 호출이 있는지 본다."""
    try:
        rows = open(transcript_path, encoding="utf-8")
    except OSError:
        return False
    with rows:
        for line in rows:
            try:
                row = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if row.get("type") != "assistant":
                continue
            for block in (row.get("message") or {}).get("content") or []:
                if (isinstance(block, dict)
                        and block.get("type") == "tool_use"
                        and block.get("name") == "Skill"
                        and (block.get("input") or {}).get("skill") == SKILL):
                    return True
    return False


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    if called(payload.get("transcript_path", "")):
        return
    print(f"[doc-skill-guard] 문서를 쓰기 전에 `{SKILL}` 스킬을 불러 전체 규칙을 따른다.",
          file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
