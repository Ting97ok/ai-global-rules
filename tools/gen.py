#!/usr/bin/env python3
"""AI Workflow 그림 생성기: 요청부터 병합까지의 절차를 스윔레인 여러 장으로 그린다.

실행하면 같은 폴더에 미리보기 preview.html 을 쓴다. 문서에는 build_workflow.py 로 넣고 check.js 로 렌더를 측정한다.
"""
import html
from pathlib import Path

OUT = Path(__file__).parent
esc = html.escape
W = 1240                  # 장마다 viewBox 폭
LX = 16                   # 왼쪽 끝
NAME_R = 80               # 줄 이름 칸의 오른쪽 끝
X0 = 96                   # 노드 영역의 왼쪽 끝
XR = 1224                 # 오른쪽 끝
LANE_TOP = 88             # 첫 줄의 위 끝
HEAD_CUT = 64             # 머리를 뺄 때 viewBox 가 시작하는 y. 4장 오른쪽 위 입구 라벨(y 74)이 가장 높다
NUM = "①②③④⑤⑥⑦⑧⑨⑩"
T, F = True, False


def ortho(pts, r=8):
    """직각 꺾임을 둥근 모서리로 잇는 path d. 짧은 구간에서는 반경을 줄인다."""
    sg = lambda a, b: (b > a) - (b < a)
    d = f"M{pts[0][0]:g} {pts[0][1]:g}"
    for i in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
        k = min(r, (abs(x1 - x0) + abs(y1 - y0)) / 2, (abs(x2 - x1) + abs(y2 - y1)) / 2)
        d += (f" L{x1 - k * sg(x0, x1):g} {y1 - k * sg(y0, y1):g}"
              f" Q{x1:g} {y1:g} {x1 + k * sg(x1, x2):g} {y1 + k * sg(y1, y2):g}")
    return d + f" L{pts[-1][0]:g} {pts[-1][1]:g}"


def tw(text, size=13.0, bold=False):
    """본문 글꼴의 글자 폭 근사. 13px 한글 11.25 는 브라우저에서 잰 값이다."""
    w = 0.0
    for c in text:
        o = ord(c)
        if c in "→←—": w += 13.0
        elif o > 0x2000: w += 11.5
        elif c == " ": w += 3.7
        elif c == "·": w += 4.5
        elif c.isupper(): w += 9.1
        elif c.isdigit(): w += 8.2
        elif c.isalpha(): w += 7.3
        else: w += 7.0
    return w * size / 13 * (1.04 if bold else 1.0) * 1.02


def twm(text, size=13.0):
    """고정폭 글꼴의 글자 폭."""
    return len(text) * 7.9 * size / 13


def wrap(text, width, size=13.0, bold=False):
    """빈칸과 가운뎃점 뒤에서 줄을 바꾼다."""
    toks = []
    for word in text.split(" "):
        parts = word.split("·")
        toks += [(p + "·", "") for p in parts[:-1]] + [(parts[-1], " ")]
    lines, cur = [], ""
    for t, sep in toks:
        if cur and tw((cur + t).rstrip(), size, bold) > width:
            lines.append(cur.rstrip()); cur = ""
        cur += t + sep
    return lines + [cur.rstrip()]


# 상자 정렬 규칙(모든 상자 공통, viewBox 단위)
PAD, TOP, FIRST, PITCH, ITEM, BOTTOM = 12, 24, 22, 18, 6, 14


def lay(title, desc, w):
    """상자 안 글자 배치와 상자 높이. desc 는 문자열 또는 항목 목록이다. 제목의 \\n 은 줄을 직접 나눈다."""
    out, y = [], TOP
    for k, t in enumerate(t for part in title.split("\n") for t in wrap(part, w - 2 * PAD, 14, True)):
        if k: y += PITCH
        out.append(("title", y, t))
    first = True
    for item in ([desc] if isinstance(desc, str) else desc):
        for k, t in enumerate(wrap(item, w - 2 * PAD) if item else []):
            y += FIRST if first else PITCH + (ITEM if k == 0 else 0)
            first = False
            out.append(("sub", y, t))
    return out, y + BOTTOM


class Page:
    """스윔레인 한 장. 줄(lane)은 주체다."""

    def __init__(self, n, title, lead, prev):
        self.n, self.title, self.lead, self.prev = n, title, lead, prev
        self.lanes = []                     # (kind, 이름, 위 끝, 아래 끝)
        self.zones, self.conns, self.labels, self.fore = [], [], [], []
        self.N, self.notes = {}, []
        self.count = {"node": 0, "conn": 0}
        self.floor = 0                      # 줄 없는 장의 그림 바닥

    # ── 노드 ──
    def box(self, nid, kind, title, desc, x, y, w, h=None, tags=(), memo=None):
        """그림의 모든 상자를 그리는 하나뿐인 함수. 산출물은 모서리가 접힌 문서 모양이다."""
        texts, nh = lay(title, desc, w)
        h = h or nh
        if kind == "art":
            shape = (f'<path class="shape" d="M{x} {y} H{x + w - 14} L{x + w} {y + 14} V{y + h} H{x} Z"/>'
                     f'<path class="fold" d="M{x + w - 14} {y} V{y + 14} H{x + w}"/>')
        else:
            shape = f'<rect class="shape" x="{x}" y="{y}" width="{w}" height="{h}" rx="{0 if kind == "note" else 6}"/>'
        o = [f'<g class="cell {kind}">{shape}']
        o += [f'<text class="{c}" x="{x + PAD}" y="{y + dy}">{esc(t)}</text>' for c, dy, t in texts]
        self.fore.append("".join(o) + "</g>")
        self.N[nid] = dict(x=x, y=y, w=w, h=h, r=x + w, b=y + h, cx=x + w / 2, cy=y + h / 2)
        if kind != "note":
            self.count["node"] += 1
        bottom = y + h
        if tags:
            bottom = self.tags(tags, x, bottom + 8, w)
        if memo:
            for k, t in enumerate(wrap(memo, w)):
                bottom += 18
                self.fore.append(f'<text class="memo" x="{x}" y="{bottom - 4}">{esc(t)}</text>')
        self.N[nid]["foot"] = bottom
        return bottom

    def diamond(self, nid, kind, title, cx, y, w, h=76):
        """판단 마름모. 제목은 가운데 정렬 한 줄 또는 두 줄. 꼭지점 좌표를 N 에 함께 넣는다."""
        cy = y + h / 2
        lines = wrap(title, w - 56, 13, True)
        ys = [cy + 5] if len(lines) == 1 else [cy - 4, cy + 14]
        o = [f'<g class="cell {kind} decision"><path class="shape" d="M{cx:g} {y:g} L{cx + w / 2:g} {cy:g} '
             f'L{cx:g} {y + h:g} L{cx - w / 2:g} {cy:g} Z"/>']
        o += [f'<text class="dtitle" x="{cx:g}" y="{ty:g}" text-anchor="middle">{esc(t)}</text>' for ty, t in zip(ys, lines)]
        self.fore.append("".join(o) + "</g>")
        self.N[nid] = dict(x=cx - w / 2, y=y, w=w, h=h, r=cx + w / 2, b=y + h, cx=cx, cy=cy, foot=y + h)
        self.count["node"] += 1

    def merge(self, x, y):
        """갈래가 다시 만나는 합류점. 작은 점 하나."""
        self.fore.append(f'<circle class="merge" cx="{x:g}" cy="{y:g}" r="4"/>')

    @staticmethod
    def height(title, desc, w):
        return lay(title, desc, w)[1]

    @staticmethod
    def tag_lines(name, mono, w):
        head = "① "
        if mono:
            return [name]
        return [t for part in name.split("\n") for t in wrap(part, w - 16 - tw(head))]

    @classmethod
    def tags_height(cls, tags, w):
        h = 0
        for name, mono, _ in tags:
            h += 8 + 24 + 18 * (len(cls.tag_lines(name, mono, w)) - 1)
        return h

    def tags(self, tags, x, y, w):
        """노드 아래 강제 장치 꼬리표. 번호와 이름만 두고 설명은 장 아래 띠로 보낸다. 아래 끝 y 를 돌려준다."""
        for name, mono, desc in tags:
            num = NUM[len(self.notes)]
            lines = self.tag_lines(name, mono, w)
            lw = max((twm(t) if mono else tw(t, 13, True)) for t in lines) + tw(num + " ")
            tw_ = int(lw + 16); tw_ += -tw_ % 4
            th = 24 + 18 * (len(lines) - 1)
            cls = "mono" if mono else "tagname"
            o = [f'<g class="tag"><rect x="{x}" y="{y}" width="{tw_}" height="{th}"/>']
            for k, t in enumerate(lines):
                lead = f'<tspan class="num">{num}</tspan> ' if k == 0 else ""
                dx = 0 if k == 0 else tw(num + " ")
                o.append(f'<text x="{x + 8 + dx:g}" y="{y + 17 + 18 * k}">{lead}<tspan class="{cls}">{esc(t)}</tspan></text>')
            self.fore.append("".join(o) + "</g>")
            self.notes.append((num, name.replace("\n", " "), mono, desc))
            y += th + 8
        return y - 8

    # ── 연결 ──
    def conn(self, pts, cls="c", end=True):
        m = f' marker-end="url(#fb-p{self.n}-ah)"' if end else ""
        self.conns.append(f'<path class="{cls}" d="{ortho(pts)}"{m}/>')
        self.count["conn"] += 1

    def bridge(self, x, y, r=6):
        """교차점의 건너뛰기 표시. 가로선을 끊고 반원으로 세로선을 넘는다."""
        self.fore.insert(0, f'<rect class="bridge-cut" x="{x - r:g}" y="{y - 3:g}" width="{2 * r}" height="6"/>'
                            f'<path class="bridge" d="M{x:g} {y - 3:g} V{y + 3:g}"/>'
                            f'<path class="bridge" d="M{x - r:g} {y:g} A{r} {r} 0 0 1 {x + r:g} {y:g}"/>')

    def label(self, x, y, lines, anchor="start"):
        """선 옆 라벨. (x, y) 는 마스크의 왼쪽 위(anchor=end 이면 오른쪽 위)."""
        w = max(tw(t, 13, True) for t in lines) + 10
        w = int(w + (-w % 4))
        if anchor == "end":
            x -= w
        self.labels.append(f'<rect class="mask" x="{x:g}" y="{y:g}" width="{w}" height="{18 * len(lines)}" rx="2"/>')
        for i, t in enumerate(lines):
            self.labels.append(f'<text class="lbl" x="{x + 5:g}" y="{y + 13 + 18 * i:g}">{esc(t)}</text>')
        return w

    def edge(self, pts, text, side, cls="c back"):
        """다른 장으로 가는 선. 장 가장자리에서 끝나고 끝에 라벨을 둔다. side 는 선 끝에서 라벨이 놓이는 쪽."""
        self.conn(pts, cls)
        x, y = pts[-1]
        lines = text if isinstance(text, list) else [text]
        h = 18 * len(lines)
        if side == "right":
            self.label(x + 8, y - h / 2, lines)
        elif side == "left":
            self.label(x - 8, y - h / 2, lines, "end")
        elif side in ("below", "above"):
            w = int(max(tw(t, 13, True) for t in lines) + 10); w += -w % 4
            self.label(min(x - w // 2, XR - w), y + 8 if side == "below" else y - 8 - h, lines)

    def lane(self, kind, name, top, bottom):
        self.lanes.append((kind, name, top, bottom))

    # ── 조립 ──
    def svg(self, desc, head=True):
        """head=False 면 앞 장·장 제목·설명 줄을 빼고 그 높이만큼 viewBox 를 당긴다. 문서는 그 셋을 소제목과 본문으로 쓴다."""
        lane_bottom = max([b for *_, b in self.lanes] + [self.floor])
        H = lane_bottom + 20
        v = f"fb-p{self.n}"
        back = []
        if self.lanes:
            for i, (kind, name, top, bottom) in enumerate(self.lanes):
                cy = (top + bottom) / 2
                back.append(f'<g class="cell {kind} swatch"><rect class="shape" x="{LX}" y="{cy - 30:g}" width="14" height="14" rx="3"/></g>'
                            f'<text class="lane-name" x="{LX}" y="{cy:g}">{esc(name)}</text>')
                for yy in ([top] if i == 0 else []) + [bottom]:
                    back.append(self.rule(yy))
            back.append(f'<line class="rule" x1="{NAME_R}" y1="{self.lanes[0][2]}" x2="{NAME_R}" y2="{lane_bottom}"/>')
        top = 0 if head else HEAD_CUT
        head, show = [], head
        if show and self.prev:
            head.append(f'<text class="nav" x="{LX}" y="20">{esc("← 앞 장: " + self.prev)}</text>')
        if show:
            head.append(f'<text class="page-title" x="{LX}" y="46">{esc(f"{self.n}장 {self.title}")}</text>')
            head.append(f'<text class="lead" x="{LX}" y="68">{esc(self.lead)}</text>')
        mk = (f'<marker id="{v}-ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
              f'<path d="M0 0L10 5L0 10z" class="ah"/></marker>')
        body = "\n".join(head + back + self.zones + self.conns + self.labels + self.fore)
        title = f"{self.n}장 {self.title}"
        return (f'<svg class="page" id="{v}" viewBox="0 {top} {W} {H - top:g}" role="img" aria-labelledby="{v}-title {v}-desc">\n'
                f'<title id="{v}-title">{esc(title)}</title>\n<desc id="{v}-desc">{esc(desc)}</desc>\n'
                f'<defs>{mk}</defs>\n{body}\n</svg>'), H

    def rule(self, y):
        """줄 구분선."""
        return f'<line class="rule" x1="{LX}" y1="{y}" x2="{XR}" y2="{y}"/>'


# ── 강제 장치: (이름, 고정폭 여부, 장 아래 장치 설명) ──────────────────────
# 장치 설명은 라벨 목록 [(라벨, 문장 또는 (도입 문장, 항목))] 이다. 훅은 언제·막는 것·알리는 것·건너뛰는 경우,
# 스킬과 규칙은 언제·하는 일 가운데 그 장치에 있는 라벨만 쓴다. prose-check 만 표다.
G_ASK = ("전역 규칙\n「모호하면 먼저 질문」", F, [
    ("언제", "개발자가 아는 사실(진행 상황·완료 여부·범위·의도)이 모호할 때"),
    ("하는 일", "Claude가 코드나 문서를 찾아보기 전에 개발자에게 먼저 묻는다.")])
G_GRILL = ("grill-me ·\ngrill-with-docs", F, [
    ("언제", "Claude가 문서를 쓰거나 고치기 전"),
    ("하는 일", "Claude가 누가 읽을 문서인지부터 묻고 담을 내용을 캐묻는다. "
               "저장소 규칙 파일(CLAUDE.md)이 결정과 용어를 적은 문서를 따로 정했으면 grill-with-docs 로 그 문서와 대조해 묻는다.")])
G_DOCW = ("doc-writing", F, [
    ("언제", "Claude가 문서를 쓰거나 고칠 때"),
    ("하는 일", "문장·어휘·형식과 확인 절차의 규칙을 Claude에게 알려 준다.")])
G_DSG = ("doc-skill-guard.py", T, [
    ("언제", "Claude가 문서 파일을 쓰거나 고치기 전. 셸 명령으로 쓰는 것도 본다."),
    ("막는 것", "doc-writing 이나 이번 요청의 캐묻기 스킬을 부르지 않고 쓰면 그 쓰기를 막는다."),
    ("건너뛰는 경우", ("", [
        "개발자가 요청이나 질문 창 답에 「캐묻기 생략」을 따로 한 줄로 적으면 그 요청에서는 캐묻기 확인을 건너뛴다. doc-writing을 불렀는지는 그래도 확인한다.",
        "같은 세션에서 그 문서를 두고 캐물은 뒤에 고치면 캐묻기 확인을 건너뛴다."]))])
BLOCKED, NOTED = "Claude에게 오류로 알려 다시 고치게 한다", "Claude에게 참고로 알린다"
G_PROSE = ("prose-check.py", T, {
    "intro": "Claude가 .md·.html 문서를 쓰거나 고친 직후 마지막 커밋 뒤에 더한 줄만 검사한다. 파일 쓰기를 되돌리지 않고 Claude에게 알린다.",
    "head": ("검사", "예", "처리"),
    "rows": [("전각 대시로 두 문장 잇기", ["초안을 먼저 쓴다 — 그다음 고친다"], BLOCKED),
             ("표 칸 한 줄에 문장 두 개", ["막는다. 알린다."], BLOCKED),
             ("연결어미 뒤 쉼표", ["~지만,", "~는데,", "~하고,"], BLOCKED),
             ("질문형 제목", ["왜 훅인가?"], NOTED),
             ("제목 안의 개수", ["근거 문서 두 편"], NOTED),
             ("잦은 「~기 때문」", "열 문장에 두 번 이상", NOTED),
             ("명사와 헷갈리는 「~고,」", ["받고,"], NOTED)]})
G_CROSS = ("codex-cross-check", F, [
    ("언제", "개발자가 교차 검증을 요구할 때, 개발자의 리뷰에 답할 때, 공개 문서나 중요한 설계 판단의 최종안을 낼 때, 독자 테스트 피드백을 반영할지 정할 때"),
    ("하는 일", "Claude가 Codex의 남은 사용량(5시간·7일 한도)을 확인하고 이전 맥락을 모르는 새 작업으로 요청한다. "
               "결과는 답변에서만 보고하고 PR 댓글로 남기지 않는다.")])
G_RENDER = ("render-check.js", F, [
    ("언제", "슬라이드처럼 크기가 정해진 문서를 렌더해 확인할 때"),
    ("하는 일", "장마다 넘침·잘림·바닥 여백·겹침을 측정한다.")])
STATE_CMDS = "상태 확인 명령(git status·log·diff·branch·rev-parse, gh pr view·list·status)"
G_STATE = ("stop-check.py", T, [
    ("언제", "Claude가 답변을 끝내기 전"),
    ("막는 것", f"추천 명령에 스테이징·커밋·푸시·PR 명령이 있는데 이번 턴에 {STATE_CMDS}을 하나도 실행하지 않았으면 답변을 되돌린다.")])
G_CKPT = ("commit-checkpoint.py", T, [
    ("언제", "Claude가 셸 명령을 실행한 직후"),
    ("알리는 것", "Claude가 실행한 테스트·빌드가 통과했는데 이번 세션에서 고친 파일이 커밋되지 않고 남으면 "
                 "다음 사이클 RED 대신 체크포인트 보고를 내라고 Claude에게 지시한다.")])
G_ADD = ("git-guard.py", T, [
    ("언제", "Claude가 셸 명령을 실행하기 전"),
    ("막는 것", "git add -A, git add --all, git add . 을 막는다.")])
G_STOP = ("stop-check.py", T, [
    ("언제", "Claude가 답변을 끝내기 전"),
    ("막는 것", ("답변의 추천 명령이 아래에 해당하면 답변을 되돌린다.", [
        f"이번 턴에 {STATE_CMDS}을 하나도 실행하지 않고 스테이징·커밋·푸시·PR 명령을 냈다.",
        "이번 턴의 마지막 테스트가 실패했는데 스테이징·커밋·푸시·PR 명령을 냈다. 빈 커밋 명령은 뺀다.",
        "현재 대화에서 고친 문서를 새 파일이나 추가·삭제 합 50줄 이상으로 커밋하는데 마지막 수정 뒤에 그 문서의 독자 테스트를 끝까지 실행하지 않았다.",
        "커밋 메시지에 「검토:」 줄이 있는데 같은 명령 블록에 PR 댓글 주소가 없다.",
        "PR 댓글을 올리고 커밋 명령을 냈는데 git push 블록이 없다.",
        "개발자에게 cat·grep 같은 조회 명령으로 시작하는 블록을 줬다."])),
    ("건너뛰는 경우", "개발자가 마지막 메시지나 그 뒤 질문 창 답에 「독자 테스트 생략」을 따로 한 줄로 적으면 독자 테스트 확인을 건너뛴다.")])
G_FB = ("stop-check.py", T, [
    ("언제", "Claude가 커밋 명령을 낸 뒤 받은 요청에 답을 끝내기 전"),
    ("막는 것", "PR 댓글을 남길지 판단하지 않은 답변을 되돌린다. 판단했는지는 답변에 「댓글」이라는 말이 있는지나 댓글을 올렸는지로 본다.")])
G_CMT = ("git-guard.py", T, [
    ("언제", "Claude가 PR 댓글을 올리기 전"),
    ("막는 것", ("아래에 해당하면 댓글을 올리지 못하게 막는다.", [
        "푸시하지 않은 커밋이 있다.",
        "「변경 파일:」 줄에 없는 추적 파일에 커밋하지 않은 변경이 있다.",
        "「교차 검증 지적:」 줄이 있다.",
        "「사용자 피드백:」 줄이 둘 이상이다.",
        "결정 항목 줄 하나에 문장이 둘 이상이다."]))])
G_IJ = ("ij-debugger", F, [
    ("언제", "JVM 프로젝트의 앱을 IntelliJ IDEA 디버거로 띄워 확인할 때"),
    ("하는 일", "IDEA 디버그 실행·로그포인트·중단점으로 실제로 흐른 값과 분기를 본다. 로그포인트는 실행을 멈추지 않고 값만 기록하는 중단점이다. "
               "디버거 도구가 없으면 Claude가 그 사실을 먼저 알린다.")])
G_PONY = ("ponytail-review", F, [
    ("언제", "Claude가 브랜치의 변경 전체를 리뷰할 때"),
    ("하는 일", "diff 만 검토한다. 표준 라이브러리나 이미 설치된 의존성으로 대신할 수 있는 코드, 쓰지 않는 코드, 과한 추상화를 찾는다.")])
MEMO_COMMIT = "개발자가 실행하는 명령에는 훅이 적용되지 않는다. 명령은 체크포인트 보고에서 검사를 거쳤다."


def next_page(p, node, text):
    """마지막 노드에서 오른쪽으로 나가 다음 장 표시로 끝나는 진행 선."""
    n = p.N[node]
    p.edge([(n["r"], n["cy"]), (n["r"] + 32, n["cy"])], text, "right", "c")


# ── 1장 ───────────────────────────────────────────────────────────────
def page1():
    p = Page(1, "요청과 설계 · 요청 확정과 초안",
             "Claude가 모호한 사실과 독자를 먼저 묻고 개발자의 답으로 설계 문서 초안을 쓴다.", None)
    ai_nodes = [("ask", "먼저 질문", ["요청 범위·의도나 진행 상황이 모호하면", "코드나 문서를 찾아보기 전에 묻는다"], 192, 176, [G_ASK]),
                ("grill", "캐묻기", ["누가 읽을 문서인지와 담을 내용을 묻는다", "첫 질문은 독자"], 600, 144, [G_GRILL]),
                ("draft", "설계 문서 초안", "", 840, 176, [G_DOCW, G_DSG, G_PROSE])]
    dev_nodes = [("req", "dev", "요청", "작업 요청", 96, 128),
                 ("ans0", "dev", "답변", "진행 상황·범위·의도", 336, 128),
                 ("req2", "art", "확정된 요청", "범위가 정해진 요청", 504, 128),
                 ("ans1", "dev", "답변", "독자·범위", 672, 128)]
    top = LANE_TOP
    y = top + 24
    h = max(Page.height(t, d, w) for _, t, d, _, w, _ in ai_nodes)
    foot = max(y + h + (Page.tags_height(g, w) if g else 0) for _, t, d, x, w, g in ai_nodes)
    ai_bottom = foot + 24
    p.lane("ai", "Claude", top, ai_bottom)
    for nid, t, d, x, w, g in ai_nodes:
        p.box(nid, "ai", t, d, x, y, w, h, tags=g)
    y2 = ai_bottom + 24
    h2 = max(Page.height(t, d, w) for _, _, t, d, _, w in dev_nodes)
    for nid, kind, t, d, x, w in dev_nodes:
        p.box(nid, kind, t, d, x, y2, w, h2)
    p.lane("dev", "개발자", ai_bottom, y2 + h2 + 24)
    N = p.N
    # 요청 → 먼저 질문: 요청 위 면에서 올라가 질문 왼쪽 면으로
    p.conn([(N["req"]["cx"], N["req"]["y"]), (N["req"]["cx"], N["ask"]["cy"]), (N["ask"]["x"], N["ask"]["cy"])])
    # 먼저 질문 ⇄ 답변, 캐묻기 ⇄ 답변
    for a, b in (("ask", "ans0"), ("grill", "ans1")):
        A, B = N[a], N[b]
        p.conn([(A["r"], A["cy"] - 12), (A["r"] + 48, A["cy"] - 12), (A["r"] + 48, B["y"])])
        p.conn([(A["r"] + 16, B["y"]), (A["r"] + 16, A["cy"] + 12), (A["r"], A["cy"] + 12)], "c back")
    p.conn([(N["ans0"]["r"], N["ans0"]["cy"]), (N["req2"]["x"], N["req2"]["cy"])])
    # 확정된 요청 → 캐묻기, 답변 → 초안
    p.conn([(N["req2"]["cx"], N["req2"]["y"]), (N["req2"]["cx"], N["grill"]["cy"]), (N["grill"]["x"], N["grill"]["cy"])])
    A, B = N["ans1"], N["draft"]
    p.conn([(A["r"], A["cy"]), (A["r"] + 20, A["cy"]), (A["r"] + 20, B["cy"]), (B["x"], B["cy"])])
    next_page(p, "draft", "다음 장: 2장 독자 테스트 →")
    desc = ("1장. 개발자가 요청하면 Claude는 요청 범위·의도나 진행 상황이 모호할 때만 코드나 문서를 찾아보기 전에 먼저 묻는다. "
            "개발자가 답해 요청을 확정한다. "
            "Claude가 누가 읽을 문서인지와 어떤 내용을 담을지 캐묻고 개발자가 답한 뒤 Claude가 설계 문서 초안을 쓴다. "
            "초안에는 doc-writing, doc-skill-guard.py, prose-check.py 가 적용된다.")
    return p, desc


# ── 2장 ───────────────────────────────────────────────────────────────
def page2():
    p = Page(2, "설계 · 초안 검토와 확인",
             "Claude가 검토를 준비하고 Codex가 따로 답한다. Claude가 결과를 대조해 반영하고 실제 크기로 렌더해 확인한다.",
             "1장 설계 문서 초안")
    cx_nodes = [("reader", "독자 테스트",
                 ["문서 사본만 보고 질문에 답한다", "빠진 설명과 필요 없는 글을 찾는다", "새 문서나 추가·삭제 합이 50줄 이상인 문서 대상"], 128, 232, []),
                ("cross", "Codex 독립 검증", "Claude의 답을 모르는 채 같은 질문에 답한다", 488, 232, [G_CROSS]),
                ("reader2", "마지막 독자 테스트",
                 ["커밋 전에 마지막 수정본으로 한 번 더", "새 피드백이 없을 때까지 되풀이"], 1000, 224, [])]
    row1 = [("prep", "독자 테스트 준비",
             ["문서 사본만 둔 폴더를 만든다", "독자와 질문을 적어 이전 맥락을 모르는 새 작업으로 요청한다"], 128, 216, []),
            ("fix", "실제 결함만 수정", "교차 검증으로 정한 피드백만 고친다", 368, 168, []),
            ("pin", "Claude 답·근거 기록", ["질문에 먼저 답한다", "답과 근거를 파일로 남긴다"], 624, 200, []),
            ("merge2", "두 답 대조·반영", ["항목별로 대조한다", "맞는 반론만 반영한다"], 856, 232, [])]
    row2 = [("vocab", "어휘 대조", ["명사·동사·한자어 점검", "보통 쓰는 말인지"], 128, 216, []),
            ("human", "humanize 진단", ["AI 문체 패턴 검사", "진단에 나온 곳만 수정"], 376, 216, []),
            ("render", "렌더 확인", ["실제 크기로 렌더", "크기가 정해진 문서는 잘림·겹침 측정"], 624, 216, [G_RENDER])]

    def row(nodes, y, kind):
        h = max(Page.height(t, d, w) for _, t, d, _, w, _ in nodes)
        return max(p.box(nid, kind, t, d, x, y, w, h, tags=g) for nid, t, d, x, w, g in nodes)

    top = LANE_TOP
    cx_bottom = row(cx_nodes, top + 48, "codex") + 16   # 위 48 에 다음 장 선과 독립 검증으로 되돌아가는 선·라벨이 있다
    p.lane("codex", "Codex", top, cx_bottom)
    y1 = cx_bottom + 24
    f1 = row(row1, y1, "ai")
    y2 = f1 + 64                           # 행 사이에 어휘 대조로 가는 선과 그 위 「대상이 아니면」 라벨이 지난다
    f2 = row(row2, y2, "ai")
    yWrap, yBelow = (f1 + y2) / 2, f2 + 34
    yOut = yBelow + 12                     # 독자 테스트로 되돌아가는 선. 어휘 대조로 가는 선 바깥을 돈다
    p.lane("ai", "Claude", cx_bottom, yOut + 24)
    N = p.N
    R, C, R2 = N["reader"], N["cross"], N["reader2"]
    Pp, Fx, Pn, M = N["prep"], N["fix"], N["pin"], N["merge2"]
    V, Rd = N["vocab"], N["render"]
    p.conn([(320, Pp["y"]), (320, R["b"])])
    p.conn([(R["r"], R["cy"]), (Fx["x"] + 64, R["cy"]), (Fx["x"] + 64, Fx["y"])])
    # 고쳤으면 독자 테스트를 다시 한다. 수정 상자 왼쪽 면에서 나와 독자 테스트 아래 면으로 올라간다
    p.conn([(Fx["x"], Fx["cy"]), (352, Fx["cy"]), (352, R["b"])], "c back")
    p.label(360, R["b"] + 8, ["고쳤으면", "→ 다시"])
    # 수정한 뒤 교차 검증 대상인지 가른다. 대상이면 오른쪽, 아니면 아래로 내려가 어휘 대조로 가는 선에 합류한다
    p.conn([(Fx["r"], Fx["cy"]), (Pn["x"], Pn["cy"])])
    p.label(Fx["r"] + 4, Fx["cy"] - 44, ["교차 검증", "대상이면"])
    p.conn([(Fx["cx"], Fx["b"]), (Fx["cx"], yWrap)], "c", False)
    p.merge(Fx["cx"], yWrap)
    p.label(Fx["cx"] + 10, yWrap - 26, ["대상이 아니면"])
    # Claude 답을 기록한 뒤 결론을 빼고 Codex에 보낸다. 선은 독립 검증의 꼬리표 오른쪽으로 올라간다
    p.conn([(680, Pn["y"]), (680, C["b"])])
    p.label(688, (C["b"] + Pn["y"]) / 2 - 9, ["결론 없이 검증 요청"])
    xi, xb, yb = 872, 952, top + 28
    p.conn([(C["r"], C["cy"]), (xi, C["cy"]), (xi, M["y"])])
    # 두 답이 갈리면 대조에서 위쪽 통로로 올라가 독립 검증 위 면으로 되돌아간다
    p.conn([(xb, M["y"]), (xb, yb), (520, yb), (520, C["y"])], "c back")
    p.label(528, yb - 26, ["갈리면 → 근거와 통합안을 보내 다시 묻는다(두세 차례까지)"])
    p.conn([(M["cx"], M["b"]), (M["cx"], yWrap), (V["cx"], yWrap), (V["cx"], V["y"])])
    p.label(M["cx"] + 10, M["b"] + 4, ["대조를 마치면"])
    for a, b in (("vocab", "human"), ("human", "render")):
        p.conn([(N[a]["r"], N[a]["cy"]), (N[b]["x"], N[b]["cy"])])
    # 렌더 확인에서 나가는 셋. 라벨은 선이 시작하는 곳에 둔다
    # 되돌아가는 둘은 아래 면에서 나가 행 2 아래로 돈다. 독자 테스트로 가는 선이 바깥을 돌아 왼쪽 통로로 올라간다
    p.conn([(800, Rd["b"]), (800, yBelow), (V["cx"], yBelow), (V["cx"], V["b"])], "c back")
    p.label(790, Rd["foot"] + 8, ["산문을 고치면 → 어휘 대조부터 다시"], "end")
    p.conn([(824, Rd["b"]), (824, yOut), (104, yOut), (104, R["cy"]), (R["x"], R["cy"])], "c back")
    p.label(834, Rd["b"] + 8, ["의미·범위가 바뀌면 → 독자 테스트부터 다시"])
    # 통과하면 오른쪽 통로로 올라가 마지막 독자 테스트 아래 면으로 들어간다
    p.conn([(Rd["r"], Rd["cy"]), (1112, Rd["cy"]), (1112, R2["b"])])
    p.label(Rd["r"] + 10, Rd["cy"] - 26, ["통과 → 마지막 독자 테스트"])
    # 다음 장 선. 마지막 독자 테스트가 줄 오른쪽 끝이라 오른쪽에 라벨 자리가 없어 위 면에서 나간다
    p.edge([(R2["x"] + 24, R2["y"]), (R2["x"] + 24, top + 16)], "다음 장: 3장 설계 문서 →", "right", "c")
    desc = ("2장. Claude가 문서 사본만 둔 폴더를 만들고 독자와 질문을 적어 독자 테스트를 준비한다. "
            "Codex가 사본만 보고 질문에 답하고 빠진 설명과 필요 없는 글을 찾는다. 반영할 피드백은 Claude와 Codex가 교차 검증으로 정하고 Claude가 고친다. "
            "고쳤으면 독자 테스트를 다시 하고 새 피드백이 없을 때까지 되풀이한다. "
            "교차 검증 대상이면 Claude가 질문에 먼저 답하고 답과 근거를 파일로 남긴 뒤 결론 없이 검증을 요청한다. "
            "Codex는 Claude의 답을 모르는 채 같은 질문에 답하고 Claude가 두 답을 항목별로 대조해 맞는 반론만 반영한다. "
            "두 답이 갈리면 근거와 통합안을 보내 다시 묻는다. 두세 차례에도 합의하지 못하면 개발자가 정한다. "
            "교차 검증 대상이 아니거나 대조를 마치면 Claude가 어휘 대조, humanize 진단, 렌더 확인을 이어서 한다. "
            "렌더 확인을 통과하면 Codex가 마지막 독자 테스트를 하고 3장으로 간다. "
            "렌더 확인에서 산문을 고치면 어휘 대조부터, 의미나 범위가 바뀌면 독자 테스트부터 다시 한다. "
            "독자 테스트 대상 문서는 커밋하기 전에 마지막 수정본으로 독자 테스트를 한 번 더 실행한다. "
            "이 테스트의 피드백도 같은 방식으로 반영하고 새 피드백이 없을 때까지 되풀이한다. 개발자는 그 뒤 최종 문서를 리뷰한다.")
    return p, desc


# ── 3장 ───────────────────────────────────────────────────────────────
def page3():
    p = Page(3, "설계 · 이해·토론과 드래프트 PR",
             "개발자가 이해한 설계 문서만 구현으로 넘긴다. 그 뒤 Claude가 드래프트 PR을 먼저 여는 명령을 낸다.", "2장 마지막 독자 테스트")
    top = LANE_TOP
    y = top + 56                           # 위 56 에 4·5장과 6장에서 들어오는 선 둘이 지난다
    p.box("doc", "art", "설계 문서", "검토와 렌더 확인을 마친 문서", 128, y, 144)
    p.box("explain", "ai", "설명·설계 문서 수정", ["개발자의 질문에 답한다", "필요하면 설계 문서를 고친다"], 320, y, 192)
    pb = p.box("prcmd", "ai", "브랜치·드래프트 PR 명령 제시", ["빈 커밋으로 브랜치 시작", "드래프트 PR을 먼저 연다"], 544, y, 176, tags=[G_STOP])
    ai_bottom = max(p.N["doc"]["b"], p.N["explain"]["b"], pb) + 24
    p.lane("ai", "Claude", top, ai_bottom)
    y2 = ai_bottom + 24
    gf = p.box("gate1", "dev", "이해·토론", ["설계 문서를 읽고 묻는다", "이해했는지 확인한다"], 128, y2, 272,
               memo="고친 설계 문서는 커밋 전에 마지막 독자 테스트를 다시 거친다. 의미나 범위가 바뀌었으면 2장 독자 테스트부터 다시 한다.")
    run = [("prrun", "실행", "추천 명령 실행", 672, 128),
           ("doccommit", "설계 문서 첫 커밋", ["첫 브랜치에서만. 다음 브랜치는 바로 4장 RED", "구현이 여러 작업으로 나뉘면 이 브랜치를 먼저 병합하고 구현 브랜치를 새로 연다"], 832, 232)]
    h2 = max(Page.height(t, d, w) for _, t, d, _, w in run)   # 같은 높이라야 둘 사이 선이 꺾이지 않는다
    for nid, t, d, x, w in run:
        p.box(nid, "dev", t, d, x, y2, w, h2)
    N = p.N
    D, E, G, P, Q, C = N["doc"], N["explain"], N["gate1"], N["prcmd"], N["prrun"], N["doccommit"]
    p.lane("dev", "개발자", ai_bottom, max(gf, C["b"]) + 24)
    p.conn([(D["cx"], D["b"]), (D["cx"], G["y"])])
    # 이해·토론 고리. 개발자가 묻고 Claude가 설명하거나 고친 뒤 개발자가 다시 확인한다
    p.conn([(336, G["y"]), (336, E["b"])])
    p.label(328, (E["b"] + G["y"]) / 2 - 9, ["이해하지 못하면"], "end")
    p.conn([(384, E["b"]), (384, G["y"])], "c back")
    p.conn([(G["r"], G["cy"]), (528, G["cy"]), (528, P["cy"]), (P["x"], P["cy"])])
    p.label(G["r"] + 8, G["cy"] + 8, ["이해하면"])
    p.conn([(P["r"], P["cy"]), (Q["cx"], P["cy"]), (Q["cx"], Q["y"])])
    # 다른 장에서 들어오는 선 둘. 4·5장의 설계 허점은 토론으로, 6장의 다음 브랜치는 브랜치 명령으로 온다
    p.conn([(XR, top + 12), (E["cx"], top + 12), (E["cx"], E["y"])], "c back")
    p.label(XR, top - 14, ["4·5장에서 설계 허점이면 → 토론 뒤 원래 장으로"], "end")
    p.conn([(XR, top + 36), (P["cx"], top + 36), (P["cx"], P["y"])], "c back")
    p.label(XR, top + 44, ["6장에서 병합한 뒤 다음 브랜치면"], "end")
    p.conn([(Q["r"], Q["cy"]), (C["x"], Q["cy"])])
    next_page(p, "doccommit", "다음 장: 4장 RED →")
    desc = ("3장. 검토와 렌더 확인을 마친 설계 문서를 개발자가 읽고 Claude와 토론한다. "
            "개발자가 이해하지 못하면 묻고 Claude가 설명하거나 설계 문서를 고친다. 개발자는 이해했는지 다시 확인한다. "
            "고친 설계 문서는 커밋 전에 마지막 독자 테스트를 다시 거친다. 의미나 범위가 바뀌었으면 2장 독자 테스트부터 다시 한다. "
            "4장·5장에서 설계 허점을 찾아도 이 토론으로 오고 토론이 끝나면 원래 장으로 돌아간다. "
            "이해하면 Claude가 빈 커밋으로 브랜치를 시작하고 드래프트 PR을 먼저 여는 명령을 내고 개발자가 실행한다. "
            "첫 브랜치에서는 그 뒤 개발자가 설계 문서를 첫 실제 커밋으로 올리고 4장 RED로 간다. 6장에서 돌아온 다음 브랜치는 빈 커밋 뒤에 바로 4장 RED로 간다. "
            "구현이 여러 작업으로 나뉘면 이 브랜치를 먼저 병합하고 구현 브랜치를 새로 연다. "
            "6장에서 브랜치를 병합한 뒤 다음 브랜치가 있으면 브랜치 명령부터 다시 한다.")
    return p, desc


# ── 4장 ───────────────────────────────────────────────────────────────
def page4():
    p = Page(4, "구현 · TDD 사이클과 리뷰",
             "Claude가 RED와 GREEN을 이어서 진행하고 개발자가 사이클마다 한 번 리뷰한다. 문서는 마지막 사이클 뒤에 한 번 갱신한다. "
             "판단은 마름모, 색은 주체다.",
             "3장 설계 문서 첫 커밋")
    R1, R2, LEGEND = 724, 740, 784               # 되돌아감 레일 둘, 범례 기준선
    P1, P4, P5, P6, P7 = 24, 432, 456, 760, 728  # 세로 통로. P5 는 리뷰 열 왼쪽, P7 은 리뷰 열 오른쪽
    p.floor = LEGEND - 4                         # svg() 가 20 을 더해 그림 높이 800
    for x, name in ((160, "TDD 사이클"), (488, "리뷰"), (784, "피드백 반영")):
        p.zones.append(f'<text class="stage" x="{x}" y="104">{esc(name)}</text>')
    for x in (420, 748):
        p.zones.append(f'<line class="rule" x1="{x}" y1="112" x2="{x}" y2="{R1 - 20}"/>')
    N = p.N
    # ① TDD 사이클
    p.box("red", "ai", "RED", ["실패하는 테스트 하나", "실패 확인"], 160, 124, 248)
    p.box("green", "ai", "GREEN", "그 테스트를 통과시키는 최소 구현", 160, N["red"]["b"] + 32, 248, tags=[G_CKPT])
    p.box("ckpt", "ai", "체크포인트 보고",
          ["작업 내역·진행 표", "경로를 적은 스테이징", "단계별 추천 커밋 명령 [Test]·[Feat]·[Refactor]"],
          160, N["green"]["foot"] + 32, 248, tags=[G_ADD, G_STOP])
    # ② 리뷰
    p.box("rev", "dev", "리뷰", "사이클이 끝난 뒤 한 번", 488, 124, 248)
    # 폭을 줄여 왼쪽 꼭지점과 체크포인트 보고에서 올라가는 선 사이에 설계 허점 라벨 자리를 만든다
    p.diamond("dpass", "dev", "통과인가", 612, N["rev"]["b"] + 44, 152)
    p.box("commit", "dev", "커밋", ["추천 명령으로 단계별 커밋", "PR 댓글이 있는 보고면 푸시까지"], 488, N["dpass"]["b"] + 48, 248)
    p.diamond("dlast", "ai", "마지막 사이클인가", 612, N["commit"]["foot"] + 44, 192)
    # 폭을 줄여 오른쪽에 다음 사이클로 돌아가는 통로(P7)를 둔다
    p.box("docsync", "ai", "문서 갱신", ["설계 문서·README 에 한 번에 반영한다", "[Docs] 커밋 명령은 5장 보고에서"],
          488, N["dlast"]["b"] + 44, 224)
    # ③ 피드백 반영. 마름모 폭을 줄여야 옆 꼭지점에서 아래 상자 가운데까지 꺾을 거리가 생긴다
    p.box("judge", "ai", "PR 댓글 작성 여부 판단", "방향이 바뀌었는지 먼저 정한다", 880, 124, 248, tags=[G_FB])
    p.diamond("dturn", "ai", "방향이 바뀌었나", 1004, N["judge"]["foot"] + 44, 176)
    y = N["dturn"]["b"] + 52
    p.box("keep", "ai", "피드백 반영 수정 · REFACTOR", "구조·중복 피드백이면 REFACTOR", 784, y, 208)
    p.box("amend", "ai", "반영 수정 · PR 댓글 작성",
          ["쌓인 커밋이 있으면 푸시 명령부터", "바뀐 결정을 다섯 줄로 요약", "바뀐 방향으로 수정"], 1016, y, 208, tags=[G_CMT])
    # 두 갈래가 만난 뒤 판단한다. 방향 유지 갈래가 곧게 내려와 위 꼭지점에 닿도록 가운데를 그 선에 맞춘다
    yj = N["amend"]["foot"] + 48                 # 합류점. 방향 변경 갈래의 라벨 아래
    p.diamond("dfrom", "ai", "인수 확인에서 온 수정인가", N["keep"]["r"] - 64, yj + 32, 240)
    Rd, Gr, K = (N[k] for k in ("red", "green", "ckpt"))
    Rv, Dp, Co, Dl, Ds = (N[k] for k in ("rev", "dpass", "commit", "dlast", "docsync"))
    Ju, Dt, Kp, Am, Df = (N[k] for k in ("judge", "dturn", "keep", "amend", "dfrom"))
    # 전진(실선)
    p.conn([(Rd["cx"], Rd["b"]), (Rd["cx"], Gr["y"])])
    p.conn([(Gr["r"] - 40, Gr["b"]), (Gr["r"] - 40, K["y"])])
    p.conn([(K["r"], K["cy"]), (P4, K["cy"]), (P4, Rv["cy"]), (Rv["x"], Rv["cy"])])
    p.conn([(Rv["cx"], Rv["b"]), (Rv["cx"], Dp["y"])])
    p.conn([(Dp["cx"], Dp["b"]), (Dp["cx"], Co["y"])])
    p.label(Dp["cx"] + 10, (Dp["b"] + Co["y"]) / 2 - 9, ["통과"])
    p.conn([(Co["cx"], Co["b"]), (Co["cx"], Dl["y"])])
    p.conn([(Dl["cx"], Dl["b"]), (Dl["cx"], Ds["y"])])
    p.label(Dl["cx"] - 10, Dl["b"] + 8, ["맞다 → 문서 갱신"], "end")
    p.conn([(Dp["r"], Dp["cy"]), (P6, Dp["cy"]), (P6, Ju["cy"]), (Ju["x"], Ju["cy"])])
    p.label(P6 + 10, (Ju["cy"] + Dp["cy"]) / 2 - 18, ["미통과 ·", "수정 요청"])
    p.conn([(XR, 100), (Ju["cx"] + 60, 100), (Ju["cx"] + 60, Ju["y"])], "c back")
    p.label(XR, 74, ["5장 리뷰에서 피드백이면"], "end")
    # 꼬리표 오른쪽으로 내려와 꼬리표 아래에서 마름모 위 꼭지점으로 꺾는다
    ym = (Ju["foot"] + Dt["y"]) / 2
    p.conn([(Ju["r"] - 40, Ju["b"]), (Ju["r"] - 40, ym), (Dt["cx"], ym), (Dt["cx"], Dt["y"])])
    p.conn([(Dt["x"], Dt["cy"]), (Kp["cx"], Dt["cy"]), (Kp["cx"], Kp["y"])])
    p.label(Kp["cx"] - 10, Dt["cy"] + 8, ["방향 유지"], "end")
    p.conn([(Dt["r"], Dt["cy"]), (Am["cx"], Dt["cy"]), (Am["cx"], Am["y"])])
    p.label(Am["cx"] + 10, Dt["cy"] + 8, ["방향이 바뀌면"])
    # 방향 유지와 방향 변경 두 갈래가 합류점에서 만나 판단으로 간다. 방향 유지 갈래가 곧게 내려가고 방향 변경 갈래가 합류한다
    kx, ax, ux = Df["cx"], Am["r"] - 40, K["r"] - 64    # ux 는 문서 갱신에서 5장으로 나가는 라벨 왼쪽
    p.conn([(kx, Kp["b"]), (kx, Df["y"])])
    p.conn([(ax, Am["b"]), (ax, yj), (kx, yj)], "c", False)
    p.merge(kx, yj)
    p.label(ax - 10, Am["foot"] + 16, ["커밋 명령에 검토 줄 · 푸시 명령을 더해"], "end")
    # 되돌아감(점선). 체크포인트 보고로는 아래 면으로 들어간다. 라벨은 선이 시작하는 곳에 둔다
    p.conn([(kx, Df["b"]), (kx, R1), (ux, R1), (ux, K["b"])], "c back")
    p.label(kx - 10, Df["b"] + 8, ["아니다 → 체크포인트 보고"], "end")
    # 마지막 사이클이 아니면 다음 사이클 RED 로. 오른쪽 꼭지점에서 나가 리뷰 열 오른쪽 통로로 내려간다
    p.conn([(Dl["r"], Dl["cy"]), (P7, Dl["cy"]), (P7, R2), (P1, R2), (P1, Rd["cy"]), (Rd["x"], Rd["cy"])], "c back")
    p.label(Dl["r"] + 4, Dl["cy"] - 26, ["아니다 → 다음 사이클 RED"])
    p.bridge(P7, R1)
    # 다른 장으로 나가는 선(점선). 첫 꺾임 뒤 40 에서 끝내고 선 끝에는 장 번호만 둔다
    p.edge([(Ds["x"], Ds["cy"]), (P5, Ds["cy"]), (P5, Ds["cy"] + 40)], "5장", "below")
    p.label(Ds["x"] - 10, Ds["cy"] - 26, ["→ 5장 인수 확인"], "end")
    p.edge([(Dp["x"], Dp["cy"]), (P5, Dp["cy"]), (P5, Dp["cy"] + 40)], "3장", "below")
    # 가로 구간 위. 왼쪽은 체크포인트 보고에서 올라가는 선, 오른쪽은 마름모 변이다
    p.label(P4 + 10, Dp["cy"] - 44, ["설계 허점이면", "→ 3장 토론"])
    p.edge([(Df["r"], Df["cy"]), (Df["r"] + 60, Df["cy"]), (Df["r"] + 60, Df["cy"] + 40)], "5장", "below")
    p.label(Df["r"] + 4, Df["cy"] - 26, ["맞다 → 5장 인수 확인 다시"])
    # 범례 띠
    flow_legend(p, LEGEND, ((16, "ai", "Claude"), (136, "dev", "개발자"), (264, "decision", "판단"), (368, "merge", "갈래가 다시 만나는 곳")))
    p.notes.append(("", "개발자 커밋", F, (MEMO_COMMIT, [])))
    p.notes.append(("", "PR 댓글 규칙", F, ("", [
        "Claude가 gh pr comment 로 올린다.",
        "댓글을 올리기 전에 개발자가 쌓인 커밋을 먼저 푸시한다. 쌓인 커밋을 댓글 뒤에 함께 푸시하면 모두 댓글 아래에 붙어 어느 커밋이 결정을 반영했는지 구분할 수 없다.",
        "댓글 뒤의 수정 커밋은 푸시까지 한다. 그래야 PR 타임라인에서 댓글 아래에 그 커밋이 붙는다.",
        "댓글이 없는 커밋은 모아 두었다가 다음 PR 댓글을 올리기 전이나 병합하기 전에 푸시한다.",
        "첫 줄은 어느 작업에서 나온 피드백인지 적는다. 그 아래는 다섯 줄이다: 1차 AI 결정 / 사용자 피드백 / 2차 AI 결정(피드백 반영) / 2차 AI 결정 근거 / 변경 파일.",
        "줄마다 한 문장으로 쓰고 변경 파일은 이름만 적는다.",
        "피드백이 여러 건이면 건마다 따로 올린다.",
        "댓글로 남긴 결정이 다시 바뀌면 후속 댓글을 남긴다. 첫 줄은 어느 결정이 바뀌었는지 적고 그 아래는 다섯 줄이다: 직전 결정 / 다시 바뀐 계기 / 새 결정 / 새 결정 근거 / 변경 파일.",
        "방향을 바꾼 커밋은 메시지 본문 첫 줄을 「검토:」로 시작해 무엇이 어떻게 바뀌었는지 적고 댓글 주소를 단다.",
        "Claude가 낸 선택지를 고른 것은 댓글로 남기지 않는다. 다만 앞서 댓글로 남긴 결정이 다시 바뀌면 남긴다.",
        "Codex 교차 검증 결과는 댓글로 남기지 않는다."])))
    desc = ("4장. 3장에서 브랜치를 연 뒤에 이 장이 시작된다. "
            "Claude가 RED와 GREEN을 이어서 하고 GREEN에서 멈춰 체크포인트 보고를 낸다. "
            "개발자가 사이클마다 한 번 리뷰한다. "
            "통과하면 개발자가 커밋하고 PR 댓글이 있는 보고면 푸시까지 한다. "
            "브랜치의 마지막 사이클이 아니면 다음 사이클 RED로 간다. "
            "마지막 사이클이면 Claude가 브랜치의 사이클을 한 번에 반영해 설계 문서와 README 같은 저장소 문서를 갱신한다. 그 뒤 5장 인수 확인으로 간다. "
            "문서 갱신의 [Docs] 커밋 명령은 5장 체크포인트 보고에 들어간다. "
            "리뷰에서 설계 허점을 찾으면 3장 토론으로 간다. "
            "미통과로 수정을 요청받으면 Claude가 PR 댓글 작성 여부를 먼저 판단한다. 5장 리뷰에서 나온 피드백도 여기로 온다. "
            "방향이 바뀌면 개발자가 쌓인 커밋을 먼저 푸시하고 Claude가 PR 댓글을 올린 뒤 수정한다. "
            "방향을 유지하면 피드백 반영 수정이나 REFACTOR를 한다. "
            "5장 인수 확인에서 온 수정이면 5장으로 돌아가 인수 확인을 다시 한다. "
            "아니면 체크포인트 보고로 돌아가 다시 리뷰를 받는다. "
            "방향이 바뀐 보고의 커밋 명령에는 검토 줄과 댓글 주소, 푸시 명령이 붙는다.")
    return p, desc


# ── 5장 ───────────────────────────────────────────────────────────────
def page5():
    p = Page(5, "인수 확인 · 앱 기동과 결과 리뷰",
             "문서 갱신까지 마치면 앱을 기동해 운영과 같은 경로로 호출한다. 결과와 문서 커밋 명령을 담은 보고를 개발자가 리뷰하고 커밋한다.",
             "4장 문서 갱신 · 4장 반영 수정(인수 확인에서 온 수정이면)")
    ai = [("boot", "IntelliJ 디버거로 앱 기동",
           ["JVM 프로젝트에서 IDEA 디버거 도구를 쓸 수 있을 때. 아니면 일반 기동", "개발자가 보는 IDE 화면에 Claude 작업 표시", "DB·외부 의존은 일회용 컨테이너"],
           128, 208, [G_IJ]),
          ("call", "HTTP·CLI 호출", "정상·경계·거부·오류 응답", 368, 184, []),
          ("dbg", "로그포인트·중단점", ["디버거로 띄웠을 때", "테스트가 단언하지 않는 값·분기"], 584, 168, []),
          ("stop", "정지", "프로세스·컨테이너", 784, 128, []),
          ("ckpt5", "체크포인트 보고",
           ["인수 확인 결과를 항목별로", "호출한 주소·응답 코드·본문", "디버거로 본 값", "경로를 적은 스테이징", "[Docs]·수정 커밋 명령"],
           944, 280, [G_ADD, G_STOP])]
    dev = [("watch", "IntelliJ 화면 확인",
            ["디버거로 띄웠을 때", "Claude가 기동부터 정지까지 진행하는 인수 확인 과정을 IDE 화면에서 직접 확인"], 128, 296),
           ("rev5", "리뷰", "인수 확인 결과와 코드 검토", 456, 148),
           ("commit5", "커밋", ["추천 명령으로 단계별 커밋", "PR 댓글이 있는 보고면 푸시까지"], 640, 208)]
    top = LANE_TOP
    y = top + 24
    h = max(Page.height(t, d, w) for _, t, d, _, w, _ in ai)
    ai_bottom = max(p.box(nid, "ai", t, d, x, y, w, h, tags=g) for nid, t, d, x, w, g in ai) + 24
    p.lane("ai", "Claude", top, ai_bottom)
    yE = ai_bottom + 24
    h2 = max(Page.height(t, d, w) for _, t, d, _, w in dev)
    fE = max(p.box(nid, "dev", t, d, x, yE, w, h2) for nid, t, d, x, w in dev)
    N = p.N
    K, Bt, Wt, Rv, Co = (N[k] for k in ("ckpt5", "boot", "watch", "rev5", "commit5"))
    gCE = (ai_bottom + yE) / 2
    for a, b in (("boot", "call"), ("call", "dbg"), ("dbg", "stop"), ("stop", "ckpt5"), ("rev5", "commit5")):
        p.conn([(N[a]["r"], N[a]["cy"]), (N[b]["x"], N[b]["cy"])])
    p.label(Co["x"], Rv["cy"] - 26, ["통과"], "end")
    # 체크포인트 보고 → 리뷰. 꼬리표를 오른쪽으로 피해 내려간다
    p.conn([(1100, K["b"]), (1100, gCE), (Rv["cx"], gCE), (Rv["cx"], Rv["y"])])
    p.conn([(Bt["x"], Bt["cy"]), (112, Bt["cy"]), (112, Wt["cy"]), (Wt["x"], Wt["cy"])], "c back", False)
    # 리뷰에서 나가는 둘. 라벨은 선이 시작하는 곳에, 선 끝에는 장 번호만 둔다
    ya = fE + 40
    xa, xb = Rv["x"] + round(Rv["w"] / 3), Rv["x"] + round(Rv["w"] * 2 / 3)
    p.edge([(xa, Rv["b"]), (xa, ya)], "4장", "below")
    p.label(xa - 10, Rv["b"] + 8, ["피드백이면 → 4장 PR 댓글 작성 여부 판단"], "end")
    p.edge([(xb, Rv["b"]), (xb, ya)], "3장", "below")
    p.label(xb + 10, Rv["b"] + 8, ["설계 허점이면 → 3장 토론"])
    next_page(p, "commit5", "다음 장: 6장 전체 검토 →")
    p.lane("dev", "개발자", ai_bottom, ya + 8 + 18 + 24)
    desc = ("5장. 문서 갱신까지 마치면 Claude가 앱을 기동한다. "
            "JVM 프로젝트에서 IDEA 디버거 도구를 쓸 수 있으면 IntelliJ 디버거로 띄우고 아니면 일반 기동한다. "
            "DB 와 외부 의존은 일회용 컨테이너로 띄운다. HTTP·CLI 로 정상·경계·거부·오류 응답을 호출한다. "
            "디버거로 띄웠으면 로그포인트·중단점으로 테스트가 단언하지 않는 값도 보고 개발자는 같은 과정을 IntelliJ 화면에서 나란히 확인한다. "
            "끝나면 프로세스와 컨테이너를 정지한다. "
            "Claude가 인수 확인 결과를 항목별로 적은 체크포인트 보고를 내고 개발자가 리뷰한다. "
            "체크포인트 보고에는 4장에서 갱신한 문서의 [Docs] 커밋 명령도 들어간다. "
            "통과하면 커밋하고 6장 전체 검토로 간다. 브랜치 하나가 작업 하나를 담으므로 인수 확인 뒤에 남은 사이클은 없다. "
            "피드백이면 4장 PR 댓글 작성 여부 판단으로 간다. 설계 허점을 찾으면 3장 토론으로 간다. "
            "피드백을 반영하면 커밋하기 전에 5장으로 돌아와 인수 확인을 다시 한다. "
            "그 뒤 체크포인트 보고와 리뷰를 거쳐 커밋한다.")
    return p, desc


# ── 6장 ───────────────────────────────────────────────────────────────
def flow_legend(p, y, items):
    """플로차트 장의 범례 띠. items 는 (x, 종류, 이름) 목록이다."""
    p.fore.append(f'<line class="rule" x1="{LX}" y1="{y - 18}" x2="{XR}" y2="{y - 18}"/>')
    sy = y - 4
    for x, kind, text in items:
        if kind == "decision":
            sw = f'<path class="swatch-decision" d="M{x + 7} {sy - 7} L{x + 14} {sy} L{x + 7} {sy + 7} L{x} {sy} Z"/>'
        elif kind == "merge":
            sw = f'<circle class="merge" cx="{x + 7}" cy="{sy}" r="4"/>'
        else:
            sw = f'<g class="cell {kind} swatch"><rect class="shape" x="{x}" y="{sy - 7}" width="14" height="14" rx="3"/></g>'
        p.fore.append(sw + f'<text class="legend" x="{x + 22}" y="{y}">{esc(text)}</text>')


def page6():
    p = Page(6, "전체 검토·반영·병합",
             "개발자가 Claude 리뷰와 자체 리뷰를 대조해 반영할 피드백을 정한다. Claude가 반영하고 인수 확인과 리뷰를 다시 거쳐 병합한다. "
             "판단은 마름모, 색은 주체다.",
             "5장 커밋")
    TOP, RAIL, LEGEND = 136, 116, 796            # 상자 위 끝, 반영할 피드백이 없을 때 지나는 위 통로, 범례 기준선
    XA, XK, XF, XD = 396, 674, 908, 934           # 세로 통로. XF 는 피드백, XD 는 커밋에서 PR 본문으로 가는 선
    p.floor = LEGEND - 4                          # svg() 가 20 을 더해 그림 높이 812
    for x, name in ((32, "전체 검토"), (412, "반영"), (702, "리뷰"), (950, "병합")):
        p.zones.append(f'<text class="stage" x="{x}" y="100">{esc(name)}</text>')
    for x in (382, 688, 921):
        p.zones.append(f'<line class="rule" x1="{x}" y1="128" x2="{x}" y2="{LEGEND - 30}"/>')
    N = p.N
    # ① 전체 검토. 두 리뷰를 나란히 두고 대조에서 모은다
    h = max(Page.height("Claude 리뷰", "변경 전체 검토", 176), Page.height("자체 리뷰", "놓친 예외를 가장 깊게", 144))
    p.box("airev", "ai", "Claude 리뷰", "변경 전체 검토", 32, TOP, 176, h, tags=[G_PONY])
    p.box("selfrev", "dev", "자체 리뷰", "놓친 예외를 가장 깊게", 224, TOP, 144, h)
    p.box("cmp", "dev", "Claude 리뷰와 자체 리뷰 대조", "반영할 피드백을 정한다", 80, N["airev"]["foot"] + 40, 240)
    p.diamond("dpick", "dev", "반영할 피드백이 있나", N["cmp"]["cx"], N["cmp"]["b"] + 44, 200)
    # ② 반영
    p.box("judge6", "ai", "PR 댓글 작성 여부 판단 ·\n필요하면 작성",
          ["방향이 바뀌었는지 먼저 정한다", "바뀌면 쌓인 커밋 푸시 명령을 먼저 내고 PR 댓글을 올린다"], 412, TOP, 248, tags=[G_FB])
    p.box("apply", "ai", "피드백 반영 · 인수 확인 다시", ["개발자가 정한 피드백을 고친다", "5장 절차로 앱을 띄워 다시 확인한다"],
          412, N["judge6"]["foot"] + 40, 248)
    p.box("ckpt6", "ai", "체크포인트 보고", ["반영 내역과 인수 확인 결과", "경로를 적은 스테이징", "단계별 추천 커밋 명령"],
          412, N["apply"]["b"] + 40, 248, tags=[G_ADD, G_STOP])
    # ③ 리뷰. 위를 비워 피드백 선이 PR 댓글 판단으로 지나갈 자리를 둔다
    p.box("rev6", "dev", "리뷰", "반영 결과 검토", 702, 200, 192)
    p.diamond("dpass6", "dev", "통과인가", N["rev6"]["cx"], N["rev6"]["b"] + 44, 152)
    p.box("commit6", "dev", "커밋 · 푸시", ["추천 명령으로 커밋", "PR 댓글이 있으면 푸시까지"], 702, N["dpass6"]["b"] + 48, 192)
    # ④ 병합
    p.box("body", "ai", "PR 본문 · 병합 명령", ["작업 내용", "검토에서 바뀐 것", "인수 확인 결과", "드래프트 해제·스쿼시 병합 명령 제시"],
          950, TOP, 232, tags=[G_STATE])
    p.box("mrun", "dev", "실행", "추천 명령 실행", 950, N["body"]["foot"] + 36, 232)
    p.diamond("dnext", "ai", "다음 브랜치가 있나", N["mrun"]["cx"], N["mrun"]["b"] + 40, 168)
    p.box("fullrev", "dev", "기능 전체 검토", ["설계 문서의 모든 브랜치를 병합한 뒤", "Claude 리뷰와 자체 리뷰를 대조한다"],
          950, N["dnext"]["b"] + 40, 232)
    p.diamond("dfix", "dev", "반영할 피드백이 있나", N["fullrev"]["cx"], N["fullrev"]["b"] + 40, 200)
    A, S, C, D1 = (N[k] for k in ("airev", "selfrev", "cmp", "dpick"))
    J, Ap, K, Rv, D2, Co = (N[k] for k in ("judge6", "apply", "ckpt6", "rev6", "dpass6", "commit6"))
    B, M, D3, Fr, D4 = (N[k] for k in ("body", "mrun", "dnext", "fullrev", "dfix"))
    # 전진(실선). Claude 리뷰는 꼬리표 오른쪽으로 내려간다
    p.conn([(A["r"] - 16, A["b"]), (A["r"] - 16, C["y"])])
    p.conn([(S["cx"], S["b"]), (S["cx"], C["y"])])
    p.conn([(C["cx"], C["b"]), (C["cx"], D1["y"])])
    p.conn([(D1["r"], D1["cy"]), (XA, D1["cy"]), (XA, J["cy"]), (J["x"], J["cy"])])
    p.label(D1["r"] + 4, D1["cy"] - 26, ["있으면"])
    # 반영할 피드백이 없으면 왼쪽 끝과 위 통로를 돌아 PR 본문으로 간다. 라벨은 선이 시작하는 곳 위에 둔다
    p.conn([(D1["x"], D1["cy"]), (20, D1["cy"]), (20, RAIL), (B["cx"], RAIL), (B["cx"], B["y"])])
    p.label(D1["x"] - 4, D1["cy"] - 44, ["없으면 →", "PR 본문"], "end")
    p.conn([(J["r"] - 40, J["b"]), (J["r"] - 40, Ap["y"])])
    p.conn([(Ap["cx"], Ap["b"]), (Ap["cx"], K["y"])])
    p.conn([(K["r"], K["cy"]), (XK, K["cy"]), (XK, Rv["cy"]), (Rv["x"], Rv["cy"])])
    p.conn([(Rv["cx"], Rv["b"]), (Rv["cx"], D2["y"])])
    p.conn([(D2["cx"], D2["b"]), (D2["cx"], Co["y"])])
    p.label(D2["cx"] + 10, (D2["b"] + Co["y"]) / 2 - 9, ["통과"])
    p.conn([(Co["r"], Co["cy"]), (XD, Co["cy"]), (XD, 200), (B["x"], 200)])
    p.conn([(B["r"] - 40, B["b"]), (B["r"] - 40, M["y"])])
    p.conn([(M["cx"], M["b"]), (M["cx"], D3["y"])])
    p.conn([(D3["cx"], D3["b"]), (D3["cx"], Fr["y"])])
    p.label(D3["cx"] + 10, (D3["b"] + Fr["y"]) / 2 - 9, ["없으면"])
    p.conn([(Fr["cx"], Fr["b"]), (Fr["cx"], D4["y"])])
    # 되돌아감(점선). 피드백은 리뷰 위의 빈 자리를 지나 PR 댓글 판단 오른쪽 면으로 들어간다
    # 출구 옆은 커밋에서 PR 본문으로 가는 선과 실행 상자가 차지해 라벨은 리뷰와 마름모 사이, 세로 구간 왼쪽에 둔다
    p.conn([(D2["r"], D2["cy"]), (XF, D2["cy"]), (XF, 160), (J["r"], 160)], "c back")
    p.label(XF - 8, (Rv["b"] + D2["y"]) / 2 - 18, ["미통과 ·", "수정 요청"], "end")
    # 다른 장으로 나가는 선(점선). 선 끝에는 장 번호만 둔다
    p.edge([(D3["r"], D3["cy"]), (1200, D3["cy"]), (1200, D3["cy"] + 40)], "3장", "below")
    p.label(D3["r"] + 4, D3["cy"] - 44, ["있으면", "→ 3장"])
    p.edge([(D4["x"], D4["cy"]), (760, D4["cy"])], "3장", "left")
    p.label(D4["x"] - 10, D4["cy"] - 26, ["있으면 → 3장 새 브랜치"], "end")
    ex, ey = D4["r"] + 50, D4["cy"]                        # 끝 표시의 중심
    p.conn([(D4["r"], ey), (ex - 10, ey)])
    p.label(D4["r"] + 4, ey - 28, ["없으면"])
    p.fore.append(f'<circle class="end-ring" cx="{ex:g}" cy="{ey:g}" r="9"/><circle class="end-dot" cx="{ex:g}" cy="{ey:g}" r="5"/>'
                  f'<text class="legend" x="{ex:g}" y="{ey + 26:g}" text-anchor="middle">끝</text>')
    flow_legend(p, LEGEND, ((16, "ai", "Claude"), (136, "dev", "개발자"), (264, "decision", "판단")))
    desc = ("6장. 인수 확인을 통과한 브랜치를 두고 Claude 리뷰와 개발자의 자체 리뷰를 나란히 한다. "
            "개발자가 두 리뷰 결과를 대조해 반영할 피드백을 정한다. "
            "반영할 피드백이 없으면 Claude가 곧바로 PR 본문과 병합 명령을 낸다. "
            "반영할 피드백이 있으면 대조 결과를 받는 것도 요청이라 Claude가 PR 댓글 작성 여부를 먼저 판단하고 필요하면 작성한다. "
            "Claude가 개발자가 정한 피드백을 반영하고 5장 절차로 인수 확인을 다시 한 뒤 체크포인트 보고를 낸다. "
            "개발자가 리뷰해 미통과로 수정을 요청하면 PR 댓글 작성 여부 판단으로 돌아간다. "
            "통과하면 추천 명령으로 커밋하고 PR 댓글이 있으면 푸시까지 한다. "
            "Claude가 작업 내용, 검토에서 바뀐 것, 인수 확인 결과를 담은 PR 본문을 쓰고 드래프트 해제·스쿼시 병합 명령을 낸다. "
                        "개발자가 실행하면 이 브랜치가 병합된다. 다음 브랜치가 있으면 3장 브랜치 명령으로 돌아간다. "
            "없으면 설계 문서가 다룬 기능 전체의 변경을 같은 방식으로 한 번 더 검토한다. "
            "반영할 피드백이 있으면 3장에서 새 브랜치를 열고 없으면 끝난다.")
    return p, desc


# ── 모든 장에 적용되는 장치와 범례 ─────────────────────────────────────
ALWAYS = [("settings.json", F, "Claude가 실행하는 명령 가운데 rebase, force push, reset, checkout --, restore, clean, stash drop, stash clear, branch -D, rm -r 을 막는다. PR 브랜치 이력을 다시 쓰면 댓글과 커밋의 연결이 끊긴다."),
          ("agent-guard.py", T, "Claude가 일을 나눠 맡기는 서브에이전트를 부를 때 모델을 지정하면 막는다. 서브에이전트는 세션의 모델을 그대로 쓴다."),
          ("memory-note.py", T, "Claude가 대화 사이에 남기는 기록 파일(메모리)에 쓴 뒤 전역 규칙·저장소 문서에 둘 내용인지 다시 확인하게 알린다. 막지 않는다.")]


def legend_svg():
    v = "fb-legend"
    o = [f'<text class="page-title" x="{LX}" y="22">모든 장에 적용되는 장치</text>',
         f'<text class="lead" x="{LX}" y="44">훅은 모두 Claude의 도구 호출과 답변에 적용된다. 개발자가 직접 실행하는 명령에는 적용되지 않는다.</text>']
    y, dx = 60, LX + 144
    for name, mono, desc in ALWAYS:
        w = int((twm(name) if mono else tw(name, 13, True)) + 16); w += -w % 4
        o.append(f'<g class="tag"><rect x="{LX}" y="{y}" width="{w}" height="24"/>'
                 f'<text x="{LX + 8}" y="{y + 17}"><tspan class="{"mono" if mono else "tagname"}">{esc(name)}</tspan></text></g>')
        lines = wrap(desc, XR - dx)
        o += [f'<text x="{dx}" y="{y + 17 + 18 * k}">{esc(t)}</text>' for k, t in enumerate(lines)]
        y += max(24, 18 * len(lines) + 6) + 10
    y += 8
    o.append(f'<line class="rule" x1="{LX}" y1="{y}" x2="{XR}" y2="{y}"/>')
    o.append(f'<text class="band-title" x="{LX}" y="{y + 26}">범례</text>')
    y += 40
    x = LX
    items = [("ai", "Claude"), ("dev", "개발자"), ("codex", "Codex"), ("art", "산출물"),
             ("tag", "강제 장치 꼬리표"), ("go", "진행"), ("back", "되돌아감"), ("end", "끝")]
    for kind, text in items:
        if kind in ("ai", "dev", "codex"):
            o.append(f'<g class="cell {kind} swatch"><rect class="shape" x="{x}" y="{y}" width="28" height="18" rx="4"/></g>'); sw = 28
        elif kind == "art":
            o.append(f'<g class="cell art swatch"><path class="shape" d="M{x} {y} H{x + 20} L{x + 28} {y + 8} V{y + 18} H{x} Z"/>'
                     f'<path class="fold" d="M{x + 20} {y} V{y + 8} H{x + 28}"/></g>'); sw = 28
        elif kind == "tag":
            o.append(f'<g class="tag swatch"><rect x="{x}" y="{y}" width="28" height="18"/></g>'); sw = 28
        elif kind in ("go", "back"):
            o.append(f'<path class="c{" back" if kind == "back" else ""}" d="M{x} {y + 9} H{x + 32}" marker-end="url(#{v}-ah)"/>'); sw = 36
        else:
            o.append(f'<circle class="end-ring" cx="{x + 9}" cy="{y + 9}" r="9"/><circle class="end-dot" cx="{x + 9}" cy="{y + 9}" r="5"/>'); sw = 18
        o.append(f'<text class="legend" x="{x + sw + 8}" y="{y + 14}">{esc(text)}</text>')
        x += sw + 8 + int(tw(text)) + 32
    H = y + 18 + 16
    mk = (f'<marker id="{v}-ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
          f'<path d="M0 0L10 5L0 10z" class="ah"/></marker>')
    desc = ("모든 장에 적용되는 장치와 범례. settings.json 은 이력을 다시 쓰는 git 명령과 rm -r 을 막고 agent-guard.py 는 서브에이전트의 모델 지정을 막는다. "
            "memory-note.py 는 메모리에 쓴 내용의 기록 위치를 다시 확인하게 알린다. "
            "범례: 보라 상자는 Claude, 노란 상자는 개발자, 청록 상자는 Codex, 모서리가 접힌 상자는 산출물, 회색 사각 꼬리표는 강제 장치, 실선은 진행, 점선은 되돌아감이다.")
    return (f'<svg class="legend-strip" id="{v}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="{v}-title {v}-desc">\n'
            f'<title id="{v}-title">모든 장에 적용되는 장치와 범례</title>\n<desc id="{v}-desc">{esc(desc)}</desc>\n'
            f'<defs>{mk}</defs>\n' + "\n".join(o) + '\n</svg>')


def text_html(value):
    """문장 하나 또는 (도입 문장, 항목 목록)."""
    if isinstance(value, str):
        return esc(value)
    intro, items = value
    return esc(intro) + ("<ul>" + "".join(f"<li>{esc(t)}</li>" for t in items) + "</ul>" if items else "")


def notes_html(notes, n=None, seen=None):
    """장 아래 장치 설명 목록. 그림의 꼬리표 번호·이름에 라벨 목록을 잇는다. prose-check 만 표를 잇는다.

    seen 을 주면 앞 장에서 이미 설명한 장치는 목록을 다시 적지 않고 처음 설명한 자리를 가리킨다.

    표의 예 칸은 검사가 잡는 글자 그대로라 <code> 로 감싼다. 산문 검사(prose-check)는 <code> 안을 보지 않는다.
    """
    if not notes:
        return ""
    out = ['<ol class="notes">']
    for num, name, mono, desc in notes:
        head = f'<span class="num">{num}</span> ' if num else ""
        tag = f"<code>{esc(name)}</code>" if mono else f"<b>{esc(name)}</b>"
        key = id(desc) if isinstance(desc, (list, dict)) else None
        if seen is not None and key in seen:
            out.append(f"<li>{head}{tag}: 설명은 {seen[key]}에 있다.</li>")
            continue
        if seen is not None and key and num:
            seen[key] = f"{n}장 {num}"
        if isinstance(desc, dict):
            cell = lambda v: esc(v) if isinstance(v, str) else " ".join(f"<code>{esc(t)}</code>" for t in v)
            rows = "".join("<tr>" + "".join(f"<td>{cell(v)}</td>" for v in r) + "</tr>" for r in desc["rows"])
            body = (f": {esc(desc['intro'])}<table><thead><tr>" + "".join(f"<th>{esc(h)}</th>" for h in desc["head"])
                    + f"</tr></thead><tbody>{rows}</tbody></table>")
        elif isinstance(desc, list):
            body = "<dl>" + "".join(f"<dt>{esc(k)}</dt><dd>{text_html(v)}</dd>" for k, v in desc) + "</dl>"
        else:
            body = (": " if desc[0] else "") + text_html(desc)
        out.append(f"<li>{head}{tag}{body}</li>")
    return "\n" + "\n".join(out + ["</ol>"])


# ── 조립 ──────────────────────────────────────────────────────────────
CSS = """
.flow-b { --flow-codex: #0f766e; width: min(100vw - 32px, 1240px); margin: 26px 0; position: relative; left: 50%; transform: translateX(-50%); }
@media (prefers-color-scheme: dark) { .flow-b { --flow-codex: #5eead4; } }
.flow-b svg { display: block; width: 100%; height: auto; }
.flow-b svg + svg { margin-top: 40px; }
.flow-b text { font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif; font-size: 13px; fill: var(--text); }
.flow-b .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.flow-b .page-title { font-size: 15px; font-weight: 700; }
.flow-b .title, .flow-b .lane-name { font-size: 14px; font-weight: 700; }
.flow-b .lead, .flow-b .nav, .flow-b .sub, .flow-b .memo, .flow-b .legend { fill: var(--muted); }
.flow-b .band-title, .flow-b .num, .flow-b .tagname { font-weight: 700; }
.flow-b .num { font-size: 15px; }
.flow-b .rule { stroke: var(--line); stroke-width: 1; }
.flow-b .cell.ai .shape { fill: color-mix(in srgb, var(--flow-ai) 9%, var(--surface)); stroke: var(--flow-ai); stroke-width: 1.5; }
.flow-b .cell.dev .shape { fill: var(--flow-gate-soft); stroke: var(--flow-gate); stroke-width: 1.5; }
.flow-b .cell.codex .shape { fill: color-mix(in srgb, var(--flow-codex) 10%, var(--surface)); stroke: var(--flow-codex); stroke-width: 1.5; }
.flow-b .cell.decision .shape { stroke-width: 1.5; }
.flow-b .dtitle { font-size: 13px; font-weight: 700; fill: var(--text); }
.flow-b .merge { fill: var(--muted); }
.flow-b .swatch-decision { fill: none; stroke: var(--muted); stroke-width: 1.5; }
.flow-b .cell.art .shape { fill: var(--surface); stroke: var(--muted); stroke-width: 1.2; }
.flow-b .cell.art .fold { fill: none; stroke: var(--muted); stroke-width: 1.2; }
.flow-b .cell.note .shape, .flow-b .tag rect { fill: var(--code); stroke: var(--muted); stroke-width: 1; }
.flow-b .c, .flow-b .bridge { fill: none; stroke: var(--muted); stroke-width: 1.8; }
.flow-b .bridge-cut { fill: var(--bg); }
.flow-b .c.back { stroke-dasharray: 5 4; }
.flow-b .ah, .flow-b .end-dot { fill: var(--muted); }
.flow-b .end-ring { fill: none; stroke: var(--muted); stroke-width: 1.5; }
.flow-b .mask { fill: var(--bg); }
.flow-b .lbl, .flow-b .stage { font-weight: 600; fill: var(--muted); }
.flow-b figcaption { max-width: 760px; margin: 16px auto 0; color: var(--muted); font-size: 0.93rem; }
.flow-b ol.notes { list-style: none; margin: 14px 0 0; padding: 0; font-size: 13px; line-height: 1.6; color: var(--muted); }
.flow-b ol.notes > li { margin: 0 0 6px; }
.flow-b ol.notes .num { font-weight: 700; color: var(--text); }
.flow-b ol.notes b, .flow-b ol.notes code { color: var(--text); }
.flow-b ol.notes code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-weight: 700; }
.flow-b ol.notes ul { margin: 2px 0 0; padding-left: 20px; }
.flow-b ol.notes + svg { margin-top: 40px; }
""".strip()

ROOT = """:root { --bg:#f8fafc; --surface:#ffffff; --text:#172033; --muted:#5d6879; --line:#dbe1e8; --accent:#1769aa; --accent-soft:#eaf4fc; --code:#f1f4f7; --flow-ai:#6d4fc2; --flow-gate:#a8730a; --flow-gate-soft:#fdf3d8; }
@media (prefers-color-scheme: dark) { :root { --bg:#10141b; --surface:#171d27; --text:#edf1f7; --muted:#abb5c4; --line:#303948; --accent:#72b7ec; --accent-soft:#172d3e; --code:#242c38; --flow-ai:#b9a4f2; --flow-gate:#e2b95b; --flow-gate-soft:#3a3016; } }
body { margin: 0; padding: 24px 0 48px; background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif; line-height: 1.7; }
main { width: min(100% - 32px, 760px); margin: 0 auto; }"""

CAPTION = ("요청부터 병합까지의 절차를 장마다 나눠 그렸다. 줄은 그 일을 하는 주체이고 노드 하나가 절차 하나다. "
           "꼬리표의 번호는 그 장 아래 「장치 설명」의 번호다.")

def pages():
    return [f for name, f in sorted(globals().items()) if name.startswith("page") and name[4:].isdigit()]


def chapters(head=False):
    """문서에 넣을 장별 조각: (장 번호, 제목, 앞 장, 그림과 장치 설명 HTML, 높이)."""
    out, seen = [], {}
    for f in pages():
        p, desc = f()
        s, H = p.svg(desc, head=head)
        out.append((p.n, p.title, p.prev, s + notes_html(p.notes, p.n, seen), H))
    return out


if __name__ == "__main__":
    PAGES = pages()
    svgs, stats = [], []
    for f in PAGES:
        p, desc = f()
        s, H = p.svg(desc)
        svgs.append(s + notes_html(p.notes))
        stats.append((p.n, p.count["node"], p.count["conn"], H))
    if "legend_svg" in globals():
        svgs.append(legend_svg())
    figure = '<figure class="flow-b">\n' + "\n".join(svgs) + f"\n<figcaption>{esc(CAPTION)}</figcaption>\n</figure>"
    (OUT / "preview.html").write_text(
        f'<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<meta name="color-scheme" content="light dark">\n<title>AI Workflow 그림 미리보기</title>\n<style>\n{ROOT}\n{CSS}\n</style>\n</head>\n'
        f'<body>\n<main>\n{figure}\n</main>\n</body>\n</html>\n')
    for n, nodes, conns, H in stats:
        print(f"{n}장 노드 {nodes} 연결선 {conns} 높이 {H:g}")
