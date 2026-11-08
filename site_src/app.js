// Draws every chart from the data the build placed in the page, so the page works from a plain file.
"use strict";

(function main() {
  const D = JSON.parse(document.getElementById("data").textContent);
  const { lineChart, stackedColumns, groupedColumns, segmentedBar, tableTwin, fmt } = window.DMCharts;
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
        { name: "Weighed from intents.near", color: PRIVATE, points: rows.map((r) => [r.date, r.weighed]) },
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
  if (!D.flows.daily.length && $("flows-card")) $("flows-card").hidden = true;
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
  if (D.costs.windows && D.costs.windows.length && $("chart-swaps")) {
    const rows = D.costs.windows.map((w) => ({
      label: fmt.date(w.date),
      title: `${fmt.dateLong(w.date)}, ${w.hours} h sampled`,
      swaps: w.swaps_per_hour,
      n: w.n || 0,
      hours: w.hours,
    }));
    stackedColumns($("chart-swaps"), {
      label: "Private swaps seen per hour, in sampled hours",
      rows,
      height: 220,
      yFormat: (v) => `${Math.round(v)}`,
      keys: [{ key: "swaps", name: "Swaps an hour", color: PRIVATE }],
    });
    tableTwin($("table-swaps"), [
      { name: "Sample", get: (r) => r.title },
      { name: "Swaps seen", num: true, get: (r) => String(r.n) },
      { name: "Swaps an hour", num: true, get: (r) => r.swaps.toFixed(1) },
    ], rows);
  }
  if (D.costs.all && D.costs.all.n && $("chart-cost")) {
    const fp = D.costs.fingerprint;
    const rows = fp.bins.map((b) => ({ label: String(b.bps), title: `${b.bps} to ${b.bps + 10} bps`, swaps: b.n }));
    stackedColumns($("chart-cost"), {
      label: "How many private swaps cost each amount, in steps of 10 basis points",
      rows,
      height: 240,
      yFormat: (v) => `${Math.round(v)}`,
      keys: [{ key: "swaps", name: "Swaps", color: PRIVATE }],
    });
    tableTwin($("table-cost"), [
      { name: "Route", get: (r) => r.route },
      { name: "Swaps", num: true, get: (r) => String(r.n) },
      { name: "Median cost", num: true, get: (r) => fmt.bps(r.median_bps) },
    ], fp.routes, "Show cost by route");
  }

  // ---- 5b. the long term --------------------------------------------------------------------------
  {
    const rows = D.long_term.months.map((m) => ({ label: fmt.month(m.month), title: m.month, volume: m.volume }));
    stackedColumns($("chart-history"), {
      label: "NEAR Intents volume by month",
      rows,
      height: 240,
      keys: [{ key: "volume", name: "Volume", color: PRIVATE }],
    });
    tableTwin($("table-history"), [
      { name: "Month", get: (r) => r.title },
      { name: "Volume", num: true, get: (r) => fmt.usd(r.volume) },
    ], [...rows].reverse());

    const order = [["wins", PRIVATE], ["holds", THIRD], ["stalls", PUBLIC]];
    const yearOf = (d) => d.slice(0, 4);
    const percent = (v) => `${Math.round(v * 100)}%`;
    lineChart($("chart-path"), {
      label: "Share of new NEAR paid for by revenue under three cases, 2026 to 2031",
      yFormat: percent,
      xLabel: yearOf,
      series: order.map(([key, tone]) => ({
        name: D.long_term.cases[key].name,
        color: tone,
        points: D.long_term.cases[key].path.map((p) => [`${2026 + p.year}-12-31`, p.coverage]),
      })),
    });
    tableTwin($("table-path"), [
      { name: "Case", get: (r) => r.name },
      { name: "What it assumes", get: (r) => r.says },
      { name: "Volume a year", num: true, get: (r) => `${r.growth >= 0 ? "+" : ""}${Math.round(r.growth * 100)}%` },
      { name: "Take", num: true, get: (r) => fmt.bps(r.take_bps) },
      { name: "Revenue in 2031", num: true, get: (r) => fmt.usd(r.revenue_2031) },
      { name: "New NEAR paid for", num: true, get: (r) => percent(r.coverage_2031) },
      { name: "Market cap to revenue", num: true, get: (r) => `${Math.round(r.multiple_2031)}×` },
    ], order.map(([key]) => D.long_term.cases[key]), "Show the cases");
  }

  // ---- 6. the track's hypothesis and public usage -------------------------------------------------
  {
    lineChart($("chart-index"), {
      label: "Intents volume, NEAR price and active accounts, indexed",
      yFormat: (v) => `${Math.round(v)}`,
      series: [
        { name: "Intents volume", color: PRIVATE, points: D.hypothesis.index.map((r) => [r.date, r.volume]) },
        { name: "NEAR price", color: FOURTH, points: D.hypothesis.index.map((r) => [r.date, r.price]) },
        { name: "Active accounts", color: PUBLIC, points: D.hypothesis.index.map((r) => [r.date, r.accounts]) },
      ],
    });
    const lagRows = D.hypothesis.profiles.active_accounts.map((p) => ({
      label: `${p.lag}w`, title: `${p.lag} weeks later`, volume: p.volume, price: p.price,
    }));
    groupedColumns($("chart-lag"), {
      label: "Rank correlation of volume and of price with active accounts, by lag in weeks",
      rows: lagRows,
      yFormat: (v) => v.toFixed(2),
      keys: [
        { key: "volume", name: "Intents volume", color: PRIVATE },
        { key: "price", name: "NEAR price", color: FOURTH },
      ],
    });
    const names = { active_accounts: "Active accounts", txns: "Transactions", function_calls: "Function calls" };
    const testRows = Object.entries(D.hypothesis.tests).map(([key, t]) => ({ name: names[key], ...t }));
    tableTwin($("table-lag"), [
      { name: "Usage measure", get: (r) => r.name },
      { name: "Volume", num: true, get: (r) => r.volume_r.toFixed(2) },
      { name: "Price", num: true, get: (r) => r.price_r.toFixed(2) },
      { name: "Gap", num: true, get: (r) => r.difference.toFixed(2) },
      { name: "90% interval on the gap", num: true, get: (r) => `${r.difference_low.toFixed(2)} to ${r.difference_high.toFixed(2)}` },
    ], testRows, "Show the 4-week test for all three measures");

    const small = (id, key, title) => {
      lineChart($(id), {
        label: title,
        height: 190,
        yFormat: fmt.num,
        series: [{ name: title, color: PRIVATE, points: D.activity.filter((r) => r[key] != null).map((r) => [r.date, r[key]]) }],
      });
    };
    small("chart-accounts", "active_accounts", "Daily active accounts");
    small("chart-txns", "txns", "Daily transactions");
    small("chart-calls", "function_calls", "Function calls to contracts");

    lineChart($("chart-intents"), {
      label: "Share of all NEAR transactions sent to intents.near, by week",
      height: 240,
      yFormat: fmt.pct,
      series: [{ name: "intents.near", color: PRIVATE, points: D.destinations.weekly_share.map((r) => [r.date, r.share]) }],
    });
    const destinationRows = Object.entries(D.destinations.windows).flatMap(([period, w]) =>
      w.rows.slice(0, 5).map((r) => ({ period: period.slice(2), ...r })));
    tableTwin($("table-destinations"), [
      { name: "When", get: (r) => r.period },
      { name: "Destination", get: (r) => r.family },
      { name: "Transactions a day", num: true, get: (r) => fmt.num(r.per_day) },
      { name: "Share of all", num: true, get: (r) => fmt.pct(r.share) },
      { name: "Signers", num: true, get: (r) => fmt.num(r.signers) },
    ], destinationRows, "Show the busiest destinations");
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
