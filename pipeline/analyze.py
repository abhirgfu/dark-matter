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
    return {
        "monthly": monthly,
        "weekly": weekly,
        "daily": {d: {k: round(v, 2) for k, v in daily[d].items()} for d in sorted(daily)},
        "since_private_swaps_share": recent_private / recent_total if recent_total else None,
        "last_30_days_share": l30_private / l30_total if l30_total else None,
        "payments_checked": sum(m["payments"] for m in monthly),
        "matched_sweep_accounts": len(via),
        "covered_days": len(covered),
        "first_covered": first,
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
        summary = {
            "days": len(recent),
            "user_in_per_day": flow,
            "all_in_per_day": all_flow,
            "dwell_days": tvl_mean / all_flow if tvl_mean and all_flow else None,
            "user_share_of_volume": share,
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
        per_window.append({"window": path.name[:13], "rows": len(rows), **M.summarize_costs(pairs)})
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
    return {
        "all": M.summarize_costs(pairs_all),
        "by_class": {k: M.summarize_costs(v) for k, v in classes.items()},
        "by_size": {k: M.summarize_costs(v) for k, v in size.items()},
        "windows": per_window,
        "biggest": [{k: p[k] for k in ("usd_in", "bps", "from", "to", "seconds")} for p in biggest],
    }


# ---- 5. revenue per dollar --------------------------------------------------------------------------


def revenue(volume, fees, llama_revenue, flows_daily, prov_daily) -> dict:
    payments = [p for p in read_json(RAW / "wallet_inflows.json") if p["from"] == "intents.near"]
    wallet = collections.Counter()
    for pay in payments:
        wallet[day_of_ms(pay["ts_ms"])] += pay["usd"]

    def window(start: dt.date, end: dt.date | None) -> dict:
        days = [d for d in sorted(volume) if d >= start.isoformat() and (end is None or d <= end.isoformat()) and d in wallet]
        rev = sum(wallet[d] for d in days)
        vol = sum(volume[d] for d in days)
        return {"days": len(days), "revenue_per_day": rev / len(days) if days else None,
                "volume_per_day": vol / len(days) if days else None, "bps": rev / vol * 1e4 if vol else None}

    before = window(*WINDOW_BEFORE)
    after = window(*WINDOW_AFTER)
    weeks = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
    for day in volume:
        if day >= "2026-01-01" and day in wallet:
            d = dt.date.fromisoformat(day)
            key = (d - dt.timedelta(days=d.weekday())).isoformat()
            weeks[key][0] += wallet[day]
            weeks[key][1] += volume[day]
            weeks[key][2] += fees.get(day, 0.0)
    latest_week = max(weeks) if weeks else None
    weekly = [{"week": w, "bps": round(v[0] / v[1] * 1e4, 3), "fee_bps": round(v[2] / v[1] * 1e4, 3)}
              for w, v in sorted(weeks.items()) if w != latest_week and v[1]]

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
        "before": before,
        "after": after,
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
    bps = revenue_stats["before"]["bps"]
    volume = revenue_stats["after"]["volume_per_day"] or revenue_stats["before"]["volume_per_day"]
    return {
        "issued_near_per_day": issued_per_day,
        "issuance_rate": issued_per_day * 365 / supply[days[-1]]["total_supply_near"],
        "near_price": price,
        "near_price_date": latest,
        "public_bps": bps,
        "volume_per_day": volume,
        "break_even_all_public": M.break_even(issued_per_day, price, bps, 0.0, 1.0),
    }


def public_activity(network) -> list[dict]:
    return [{"date": d, **{k: network[d][k] for k in ("txns", "active_accounts", "active_contracts")}}
            for d in sorted(network) if d >= "2026-02-20"]


def main() -> None:
    assets = load_assets()
    llama = read_json(RAW / "defillama_near_intents.json")
    network = read_json(RAW / "network_daily.json")
    weighed = weigh(assets)
    prov = provenance()
    flow = flows(assets, weighed["series"], llama["volume"])
    cost = costs(assets)
    rev = revenue(llama["volume"], llama["fees"], llama["revenue"], flow["daily"], prov["daily"])
    mod = model(rev, network)
    derived = {
        "weigh": weighed,
        "provenance": prov,
        "flows": flow,
        "costs": cost,
        "revenue": rev,
        "model": mod,
        "activity": public_activity(network),
        "control": read_json(RAW / "control.json"),
    }
    write_json(DERIVED / "results.json", derived)
    print(json.dumps({k: derived[k] for k in ("model",)}, indent=1)[:900])
    print("tracking", weighed["tracking"], "corr", weighed["correlation"])
    print("latest", weighed["latest"])
    print("provenance", {k: prov[k] for k in ("since_private_swaps_share", "last_30_days_share", "payments_checked", "covered_days", "first_covered")})
    print("monthly", prov["monthly"])
    print("flows", flow["summary"], len(flow["daily"]))
    print("rev", {k: rev[k] for k in ("before", "after", "change_pct", "capture", "wallet_vs_defillama")})
    print("cost", cost["all"], cost["by_class"])


if __name__ == "__main__":
    main()
