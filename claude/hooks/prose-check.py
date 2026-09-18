#!/usr/bin/env python3
"""PostToolUse(Write|Edit) — 문서 산문의 기계 검사. ~/.claude/CLAUDE.md 「문서 작성」 중 정규식으로 잡히는 것만.

대상: .md·.html 문서. AI 설정·규칙 파일과 임시 폴더의 파일은 대상이 아니다(testrun.is_document).
추적 중인 파일은 이번 편집으로 **추가된 줄만** 본다. 옛 본문의 위반으로 새 편집을 막지 않기 위해서다.
코드 블록·코드 스팬·<pre>·<code>·<script>·<style> 안은 보지 않는다.

차단(종료 2): 전각 대시로 두 문장을 잇는 것(제목·표 라벨의 대시는 허용), 표 칸을 <br> 로 나눈 한 조각에
두 문장을 쓴 것, 연결어미 「지만·는데·면서」와 「하고·되고·있고」 꼴 뒤 쉼표.
참고(additionalContext): 「~기 때문에」가 열 문장에 한 번을 넘는 것, 질문형 제목, 제목 속 개수, 연결어미로 보이는 「고」 뒤 쉼표.
못 잡는 것: 여러 줄에 걸쳐 쓴 표 칸(줄 단위로 본다), 「재고,」 같은 명사와 구분되지 않는 「고,」(막지 않고 알리기만 한다).
파일 첫 줄에 `prose-check: off` 가 있으면 건너뛴다.
"""
import html
import json
import os
import re
import subprocess
import sys

from testrun import edited_paths, is_document

DASH = " — "
CAUSE = re.compile(r"기 때문")
HEAD_MD = re.compile(r"^\s{0,3}#{1,6}\s+(.*)$")
HEAD_HTML = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.S)
COUNT_IN_TITLE = re.compile(r"(한|두|세|네|다섯|여섯|일곱|\d+)\s?(편|가지|개|종|건|단계)\b")
CELL_HTML = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
MD_RULE_ROW = re.compile(r"\s*\|[\s:|-]*\|?\s*")
BR = re.compile(r"<br\s*/?>", re.I)
TWO_SENTENCES = re.compile(r"다\.\s+\S")
CONNECTIVE_COMMA = re.compile(r"([가-힣]*(?:지만|는데|면서)),")
CONJUNCTIONS = {"하지만", "그렇지만", "그런데", "그러는데", "그러면서"}
# 활용형이 분명한 「하고,」 꼴은 막는다. 나머지 「고,」는 「재고,」 같은 명사와 가를 수 없어 알리기만 한다
VERB_COMMA = re.compile(r"([가-힣]*(?:하고|했고|되고|됐고|있고|없고|않고|시키고|였고|었고|았고|겠고)),")
GO_COMMA = re.compile(r"([가-힣]+고),")
NOUNS_ENDING_GO = ("재고", "참고", "보고", "최고", "경고", "창고", "광고", "사고", "신고", "원고")


def cell_parts(raw, stripped, is_html):
    """표 한 줄의 칸을 <br> 로 나눈 조각을 태그를 뺀 글자로 낸다."""
    if is_html:
        cells = CELL_HTML.findall(re.sub(r"<code>.*?</code>", "", raw))
    elif stripped.lstrip().startswith("|") and not MD_RULE_ROW.fullmatch(stripped):
        cells = stripped.strip().strip("|").split("|")
    else:
        cells = []
    return [html.unescape(re.sub(r"<[^>]+>", " ", part)).strip() for cell in cells for part in BR.split(cell)]


HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")


def added_numbers(path):
    """HEAD 대비 추가된 줄의 새 파일 기준 번호. 추적하지 않는 파일이면 None(전체를 본다)."""
    d = os.path.dirname(path) or "."
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", path], cwd=d,
                             capture_output=True, text=True).returncode == 0
    if not tracked:
        return None
    r = subprocess.run(["git", "diff", "-U0", "HEAD", "--", path], cwd=d,
                       capture_output=True, text=True)
    nums, n = [], 0
    for l in r.stdout.splitlines():
        m = HUNK.match(l)
        if m:
            n = int(m.group(1))
        elif l.startswith("+") and not l.startswith("+++"):
            nums.append(n)
            n += 1
    return nums


def added_lines(path, is_html):
    """검사할 줄을 (원문, 코드 영역을 비운 것)으로 낸다.

    코드 영역 판정은 파일 전체를 보고 한다. 추가된 줄만 모아 보면 기존 블록 안의 한 줄을 고쳤을 때
    그 조각에 여는 표시가 없어 산문으로 검사하게 된다.
    """
    try:
        raw = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return [], []
    stripped = strip_code(raw, is_html)
    nums = added_numbers(path)
    if nums is None:
        return raw, stripped
    idx = [n - 1 for n in nums if 0 < n <= len(raw)]
    return [raw[i] for i in idx], [stripped[i] for i in idx]


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


def check(path):
    """문서 하나에서 이번 편집으로 추가된 줄을 검사해 (차단할 것, 참고할 것)을 낸다."""
    try:
        first = open(path, encoding="utf-8").readline()
    except OSError:
        return [], []
    if "prose-check: off" in first:
        return [], []

    is_html = path.endswith(".html")
    raw, lines = added_lines(path, is_html)
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
            blocks.append(f"{i}행 전각 대시로 두 문장을 이었다: 「{tail[-30:]} — …」. 마침표로 끊거나 접속사로 푼다")

    for i, (r, l) in enumerate(zip(raw, lines), 1):
        if not l.strip():
            continue
        for part in cell_parts(r, l, is_html):
            if TWO_SENTENCES.search(part):
                blocks.append(f"{i}행 표 칸 한 조각에 문장이 둘이다: 「{part[:40]}」. 문장마다 <br> 로 줄을 바꾼다")
        blocked_words = set()
        for word in CONNECTIVE_COMMA.findall(l) + VERB_COMMA.findall(l):
            if word not in CONJUNCTIONS:
                blocked_words.add(word)
                blocks.append(f"{i}행 연결어미 뒤에 쉼표를 찍었다: 「{word},」. 쉼표를 뺀다")
        for word in GO_COMMA.findall(l):
            if word not in blocked_words and not word.endswith(NOUNS_ENDING_GO):
                warns.append(f"연결어미 「고」 뒤 쉼표로 보인다: 「{word},」")

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
    return blocks, warns


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    paths = [p for p in edited_paths(payload) if is_document(p) and os.path.isfile(p)]
    blocked, noted = [], []
    for path in paths:
        blocks, warns = check(path)
        name = os.path.basename(path)
        if blocks:
            blocked.append("대상 파일: " + name + "\n  " + "\n  ".join(blocks[:8]) +
                           ("\n  (그 외 %d건)" % (len(blocks) - 8) if len(blocks) > 8 else "") +
                           ("\n[참고] " + "; ".join(warns) if warns else ""))
        elif warns:
            noted.append(name + ": " + "; ".join(warns))
    if blocked:
        print("[prose-check] 문서 산문 규칙을 어긴 곳이 있다. " + "\n".join(blocked), file=sys.stderr)
        sys.exit(2)
    if noted:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
              "additionalContext": "[prose-check 참고] " + " / ".join(noted)}},
              ensure_ascii=False))


if __name__ == "__main__":
    main()
