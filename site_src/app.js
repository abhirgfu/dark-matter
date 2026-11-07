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
    const rows = D.provenance.monthly.filter((m) => m.month >= "2026-05").map((m) => ({
      label: fmt.month(m.month),
      title: m.month,
      private: m.private_usd,
      public: m.public_usd,
      share: m.share,
      payments: m.payments,
    }));
    stackedColumns($("chart-provenance"), {
      label: "Share of NEAR revenue that left the private treasury first, by month",
      rows,
      percent: true,
      keys: [
        { key: "private", name: "Paid out of the private treasury", color: PRIVATE },
        { key: "public", name: "No private trace", color: PUBLIC },
      ],
    });
    tableTwin($("table-provenance"), [
      { name: "Month", get: (r) => r.title },
      { name: "From the treasury", num: true, get: (r) => fmt.usd(r.private) },
      { name: "No private trace", num: true, get: (r) => fmt.usd(r.public) },
      { name: "Share", num: true, get: (r) => fmt.pct(r.share || 0) },
      { name: "Payments", num: true, get: (r) => String(r.payments) },
    ], rows);
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

  // ---- 4. revenue per dollar ---------------------------------------------------------------------
  {
    const rows = D.revenue.weekly.filter((r) => r.week >= "2026-05-01");
    lineChart($("chart-bps"), {
      label: "What NEAR keeps from each dollar of volume, by week",
      yFormat: (v) => `${v.toFixed(v < 10 ? 1 : 0)} bps`,
      series: [{ name: "Revenue per dollar of volume", color: PRIVATE, points: rows.map((r) => [r.week, r.bps]) }],
    });
    tableTwin($("table-bps"), [
      { name: "Week starting", get: (r) => r.week },
      { name: "Revenue, bps of volume", num: true, get: (r) => r.bps.toFixed(2) },
      { name: "Gross fees, bps of volume", num: true, get: (r) => r.fee_bps.toFixed(2) },
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
    const share = $("input-share");
    const ratio = $("input-ratio");
    const volume = $("input-volume");
    const cap = $("input-issuance");
    const out = {
      share: $("output-share"), ratio: $("output-ratio"), volume: $("output-volume"), cap: $("output-issuance"),
      be: $("model-breakeven"), mult: $("model-multiple"), cover: $("model-cover"), blended: $("model-blended"),
    };
    const draw = () => {
      const s = Number(share.value) / 100;
      const r = Number(ratio.value) / 100;
      const v = Number(volume.value) * 1e6;
      const c = Number(cap.value) / 100;
      out.share.textContent = `${share.value}%`;
      out.ratio.textContent = `${ratio.value}%`;
      out.volume.textContent = `$${volume.value}M`;
      out.cap.textContent = `${Number(cap.value).toFixed(1)}%`;
      const issued = (M.total_supply * c) / 365;
      const blended = M.public_bps * ((1 - s) + s * r);
      const needed = issued * M.near_price;
      const be = blended > 0 ? needed / (blended / 1e4) : Infinity;
      out.be.textContent = Number.isFinite(be) ? `${fmt.usd(be)} a day` : "never";
      out.mult.textContent = Number.isFinite(be) ? `${(be / M.volume_per_day).toFixed(1)}× today's volume` : "no volume is enough";
      const revenue = v * (blended / 1e4);
      out.cover.textContent = fmt.pct(revenue / needed);
      out.blended.textContent = `${blended.toFixed(2)} bps`;
    };
    for (const el of [share, ratio, volume, cap]) el.addEventListener("input", draw);
    draw();
  }
})();
