"""Optional: swap volume by route from the NEAR Intents Explorer API.

It covers 1Click swaps only, and it marks a swap as confidential when a leg starts or ends in a
confidential balance. That makes it a direct check on what we infer at the boundary. A swap between two
outside chains can be confidential and still look public here, so it sets a floor, not a total. It
needs a JWT from https://partners.near-intents.org. Put it in .env:

    INTENTS_JWT=...

The 1Click terms do not allow keeping API data for more than 24 hours. So this writes daily totals to
data/local/, which git ignores, and nothing on the site depends on them. Run it, run
pipeline/explorer_check.py, and delete the files within a day.

    python pipeline/fetch_explorer.py --days 14
    python pipeline/fetch_explorer.py --since 2025-01-01 --min-usd 2500
"""
from __future__ import annotations

import argparse
import calendar
import collections
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from common import ROOT, read_json, write_json

BASE = "https://explorer.near-intents.org/api/v0/transactions"
LOCAL = ROOT / "data" / "local"


def token() -> str | None:
    if os.environ.get("INTENTS_JWT"):
        return os.environ["INTENTS_JWT"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("INTENTS_JWT="):
                return line.split("=", 1)[1].strip()
    return None


def page(jwt: str, query: dict) -> list[dict]:
    url = f"{BASE}?{urllib.parse.urlencode(query)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {jwt}", "User-Agent": "dark-matter-research/1.0"})
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code != 429 and exc.code < 500:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            print("  retrying after", type(exc).__name__, flush=True)
        time.sleep(6 + 6 * attempt)
    raise SystemExit("the Explorer API kept failing; run again with --resume")


def route(tx: dict) -> str:
    kinds = {tx.get("depositType"), tx.get("recipientType"), tx.get("refundType")}
    return "confidential" if "CONFIDENTIAL_INTENTS" in kinds else "public"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--since", help="start date, in place of --days")
    ap.add_argument("--min-usd", type=float, help="skip smaller swaps, which is far fewer pages for most of the dollars")
    ap.add_argument("--resume", action="store_true", help="carry on from a run that stopped part way")
    args = ap.parse_args()
    jwt = token()
    if not jwt:
        print("No INTENTS_JWT set, so nothing to do. Everything else in this repository works without it.")
        return 0
    start = int((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)).timestamp())
    if args.since:
        start = calendar.timegm(time.strptime(args.since, "%Y-%m-%d"))
    query = {"numberOfTransactions": 1000, "startTimestampUnix": start, "statuses": "SUCCESS"}
    if args.min_usd:
        query["minUsdPrice"] = args.min_usd
    out = LOCAL / ("explorer_history.json" if args.min_usd else "explorer_daily.json")
    totals: dict = collections.defaultdict(lambda: collections.Counter())
    oldest = None
    if args.resume and out.exists():
        saved = read_json(out)
        oldest = saved.pop("_oldest", None)  # only a run that stopped part way leaves this
        for day, counts in saved.items():
            totals[day].update(counts)
        if oldest:
            query["endTimestampUnix"] = oldest
            print("resuming before", time.strftime("%Y-%m-%d %H:%M", time.gmtime(oldest)), flush=True)

    def save(marker):
        data = {d: dict(c) for d, c in sorted(totals.items())}
        if marker:
            data["_oldest"] = marker
        write_json(out, data)

    pages = 0
    while True:
        rows = page(jwt, query)
        if not rows:
            break
        for tx in rows:
            stamp = int(tx.get("createdAtTimestamp") or 0)
            day = time.strftime("%Y-%m-%d", time.gmtime(stamp))
            kind = route(tx)
            totals[day][f"{kind}_usd"] += float(tx.get("amountInUsd") or 0)
            totals[day][f"{kind}_swaps"] += 1
            oldest = stamp if oldest is None else min(oldest, stamp)
        last = rows[-1]
        query["lastDepositAddress"] = last.get("depositAddress")
        query.pop("lastDepositMemo", None)
        if last.get("depositMemo"):
            query["lastDepositMemo"] = last["depositMemo"]
        query["direction"] = "next"  # next means older
        pages += 1
        print(len(rows), "rows, back to", time.strftime("%Y-%m-%d", time.gmtime(oldest)), flush=True)
        if pages % 10 == 0:
            save(oldest)
        time.sleep(5.5)
    save(None)
    for day, counter in sorted(totals.items()):
        print(day, dict(counter))
    return 0


if __name__ == "__main__":
    sys.exit(main())
