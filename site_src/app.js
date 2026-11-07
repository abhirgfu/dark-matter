// Draws every chart from the data the build placed in the page, so the page works from a plain file.
"use strict";

(function main() {
  const D = JSON.parse(document.getElementById("data").textContent);
  const { lineChart, stackedColumns, rankedBars, segmentedBar, tableTwin, fmt } = window.DMCharts;
  const css = getComputedStyle(document.documentElement);
  const color = (name) => css.getPropertyValue(name).trim();
  const PRIVATE = color("--private");
  const PUBLIC = color("--public");
  const THIRD = color("--third");
  const FOURTH = color("--fourth");
  const $ = (id) => document.getElementById(id);

  // ---- weigh it yourself ------------------------------------------------------------------------
  const button = $("weigh-button");
  const logBox = $("weigh-log");
  const valueBox = $("weigh-value");
  const noteBox = $("weigh-note");
  if (button) {
    button.addEventListener("click", async () => {
      button.disabled = true;
      button.textContent = "Weighing...";
      logBox.textContent = "";
      const log = (line) => { logBox.textContent += `${line}\n`; };
      try {
        const res = await window.DMWeigh.weighNow(D.treasury, log);
        valueBox.textContent = `$${(res.usd / 1e6).toFixed(1)}M`;
        const gap = ((res.usd - D.reported_latest) / D.reported_latest) * 100;
        noteBox.textContent = `Weighed just now at block ${res.height.toLocaleString("en-US")}, in your browser: ${res.priced} of ${res.tokens} tokens priced. NEAR's last reported figure is ${fmt.usd(D.reported_latest)} (${gap >= 0 ? "+" : ""}${gap.toFixed(1)}%).`;
        log(`largest: ${res.top.map(([s, v]) => `${s} ${fmt.usd(v)}`).join(", ")}`);
      } catch (err) {
        log(`Could not reach a public node from this browser: ${err.message}`);
      }
      button.disabled = false;
      button.textContent = "Weigh it again";
    });
  }

  // ---- 1. the weight ----------------------------------------------------------------------------
  {
    const rows = D.weigh.series.filter((r) => r.date >= "2026-03-01");
    lineChart($("chart-weight"), {
      label: "Treasury value weighed from intents.near against the value NEAR reports",
      series: [
        { name: "Weighed by us from intents.near", color: PRIVATE, points: rows.map((r) => [r.date, r.weighed]) },
        { name: "Reported by NEAR", color: PUBLIC, points: rows.map((r) => [r.date, r.reported]) },
      ],
    });
    tableTwin($("table-weight"), [
      { name: "Date", get: (r) => r.date },
      { name: "Weighed", num: true, get: (r) => fmt.usd(r.weighed) },
      { name: "Reported", num: true, get: (r) => (r.reported ? fmt.usd(r.reported) : "n/a") },
    ], [...rows].reverse());
    const parts = D.weigh.composition.slice(0, 5);
    const rest = D.weigh.composition.slice(5).reduce((s, r) => s + r.usd, 0);
    const palette = [PRIVATE, PUBLIC, THIRD, FOURTH, "#d55181"];
    segmentedBar($("chart-mix"), {
      parts: [
        ...parts.map((p, i) => ({ name: p.symbol, value: p.usd, color: palette[i] })),
        { name: "Everything else", value: rest, color: "#555451" },
      ],
    });
    tableTwin($("table-mix"), [
      { name: "Token", get: (r) => r.symbol },
      { name: "Value", num: true, get: (r) => fmt.usd(r.usd) },
    ], D.weigh.composition.slice(0, 30));
  }

  // ---- 2. where revenue comes from ---------------------------------------------------------------
  {
    const rows = D.revenue.weekly.filter((w) => w.week >= "2026-05-04").map((w) => ({
      label: fmt.date(w.week),
      title: `Week of ${fmt.dateLong(w.week)}`,
      private: w.private_bps,
      public: w.public_bps,
      total: w.bps,
    }));
    stackedColumns($("chart-provenance"), {
      label: "What NEAR keeps from each dollar of volume, by week and by the route the money took",
      rows,
      yFormat: (v) => `${v.toFixed(v < 10 && v % 1 ? 1 : 0)} bps`,
      keys: [
        { key: "public", name: "No private trace", color: PUBLIC },
        { key: "private", name: "Paid out of the private treasury", color: PRIVATE },
      ],
    });
    tableTwin($("table-provenance"), [
      { name: "Week", get: (r) => r.title },
      { name: "No private trace", num: true, get: (r) => fmt.bps(r.public) },
      { name: "From the treasury", num: true, get: (r) => fmt.bps(r.private) },
      { name: "Total", num: true, get: (r) => fmt.bps(r.total) },
    ], [...rows].reverse());
  }
  // ---- 3. flows --------------------------------------------------------------------------------
  if (D.flows.daily.length && $("chart-flows")) {
    const rows = D.flows.daily.filter((r) => r.date >= "2026-09-01");
    lineChart($("chart-flows"), {
      label: "Daily money entering the private chain against total reported volume",
      series: [
        { name: "Reported Intents volume", color: PUBLIC, points: rows.map((r) => [r.date, r.volume_usd]) },
        { name: "Users into the treasury", color: PRIVATE, points: rows.map((r) => [r.date, r.user_in_usd]) },
      ],
      markers: [{ date: D.private_start, label: "Private swaps" }],
    });
    tableTwin($("table-flows"), [
      { name: "Date", get: (r) => r.date },
      { name: "Users in", num: true, get: (r) => fmt.usd(r.user_in_usd) },
      { name: "Solvers in", num: true, get: (r) => fmt.usd(r.solver_in_usd) },
      { name: "Volume", num: true, get: (r) => (r.volume_usd ? fmt.usd(r.volume_usd) : "n/a") },
    ], [...rows].reverse());
  }

  // ---- 5. what privacy costs ---------------------------------------------------------------------
  if (D.costs.all && D.costs.all.n && $("chart-cost")) {
    const rows = Object.entries(D.costs.by_class).map(([name, s]) => ({ name, ...s })).sort((a, b) => b.usd - a.usd);
    rankedBars($("chart-cost"), {
      color: PRIVATE,
      yFormat: fmt.bps,
      rows: rows.map((r) => ({ name: r.name, value: r.median_bps })),
    });
    tableTwin($("table-cost"), [
      { name: "Pair type", get: (r) => r.name },
      { name: "Swaps", num: true, get: (r) => String(r.n) },
      { name: "Dollars", num: true, get: (r) => fmt.usd(r.usd) },
      { name: "Median", num: true, get: (r) => fmt.bps(r.median_bps) },
      { name: "Dollar-weighted", num: true, get: (r) => fmt.bps(r.weighted_bps) },
    ], rows);
  }

  // ---- 6. public activity ----------------------------------------------------------------------
  {
    const rows = D.activity;
    const small = (id, key, title) => {
      lineChart($(id), {
        label: title,
        height: 190,
        yFormat: fmt.num,
        series: [{ name: title, color: PRIVATE, points: rows.map((r) => [r.date, r[key]]) }],
      });
    };
    small("chart-accounts", "active_accounts", "Daily active accounts");
    small("chart-txns", "txns", "Daily transactions");
    small("chart-contracts", "active_contracts", "Contracts receiving calls");
  }

  // ---- 7. break-even model ----------------------------------------------------------------------
  {
    const M = D.model;
    const kept = $("input-kept");
    const volume = $("input-volume");
    const cap = $("input-issuance");
    const price = $("input-price");
    const out = {
      kept: $("output-kept"), volume: $("output-volume"), cap: $("output-issuance"), price: $("output-price"),
      be: $("model-breakeven"), mult: $("model-multiple"), cover: $("model-cover"), blended: $("model-blended"),
    };
    const draw = () => {
      const k = Number(kept.value) / 100;
      const v = Number(volume.value) * 1e6;
      const c = Number(cap.value) / 100;
      const p = Number(price.value);
      out.kept.textContent = `${kept.value}%`;
      out.volume.textContent = `$${volume.value}M`;
      out.cap.textContent = `${Number(cap.value).toFixed(1)}%`;
      out.price.textContent = `$${p.toFixed(2)}`;
      const issued = (M.total_supply * c) / 365;
      const blended = M.public_bps + M.private_bps * k;
      const needed = issued * p;
      const be = blended > 0 ? needed / (blended / 1e4) : Infinity;
      out.be.textContent = Number.isFinite(be) ? `${fmt.usd(be)} a day` : "never";
      out.mult.textContent = Number.isFinite(be) ? `${(be / M.volume_per_day).toFixed(1)}× today's volume` : "no volume is enough";
      out.cover.textContent = fmt.pct((v * (blended / 1e4)) / needed);
      out.blended.textContent = `${blended.toFixed(2)} bps`;
    };
    for (const el of [kept, volume, cap, price]) el.addEventListener("input", draw);
    draw();
  }})();
