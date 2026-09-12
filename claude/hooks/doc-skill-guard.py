#!/usr/bin/env python3
"""PreToolUse(Write|Edit|MultiEdit) — 문서를 쓰기 전에 doc-writing 스킬을 불렀는지 확인한다.

전역 규칙 「문서 작성」이 스킬을 먼저 부르라고 한다. 그 호출이 대화 기록에 있는지만 본다.
종료 코드 2 + stderr 가 차단이다.
"""
import json
import os
import sys

SKILL = "doc-writing"


def target(path):
    """문서 파일인지 본다. prose-check 와 같은 대상이다."""
    if not path:
        return False
    p = path.replace("\\", "/")
    if os.path.basename(p) == "README.md":
        return True
    return "/docs/" in p and p.endswith((".md", ".html"))


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
    path = (payload.get("tool_input") or {}).get("file_path", "")
    if not target(path):
        return
    if called(payload.get("transcript_path", "")):
        return
    print(f"[doc-skill-guard] 문서를 쓰기 전에 `{SKILL}` 스킬을 불러 전체 규칙을 따른다. "
          f"대상 파일: {os.path.basename(path)}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
