// 슬라이드 문서의 렌더 결함을 장마다 잰다. page.evaluate 로 페이지 안에서 실행한다.
// 쓰는 법과 판정 기준은 doc-writing 「실제 산출 형태로 확인한다」에 있다.
// 숨긴 장도 배치는 되어 있어야 잴 수 있다(visibility·opacity 로 숨기는 덱). display:none 인 장은 크기가 0 이라 재지 못한다.
(options = {}) => {
  const { slide = ".slide", body = ".body", minBottom = 20, baseWidth = 1600 } = options;
  const slides = [...document.querySelectorAll(slide)];
  if (!slides.length) return { error: `${slide} 에 맞는 장이 없다` };
  // 바닥 여백 기준은 창 폭에 비례해 줄인다. cqw 로 짠 장은 글자와 여백이 폭에 비례해 작아진다
  const limit = (minBottom * window.innerWidth) / baseWidth;
  const round = (n) => Math.round(n * 10) / 10;
  const transparent = (color) => color === "transparent" || /rgba\(.*,\s*0\)$/.test(color);
  const inSvg = (el) => el.tagName.toLowerCase() !== "svg" && Boolean(el.closest("svg"));

  const name = (el) => {
    const id = el.id ? `#${el.id}` : "";
    const cls = typeof el.className === "string" && el.className.trim() ? "." + el.className.trim().split(/\s+/).join(".") : "";
    const text = (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 24);
    return `${el.tagName.toLowerCase()}${id}${cls}${text ? `「${text}」` : ""}`;
  };

  // 테두리·배경이 보이는 상자와 표·코드·그림. 글자가 이 상자와 겹치거나 상자 바닥이 본문 바닥에 닿으면 결함이다
  const isBox = (el) => {
    if (["table", "pre", "img", "svg", "canvas", "video"].includes(el.tagName.toLowerCase())) return true;
    const style = getComputedStyle(el);
    const border = ["Top", "Right", "Bottom", "Left"].some(
      (side) => parseFloat(style[`border${side}Width`]) > 0 && !transparent(style[`border${side}Color`]));
    return border || !transparent(style.backgroundColor);
  };

  // 글자는 요소 상자가 아니라 실제 줄마다 잰다. 인라인 요소는 줄마다 사각형이 따로 나온다
  const textLines = (root, keep = () => true) => {
    const lines = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const parent = node.parentElement;
      if (!node.textContent.trim() || !parent || inSvg(parent) || ["script", "style"].includes(parent.tagName.toLowerCase()) || !keep(parent)) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      for (const rect of range.getClientRects()) {
        if (rect.width > 0 && rect.height > 0) lines.push({ el: node.parentElement, rect });
      }
    }
    return lines;
  };

  // 장 밖에서 장 위에 떠 있는 화면 요소(넘김 단추·쪽수 등). 장 안의 글자와 겹치면 결함이다
  const outsideSlides = (el) => !el.closest(slide) && !el.querySelector(slide);
  const chromeLines = textLines(document.body, outsideSlides);
  const chromeBoxes = [...document.body.querySelectorAll("*")]
    .filter((el) => outsideSlides(el) && !inSvg(el) && isBox(el))
    .map((el) => ({ el, rect: el.getBoundingClientRect() }))
    .filter(({ rect }) => rect.width > 0 && rect.height > 0);

  const problems = [];
  slides.forEach((s, index) => {
    const issues = [];
    const frame = s.getBoundingClientRect();
    if (frame.width === 0) {
      problems.push({ slide: index + 1, issues: ["장의 크기가 0 이라 재지 못했다"] });
      return;
    }
    const lines = textLines(s);
    const elements = [...s.querySelectorAll("*")].filter((el) => !inSvg(el));

    // 넘침: 스크롤이나 잘림이 생긴 요소. 코드 블록이 줄어들어 잘리는 것도 여기서 잡힌다
    for (const el of [s, ...elements]) {
      if (!(el instanceof HTMLElement)) continue;
      const style = getComputedStyle(el);
      if (style.overflowX === "visible" && style.overflowY === "visible") continue;
      const down = el.scrollHeight - el.clientHeight;
      const across = el.scrollWidth - el.clientWidth;
      if (down > 1 || across > 1) issues.push(`넘침 세로 ${down}px·가로 ${across}px: ${name(el)}`);
    }

    // 장 밖으로 나간 글자와 상자. 글자가 없는 그림·상자도 본다
    const boxes = elements.filter(isBox).map((el) => ({ el, rect: el.getBoundingClientRect() }));
    const beyond = (rect) => rect.bottom > frame.bottom + 1 || rect.right > frame.right + 1
      || rect.left < frame.left - 1 || rect.top < frame.top - 1;
    const outside = new Set();
    for (const { el, rect } of lines) {
      if (beyond(rect)) outside.add(name(el));
    }
    for (const { el, rect } of boxes) {
      if (rect.width > 0 && rect.height > 0 && beyond(rect)) outside.add(name(el));
    }
    for (const label of outside) issues.push(`장 밖으로 나감: ${label}`);

    // 바닥 여백: 본문 바닥과 그 안의 가장 낮은 글자 줄이나 상자 바닥 사이
    const main = s.querySelector(body);
    if (main) {
      const bottom = main.getBoundingClientRect().bottom;
      let lowest = -Infinity;
      let lowestName = "";
      for (const { el, rect } of lines) {
        if (main.contains(el) && rect.bottom > lowest) [lowest, lowestName] = [rect.bottom, name(el)];
      }
      for (const el of elements) {
        if (!main.contains(el) || !isBox(el)) continue;
        const rect = el.getBoundingClientRect();
        if (rect.height > 0 && rect.bottom > lowest) [lowest, lowestName] = [rect.bottom, name(el)];
      }
      if (lowest > -Infinity && bottom - lowest < limit) {
        issues.push(`바닥 여백 ${round(bottom - lowest)}px, 기준 ${round(limit)}px: ${lowestName}`);
      }
    }

    // 겹침: 글자 줄이 조상·자손이 아닌 다른 글자 줄이나 상자와 2px 넘게 겹치는 곳
    const overlaps = new Set();
    for (const line of lines) {
      for (const other of [...boxes, ...lines, ...chromeBoxes, ...chromeLines]) {
        if (other === line || other.el === line.el || other.el.contains(line.el) || line.el.contains(other.el)) continue;
        const width = Math.min(line.rect.right, other.rect.right) - Math.max(line.rect.left, other.rect.left);
        const height = Math.min(line.rect.bottom, other.rect.bottom) - Math.max(line.rect.top, other.rect.top);
        if (width > 2 && height > 2) overlaps.add([name(line.el), name(other.el)].sort().join(" ↔ "));
      }
    }
    for (const pair of overlaps) issues.push(`겹침: ${pair}`);

    if (issues.length) {
      const label = s.dataset.id || (s.querySelector(".eyebrow")?.textContent || "").trim();
      problems.push({ slide: index + 1, label, issues });
    }
  });
  return { viewport: `${window.innerWidth}×${window.innerHeight}`, slides: slides.length, bottomLimit: round(limit), problems };
}
