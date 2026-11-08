"""Record what crosses the boundary between the public chain and the private chain.

Every shielded dollar enters by a transfer to the treasury on intents.near and leaves by a transfer
from it. Those transfers are public, even though what happens between them is not. This file pulls
them from FastNear's free Transfers API, one UTC day at a time. The API allows about ten calls a
minute and returns 100 rows a call, so we ask for what each question needs and no more:

  wnear    every wNEAR transfer of at least $400 out of the treasury, which is how revenue leaves
           the private chain
           data/raw/wnear_out/YYYY-MM-DD.csv.gz

  inflows  every transfer into the treasury of at least MIN_USD. About 5% of rows, about 95% of
           dollars. Daily shielding flow and who does it.
           data/raw/flows_in/YYYY-MM-DD.csv.gz

  windows  every transfer of any size, both ways, for one random hour. This is what shows the
           cost of a private swap, and what the census leaves out.
           data/raw/flow_windows/YYYY-MM-DDTHH.csv.gz

Finished days are kept and skipped on the next run, so it is safe to stop and restart.

    python pipeline/fetch_flows.py plan            # all three, most useful first
    python pipeline/fetch_flows.py wnear --since 2026-06-20
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import io
import random
import sys
import time

from common import RAW, TRANSFERS_API, TREASURY, day_ms, post_json

MIN_USD = 2500.0
WNEAR = "nep245:intents.near:nep141:wrap.near"
COLUMNS = ("ts_ms", "tx", "other", "asset", "amount", "usd")
ASSET_PREFIX = "nep245:intents.near:"
# Windows before 27 Oct show the older use of the private chain; the rest show private swaps.
WINDOW_DAYS = [dt.date(2026, 9, 15), dt.date(2026, 10, 5), dt.date(2026, 10, 20)] + [
    dt.date(2026, 10, 28) + dt.timedelta(days=d) for d in range(0, 10, 2)
]


def pull(start_ms: int, end_ms: int, **filters) -> list[tuple]:
    """All intents.near transfers of the treasury in [start_ms, end_ms), oldest first."""
    rows, token, pages, began = [], None, 0, time.monotonic()
    while True:
        body = {"account_id": TREASURY, "from_timestamp_ms": start_ms, "to_timestamp_ms": end_ms - 1,
                "limit": 100, "desc": False, **filters}
        if token:
            body["resume_token"] = token
        page = post_json(TRANSFERS_API, body, tries=20)
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
        if pages % 20 == 0:
            print(f"  ...{pages} pages, {len(rows)} rows, {(time.monotonic() - began) / pages:.1f}s a page", flush=True)
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


def daily(folder: str, since: dt.date, until: dt.date, **filters) -> None:
    day = until
    while day >= since:  # newest first: recent days matter most if a run is cut short
        path = RAW / folder / f"{day.isoformat()}.csv.gz"
        if not path.exists():
            rows = pull(day_ms(day), day_ms(day + dt.timedelta(days=1)), **filters)
            write_rows(path, rows)
            print(folder, day, "rows", len(rows), flush=True)
        day -= dt.timedelta(days=1)


def wnear(since: dt.date, until: dt.date) -> None:
    # Every revenue payment since April is above $500: revenue is swept in lumps of about $1,000.
    # The $400 floor keeps all of them and drops about 90% of rows, which are dust.
    daily("wnear_out", since, until, asset_id=WNEAR, direction="sender", min_usd_amount=400.0)


def inflows(since: dt.date, until: dt.date) -> None:
    daily("flows_in", since, until, direction="receiver", min_usd_amount=MIN_USD)


def windows() -> None:
    rng = random.Random(20261107)
    for day in WINDOW_DAYS:
        hour = rng.randrange(24)
        path = RAW / "flow_windows" / f"{day.isoformat()}T{hour:02d}.csv.gz"
        if path.exists():
            continue
        start = day_ms(day) + hour * 3_600_000
        rows = pull(start, start + 3_600_000)
        write_rows(path, rows)
        print("window", path.stem, "rows", len(rows), flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("plan", "wnear", "inflows", "windows"))
    ap.add_argument("--since", default=None)
    ap.add_argument("--until", default=None)
    args = ap.parse_args()
    yesterday = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    until = dt.date.fromisoformat(args.until) if args.until else yesterday
    since = dt.date.fromisoformat(args.since) if args.since else None
    if args.mode in ("plan", "wnear"):
        wnear(since or dt.date(2026, 6, 20), until)
    if args.mode in ("plan", "windows"):
        windows()
    if args.mode in ("plan", "inflows"):
        inflows(since or dt.date(2026, 10, 12), until)


if __name__ == "__main__":
    sys.exit(main())
