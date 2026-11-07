"""Optional: swap volume by route from the NEAR Intents Explorer API.

This is the only source that labels a swap as confidential, so it is the direct check on what we
infer at the boundary. It needs a JWT from https://partners.near-intents.org. Put it in .env:

    INTENTS_JWT=...

The 1Click terms do not allow keeping API data for more than 24 hours. So this writes daily totals to
data/local/, which git ignores, and nothing in the repository or on the site depends on it. Run it to
compare with data/raw/flows_in, then delete the output if you keep it longer than a day.

    python pipeline/fetch_explorer.py --days 14
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from common import ROOT, write_json

BASE = "https://explorer.near-intents.org/api/v0/transactions"
OUT = ROOT / "data" / "local" / "explorer_daily.json"


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
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code != 429:
                raise
            time.sleep(6 + 4 * attempt)
    raise SystemExit("rate limited")


def route(tx: dict) -> str:
    kinds = {tx.get("depositType"), tx.get("recipientType")}
    return "confidential" if "CONFIDENTIAL_INTENTS" in kinds else "public"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=14)
    args = ap.parse_args()
    jwt = token()
    if not jwt:
        print("No INTENTS_JWT set, so nothing to do. Everything else in this repository works without it.")
        return 0
    start = int((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)).timestamp())
    query = {"numberOfTransactions": 1000, "startTimestamp": start}
    totals: dict = collections.defaultdict(lambda: collections.Counter())
    while True:
        rows = page(jwt, query)
        rows = rows if isinstance(rows, list) else rows.get("data", [])
        if not rows:
            break
        for tx in rows:
            if tx.get("status") != "SUCCESS":
                continue
            day = time.strftime("%Y-%m-%d", time.gmtime(int(tx.get("createdAtTimestamp") or 0)))
            kind = route(tx)
            totals[day][f"{kind}_usd"] += float(tx.get("amountInUsd") or 0)
            totals[day][f"{kind}_swaps"] += 1
        last = rows[-1]
        query["lastDepositAddress"] = last.get("depositAddress")
        query["lastDepositMemo"] = last.get("depositMemo") or ""
        query["direction"] = "next"
        print(len(rows), "rows", flush=True)
        time.sleep(5.5)
    write_json(OUT, {d: dict(c) for d, c in sorted(totals.items())})
    for day, counter in sorted(totals.items()):
        print(day, dict(counter))
    return 0


if __name__ == "__main__":
    sys.exit(main())
