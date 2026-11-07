"""Record what crosses the boundary between the public chain and the private chain.

Every shielded dollar enters by a transfer to the treasury on intents.near and leaves by a transfer
from it. Those transfers are public, even though what happens between them is not. This file pulls
them from FastNear's free Transfers API, one UTC day at a time.

Two datasets come out of it:

  census   every transfer of at least MIN_USD, for each day
           data/raw/flows/YYYY-MM-DD.csv.gz

  windows  every transfer of any size, for short windows, which tells us what the census misses
           data/raw/flow_windows/YYYY-MM-DDTHH.csv.gz

The API allows about ten calls a minute, so a busy day takes several minutes. Finished days are
kept and skipped on the next run.

    python pipeline/fetch_flows.py census --since 2026-10-01
    python pipeline/fetch_flows.py windows --since 2026-10-20 --per-day 1
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import io
import random
import sys

from common import RAW, TRANSFERS_API, TREASURY, day_ms, post_json, read_json, write_json

MIN_USD = 1000.0
FLOWS = RAW / "flows"
WINDOWS = RAW / "flow_windows"
COVERAGE = RAW / "flows_coverage.json"
COLUMNS = ("ts_ms", "tx", "other", "asset", "amount", "usd")
ASSET_PREFIX = "nep245:intents.near:"


def pull(start_ms: int, end_ms: int, min_usd: float, account: str = TREASURY, asset: str | None = None,
         direction: str | None = None) -> list[tuple]:
    """All transfers in [start_ms, end_ms) for an account, oldest first."""
    rows, token, pages = [], None, 0
    while True:
        body = {"account_id": account, "from_timestamp_ms": start_ms, "to_timestamp_ms": end_ms - 1,
                "limit": 100, "desc": False}
        if min_usd > 0:
            body["min_usd_amount"] = min_usd
        if asset:
            body["asset_id"] = asset
        if direction:
            body["direction"] = direction
        if token:
            body["resume_token"] = token
        page = post_json(TRANSFERS_API, body)
        batch = page.get("transfers", [])
        pages += 1
        for t in batch:
            if t.get("transfer_type") != "MtTransfer":
                continue
            rows.append((
                int(int(t["block_timestamp"]) / 1_000_000),
                t.get("transaction_id") or "",
                t.get("other_account_id") or "",
                (t.get("asset_id") or "").removeprefix(ASSET_PREFIX),
                t.get("amount") or "0",
                round(float(t.get("usd_amount") or 0), 2),
            ))
        token = page.get("resume_token")
        if not batch or not token:
            return rows


def write_rows(path, rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = io.StringIO(newline="")
    out = csv.writer(text, lineterminator="\n")
    out.writerow(COLUMNS)
    out.writerows(sorted(rows))
    # mtime=0 so that the same rows always give the same bytes and the same hash
    with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as gz:
        gz.write(text.getvalue().encode())


def read_rows(path) -> list[dict]:
    with gzip.open(path, "rt", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def census(since: dt.date, until: dt.date, min_usd: float) -> None:
    coverage = read_json(COVERAGE) if COVERAGE.exists() else {}
    day = until
    while day >= since:  # newest first: recent days matter most if a run is cut short
        key = day.isoformat()
        path = FLOWS / f"{key}.csv.gz"
        if not path.exists() or coverage.get(key, {}).get("min_usd", 1e18) > min_usd:
            rows = pull(day_ms(day), day_ms(day + dt.timedelta(days=1)), min_usd)
            write_rows(path, rows)
            coverage[key] = {"rows": len(rows), "min_usd": min_usd}
            write_json(COVERAGE, coverage)
            print(key, "rows", len(rows), flush=True)
        day -= dt.timedelta(days=1)


def windows(since: dt.date, until: dt.date, per_day: int) -> None:
    """One or more whole hours per day, at random, every transfer of any size."""
    rng = random.Random(20261107)
    day = since
    while day <= until:
        hours = rng.sample(range(24), per_day)
        for hour in hours:
            path = WINDOWS / f"{day.isoformat()}T{hour:02d}.csv.gz"
            if path.exists():
                continue
            start = day_ms(day) + hour * 3_600_000
            rows = pull(start, start + 3_600_000, 0)
            write_rows(path, rows)
            print(path.stem, "rows", len(rows), flush=True)
        day += dt.timedelta(days=1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("census", "windows"))
    ap.add_argument("--since", default="2026-02-20")
    ap.add_argument("--until", default=None)
    ap.add_argument("--min-usd", type=float, default=MIN_USD)
    ap.add_argument("--per-day", type=int, default=1)
    args = ap.parse_args()
    yesterday = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    until = dt.date.fromisoformat(args.until) if args.until else yesterday
    since = dt.date.fromisoformat(args.since)
    if args.mode == "census":
        census(since, until, args.min_usd)
    else:
        windows(since, until, args.per_day)


if __name__ == "__main__":
    sys.exit(main())
