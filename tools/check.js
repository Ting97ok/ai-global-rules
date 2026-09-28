// 작업 흐름 그림의 렌더 측정. 장(svg)마다 겹침·넘침·선 규칙을 잰다.
// ego-browser 는 스크립트를 표준 입력으로 받고 현재 폴더와 환경 변수를 넘기지 않는다. 작업 공간 번호와 측정할 파일은 실행할 때 채운다.
//   sed -e "s#__SPACE__#47#" -e "s#__PAGE__#$PWD/preview.html#" check.js | ego-browser nodejs
const task = await taskSpace(__SPACE__);
const page = task.page("p1");

const measure = () => {
  const R = (e) => { const r = e.getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom }; };
  const hit = (a, b, p = 0) => a.l < b.r - p && a.r > b.l + p && a.t < b.b - p && a.b > b.t + p;
  const inside = (a, b, p = 0) => a.l >= b.l - p && a.r <= b.r + p && a.t >= b.t - p && a.b <= b.b + p;
  const dist = (x, y, r) => Math.hypot(Math.max(r.l - x, 0, x - r.r), Math.max(r.t - y, 0, y - r.b));
  const out = { pageOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth, svgs: [] };
  for (const svg of document.querySelectorAll(".flow-b svg")) {
    const sr = R(svg), scale = (sr.r - sr.l) / svg.viewBox.baseVal.width;
    const texts = [...svg.querySelectorAll("text")].map((e) => ({ e, s: e.textContent, r: R(e) }));
    const fonts = texts.map((t) => parseFloat(getComputedStyle(t.e).fontSize));
    const res = { id: svg.id, w: Math.round(sr.r - sr.l), h: Math.round(sr.b - sr.t), scale: +scale.toFixed(3),
      fitsViewport: sr.b - sr.t <= innerHeight, minFontUnits: Math.min(...fonts), minFontPx: +(Math.min(...fonts) * scale).toFixed(1),
      outsideSvg: [], textOutOfBox: [], textOverText: [], textOverBox: [], lineOverText: [], lineBehindBox: [],
      lineOverLine: [], maskOverBox: [], labelGap: [], topic: [], topicCrossing: [], sharedAttach: [], diagonal: [] };
    for (const t of texts) if (t.r.l < sr.l || t.r.r > sr.r || t.r.t < sr.t || t.r.b > sr.b) res.outsideSvg.push(t.s);
    const boxes = [...svg.querySelectorAll("g.cell:not(.swatch), g.tag:not(.swatch)")].map((g) => ({ g, r: R(g.querySelector(".shape, rect")), name: g.textContent.slice(0, 14) }));
    for (const { g, r } of boxes) for (const te of g.querySelectorAll("text")) { const tr = R(te);
      if (tr.l < r.l + 4 * scale || tr.r > r.r - 4 * scale || tr.t < r.t || tr.b > r.b) res.textOutOfBox.push(`${te.textContent} (+${(tr.r - r.r + 4 * scale).toFixed(1)}px)`); }
    for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++)
      if (hit(texts[i].r, texts[j].r, 0.5)) res.textOverText.push(`${texts[i].s} × ${texts[j].s}`);
    for (const t of texts) for (const { g, r, name } of boxes) if (!g.contains(t.e) && hit(t.r, r)) res.textOverBox.push(`${t.s} × ${name}`);
    const masks = [...svg.querySelectorAll("rect.mask")].map((m) => ({ r: R(m), s: m.nextElementSibling?.textContent }));
    for (const m of masks) for (const { r, name } of boxes) if (hit(m.r, r)) res.maskOverBox.push(`${m.s} × ${name}`);
    // 연결선 표본점
    const m = svg.getScreenCTM();
    const paths = [...svg.querySelectorAll("path.c")].filter((p) => !p.closest("g.swatch"));
    const samples = paths.map((p) => { const L = p.getTotalLength(), pts = [];
      for (let d = 0; d <= L; d += 2) { const q = p.getPointAtLength(d); pts.push({ x: q.x * m.a + m.e, y: q.y * m.d + m.f, d, L }); }
      return pts; });
    paths.forEach((p, pi) => {
      const seenT = new Set(), seenB = new Set();
      for (const q of samples[pi]) {
        for (const t of texts) if (dist(q.x, q.y, t.r) < 1) seenT.add(t.s);
        if (q.d > 6 && q.d < q.L - 6) for (const { r, name } of boxes) if (dist(q.x, q.y, r) === 0 && q.x > r.l + 1.5 && q.x < r.r - 1.5 && q.y > r.t + 1.5 && q.y < r.b - 1.5) seenB.add(name);
      }
      seenT.forEach((s) => res.lineOverText.push(`${pi} × ${s}`));
      seenB.forEach((s) => res.lineBehindBox.push(`${pi} × ${s}`));
      // 대각선: L 구간의 양 끝이 x·y 모두 다르면 대각선이다
      const nums = p.getAttribute("d").match(/[MLQ]|-?[\d.]+/g); let cur = null, cmd = null, buf = [];
      for (const tok of nums) { if (/[MLQ]/.test(tok)) { cmd = tok; buf = []; continue; } buf.push(+tok);
        if (cmd === "M" && buf.length === 2) { cur = buf; buf = []; }
        else if (cmd === "L" && buf.length === 2) { if (Math.abs(buf[0] - cur[0]) > 0.5 && Math.abs(buf[1] - cur[1]) > 0.5) res.diagonal.push(`${pi}: ${cur} → ${buf}`); cur = buf; buf = []; }
        else if (cmd === "Q" && buf.length === 4) { cur = buf.slice(2); buf = []; } }
    });
    for (let i = 0; i < samples.length; i++) for (let j = i + 1; j < samples.length; j++) { let n = 0;
      for (const a of samples[i]) if (a.d > 14 && a.d < a.L - 14) for (const b of samples[j]) if (b.d > 14 && b.d < b.L - 14 && Math.abs(a.x - b.x) < 3 && Math.abs(a.y - b.y) < 3) n++;
      if (n) res.lineOverLine.push(`${i} × ${j} (${n})`); }
    // 라벨과 선의 간격: 가장 가까운 선까지 6~10px(viewBox 단위)
    for (const mk of masks) { let best = Infinity;
      for (const pts of samples) for (const q of pts) best = Math.min(best, dist(q.x, q.y, mk.r));
      const gap = best / scale - 0.9;   // 선 굵기 1.8 의 절반을 뺀다
      if (!(gap >= 6 && gap <= 10)) res.labelGap.push(`${mk.s}: ${gap.toFixed(1)}`); }
    // 같은 상자 변에 붙은 연결점 사이 간격
    const ends = [];
    samples.forEach((pts, pi) => { ends.push({ pi, ...pts[0] }, { pi, ...pts[pts.length - 1] }); });
    for (const { r, name } of boxes) {
      const sides = { l: [], r: [], t: [], b: [] };
      for (const e of ends) {
        if (e.y >= r.t - 1 && e.y <= r.b + 1) { if (Math.abs(e.x - r.l) < 3) sides.l.push(e); if (Math.abs(e.x - r.r) < 3) sides.r.push(e); }
        if (e.x >= r.l - 1 && e.x <= r.r + 1) { if (Math.abs(e.y - r.t) < 3) sides.t.push(e); if (Math.abs(e.y - r.b) < 3) sides.b.push(e); } }
      for (const [side, list] of Object.entries(sides)) for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
        const g = side === "l" || side === "r" ? Math.abs(list[i].y - list[j].y) : Math.abs(list[i].x - list[j].x);
        if (g < 12 * scale) res.sharedAttach.push(`${name} ${side}: ${list[i].pi}·${list[j].pi} ${(g / scale).toFixed(1)}`); } }
    // 주제 영역
    const zone = svg.querySelector("rect.topic:not(.swatch)");
    if (zone) { const z = R(zone), tab = R(svg.querySelector("path.topic-tab:not(.swatch)")), all = { l: z.l, r: z.r, t: tab.t, b: z.b };
      const members = boxes.filter((b) => inside(b.r, z));
      res.topicMembers = members.map((b) => b.name);
      for (const b of boxes) if (!members.includes(b) && hit(b.r, all)) res.topic.push(`상자 ${b.name}`);
      for (const mk of masks) if (hit(mk.r, all)) res.topic.push(`라벨 ${mk.s}`);
      for (const t of texts) if (!members.some((b) => b.g.contains(t.e)) && !t.e.classList.contains("topic-name") && hit(t.r, all)) res.topic.push(`글자 ${t.s}`);
      samples.forEach((pts, pi) => {
        const onEdge = pts.some((q) => (Math.abs(q.x - z.l) < 2 || Math.abs(q.x - z.r) < 2) && q.y > z.t && q.y < z.b || (Math.abs(q.y - z.t) < 2 || Math.abs(q.y - z.b) < 2) && q.x > z.l && q.x < z.r);
        if (!onEdge) return;
        const a = pts[0], b = pts[pts.length - 1];
        const fromMember = members.some((mb) => dist(a.x, a.y, mb.r) < 4 || dist(b.x, b.y, mb.r) < 4);
        (fromMember ? res.topicCrossing : res.topic).push(`선 ${pi}`); });
      if (hit(tab, R(svg.querySelector("text.page-title")))) res.topic.push("탭 × 장 제목"); }
    // 상자 정렬 규칙
    const A = { titleBaseline: new Set(), leftPad: new Set(), titleToFirst: new Set() };
    for (const { g } of boxes) { if (!g.classList.contains("cell")) continue; const bb = g.querySelector(".shape").getBBox(), ts = [...g.querySelectorAll("text")];
      A.titleBaseline.add(+ts[0].getAttribute("y") - bb.y); ts.forEach((t) => A.leftPad.add(+t.getAttribute("x") - bb.x));
      const lastTitle = ts.filter((t) => t.classList.contains("title")).pop(), sub = ts.find((t) => t.classList.contains("sub"));
      if (sub) A.titleToFirst.add(+sub.getAttribute("y") - +lastTitle.getAttribute("y")); }
    res.align = { titleBaseline: [...A.titleBaseline], leftPad: [...A.leftPad], titleToFirst: [...A.titleToFirst] };
    res.nodes = boxes.filter((b) => b.g.classList.contains("cell") && !b.g.classList.contains("note")).length;
    res.tags = boxes.filter((b) => b.g.classList.contains("tag")).length; res.connectors = paths.length;
    for (const k of Object.keys(res)) if (Array.isArray(res[k]) && !res[k].length) delete res[k];
    out.svgs.push(res);
  }
  return out;
};

for (const scheme of ["light", "dark"]) {
  await page.cdp("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: scheme }] });
  for (const [w, h] of [[1440, 900], [1024, 768]]) {
    await page.cdp("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: false });
    await page.goto("file://__PAGE__");
    console.log(scheme, w, JSON.stringify(await page.evaluate(measure)));
  }
}
console.log({ spaceId: task.spaceId });
