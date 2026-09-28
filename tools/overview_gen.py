from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "docs/index.html"
t = FILE.read_text(encoding="utf-8")
def rep(old, new, count=1):
    global t
    assert t.count(old) == count, (old[:60], t.count(old))
    t = t.replace(old, new)

# ---------- 색 토큰 ----------
if "--flow-ai:" not in t:
    rep("      --code: #f1f4f7;\n    }", "      --code: #f1f4f7;\n      --flow-ai: #6d4fc2;\n      --flow-gate: #a8730a;\n      --flow-gate-soft: #fdf3d8;\n    }")
    rep("        --code: #242c38;\n      }", "        --code: #242c38;\n        --flow-ai: #b9a4f2;\n        --flow-gate: #e2b95b;\n        --flow-gate-soft: #3a3016;\n      }")

# ---------- CSS ----------
css = """    /* 작업 흐름 그림: Claude(보라)가 만든 산출물이 개발자의 관문(마름모, 노랑)을 지나 다음 Claude 작업으로 간다.
       본문 폭보다 넓게 두고 좁은 화면은 세로 SVG 를 쓴다 */
    .flow-lead { margin: 26px 0 14px; }
    .flow {
      width: min(100vw - 32px, 1060px);
      margin: 0;
      position: relative;
      left: 50%;
      transform: translateX(-50%);
    }
    .flow svg { display: block; width: 100%; height: auto; }
    .flow .v { display: none; }
    .flow text { font-size: 14px; font-weight: 700; fill: var(--text); text-anchor: middle; }
    .flow .ai { font-size: 12.5px; font-weight: 600; fill: var(--flow-ai); }
    .flow .gate-label { font-size: 12.5px; fill: var(--flow-gate); }
    .flow .lane { font-size: 13px; text-anchor: start; }
    .flow .lane.ai-lane { fill: var(--flow-ai); }
    .flow .lane.dev-lane { fill: var(--flow-gate); }
    .flow .lbl { font-size: 11px; font-weight: 600; fill: var(--flow-ai); }
    .flow .tag-text { font-size: 11px; font-weight: 600; fill: var(--text); }
    .flow .end { font-size: 13px; fill: var(--muted); text-anchor: start; }
    .flow .art { fill: var(--surface); stroke: var(--line); stroke-width: 1.5; }
    .flow .gate { fill: var(--flow-gate-soft); stroke: var(--flow-gate); stroke-width: 1.8; }
    .flow .tag { fill: var(--code); stroke: var(--muted); stroke-width: 1; }
    .flow .arrow { fill: none; stroke: var(--muted); stroke-width: 1.8; }
    .flow .ahead { fill: var(--muted); }
    .flow .ai-arrow { fill: none; stroke: var(--flow-ai); stroke-width: 1.8; }
    .flow .ai-arrow.back { stroke-dasharray: 4 4; }
    .flow .ahead-ai { fill: var(--flow-ai); }
    .flow .ret path { fill: none; stroke: var(--muted); stroke-width: 1.8; stroke-dasharray: 6 5; }
    .flow .ahead-ret { fill: var(--muted); }
    .flow .ret text { font-size: 12px; font-weight: 600; fill: var(--muted); }
    .flow .topic { fill: none; stroke: var(--text); stroke-width: 2; }
    .flow .topic-tab { fill: var(--bg); stroke: var(--text); stroke-width: 2; }
    .flow .topic-name { font-size: 12px; font-weight: 700; fill: var(--text); }
    .flow .v text { font-size: 12.5px; }
    .flow .v .ai, .flow .v .gate-label { font-size: 11.5px; }
    .flow .v .lbl, .flow .v .tag-text { font-size: 10.5px; }
    .flow .v .ret text { font-size: 11px; }
    .flow figcaption { max-width: 760px; margin: 10px auto 0; color: var(--muted); font-size: 0.93rem; }
    @media (max-width: 640px) {
      .flow { width: 100%; left: 0; transform: none; }
      .flow .h { display: none; }
      .flow .v { display: block; }
    }
"""
a = t.index("    /* 작업 흐름 그림")
end_marker = "      .flow .v { display: block; }\n    }\n"
b = t.index(end_marker) + len(end_marker)
t = t[:a] + css + t[b:]

# ---------- 스크립트 제거 ----------
js_start = t.find("    /* 작업 흐름 그림: 열 때 한 번 재생")
if js_start != -1:
    js_end = t.index("    })();\n", js_start) + len("    })();\n")
    t = t[:js_start] + t[js_end:]

# ---------- 내용 ----------
arts = ["설계 문서", "테스트·코드", "실행 결과", "Claude 리뷰 · 자체 리뷰"]
ai_acts = ["초안 작성", "테스트 → 구현", "앱 띄워 호출", "Claude 리뷰"]
gates = ["이해", "리뷰·커밋", "결과 확인", "Claude 리뷰와 자체 리뷰 대조"]
DESC = ("Claude가 만든 산출물이 개발자의 관문을 지나야 다음 Claude 작업으로 넘어간다. "
        "1 Claude가 설계 문서 초안을 쓴다. 개발자가 읽고 이해한다. 이해가 안 되면 되묻는다. 문서 규칙과 훅, 독자 테스트가 이 관문에 붙어 있고 이 글의 주제다. "
        "2 Claude가 테스트와 구현을 쓴다. 개발자가 사이클마다 리뷰하고 커밋한다. 리뷰에서 설계 허점을 찾으면 설계 문서로 돌아가 재설계할지 기술 부채로 남길지 정한다. "
        "3 Claude가 앱을 띄워 호출한다. 개발자가 결과를 확인한다. 결과에서 설계 허점을 찾으면 설계 문서로 돌아가 재설계할지 기술 부채로 남길지 정한다. "
        "4 Claude가 변경 전체를 리뷰한다. 개발자도 전체를 자체 리뷰한다. 개발자가 Claude 리뷰와 자체 리뷰를 대조해 필요한 지적만 남기고 마무리한다.")

def topic_zone(x, y, w, h, out):
    """설계 문서와 이해 관문을 굵은 테두리로 묶고 왼쪽 위에 탭 라벨을 단다. 뒤에 깔리게 맨 앞에 넣는다."""
    name, fs = "이 글의 주제", 12
    text_w = sum(4 if c == " " else fs for c in name)
    tab_w = text_w + 24; tab_w += -tab_w % 4
    out.insert(0, f'<rect class="topic" x="{x}" y="{y}" width="{w}" height="{h}" rx="10"/>'
                  f'<path class="topic-tab" d="M{x + 12} {y} V{y - 22} Q{x + 12} {y - 28} {x + 18} {y - 28} '
                  f'H{x + 6 + tab_w} Q{x + 12 + tab_w} {y - 28} {x + 12 + tab_w} {y - 22} V{y}"/>'
                  f'<text class="topic-name" x="{x + 12 + tab_w // 2}" y="{y - 9}">{name}</text>')


def markers(sfx):
    m = lambda mid, cls: (f'<marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                          f'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="{cls}"/></marker>')
    return m(f"ah-{sfx}", "ahead") + m(f"ah-{sfx}-ai", "ahead-ai") + m(f"ah-{sfx}-ret", "ahead-ret")

# ---------- 가로 ----------
X0, RW, DW, GAP = 40, 104, 60, 38
MAIN_Y, AI_Y, GATE_LBL_Y = 150, 58, 204
xs = []; x = X0
for i in range(4):
    xs.append(("art", x, x + RW // 2)); x += RW + GAP
    xs.append(("gate", x, x + DW // 2)); x += DW + GAP
last_right = x - GAP
END_X0, END_X1 = last_right + 4, last_right + 40
H = []
H.append(f'<text class="lane ai-lane" x="8" y="{AI_Y}">Claude</text>')
H.append(f'<text class="lane dev-lane" x="8" y="{GATE_LBL_Y}">개발자</text>')
gi = 0
for kind, xl, cx in xs:
    if kind == "art":
        i = gi
        H.append(f'<text class="ai" x="{cx}" y="{AI_Y}">{ai_acts[i]}</text>')
        H.append(f'<line class="ai-arrow" x1="{cx}" y1="{AI_Y + 10}" x2="{cx}" y2="{MAIN_Y - 27}" marker-end="url(#ah-h-ai)"/>')
        H.append(f'<rect class="art" x="{xl}" y="{MAIN_Y - 24}" width="{RW}" height="48" rx="8"/>')
        if " · " in arts[i]:
            top, bottom = arts[i].split(" · ")
            H.append(f'<text x="{cx}" y="{MAIN_Y - 4}">{top}</text><text x="{cx}" y="{MAIN_Y + 15}">{bottom}</text>')
        else:
            H.append(f'<text x="{cx}" y="{MAIN_Y + 5}">{arts[i]}</text>')
    else:
        i = gi
        H.append(f'<path class="gate" d="M{xl} {MAIN_Y} L{cx} {MAIN_Y - 30} L{xl + DW} {MAIN_Y} L{cx} {MAIN_Y + 30} Z"/>')
        H.append(f'<text class="gate-label" x="{cx}" y="{GATE_LBL_Y}">{gates[i]}</text>')
        gi += 1
for k in range(len(xs) - 1):
    kind, xl, cx = xs[k]; w = RW if kind == "art" else DW; nxl = xs[k + 1][1]
    H.append(f'<line class="arrow" x1="{xl + w + 3}" y1="{MAIN_Y}" x2="{nxl - 3}" y2="{MAIN_Y}" marker-end="url(#ah-h)"/>')
H.append(f'<line class="arrow" x1="{END_X0}" y1="{MAIN_Y}" x2="{END_X1}" y2="{MAIN_Y}" marker-end="url(#ah-h)"/>')
H.append(f'<text class="end" x="{END_X1 + 6}" y="{MAIN_Y + 5}">마무리</text>')
g1x = xs[1][2]
H.append(f'<line class="ai-arrow back" x1="{g1x}" y1="{MAIN_Y - 33}" x2="{g1x}" y2="{AI_Y + 14}" marker-end="url(#ah-h-ai)"/>')
H.append(f'<text class="lbl" x="{g1x + 7}" y="{AI_Y + 48}" style="text-anchor:start">되묻기</text>')
tag_w = 150
H.append(f'<rect class="tag" x="{g1x - tag_w // 2}" y="{GATE_LBL_Y + 9}" width="{tag_w}" height="20" rx="10"/>')
H.append(f'<text class="tag-text" x="{g1x}" y="{GATE_LBL_Y + 23}">문서 규칙 · 훅 · 독자 테스트</text>')
b2x = xs[3][1] + DW + GAP // 2; b3x = xs[5][1] + DW + GAP // 2; a1x = xs[0][2]
RET_Y = GATE_LBL_Y + 46
H.append(f'<g class="ret"><path d="M{b3x} {MAIN_Y + 2} V{RET_Y} H{a1x} V{MAIN_Y + 28}" marker-end="url(#ah-h-ret)"/>'
         f'<path d="M{b2x} {MAIN_Y + 2} V{RET_Y}"/>'
         f'<text x="{(b2x + a1x) // 2}" y="{RET_Y + 19}">설계 허점을 찾으면 재설계하거나 기술 부채로 남김</text></g>')
H_PLAIN = list(H)                        # README 판은 「이 글의 주제」 영역 없이 쓴다
topic_zone(xs[0][1] - 12, MAIN_Y - 42, (g1x + tag_w // 2 + 12) - (xs[0][1] - 12), (GATE_LBL_Y + 29 + 10) - (MAIN_Y - 42), H)
h_w = END_X1 + 60
h_svg = (f'<svg class="h" viewBox="0 0 {h_w} {RET_Y + 32}" role="img" aria-labelledby="flow-title-h" aria-describedby="flow-desc-h">\n'
         '          <title id="flow-title-h">작업 흐름. Claude 가 만든 산출물이 개발자의 관문을 지나 다음 Claude 작업으로 간다</title>\n'
         f'          <desc id="flow-desc-h">{DESC}</desc>\n'
         f'          <defs>{markers("h")}</defs>\n' + "\n".join("          " + s for s in H) + "\n        </svg>")

# ---------- 세로 ----------
CX, RW2, RH2, DH2, GAP2 = 196, 128, 42, 50, 22
AI_X_END, RET_X = 108, 396
ys = []; y = 44
for i in range(4):
    ys.append(("art", y, y + RH2 // 2)); y += RH2 + GAP2
    ys.append(("gate", y, y + DH2 // 2)); y += DH2 + GAP2
last_bottom = y - GAP2
END_Y0, END_Y1 = last_bottom + 4, last_bottom + 34
V = []
V.append('<text class="lane ai-lane" x="10" y="22">Claude</text>')
V.append(f'<text class="lane dev-lane" x="{CX + 36}" y="22">개발자</text>')
gi = 0
for kind, yt, cy in ys:
    if kind == "art":
        i = gi
        V.append(f'<text class="ai" x="{AI_X_END}" y="{cy + 4}" style="text-anchor:end">{ai_acts[i]}</text>')
        V.append(f'<line class="ai-arrow" x1="{AI_X_END + 8}" y1="{cy}" x2="{CX - RW2 // 2 - 3}" y2="{cy}" marker-end="url(#ah-v-ai)"/>')
        V.append(f'<rect class="art" x="{CX - RW2 // 2}" y="{yt}" width="{RW2}" height="{RH2}" rx="8"/>')
        if " · " in arts[i]:
            top, bottom = arts[i].split(" · ")
            V.append(f'<text x="{CX}" y="{cy - 4}">{top}</text><text x="{CX}" y="{cy + 14}">{bottom}</text>')
        else:
            V.append(f'<text x="{CX}" y="{cy + 5}">{arts[i]}</text>')
    else:
        i = gi
        V.append(f'<path class="gate" d="M{CX - 30} {cy} L{CX} {yt} L{CX + 30} {cy} L{CX} {yt + DH2} Z"/>')
        if "와 " in gates[i]:
            first, second = gates[i].split("와 ", 1)
            V.append(f'<text class="gate-label" x="{CX + 38}" y="{cy - 4}" style="text-anchor:start">{first}와</text>'
                     f'<text class="gate-label" x="{CX + 38}" y="{cy + 12}" style="text-anchor:start">{second}</text>')
        else:
            V.append(f'<text class="gate-label" x="{CX + 38}" y="{cy + 4}" style="text-anchor:start">{gates[i]}</text>')
        gi += 1
for k in range(len(ys) - 1):
    kind, yt, cy = ys[k]; h = RH2 if kind == "art" else DH2; nyt = ys[k + 1][1]
    V.append(f'<line class="arrow" x1="{CX}" y1="{yt + h + 3}" x2="{CX}" y2="{nyt - 3}" marker-end="url(#ah-v)"/>')
V.append(f'<line class="arrow" x1="{CX}" y1="{END_Y0}" x2="{CX}" y2="{END_Y1}" marker-end="url(#ah-v)"/>')
V.append(f'<text class="end" x="{CX + 10}" y="{END_Y1 + 4}">마무리</text>')
g1y = ys[1][2]
V.append(f'<line class="ai-arrow back" x1="{CX - 33}" y1="{g1y}" x2="{AI_X_END + 12}" y2="{g1y}" marker-end="url(#ah-v-ai)"/>')
V.append(f'<text class="lbl" x="{(CX - 33 + AI_X_END + 12) // 2}" y="{g1y - 8}">되묻기</text>')
tag_w2 = 136
V.append(f'<rect class="tag" x="{CX + 38}" y="{g1y + 12}" width="{tag_w2}" height="20" rx="10"/>')
V.append(f'<text class="tag-text" x="{CX + 38 + tag_w2 // 2}" y="{g1y + 26}">문서 규칙 · 훅 · 독자 테스트</text>')
b2y = ys[3][1] + DH2 + GAP2 // 2; b3y = ys[5][1] + DH2 + GAP2 // 2; a1y = ys[0][2]
V.append(f'<g class="ret"><path d="M{CX + 2} {b3y} H{RET_X} V{a1y} H{CX + RW2 // 2 + 3}" marker-end="url(#ah-v-ret)"/>'
         f'<path d="M{CX + 2} {b2y} H{RET_X}"/>'
         f'<text x="{(CX + RW2 // 2 + RET_X) // 2 + 2}" y="{a1y - 23}">설계 허점을 찾으면</text>'
         f'<text x="{(CX + RW2 // 2 + RET_X) // 2 + 2}" y="{a1y - 9}">재설계·부채 판단</text></g>')
topic_zone(CX - RW2 // 2 - 12, ys[0][1] - 12, (CX + 38 + tag_w2 + 10) - (CX - RW2 // 2 - 12), (g1y + 42) - (ys[0][1] - 12), V)
v_svg = (f'<svg class="v" viewBox="0 0 {RET_X + 22} {END_Y1 + 26}" role="img" aria-labelledby="flow-title-v" aria-describedby="flow-desc-v">\n'
         '          <title id="flow-title-v">작업 흐름. Claude 가 만든 산출물이 개발자의 관문을 지나 다음 Claude 작업으로 간다</title>\n'
         f'          <desc id="flow-desc-v">{DESC}</desc>\n'
         f'          <defs>{markers("v")}</defs>\n' + "\n".join("          " + s for s in V) + "\n        </svg>")

block = ('      <p class="flow-lead">내 작업 흐름은 아래와 같다. 이 글은 그 가운데 첫 관문, 설계 문서를 이해하는 일에서 생긴 문제를 다룬다.</p>\n'
         '      <figure class="flow">\n'
         f'        {h_svg}\n        {v_svg}\n'
         '        <figcaption>작업 흐름. 보라색은 Claude가 하는 일, 노란 마름모는 개발자가 판단하는 관문이다. Claude가 만든 산출물이 관문을 지나야 다음 Claude 작업으로 넘어간다. 굵은 테두리로 묶은 설계 문서와 이해 관문, 거기 붙은 문서 규칙·훅·독자 테스트가 이 글의 주제다. 독자 테스트는 문서만 읽는 AI에게 질문에 답하게 해 빠진 설명과 필요 없는 글을 찾는 절차다. 이 글에서 개발자는 나다. 절차마다 누가 무엇을 하고 어떤 훅과 스킬(필요할 때만 불러 읽는 지시 파일)이 적용되는지는 <a href="ai-workflow.html">AI Workflow</a> 문서에 그렸다.</figcaption>\n'
         '      </figure>\n')
c = t.index('      <p class="flow-lead">')
dd = t.index("      </figure>\n") + len("      </figure>\n")
t = t[:c] + block + t[dd:]
FILE.write_text(t, encoding="utf-8")
print("written; h viewBox", h_w, RET_Y + 32, "| v viewBox", RET_X + 22, END_Y1 + 26)


# ---------- README 판: 「이 글의 주제」 영역을 빼고 색을 고정한 가로 SVG 두 벌 ----------
# GitHub README 는 HTML 안의 SVG 를 보여 주지 않는다. 파일로 내보내 <picture> 로 테마에 맞는 쪽을 건다
import re
THEMES = {
    "light": {"text": "#172033", "muted": "#5d6879", "surface": "#ffffff", "line": "#dbe1e8", "code": "#f1f4f7",
              "flow-ai": "#6d4fc2", "flow-gate": "#a8730a", "flow-gate-soft": "#fdf3d8"},
    "dark": {"text": "#edf1f7", "muted": "#abb5c4", "surface": "#171d27", "line": "#303948", "code": "#242c38",
             "flow-ai": "#b9a4f2", "flow-gate": "#e2b95b", "flow-gate-soft": "#3a3016"},
}
RULES = [l.strip() for l in css.splitlines()
         if l.strip().startswith(".flow ") and "{" in l and "}" in l and not re.match(r"\.flow (\.v|\.h|svg|figcaption|\.topic)", l.strip())]
DESC_README = DESC.replace(" 문서 규칙과 훅, 독자 테스트가 이 관문에 붙어 있고 이 글의 주제다.", " 문서 규칙과 훅, 독자 테스트가 이 관문에 붙어 있다.")
assert DESC_README != DESC
for theme, vals in THEMES.items():
    style = "\n".join(RULES).replace(".flow ", "")
    style = re.sub(r"var\(--([\w-]+)\)", lambda m: vals[m.group(1)], style)
    style = 'text { font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif; }\n' + style
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {h_w} {RET_Y + 32}" role="img" aria-labelledby="flow-title flow-desc">\n'
           '<title id="flow-title">작업 흐름. Claude 가 만든 산출물이 개발자의 관문을 지나 다음 Claude 작업으로 간다</title>\n'
           f'<desc id="flow-desc">{DESC_README}</desc>\n'
           f'<style>\n{style}\n</style>\n<defs>{markers("h")}</defs>\n' + "\n".join(H_PLAIN) + "\n</svg>\n")
    out = FILE.parent / f"workflow-overview-{theme}.svg"
    out.write_text(svg, encoding="utf-8")
    print("written", out.name)
