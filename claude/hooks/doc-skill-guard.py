#!/usr/bin/env python3
"""PreToolUse(Write|Edit|MultiEdit|Bash) — 문서를 작성하거나 수정하기 전에 doc-writing 과 심층 인터뷰 스킬을 호출했는지 확인한다.

전역 규칙 「문서 작성」이 doc-writing 을 먼저 호출하게 하고, doc-writing 「쓰기 전에 심층 인터뷰를 진행한다」가
grill-me 나 grill-with-docs 로 사용자에게 먼저 질문하게 한다. 그 호출이 대화 기록에 있는지만 확인한다.
사용자가 「심층 인터뷰 생략」이라고 작성하거나 질문 창에서 그렇게 답했으면 심층 인터뷰 확인은 생략한다.
종료 코드 2 + stderr 가 차단이다.
"""
import json
import os
import sys

from testrun import called_paths, content_blocks, edited_paths, failed_calls, human_message, is_document, load_rows, said

SKILL = "doc-writing"
GRILL = {"grill-me", "grill-with-docs"}
SKIP = "심층 인터뷰 생략"


def skills(row):
    """그 줄에서 부른 스킬 이름."""
    if row.get("type") != "assistant":
        return set()
    return {(b.get("input") or {}).get("skill") for b in content_blocks(row)
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Skill"}


def scan(transcript_path):
    """doc-writing 을 불렀는지, 지금 요청에서 심층 인터뷰를 진행했는지, 앞서 심층 인터뷰를 마친 뒤 쓴 문서가 무엇인지 본다.

    심층 인터뷰와 생략은 사용자 메시지마다 새로 받는다. 앞선 요청의 심층 인터뷰로 다른 문서까지 통과시키지 않기 위해서다.
    다만 심층 인터뷰를 마친 뒤 쓴 문서는 같은 세션에서 다시 묻지 않는다. 리뷰를 반영하는 요청마다 같은 문서의 독자를 다시 묻게 되기 때문이다.
    """
    rows = load_rows(transcript_path)
    wrote = any(SKILL in skills(r) for r in rows)
    failed = failed_calls(rows)
    asked, covered = False, set()
    for r in rows:
        if human_message(r):
            asked = False
        if GRILL & skills(r) or said(r, SKIP):
            asked = True
        if asked:
            covered.update(called_paths(r, failed))
    return wrote, asked, covered


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    content = (payload.get("tool_input") or {}).get("content")
    docs = [p for p in edited_paths(payload) if is_document(p, content)]
    if not docs:
        return
    wrote, asked, covered = scan(payload.get("transcript_path", ""))
    target = f"대상 파일: {os.path.basename(docs[0])}"
    if payload.get("tool_name") == "Bash":
        target += ". 이 Bash 명령 전체가 실행되지 않았다. 같은 명령에 묶은 다른 작업도 실행되지 않았다"
    if not wrote:
        print(f"[doc-skill-guard] 문서를 쓰기 전에 `{SKILL}` 스킬을 불러 전체 규칙을 따른다. {target}", file=sys.stderr)
        sys.exit(2)
    if asked or all(os.path.realpath(p) in covered for p in docs):
        return
    print(f"[doc-skill-guard] 문서를 쓰거나 고치기 전에 `grill-me` 나 `grill-with-docs` 로 사용자에게 심층 인터뷰를 진행한다. "
          f"건너뛰려면 사용자가 「{SKIP}」이라고 말해야 한다. {target}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
