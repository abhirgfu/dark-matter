// Small chart kit with no dependencies. Marks follow one spec across the page: 2px lines, bars no
// wider than 24px with a 4px rounded data end, a 2px surface gap between touching fills, hairline
// grids, a hover layer on everything, and a table twin under every chart.
"use strict";

const NS = "http://www.w3.org/2000/svg";

function svgEl(tag, attrs = {}, parent) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (parent) parent.appendChild(el);
  return el;
}

function htmlEl(tag, attrs = {}, parent) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "text") el.textContent = v;
    else el.setAttribute(k, v);
  }
  if (parent) parent.appendChild(el);
  return el;
}

const fmt = {
  usd(v) {
    const a = Math.abs(v);
    if (a >= 1e9) return `$${(v / 1e9).toFixed(a >= 1e10 ? 0 : 1)}B`;
    if (a >= 1e6) return `$${(v / 1e6).toFixed(a >= 1e8 ? 0 : 1)}M`;
    if (a >= 1e3) return `$${(v / 1e3).toFixed(a >= 1e5 ? 0 : 1)}K`;
    return `$${v.toFixed(0)}`;
  },
  pct(v) { return `${(v * 100).toFixed(v >= 0.1 ? 0 : 1)}%`; },
  bps(v) { return `${v.toFixed(v >= 100 ? 0 : 1)} bps`; },
  num(v) {
    const a = Math.abs(v);
    if (a >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
    if (a >= 1e4) return `${(v / 1e3).toFixed(0)}K`;
    return Math.round(v).toLocaleString("en-US");
  },
  date(d) {
    const t = new Date(`${d}T00:00:00Z`);
    return t.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
  },
  dateLong(d) {
    const t = new Date(`${d}T00:00:00Z`);
    return t.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  },
  month(m) {
    const t = new Date(`${m}-01T00:00:00Z`);
    return t.toLocaleDateString("en-GB", { month: "short", timeZone: "UTC" });
  },
};

function niceTicks(lo, hi, count = 4) {
  if (hi <= lo) hi = lo + 1;
  const raw = (hi - lo) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  const start = Math.floor(lo / step) * step;
  const ticks = [];
  for (let v = start; v <= hi + step * 0.001; v += step) ticks.push(Math.round(v / step) * step);
  if (ticks[ticks.length - 1] < hi) ticks.push(ticks[ticks.length - 1] + step);
  return ticks;
}

const tooltip = (() => {
  let box;
  function ensure() {
    if (!box) {
      box = htmlEl("div", { class: "tip", role: "status" }, document.body);
    }
    return box;
  }
  return {
    show(x, y, title, rows) {
      const el = ensure();
      el.replaceChildren();
      htmlEl("div", { class: "tip-title", text: title }, el);
      for (const row of rows) {
        const line = htmlEl("div", { class: "tip-row" }, el);
        const key = htmlEl("span", { class: "tip-key" }, line);
        key.style.background = row.color || "transparent";
        htmlEl("strong", { text: row.value }, line);
        htmlEl("span", { class: "tip-name", text: row.name }, line);
      }
      el.style.display = "block";
      const pad = 14;
      const w = el.offsetWidth;
      const h = el.offsetHeight;
      const left = x + pad + w > window.innerWidth ? x - pad - w : x + pad;
      const top = Math.min(Math.max(8, y - h / 2), window.innerHeight - h - 8);
      el.style.left = `${Math.max(8, left)}px`;
      el.style.top = `${top}px`;
    },
    hide() { if (box) box.style.display = "none"; },
  };
})();

function legend(host, items) {
  const row = htmlEl("div", { class: "legend" }, host);
  for (const item of items) {
    const entry = htmlEl("span", { class: "legend-item" }, row);
    const key = htmlEl("span", { class: item.kind === "bar" ? "key-bar" : "key-line" }, entry);
    key.style.background = item.color;
    htmlEl("span", { text: item.name }, entry);
  }
}

function responsive(host, draw) {
  let last = 0;
  const run = () => {
    const w = Math.round(host.clientWidth);
    if (w && w !== last) {
      last = w;
      draw(w);
    }
  };
  new ResizeObserver(run).observe(host);
  run();
}

// ---- line chart -----------------------------------------------------------------------------

function lineChart(host, opts) {
  const { series, yFormat = fmt.usd, height = 280, markers = [], yMin, yMax, endLabels = true } = opts;
  if (series.length > 1) legend(host, series.map((s) => ({ name: s.name, color: s.color, kind: "line" })));
  const plot = htmlEl("div", { class: "plot" }, host);
  const dates = [...new Set(series.flatMap((s) => s.points.map((p) => p[0])))].sort();
  const index = new Map(dates.map((d, i) => [d, i]));
  const values = series.flatMap((s) => s.points.map((p) => p[1])).filter((v) => v != null);
  const lo = yMin !== undefined ? yMin : Math.min(0, ...values);
  const hi = yMax !== undefined ? yMax : Math.max(...values);
  const ticks = niceTicks(lo, hi);

  responsive(plot, (width) => {
    plot.replaceChildren();
    const narrow = width < 520;
    const m = { top: 14, right: endLabels ? (narrow ? 58 : 68) : 14, bottom: 26, left: narrow ? 44 : 52 };
    const iw = width - m.left - m.right;
    const ih = height - m.top - m.bottom;
    const svg = svgEl("svg", { width, height, role: "img", "aria-label": opts.label || "line chart" }, plot);
    const x = (i) => m.left + (dates.length > 1 ? (i / (dates.length - 1)) * iw : iw / 2);
    const top = ticks[ticks.length - 1];
    const bottom = Math.min(lo, ticks[0]);
    const y = (v) => m.top + ih - ((v - bottom) / (top - bottom)) * ih;

    for (const t of ticks) {
      if (t < bottom) continue;
      svgEl("line", { x1: m.left, x2: width - m.right, y1: y(t), y2: y(t), class: t === bottom ? "axis" : "grid" }, svg);
      const lab = svgEl("text", { x: m.left - 8, y: y(t) + 4, "text-anchor": "end", class: "tick" }, svg);
      lab.textContent = yFormat(t);
    }
    // month ticks
    const seen = new Set();
    const maxLabels = Math.max(3, Math.floor(iw / 62));
    const months = dates.filter((d) => {
      const k = d.slice(0, 7);
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
    const every = Math.ceil(months.length / maxLabels);
    months.forEach((d, i) => {
      if (i % every) return;
      const lab = svgEl("text", { x: x(index.get(d)), y: height - 8, "text-anchor": "middle", class: "tick" }, svg);
      lab.textContent = fmt.month(d.slice(0, 7));
    });
    for (const mark of markers) {
      if (!index.has(mark.date)) continue;
      const mx = x(index.get(mark.date));
      svgEl("line", { x1: mx, x2: mx, y1: m.top, y2: m.top + ih, class: "marker-line" }, svg);
      const t = svgEl("text", { x: mx - 6, y: m.top + 10, "text-anchor": "end", class: "marker-text" }, svg);
      t.textContent = mark.label;
    }
    for (const s of series) {
      let d = "";
      let open = false;
      for (const [day, v] of s.points) {
        if (v == null) { open = false; continue; }
        d += `${open ? "L" : "M"}${x(index.get(day)).toFixed(1)} ${y(v).toFixed(1)}`;
        open = true;
      }
      svgEl("path", { d, fill: "none", stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round", ...(s.dash ? { "stroke-dasharray": s.dash } : {}) }, svg);
    }
    if (endLabels) {
      const ends = series.map((s) => {
        const pts = s.points.filter((p) => p[1] != null);
        return { s, last: pts[pts.length - 1] };
      }).filter((e) => e.last);
      const spaced = ends.every((a, i) => ends.every((b, j) => i === j || Math.abs(y(a.last[1]) - y(b.last[1])) > 14));
      ends.forEach(({ s, last }, i) => {
        const ex = x(index.get(last[0]));
        const ey = y(last[1]);
        svgEl("circle", { cx: ex, cy: ey, r: 4, fill: s.color, stroke: "var(--surface)", "stroke-width": 2 }, svg);
        if (spaced || i === 0) {
          const t = svgEl("text", { x: ex + 8, y: ey + 4, class: "end-label" }, svg);
          t.textContent = yFormat(last[1]);
        }
      });
    }
    // hover layer
    const cross = svgEl("line", { x1: 0, x2: 0, y1: m.top, y2: m.top + ih, class: "cross", visibility: "hidden" }, svg);
    const hit = svgEl("rect", { x: m.left, y: m.top, width: iw, height: ih, fill: "transparent", tabindex: 0, "aria-label": "Chart values; use left and right arrows" }, svg);
    let at = dates.length - 1;
    const lookups = series.map((s) => new Map(s.points));
    const show = (i, cx, cy) => {
      at = Math.max(0, Math.min(dates.length - 1, i));
      const px = x(at);
      cross.setAttribute("x1", px);
      cross.setAttribute("x2", px);
      cross.setAttribute("visibility", "visible");
      const rows = series.map((s, n) => {
        const v = lookups[n].get(dates[at]);
        return v == null ? null : { name: s.name, value: yFormat(v), color: s.color };
      }).filter(Boolean);
      tooltip.show(cx, cy, fmt.dateLong(dates[at]), rows);
    };
    hit.addEventListener("pointermove", (e) => {
      const box = svg.getBoundingClientRect();
      show(Math.round(((e.clientX - box.left - m.left) / iw) * (dates.length - 1)), e.clientX, e.clientY);
    });
    hit.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); tooltip.hide(); });
    hit.addEventListener("focus", () => { const b = svg.getBoundingClientRect(); show(at, b.left + x(at), b.top + ih / 2); });
    hit.addEventListener("blur", () => { cross.setAttribute("visibility", "hidden"); tooltip.hide(); });
    hit.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault();
      const b = svg.getBoundingClientRect();
      const next = at + (e.key === "ArrowLeft" ? -1 : 1);
      show(next, b.left + x(Math.max(0, Math.min(dates.length - 1, next))), b.top + ih / 2);
    });
  });
}

// ---- stacked columns, as share of a whole -------------------------------------------------------

function stackedColumns(host, opts) {
  const { rows, keys, height = 280, yFormat = fmt.usd, percent = false, label = "" } = opts;
  if (keys.length > 1) legend(host, keys.map((k) => ({ name: k.name, color: k.color, kind: "bar" })));
  const plot = htmlEl("div", { class: "plot" }, host);
  const totals = rows.map((r) => keys.reduce((sum, k) => sum + (r[k.key] || 0), 0));
  const ticks = percent ? [0, 0.25, 0.5, 0.75, 1] : niceTicks(0, Math.max(...totals));
  responsive(plot, (width) => {
    plot.replaceChildren();
    const m = { top: 14, right: 10, bottom: 26, left: 48 };
    const iw = width - m.left - m.right;
    const ih = height - m.top - m.bottom;
    const svg = svgEl("svg", { width, height, role: "img", "aria-label": label || "stacked columns" }, plot);
    const top = ticks[ticks.length - 1];
    const y = (v) => m.top + ih - (v / top) * ih;
    for (const t of ticks) {
      svgEl("line", { x1: m.left, x2: width - m.right, y1: y(t), y2: y(t), class: t === 0 ? "axis" : "grid" }, svg);
      const lab = svgEl("text", { x: m.left - 8, y: y(t) + 4, "text-anchor": "end", class: "tick" }, svg);
      lab.textContent = percent ? `${Math.round(t * 100)}%` : yFormat(t);
    }
    const band = iw / rows.length;
    const barW = Math.min(24, band * 0.62);
    const labelEvery = Math.max(1, Math.ceil(rows.length / Math.max(2, Math.floor(iw / 54))));
    rows.forEach((row, i) => {
      const cx = m.left + band * (i + 0.5);
      const total = totals[i];
      let base = 0;
      const live = keys.filter((k) => (row[k.key] || 0) > 0);
      live.forEach((k, n) => {
        const value = percent ? (total ? row[k.key] / total : 0) : row[k.key];
        const y0 = y(base);
        const y1 = y(base + value);
        const gap = n > 0 ? 2 : 0;
        const h = Math.max(1, y0 - y1 - gap);
        const topEdge = n === live.length - 1;
        const r = topEdge ? Math.min(4, h) : 0;
        const left = cx - barW / 2;
        const yy = y1;
        const d = `M${left} ${yy + h}V${yy + r}${r ? `Q${left} ${yy} ${left + r} ${yy}` : ""}H${left + barW - r}${r ? `Q${left + barW} ${yy} ${left + barW} ${yy + r}` : ""}V${yy + h}Z`;
        const mark = svgEl("path", { d, fill: k.color, class: "mark", tabindex: 0, "aria-label": `${row.label}, ${k.name}, ${yFormat(row[k.key])}` }, svg);
        const tip = (cx2, cy2) => tooltip.show(cx2, cy2, row.title || row.label, keys.map((q) => ({
          name: q.name,
          value: percent && total ? `${yFormat(row[q.key] || 0)} (${fmt.pct((row[q.key] || 0) / total)})` : yFormat(row[q.key] || 0),
          color: q.color,
        })));
        mark.addEventListener("pointermove", (e) => tip(e.clientX, e.clientY));
        mark.addEventListener("pointerleave", () => tooltip.hide());
        mark.addEventListener("focus", () => { const b = mark.getBoundingClientRect(); tip(b.right, b.top); });
        mark.addEventListener("blur", () => tooltip.hide());
        base += value;
      });
      if (i % labelEvery === 0) {
        const lab = svgEl("text", { x: cx, y: height - 8, "text-anchor": "middle", class: "tick" }, svg);
        lab.textContent = row.label;
      }
    });
  });
}

// ---- horizontal ranked bars ------------------------------------------------------------------------

function rankedBars(host, opts) {
  const { rows, color, yFormat = fmt.usd } = opts;
  const list = htmlEl("div", { class: "bars" }, host);
  const max = Math.max(...rows.map((r) => r.value));
  for (const row of rows) {
    const line = htmlEl("div", { class: "bar-row" }, list);
    htmlEl("div", { class: "bar-name", text: row.name, title: row.name }, line);
    const track = htmlEl("div", { class: "bar-track" }, line);
    const fill = htmlEl("div", { class: "bar-fill" }, track);
    fill.style.width = `${Math.max(0.5, (row.value / max) * 100)}%`;
    fill.style.background = row.color || color;
    htmlEl("div", { class: "bar-value", text: yFormat(row.value) }, line);
  }
}

// ---- one whole, split into parts ---------------------------------------------------------------------

function segmentedBar(host, opts) {
  const { parts, yFormat = fmt.usd } = opts;
  const total = parts.reduce((s, p) => s + p.value, 0);
  const bar = htmlEl("div", { class: "segmented", role: "img", "aria-label": parts.map((p) => `${p.name} ${fmt.pct(p.value / total)}`).join(", ") }, host);
  for (const part of parts) {
    const block = htmlEl("div", { class: "segment", tabindex: 0 }, bar);
    block.style.flexGrow = part.value;
    block.style.background = part.color;
    if (part.dark) block.style.color = "#0b0b0b";
    const share = part.value / total;
    if (share > 0.085) block.textContent = fmt.pct(share);
    const tip = (x, y) => tooltip.show(x, y, part.name, [{ name: "share", value: fmt.pct(share), color: part.color }, { name: "value", value: yFormat(part.value), color: part.color }]);
    block.addEventListener("pointermove", (e) => tip(e.clientX, e.clientY));
    block.addEventListener("pointerleave", () => tooltip.hide());
    block.addEventListener("focus", () => { const b = block.getBoundingClientRect(); tip(b.left, b.bottom); });
    block.addEventListener("blur", () => tooltip.hide());
  }
  legend(host, parts.map((p) => ({ name: p.name, color: p.color, kind: "bar" })));
}

// ---- table twin ---------------------------------------------------------------------------------------

function tableTwin(host, columns, rows, caption = "Show the numbers") {
  const box = htmlEl("details", { class: "fold" }, host);
  htmlEl("summary", { text: caption }, box);
  const scroll = htmlEl("div", { class: "table-scroll" }, box);
  const table = htmlEl("table", {}, scroll);
  const head = htmlEl("tr", {}, htmlEl("thead", {}, table));
  for (const c of columns) htmlEl("th", { text: c.name, class: c.num ? "num" : "" }, head);
  const body = htmlEl("tbody", {}, table);
  for (const row of rows) {
    const tr = htmlEl("tr", {}, body);
    for (const c of columns) htmlEl("td", { text: c.get(row), class: c.num ? "num" : "" }, tr);
  }
}

window.DMCharts = { lineChart, stackedColumns, rankedBars, segmentedBar, tableTwin, fmt, htmlEl, svgEl, tooltip };
