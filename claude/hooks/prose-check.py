#!/usr/bin/env python3
"""PostToolUse(Write|Edit) — 문서 산문의 기계 검사. ~/.claude/CLAUDE.md 「문서 작성」 중 정규식으로 잡히는 것만.

대상: docs/ 아래의 .md·.html, 저장소 루트 README.md. 메모리·규칙 파일(.claude/)은 대상이 아니다.
추적 중인 파일은 이번 편집으로 **추가된 줄만** 본다. 옛 본문의 위반으로 새 편집을 막지 않기 위해서다.
코드 블록·코드 스팬·<pre>·<code>·<script>·<style> 안은 보지 않는다.

차단(종료 2): 전각 대시로 두 문장을 잇는 것. 제목·표 라벨의 대시는 허용한다.
참고(additionalContext): 「~기 때문에」가 열 문장에 한 번을 넘는 것, 질문형 제목, 제목 속 개수.
파일 첫 줄에 `prose-check: off` 가 있으면 건너뛴다.
"""
import html
import json
import os
import re
import subprocess
import sys

DASH = " — "
CAUSE = re.compile(r"기 때문")
HEAD_MD = re.compile(r"^\s{0,3}#{1,6}\s+(.*)$")
HEAD_HTML = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.S)
COUNT_IN_TITLE = re.compile(r"(한|두|세|네|다섯|여섯|일곱|\d+)\s?(편|가지|개|종|건|단계)\b")


def target(path):
    if not path:
        return False
    p = path.replace("\\", "/")
    if "/.claude/" in p:
        return False
    if os.path.basename(p) == "README.md":
        return True
    return "/docs/" in p and p.endswith((".md", ".html"))


def added_lines(path):
    """git 추적 파일이면 HEAD 대비 추가된 줄, 아니면 전체."""
    d = os.path.dirname(path) or "."
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", path], cwd=d,
                             capture_output=True, text=True).returncode == 0
    if tracked:
        r = subprocess.run(["git", "diff", "-U0", "HEAD", "--", path], cwd=d,
                           capture_output=True, text=True)
        return [l[1:] for l in r.stdout.splitlines() if l.startswith("+") and not l.startswith("+++")]
    try:
        return open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return []


def strip_code(lines, is_html):
    """코드 영역을 비운 줄 목록을 돌려준다. 줄 수는 유지한다."""
    out, skip = [], False
    for l in lines:
        if is_html:
            low = l.lower()
            if any(t in low for t in ("<pre", "<script", "<style")):
                skip = True
            if skip:
                out.append("")
                if any(t in low for t in ("</pre>", "</script>", "</style>")):
                    skip = False
                continue
            l = re.sub(r"<code>.*?</code>", "", l)
            l = html.unescape(re.sub(r"<[^>]+>", " ", l))
        else:
            if l.strip().startswith("```"):
                skip = not skip
                out.append("")
                continue
            if skip:
                out.append("")
                continue
            l = re.sub(r"`[^`]*`", "", l)
        out.append(l)
    return out


def is_heading_or_table(raw, is_html):
    s = raw.lstrip()
    if is_html:
        return bool(re.search(r"<h[1-6]|<th|<td|<caption|<summary", s, re.I))
    return s.startswith("#") or s.startswith("|")


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    path = (payload.get("tool_input") or {}).get("file_path", "")
    if not target(path) or not os.path.isfile(path):
        return
    try:
        first = open(path, encoding="utf-8").readline()
    except OSError:
        return
    if "prose-check: off" in first:
        return

    is_html = path.endswith(".html")
    raw = added_lines(path)
    lines = strip_code(raw, is_html)
    blocks, warns = [], []

    for i, (r, l) in enumerate(zip(raw, lines), 1):
        if DASH not in l or is_heading_or_table(r, is_html):
            continue
        head = l.split(DASH, 1)[0]
        # 마지막 문장 끝(마침표) 뒤부터 대시까지의 길이. 라벨(짧음)은 허용, 문장 잇기(김)는 차단
        tail = re.split(r"[.!?]\s", head)[-1].strip()
        tail = re.sub(r"^([-*+]|\d+\.)\s+", "", tail)  # 목록 표식은 어절로 세지 않는다
        # 라벨(「낙관적 락」)은 짧고 띄어쓰기가 한 번 이하다. 문장은 어절이 셋 이상이거나 길다
        if tail.count(" ") >= 2 or len(tail) >= 16:
            blocks.append(f"{i}행: 「{tail[-30:]} — …」")

    text = "\n".join(lines)
    sentences = max(1, len(re.findall(r"[.!?다]\s|[.!?]$", text, re.M)))
    causes = len(CAUSE.findall(text))
    if causes > 0 and causes * 10 > sentences:
        warns.append(f"「~기 때문에」 {causes}회 / 문장 약 {sentences}개. 열 문장에 한 번을 넘는다")

    heads = []
    for l in lines:
        m = HEAD_MD.match(l)
        if m:
            heads.append(m.group(1))
    if is_html:
        heads += [re.sub(r"<[^>]+>", "", h) for h in HEAD_HTML.findall("\n".join(raw))]
    for h in heads:
        h = h.strip()
        if h.endswith("?") or h.endswith("？"):
            warns.append(f"질문형 제목: 「{h}」")
        if COUNT_IN_TITLE.search(h):
            warns.append(f"제목 속 개수: 「{h}」")

    if blocks:
        print("[prose-check] 전각 대시로 두 문장을 잇지 않는다. 마침표로 끊거나 접속사로 푼다. "
              "대상 파일: " + os.path.basename(path) + "\n  " + "\n  ".join(blocks[:8]) +
              ("\n  (그 외 %d건)" % (len(blocks) - 8) if len(blocks) > 8 else "") +
              ("\n[참고] " + "; ".join(warns) if warns else ""), file=sys.stderr)
        sys.exit(2)
    if warns:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
              "additionalContext": "[prose-check 참고] " + os.path.basename(path) + ": " + "; ".join(warns)}},
              ensure_ascii=False))


if __name__ == "__main__":
    main()
