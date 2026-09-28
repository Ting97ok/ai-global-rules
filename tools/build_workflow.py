#!/usr/bin/env python3
"""docs/ai-workflow.html 의 표시한 자리에 작업 흐름 그림과 그림 스타일을 넣는다. 산문은 문서 파일에서 직접 고친다."""
import re
import sys
from pathlib import Path

import gen

DOC = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "docs/ai-workflow.html")


def put(text, start, end, body):
    """start 와 end 표시 사이를 body 로 바꾼다. 표시는 그대로 둔다."""
    pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    assert len(pat.findall(text)) == 1, start
    return pat.sub(lambda _: f"{start}\n{body}\n{end}", text)


doc = DOC.read_text(encoding="utf-8")
doc = put(doc, "/* flow-b:start */", "/* flow-b:end */", gen.CSS)
for n, _title, _prev, html, _h in gen.chapters(head=False):
    i = html.find('<ol class="notes">')
    svg, notes = (html[:i].rstrip(), html[i:]) if i >= 0 else (html, "")
    doc = put(doc, f"<!-- ch{n}:start -->", f"<!-- ch{n}:end -->", svg)
    doc = put(doc, f"<!-- notes{n}:start -->", f"<!-- notes{n}:end -->", notes)
DOC.write_text(doc, encoding="utf-8")
print("written", DOC)
