"""Check the results without trusting the code that made them.

Run after analyze.py and build_site.py. It fails loudly on any of these:

 1. a raw file differs from the hash in data/manifest.json
 2. a headline number does not match an independent recalculation from the raw files, written here
    from scratch without importing metrics.py or analyze.py
 3. THESIS.md, README.md or the site still holds an unfilled {{placeholder}}, or a number that does
    not match data/derived/numbers.json
"""
from __future__ import annotations

import calendar
import csv
import gzip
import hashlib
import json
import math
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def close(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance * max(abs(a), abs(b), 1e-12)


def check_manifest() -> None:
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    bad = []
    for rel, digest in manifest.items():
        path = ROOT / rel
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            bad.append(rel)
    check(f"raw data matches the manifest ({len(manifest)} files)", not bad, ", ".join(bad[:3]))


def revenue_days() -> dict[str, float]:
    """Wallet receipts by UTC day, from intents.near only."""
    rows = json.loads((RAW / "wallet_inflows.json").read_text(encoding="utf-8"))
    days: dict[str, float] = {}
    for row in rows:
        if row["from"] == "intents.near":
            day = time.strftime("%Y-%m-%d", time.gmtime(row["ts_ms"] / 1000))
            days[day] = days.get(day, 0.0) + row["usd"]
    return days


def check_numbers(n: dict) -> None:
    # Revenue per dollar, from wallet receipts and DefiLlama volume
    volume = json.loads((RAW / "defillama_near_intents.json").read_text(encoding="utf-8"))["volume"]
    receipts = revenue_days()
    start = n["era_start"]
    first = time.strftime("%Y-%m-%d", time.gmtime(calendar.timegm(time.strptime(start, "%Y-%m-%d")) - int(n["era_baseline_days"]) * 86400))
    after_days = [d for d in receipts if d >= start and d in volume]
    before_days = [d for d in receipts if first <= d < start and d in volume]
    after = sum(receipts[d] for d in after_days) / sum(volume[d] for d in after_days) * 1e4
    before = sum(receipts[d] for d in before_days) / sum(volume[d] for d in before_days) * 1e4
    check("revenue per dollar since the step", close(after, float(n["bps_after"]), 0.002), f"{after:.3f}")
    check("revenue per dollar before the step", close(before, float(n["bps_before"]), 0.002), f"{before:.3f}")
    since = [d for d in receipts if d >= "2026-10-27" and d in volume]
    month = [d for d in receipts if "2026-09-27" <= d <= "2026-10-26" and d in volume]
    late_after = sum(receipts[d] for d in since) / sum(volume[d] for d in since) * 1e4
    late_before = sum(receipts[d] for d in month) / sum(volume[d] for d in month) * 1e4
    check("revenue per dollar since 27 Oct", close(late_after, float(n["late_bps_after"]), 0.002), f"{late_after:.3f}")
    check("revenue per dollar in the 30 days before", close(late_before, float(n["late_bps_before"]), 0.002), f"{late_before:.3f}")

    # Private share of revenue over the last 30 days, by a plain multiset match on amounts
    outflows: dict[str, list[int]] = {}
    for path in sorted((RAW / "wnear_out").glob("*.csv.gz")):
        with gzip.open(path, "rt", newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                outflows.setdefault(row["amount"].lstrip("-"), []).append(int(row["ts_ms"]))
    for times in outflows.values():
        times.sort()
    payments = sorted(
        (p for p in json.loads((RAW / "wallet_inflows.json").read_text(encoding="utf-8")) if p["from"] == "intents.near"),
        key=lambda p: p["ts_ms"],
    )
    covered = {p.name[:10] for p in (RAW / "wnear_out").glob("*.csv.gz")}
    last_30 = set(sorted(d for d in receipts if d in covered)[-30:])
    matched = total = 0.0
    for pay in payments:
        times = outflows.get(pay["yocto"], [])
        found = next((t for t in times if 0 <= pay["ts_ms"] - t <= 6 * 3_600_000), None)
        if found is not None:
            times.remove(found)
        if time.strftime("%Y-%m-%d", time.gmtime(pay["ts_ms"] / 1000)) in last_30:
            total += pay["usd"]
            if found is not None:
                matched += pay["usd"]
    share = matched / total
    shown = float(n["rev_share_recent"].rstrip("%")) / 100
    check("private share of revenue, last 30 days", abs(share - shown) <= 0.006, f"{share:.4f}")

    # NEAR held in the treasury at the latest reading
    last = None
    with open(RAW / "treasury_daily.jsonl", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if last is None or row["date"] > last["date"]:
                last = row
    near = int(last["balances"].get("nep141:wrap.near", "0")) / 1e24 / 1e6
    check("NEAR in the treasury", abs(near - float(n["near_held"].rstrip("M"))) <= 0.051, f"{near:.2f}M")

    # New NEAR per day, from two block headers
    supply = json.loads((RAW / "near_supply.json").read_text(encoding="utf-8"))
    days = sorted(supply)
    span = (calendar.timegm(time.strptime(days[-1], "%Y-%m-%d")) - calendar.timegm(time.strptime(days[0], "%Y-%m-%d"))) / 86400
    issued = (supply[days[-1]]["total_supply_near"] - supply[days[0]]["total_supply_near"]) / span
    check("new NEAR per day", close(issued, float(n["issued_day"].replace(",", "")), 0.002), f"{issued:,.0f}")


def rank_correlation(xs: list[float], ys: list[float]) -> float:
    def ranked(values: list[float]) -> list[float]:
        positions: dict[float, list[int]] = {}
        for i, value in enumerate(sorted(values)):
            positions.setdefault(value, []).append(i + 1)
        return [sum(positions[v]) / len(positions[v]) for v in values]

    a, b = ranked(xs), ranked(ys)
    mean_a, mean_b = sum(a) / len(a), sum(b) / len(b)
    top = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    return top / math.sqrt(sum((x - mean_a) ** 2 for x in a) * sum((y - mean_b) ** 2 for y in b))


def check_long_term(n: dict) -> None:
    volume = json.loads((RAW / "defillama_near_intents.json").read_text(encoding="utf-8"))["volume"]
    network = json.loads((RAW / "network_daily.json").read_text(encoding="utf-8"))

    # Growth needed by 2031, from the definition, by trying rates until revenue meets new NEAR
    supply = json.loads((RAW / "near_supply.json").read_text(encoding="utf-8"))
    total = supply[max(supply)]["total_supply_near"]
    price = network[max(network)]["near_price"]
    receipts = revenue_days()
    since = [d for d in receipts if d >= "2026-10-27" and d in volume]
    per_day = sum(volume[d] for d in since) / len(since)
    take = sum(receipts[d] for d in since) / sum(volume[d] for d in since)
    low, high = 0.0, 3.0
    for _ in range(80):
        mid = (low + high) / 2
        paid = per_day * (1 + mid) ** 5 * take
        needed = total * 1.016 ** 5 * 0.016 / 365 * price
        low, high = (mid, high) if paid < needed else (low, mid)
    shown = float(n["needed_floor"].replace("+", "").replace("\u2212", "-").rstrip("%")) / 100
    check("volume growth needed by 2031", abs(low - shown) <= 0.006, f"{low:.3f}")

    # The track's hypothesis, for active accounts
    with open(RAW / "bigquery" / "network_daily.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["date"] in network:
                network[row["date"]].update(active_accounts=int(row["active_signers"]), txns=int(row["transactions"]))
    with open(RAW / "bigquery" / "contract_usage_daily.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["date"] in network:
                network[row["date"]]["function_calls"] = int(row["function_calls"])

    def whole_weeks(daily: dict[str, float], total_up: bool) -> dict[int, float]:
        buckets: dict[int, list[float]] = {}
        for day, value in daily.items():
            stamp = calendar.timegm(time.strptime(day, "%Y-%m-%d"))
            monday = stamp - (time.gmtime(stamp).tm_wday * 86400)
            buckets.setdefault(monday, []).append(value)
        return {k: (sum(v) if total_up else sum(v) / len(v)) for k, v in buckets.items() if len(v) == 7}

    weekly_volume = whole_weeks(volume, True)
    usage = {key: whole_weeks({d: float(v[key]) for d, v in network.items() if key in v}, False)
             for key in ("active_accounts", "txns", "function_calls")}
    weekly_price = whole_weeks({d: v["near_price"] for d, v in network.items() if v["near_price"] > 0}, False)
    weeks = sorted(w for w in weekly_volume if weekly_volume[w] > 0 and w in weekly_price
                   and all(usage[k].get(w, 0) > 0 for k in usage))
    accounts = usage["active_accounts"]
    span = range(4, len(weeks) - 4)
    past = [math.log(weekly_volume[weeks[t]] / weekly_volume[weeks[t - 4]]) for t in span]
    ahead = [math.log(accounts[weeks[t + 4]] / accounts[weeks[t]]) for t in span]
    r = rank_correlation(past, ahead)
    check("volume against later active accounts", abs(r - float(n["h_accounts_v"])) <= 0.006, f"{r:.3f}")


def check_destinations(n: dict) -> None:
    """intents.near's share of the chain's transactions, from the BigQuery files alone."""
    def column(name: str, field: str) -> dict[str, int]:
        with open(RAW / "bigquery" / name, newline="", encoding="utf-8") as fh:
            return {row["date"]: int(row[field]) for row in csv.DictReader(fh)}

    chain, intents = column("network_daily.csv", "transactions"), column("intents_daily.csv", "transactions")
    days = sorted(chain)[-90:]
    share = sum(intents[d] for d in days) / sum(chain[d] for d in days)
    check("intents.near's share of transactions", abs(share * 100 - float(n["intents_share_now"].rstrip("%"))) <= 0.06, f"{share:.4f}")


def check_documents(n: dict) -> None:
    for rel in ("THESIS.md", "README.md", "site/index.html"):
        path = ROOT / rel
        if not path.exists():
            check(f"{rel} exists", False)
            continue
        text = path.read_text(encoding="utf-8")
        left = re.findall(r"\{\{[a-z_0-9]+\}\}", text)
        check(f"{rel} has no unfilled placeholders", not left, ", ".join(left[:3]))
    readme = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").exists() else ""
    for key in ("rev_share_recent", "bps_after", "snapshot_usd"):
        check(f"README states {key} = {n[key]}", n[key] in readme)


def main() -> int:
    n = json.loads((ROOT / "data" / "derived" / "numbers.json").read_text(encoding="utf-8"))
    check_manifest()
    check_numbers(n)
    check_long_term(n)
    check_destinations(n)
    check_documents(n)
    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED")
        return 1
    print("ALL CHECKS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
