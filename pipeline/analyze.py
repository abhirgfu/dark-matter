"""Turn committed raw data into every number on the site and in THESIS.md.

Reads data/raw and data/static, writes data/derived. Needs no network, so anyone can run it offline.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import gzip
import json
import statistics
import time

import metrics as M
from common import DERIVED, PRIVATE_SWAPS_START, RAW, STATIC, TREASURY, read_json, write_json

WINDOW_BEFORE = (dt.date(2026, 9, 27), dt.date(2026, 10, 26))
WINDOW_AFTER = (PRIVATE_SWAPS_START, None)
ERA_SHARE = 0.25  # the private era starts when this share of revenue comes from the treasury
ERA_BASELINE_DAYS = 60  # compared with this many days just before it


def day_of_ms(ms: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(int(ms) / 1000))


def read_gz_csv(path) -> list[dict]:
    with gzip.open(path, "rt", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_assets() -> dict[str, dict]:
    with open(STATIC / "assets.csv", newline="", encoding="utf-8") as fh:
        return {r["asset_id"]: r for r in csv.DictReader(fh)}


def load_treasury() -> dict[str, dict]:
    with open(RAW / "treasury_daily.jsonl", encoding="utf-8") as fh:
        return {r["date"]: r for r in map(json.loads, fh)}


# ---- 1. weigh -----------------------------------------------------------------------------------


def weigh(assets) -> dict:
    days = load_treasury()
    prices = read_json(RAW / "prices_daily.json")
    reported = {r["date"]: r["value"] for r in read_json(RAW / "near_reported.json")["tvlChartSeries"]}
    series = []
    for day in sorted(days):
        value = M.value_treasury(days[day]["balances"], assets, prices, day)
        previous = (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat()
        series.append({
            "date": day,
            "weighed": round(value["usd"], 2),
            # NEAR's value for a date is the end of that UTC day, and ours is the start of it, so
            # the fair comparison for our reading on day D is NEAR's figure for D-1.
            "reported": round(reported[previous], 2) if previous in reported else None,
            "tokens": value["tokens"],
            "unpriced_tokens": value["unpriced_tokens"],
            "by_symbol": value["by_symbol"],
        })
    pairs = [(r["weighed"], r["reported"]) for r in series if r["reported"] and r["reported"] > 1e6]
    recent = pairs[-60:]
    latest = series[-1]
    top = sorted(latest["by_symbol"].items(), key=lambda kv: -kv[1])
    near_series = []
    wnear = "nep141:wrap.near"
    for day in sorted(days):
        near_series.append({"date": day, "near": int(days[day]["balances"].get(wnear, "0")) / 1e24})
    return {
        "series": [{k: r[k] for k in ("date", "weighed", "reported")} for r in series],
        "tracking": M.tracking_error(pairs),
        "recent_gap_pct": M.tracking_error(recent).get("median_abs_pct"),
        "correlation": M.correlation([p[0] for p in pairs], [p[1] for p in pairs]) if len(pairs) > 2 else None,
        "latest": {k: latest[k] for k in ("date", "weighed", "reported", "tokens", "unpriced_tokens")},
        "block": days[latest["date"]]["block"],
        "composition": [{"symbol": s, "usd": round(v, 2)} for s, v in top],
        "near_series": near_series,
    }


# ---- 2. provenance ---------------------------------------------------------------------------


def provenance() -> dict:
    payments = [p for p in read_json(RAW / "wallet_inflows.json") if p["from"] == "intents.near"]
    outflows = []
    covered = []
    for path in sorted((RAW / "wnear_out").glob("*.csv.gz")):
        covered.append(path.name[:10])
        outflows += read_gz_csv(path)
    marked = M.match_payments(payments, outflows)
    covered_set = set(covered)
    months = collections.defaultdict(lambda: {"private": 0.0, "public": 0.0, "n_private": 0, "n_public": 0})
    weeks = collections.defaultdict(lambda: {"private": 0.0, "public": 0.0})
    daily = collections.defaultdict(lambda: {"private": 0.0, "public": 0.0})
    first = min(covered) if covered else None
    for pay in marked:
        day = day_of_ms(pay["ts_ms"])
        if day in covered_set or (first and day < first):
            # Days before the census began have no treasury outflows to match. The first treasury
            # payment we found by hand is in July, so June 20 is a safe floor: see METHOD.md.
            kind = "private" if pay["private"] else "public"
            months[day[:7]][kind] += pay["usd"]
            months[day[:7]]["n_" + kind] += 1
            monday = dt.date.fromisoformat(day) - dt.timedelta(days=dt.date.fromisoformat(day).weekday())
            weeks[monday.isoformat()][kind] += pay["usd"]
            daily[day][kind] += pay["usd"]
    monthly = []
    for month in sorted(months):
        m = months[month]
        total = m["private"] + m["public"]
        monthly.append({
            "month": month,
            "private_usd": round(m["private"], 2),
            "public_usd": round(m["public"], 2),
            "share": round(m["private"] / total, 4) if total else None,
            "payments": m["n_private"] + m["n_public"],
        })
    weekly = []
    for week in sorted(weeks):
        w = weeks[week]
        total = w["private"] + w["public"]
        weekly.append({"week": week, "share": round(w["private"] / total, 4) if total else None,
                       "private_usd": round(w["private"], 2), "public_usd": round(w["public"], 2)})
    recent = [d for d in sorted(daily) if d >= (PRIVATE_SWAPS_START.isoformat())]
    recent_private = sum(daily[d]["private"] for d in recent)
    recent_total = sum(daily[d]["private"] + daily[d]["public"] for d in recent)
    last30 = sorted(daily)[-30:]
    l30_private = sum(daily[d]["private"] for d in last30)
    l30_total = sum(daily[d]["private"] + daily[d]["public"] for d in last30)
    via = collections.Counter(p["via"] for p in marked if p["private"])
    first_private = min((day_of_ms(p["ts_ms"]) for p in marked if p["private"]), default=None)
    return {
        "monthly": monthly,
        "weekly": weekly,
        "daily": {d: {k: round(v, 2) for k, v in daily[d].items()} for d in sorted(daily)},
        "since_private_swaps_share": recent_private / recent_total if recent_total else None,
        "last_30_days_share": l30_private / l30_total if l30_total else None,
        "payments_checked": sum(m["payments"] for m in monthly),
        "matched_sweep_accounts": len(via),
        "first_private_payment": first_private,
        "covered_days": len(covered),
        "first_covered": first,
    }


def hand_trace() -> dict:
    """What reading four transactions a week showed, before the exact match was run on all of them."""
    rows = read_json(RAW / "hand_trace.json")
    read = [r for r in rows if r["signer"]]
    from_treasury = [r for r in read if r["src"] and r["src"][0][0] == TREASURY]
    first = min((r["date"] for r in from_treasury), default=None)
    early = [r for r in read if r["date"] < "2026-07-01"]
    return {
        "sampled": len(rows),
        "read": len(read),
        "from_treasury": len(from_treasury),
        "treasury_accounts": len({r["signer"] for r in from_treasury}),
        "first_from_treasury": first,
        "before_july": len(early),
        "before_july_from_treasury": sum(1 for r in early if r in from_treasury),
    }


# ---- 3. flows ------------------------------------------------------------------------------------


def flows(assets, tvl_series, volume) -> dict:
    daily = []
    who = collections.Counter()
    who_recent = collections.Counter()
    by_class_recent = collections.Counter()
    tvl = {r["date"]: r["weighed"] for r in tvl_series}
    for path in sorted((RAW / "flows_in").glob("*.csv.gz")):
        day = path.name[:10]
        rows = read_gz_csv(path)
        solver = user = 0.0
        accounts = set()
        for row in rows:
            usd = float(row["usd"])
            if usd <= 0:
                continue
            kind = M.account_class(row["other"])
            if kind == "solver":
                solver += usd
            else:
                user += usd
                accounts.add(row["other"])
            who[row["other"]] += usd
            if day >= PRIVATE_SWAPS_START.isoformat():
                who_recent[row["other"]] += usd
                by_class_recent[kind] += usd
        daily.append({
            "date": day,
            "user_in_usd": round(user, 2),
            "solver_in_usd": round(solver, 2),
            "accounts": len(accounts),
            "volume_usd": volume.get(day),
            "tvl_usd": tvl.get(day),
            "user_share": round(user / volume[day], 4) if volume.get(day) else None,
        })
    recent = [d for d in daily if d["date"] >= PRIVATE_SWAPS_START.isoformat()]
    summary = {}
    if recent:
        flow = statistics.mean(d["user_in_usd"] for d in recent)
        all_flow = statistics.mean(d["user_in_usd"] + d["solver_in_usd"] for d in recent)
        tvl_mean = statistics.mean(d["tvl_usd"] for d in recent if d["tvl_usd"]) if any(d["tvl_usd"] for d in recent) else None
        vol_days = [d for d in recent if d["volume_usd"]]
        share = sum(d["user_in_usd"] for d in vol_days) / sum(d["volume_usd"] for d in vol_days) if vol_days else None
        def period(days):
            with_volume = [d for d in days if d["volume_usd"]]
            if not with_volume:
                return None
            return {
                "days": len(with_volume),
                "share": sum(d["user_in_usd"] for d in with_volume) / sum(d["volume_usd"] for d in with_volume),
                "accounts": statistics.mean(d["accounts"] for d in with_volume),
                "user_in_per_day": statistics.mean(d["user_in_usd"] for d in with_volume),
            }

        summary = {
            "days": len(recent),
            "user_in_per_day": flow,
            "all_in_per_day": all_flow,
            "dwell_days": tvl_mean / all_flow if tvl_mean and all_flow else None,
            "user_share_of_volume": share,
            "before": period([d for d in daily if d["date"] < PRIVATE_SWAPS_START.isoformat()]),
            "last_week": period(daily[-7:]),
        }
    return {
        "daily": daily,
        "summary": summary,
        "top_recent": [{"account": a, "usd": round(v, 2)} for a, v in who_recent.most_common(12)],
        "class_recent": {k: round(v, 2) for k, v in by_class_recent.items()},
    }


# ---- 4. cost of a private swap ---------------------------------------------------------------------


def costs(assets) -> dict:
    rows = []
    windows = sorted((RAW / "flow_windows").glob("*.csv.gz"))
    pairs_all = []
    per_window = []
    symbols = {a: info["symbol"] for a, info in assets.items()}
    for path in windows:
        rows = read_gz_csv(path)
        pairs = M.pair_accounts(rows, symbols)
        pairs_all += [{**p, "window": path.name[:13]} for p in pairs]
        stamps = [int(r["ts_ms"]) for r in rows]
        hours = max(1.0, (max(stamps) - min(stamps)) / 3_600_000) if stamps else 1.0
        summary = M.summarize_costs(pairs)
        lost = sum(p["usd_in"] - p["usd_out"] for p in pairs)
        per_window.append({
            "window": path.name[:13], "date": path.name[:10], "rows": len(rows), "hours": round(hours, 2),
            "swaps_per_hour": round(len(pairs) / hours, 1), "usd_per_hour": round(summary.get("usd", 0.0) / hours, 2),
            "lost_usd_per_hour": round(lost / hours, 2), **summary,
        })
    # The fee shows only on swaps between different assets of a size where cents do not matter, and
    # only since swaps moved to the private chain.
    late_pairs = [p for p in pairs_all if p["window"][:10] >= PRIVATE_SWAPS_START.isoformat()]
    priced = [p for p in late_pairs if p["usd_in"] >= 50
              and not (M.asset_class(p["from"]) == "stable" and M.asset_class(p["to"]) == "stable")]
    routes = collections.defaultdict(list)
    for pair in priced:
        routes[f"{pair['from']} to {pair['to']}"].append(pair["bps"])
    top_routes = sorted(routes.items(), key=lambda kv: -len(kv[1]))[:14]
    by_size_priced = collections.defaultdict(list)
    for pair in priced:
        u = pair["usd_in"]
        by_size_priced["under $1K" if u < 1000 else "$1K to $10K" if u < 10000 else "over $10K"].append(pair["bps"])
    fingerprint = {
        **M.fee_fingerprint(priced),
        "routes": [{"route": k, "n": len(v), "median_bps": round(statistics.median(v), 1)} for k, v in top_routes],
        "by_size": {k: round(statistics.median(v), 1) for k, v in by_size_priced.items()},
    }
    classes = collections.defaultdict(list)
    for pair in pairs_all:
        a, b = M.asset_class(pair["from"]), M.asset_class(pair["to"])
        name = "stable to stable" if a == b == "stable" else "with a privacy coin" if "privacy" in (a, b) else "other"
        classes[name].append(pair)
    size = collections.defaultdict(list)
    for pair in pairs_all:
        u = pair["usd_in"]
        size["under $1K" if u < 1000 else "$1K to $10K" if u < 10000 else "over $10K"].append(pair)
    biggest = sorted(pairs_all, key=lambda p: -p["usd_in"])[:10]
    cut = PRIVATE_SWAPS_START.isoformat()
    early = [w for w in per_window if w["date"] < cut]
    late = [w for w in per_window if w["date"] >= cut]
    rate = lambda items, key: sum(w[key] * w["hours"] for w in items) / sum(w["hours"] for w in items) if items else None
    return {
        "fingerprint": fingerprint,
        "swaps_per_hour_before": rate(early, "swaps_per_hour"),
        "swaps_per_hour_after": rate(late, "swaps_per_hour"),
        "usd_per_hour_after": rate(late, "usd_per_hour"),
        "lost_usd_per_hour_after": rate(late, "lost_usd_per_hour"),
        "hours_before": sum(w["hours"] for w in early),
        "hours_after": sum(w["hours"] for w in late),
        "all": M.summarize_costs(pairs_all),
        "by_class": {k: M.summarize_costs(v) for k, v in classes.items()},
        "by_size": {k: M.summarize_costs(v) for k, v in size.items()},
        "windows": per_window,
        "biggest": [{k: p[k] for k in ("usd_in", "bps", "from", "to", "seconds")} for p in biggest],
    }


# ---- 5. revenue per dollar --------------------------------------------------------------------------


def private_era(weekly: list[dict]) -> dt.date | None:
    """The first week of two in a row with at least a quarter of revenue paid from the treasury."""
    for this_week, next_week in zip(weekly, weekly[1:]):
        if (this_week["share"] or 0) >= ERA_SHARE and (next_week["share"] or 0) >= ERA_SHARE:
            return dt.date.fromisoformat(this_week["week"])
    return None


def revenue(volume, fees, llama_revenue, flows_daily, prov) -> dict:
    payments = [p for p in read_json(RAW / "wallet_inflows.json") if p["from"] == "intents.near"]
    wallet = collections.Counter()
    for pay in payments:
        wallet[day_of_ms(pay["ts_ms"])] += pay["usd"]
    traced = prov["daily"]

    def window(start: dt.date, end: dt.date | None) -> dict:
        days = [d for d in sorted(volume) if d >= start.isoformat() and (end is None or d <= end.isoformat()) and d in wallet]
        rev = sum(wallet[d] for d in days)
        vol = sum(volume[d] for d in days)
        fee = sum(fees.get(d, 0.0) for d in days)
        private = sum(traced.get(d, {}).get("private", 0.0) for d in days)
        return {"days": len(days), "revenue_per_day": rev / len(days) if days else None,
                "volume_per_day": vol / len(days) if days else None, "bps": rev / vol * 1e4 if vol else None,
                "fee_bps": fee / vol * 1e4 if vol else None,
                "private_bps": private / vol * 1e4 if vol else None,
                "public_bps": (rev - private) / vol * 1e4 if vol else None,
                "capture": rev / fee if fee else None}

    route_start = private_era(prov["weekly"]) or PRIVATE_SWAPS_START
    weeks = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0])
    for day in volume:
        if day >= "2026-01-01" and day in wallet:
            d = dt.date.fromisoformat(day)
            key = (d - dt.timedelta(days=d.weekday())).isoformat()
            weeks[key][0] += wallet[day]
            weeks[key][1] += volume[day]
            weeks[key][2] += fees.get(day, 0.0)
            weeks[key][3] += traced.get(day, {}).get("private", 0.0)
            weeks[key][4] += 1
    weekly = [{"week": w, "bps": round(v[0] / v[1] * 1e4, 3), "fee_bps": round(v[2] / v[1] * 1e4, 3),
               "private_bps": round(v[3] / v[1] * 1e4, 3), "public_bps": round((v[0] - v[3]) / v[1] * 1e4, 3),
               "days": v[4]}
              for w, v in sorted(weeks.items()) if v[1] and v[4] >= 5]

    # Two separate moments. The route changed first; the take stepped up later. Each date comes from
    # the data: the route by a share threshold, the step by the best two-level fit to weekly revenue
    # per dollar since June.
    since_june = [w for w in weekly if w["week"] >= "2026-06-01"]
    at = M.change_point([w["bps"] for w in since_june])
    step = dt.date.fromisoformat(since_june[at]["week"]) if at is not None else route_start
    before = window(step - dt.timedelta(days=ERA_BASELINE_DAYS), step - dt.timedelta(days=1))
    after = window(step, None)
    between = window(route_start, step - dt.timedelta(days=1))
    late_before = window(*WINDOW_BEFORE)
    late_after = window(*WINDOW_AFTER)

    # What is a private dollar worth to NEAR, against a public one? Fit on days with both figures.
    rows = []
    for item in flows_daily:
        day = item["date"]
        if day in wallet and item["volume_usd"]:
            priv = item["user_in_usd"]
            pub = max(item["volume_usd"] - priv, 0.0)
            rows.append((day, [pub, priv], wallet[day]))
    capture = None
    if len(rows) >= 21:
        fit = M.block_bootstrap_ols([r[1] for r in rows], [r[2] for r in rows])
        a, b = fit["terms"]
        capture = {
            "days": len(rows),
            "public_bps": a["estimate"] * 1e4,
            "public_bps_low": a["low"] * 1e4,
            "public_bps_high": a["high"] * 1e4,
            "private_bps": b["estimate"] * 1e4,
            "private_bps_low": b["low"] * 1e4,
            "private_bps_high": b["high"] * 1e4,
            "ratio": b["estimate"] / a["estimate"] if a["estimate"] else None,
        }
    llama_days = [d for d in wallet if d in llama_revenue and d >= "2026-06-20"]
    wallet_sum = sum(wallet[d] for d in llama_days)
    llama_sum = sum(llama_revenue[d] for d in llama_days)
    return {
        "era_start": step.isoformat(),
        "route_start": route_start.isoformat(),
        "between": between,
        "before": before,
        "after": after,
        "late_before": late_before,
        "late_after": late_after,
        "change_pct": (after["bps"] / before["bps"] - 1) * 100 if before["bps"] and after["bps"] else None,
        "weekly": weekly,
        "capture": capture,
        "wallet_vs_defillama": {"days": len(llama_days), "wallet_usd": wallet_sum, "defillama_usd": llama_sum,
                                "gap_pct": (wallet_sum / llama_sum - 1) * 100 if llama_sum else None},
    }


# ---- 6. model inputs and public activity ---------------------------------------------------------


def model(revenue_stats, network) -> dict:
    supply = read_json(RAW / "near_supply.json")
    days = sorted(supply)
    span = (dt.date.fromisoformat(days[-1]) - dt.date.fromisoformat(days[0])).days
    issued_per_day = (supply[days[-1]]["total_supply_near"] - supply[days[0]]["total_supply_near"]) / span
    latest = max(network)
    price = network[latest]["near_price"]
    # "Today" for the model is the take since swaps moved to the private chain.
    after = revenue_stats["late_after"]
    return {
        "issued_near_per_day": issued_per_day,
        "issuance_rate": issued_per_day * 365 / supply[days[-1]]["total_supply_near"],
        "total_supply": supply[days[-1]]["total_supply_near"],
        "near_price": price,
        "near_price_date": latest,
        "public_bps": after["public_bps"],
        "private_bps": after["private_bps"],
        "volume_per_day": after["volume_per_day"],
        "break_even_today": M.break_even(issued_per_day, price, after["public_bps"], after["private_bps"]),
        "break_even_half": M.break_even(issued_per_day, price, after["public_bps"], after["private_bps"], kept=0.5),
        "break_even_none": M.break_even(issued_per_day, price, after["public_bps"], after["private_bps"], kept=0.0),
    }


def bigquery_usage(network: dict) -> dict:
    """Usage from the BigQuery results. NearBlocks matches them on accounts and transactions, so it fills the days
    after the last run. Its active_contracts field is not a count of contracts, so it is dropped."""
    folder = RAW / "bigquery"
    merged = {d: {k: v for k, v in row.items() if k != "active_contracts"} for d, row in network.items()}
    with open(folder / "network_daily.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["date"] in merged:
                merged[row["date"]].update(active_accounts=int(row["active_signers"]), txns=int(row["transactions"]))
    with open(folder / "contract_usage_daily.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["date"] in merged:
                merged[row["date"]].update(function_calls=int(row["function_calls"]), active_contracts=int(row["active_contracts"]))
    return merged


def source_agreement(nearblocks: dict) -> dict:
    """How often BigQuery and NearBlocks give the same daily number."""
    with open(RAW / "bigquery" / "network_daily.csv", newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["date"] in nearblocks]
    return {
        "days": len(rows),
        "accounts_equal": sum(int(r["active_signers"]) == nearblocks[r["date"]]["active_accounts"] for r in rows),
        "txns_equal": sum(int(r["transactions"]) == nearblocks[r["date"]]["txns"] for r in rows),
    }


def public_activity(network) -> list[dict]:
    keys = ("txns", "active_accounts", "function_calls", "active_contracts")
    return [{"date": d, **{k: network[d].get(k) for k in keys}} for d in sorted(network) if d >= "2025-01-01"]


# The four windows in sql/top_contracts.sql, and the accounts behind the fall in April 2026.
WINDOWS = {
    "1 a year ago": ("2025-10-24", "2025-11-06"),
    "2 before the fall": ("2026-03-18", "2026-03-31"),
    "3 after the fall": ("2026-04-03", "2026-04-16"),
    "4 now": ("2026-10-24", "2026-11-06"),
}
SENDER = ("users.kaiching", "wallet.kaiching")


def destinations(network: dict) -> dict:
    """Where the public chain's transactions go."""
    folder = RAW / "bigquery"
    with open(folder / "intents_daily.csv", newline="", encoding="utf-8") as fh:
        intents = {r["date"]: float(r["transactions"]) for r in csv.DictReader(fh)}
    with open(folder / "top_contracts.csv", newline="", encoding="utf-8") as fh:
        top = list(csv.DictReader(fh))
    days = sorted(d for d in intents if d in network)
    last = days[-1]
    weekly_in = M.weekly({d: intents[d] for d in days}, "sum")
    weekly_all = M.weekly({d: float(network[d]["txns"]) for d in days}, "sum")

    def before(end: str, count: int = 90) -> list[str]:
        finish = dt.date.fromisoformat(end)
        return [d for d in days if finish - dt.timedelta(days=count) < dt.date.fromisoformat(d) <= finish]

    now, then = before(last), before((dt.date.fromisoformat(last) - dt.timedelta(days=365)).isoformat())
    share = lambda span: sum(intents[d] for d in span) / sum(network[d]["txns"] for d in span)
    per_day = lambda values: sum(values) / len(values)

    windows = {}
    for period, (first, final) in WINDOWS.items():
        span = [d for d in days if first <= d <= final]
        total = sum(network[d]["txns"] for d in span)
        windows[period] = {
            "first": first, "last": final, "per_day": total / len(span),
            "rows": [{"family": r["family"], "per_day": int(r["transactions"]) / len(span),
                      "share": int(r["transactions"]) / total, "accounts": int(r["accounts"]), "signers": int(r["signers"])}
                     for r in top if r["period"] == period],
        }

    def rank(period: str) -> int:
        named = [r["family"] for r in windows[period]["rows"] if not r["family"].startswith("(")]
        return named.index("intents.near") + 1

    sender = lambda period: sum(r["per_day"] for r in windows[period]["rows"] if r["family"] in SENDER)
    gap = lambda a, b: (sender(a) - sender(b)) / (windows[a]["per_day"] - windows[b]["per_day"])
    a, b, c, d = WINDOWS
    return {
        "last_day": last,
        "weekly_share": [{"date": w, "share": weekly_in[w] / weekly_all[w]} for w in weekly_in if w >= "2025-01-01"],
        "share_then": share(then), "share_now": share(now),
        "share_recent": share([x for x in days if WINDOWS[d][0] <= x <= WINDOWS[d][1]]),
        "intents_per_day_then": per_day([intents[x] for x in then]),
        "intents_per_day_now": per_day([intents[x] for x in now]),
        "chain_per_day_then": per_day([network[x]["txns"] for x in then]),
        "chain_per_day_now": per_day([network[x]["txns"] for x in now]),
        "rank_then": rank(a), "rank_now": rank(d),
        "windows": windows,
        "sender": {
            "per_day": sender(b),
            "share": sender(b) / windows[b]["per_day"],
            "share_of_fall": gap(b, c),
            "share_of_year_fall": gap(a, d),
            "signers": sum(r["signers"] for r in windows[b]["rows"] if r["family"] in SENDER),
            "accounts": sum(r["accounts"] for r in windows[b]["rows"] if r["family"] in SENDER),
        },
    }


# ---- 7. the hypothesis in the track prompt ---------------------------------------------------------


USAGE = {"active_accounts": "Daily active accounts", "txns": "Daily transactions", "function_calls": "Function calls"}


def hypothesis(volume, network) -> dict:
    """Is Intents volume a better leading indicator of real network usage than the NEAR price?"""
    v = M.weekly(volume, "sum")
    series = {key: M.weekly({d: float(network[d][key]) for d in network if key in network[d]}) for key in USAGE}
    price = M.weekly({d: network[d]["near_price"] for d in network if network[d]["near_price"] > 0})
    weeks = [w for w in sorted(v) if v[w] > 0 and w in price and all(series[k].get(w, 0) > 0 for k in USAGE)]
    vol = [v[w] for w in weeks]
    pri = [price[w] for w in weeks]
    tests, profiles = {}, {}
    for key in USAGE:
        use = [series[key][w] for w in weeks]
        tests[key] = M.leading_test(vol, pri, use)
        by_volume = M.lag_profile(vol, use)
        by_price = M.lag_profile(pri, use)
        profiles[key] = [{"lag": a["lag"], "volume": round(a["r"], 4), "price": round(b["r"], 4)}
                         for a, b in zip(by_volume, by_price)]
    wins = sum(1 for t in tests.values() if t["difference_low"] > 0)
    losses = sum(1 for t in tests.values() if t["difference_high"] < 0)
    # Volume began from almost nothing, so the common base is October 2025, when it became meaningful.
    base = next(w for w in weeks if w >= "2025-10-01")
    index = [{"date": w, "volume": round(v[w] / v[base] * 100, 2), "price": round(price[w] / price[base] * 100, 2),
              "accounts": round(series["active_accounts"][w] / series["active_accounts"][base] * 100, 2)}
             for w in weeks if w >= base]
    return {"weeks": len(weeks), "first": weeks[0], "last": weeks[-1], "tests": tests, "profiles": profiles,
            "index": index, "clear_wins": wins, "clear_losses": losses}


# ---- 8. the long term ------------------------------------------------------------------------------


def long_term(llama, network, rev, mod) -> dict:
    volume = llama["volume"]
    months: dict[str, list[float]] = collections.defaultdict(list)
    for day, value in volume.items():
        months[day[:7]].append(value)
    full = {m: sum(v) for m, v in sorted(months.items())
            if len(v) >= (dt.date.fromisoformat(m + "-01").replace(day=28) + dt.timedelta(days=4)).replace(day=1).__sub__(dt.timedelta(days=1)).day}
    names = sorted(full)
    last_12 = [full[m] for m in names[-12:]]
    monthly_growth = M.log_trend(last_12)
    observed = (1 + monthly_growth) ** 12 - 1

    latest = max(network)
    year_ago = (dt.date.fromisoformat(latest) - dt.timedelta(days=365)).isoformat()
    mean = lambda key, days: statistics.mean(network[d][key] for d in days if key in network[d])
    now_days = sorted(d for d in network if d > (dt.date.fromisoformat(latest) - dt.timedelta(days=90)).isoformat())
    then_days = sorted(d for d in network if year_ago >= d > (dt.date.fromisoformat(year_ago) - dt.timedelta(days=90)).isoformat())
    usage_change = {k: mean(k, now_days) / mean(k, then_days) - 1 for k in USAGE}
    # A few days in late 2025 reach about 90,000, so a typical day is the median, not the mean.
    typical = lambda days: statistics.median(network[d]["active_contracts"] for d in days if "active_contracts" in network[d])

    now_vol = [volume[d] for d in now_days if d in volume]
    then_vol = [volume[d] for d in then_days if d in volume]
    volume_change = statistics.mean(now_vol) / statistics.mean(then_vol) - 1 if then_vol else None

    late, late_before = rev["late_after"], rev["late_before"]
    supply, price, day_volume = mod["total_supply"], mod["near_price"], mod["volume_per_day"]
    rate_now, rate_floor = 0.025, 0.016
    cases = {
        "stalls": {"name": "Stalls", "growth": 0.0, "take_bps": late["public_bps"], "rate_end": rate_now,
                   "says": "Volume stops growing, private swaps pay NEAR nothing, and issuance stays at 2.5%"},
        "holds": {"name": "Holds", "growth": observed / 2, "take_bps": late["bps"], "rate_end": rate_floor,
                  "says": "Volume grows at half its recent pace, the take stays where it is, and HSP-029 lands"},
        "wins": {"name": "Private layer wins", "growth": observed, "take_bps": late_before["bps"], "rate_end": rate_floor,
                 "says": "Volume keeps its recent pace, the take recovers, and HSP-029 lands"},
    }
    market_cap = network[latest]["market_cap"]
    for case in cases.values():
        case["path"] = M.project(day_volume, case["growth"], case["take_bps"], supply, price, rate_now, case["rate_end"])
        end = case["path"][-1]
        case["coverage_2031"] = end["coverage"]
        case["revenue_2031"] = end["revenue_per_year"]
        case["multiple_2031"] = market_cap / end["revenue_per_year"]
    revenue_now = late["revenue_per_day"] * 365
    return {
        "months": [{"month": m, "volume": round(full[m], 2)} for m in names],
        "first_month": names[0], "last_month": names[-1],
        "observed_growth": observed,
        "monthly_growth": monthly_growth,
        "volume_change_year": volume_change,
        "usage_change_year": usage_change,
        "contracts_typical": {"now": typical(now_days), "then": typical(then_days)},
        "market_cap": market_cap,
        "revenue_now_per_year": revenue_now,
        "multiple_now": market_cap / revenue_now,
        "cases": cases,
        "needed_growth_cap": M.required_growth(day_volume, late["bps"], supply, price, rate_now),
        "needed_growth_floor": M.required_growth(day_volume, late["bps"], supply, price, rate_floor),
        "needed_growth_public_only": M.required_growth(day_volume, late["public_bps"], supply, price, rate_floor),
    }


def main() -> None:
    assets = load_assets()
    llama = read_json(RAW / "defillama_near_intents.json")
    nearblocks = read_json(RAW / "network_daily.json")
    network = bigquery_usage(nearblocks)
    weighed = weigh(assets)
    prov = provenance()
    flow = flows(assets, weighed["series"], llama["volume"])
    cost = costs(assets)
    rev = revenue(llama["volume"], llama["fees"], llama["revenue"], flow["daily"], prov)
    mod = model(rev, network)
    derived = {
        "weigh": weighed,
        "provenance": prov,
        "flows": flow,
        "costs": cost,
        "revenue": rev,
        "model": mod,
        "activity": public_activity(network),
        "usage_source": "BigQuery",
        "source_agreement": source_agreement(nearblocks),
        "destinations": destinations(network),
        "hypothesis": hypothesis(llama["volume"], network),
        "long_term": long_term(llama, network, rev, mod),
        "control": read_json(RAW / "control.json"),
        "hand_trace": hand_trace(),
    }
    write_json(DERIVED / "results.json", derived)
    print(json.dumps({k: derived[k] for k in ("model",)}, indent=1)[:900])
    print("tracking", weighed["tracking"], "corr", weighed["correlation"])
    print("latest", weighed["latest"])
    print("provenance", {k: prov[k] for k in ("since_private_swaps_share", "last_30_days_share", "payments_checked", "covered_days", "first_covered")})
    print("monthly", prov["monthly"])
    print("flows", flow["summary"], len(flow["daily"]))
    print("rev", {k: rev[k] for k in ("era_start", "route_start", "between", "before", "after", "late_before", "late_after", "change_pct", "capture", "wallet_vs_defillama")})
    print("cost", cost["all"], cost["by_class"])


if __name__ == "__main__":
    main()
