"""Weigh the private treasury at the first block of every UTC day since launch.

Reads `mt_tokens_for_owner` and `mt_batch_balance_of` on intents.near from a free archival RPC.
No key is needed. Writes one JSON line per day to data/raw/treasury_daily.jsonl. Finished days are
kept, so a re-run only fetches what is new.
"""
from __future__ import annotations

import datetime as dt
import json
import sys

from common import LAUNCH, RAW, TREASURY, VERIFIER, block_header, first_block_of_day, view

OUT = RAW / "treasury_daily.jsonl"
BLOCKS_PER_DAY = 143_000


def load() -> dict[str, dict]:
    if not OUT.exists():
        return {}
    with open(OUT, encoding="utf-8") as fh:
        return {r["date"]: r for r in map(json.loads, fh)}


def save(days: dict[str, dict]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        for date in sorted(days):
            fh.write(json.dumps(days[date], sort_keys=True, separators=(",", ":")) + "\n")


def read_treasury(block: int) -> dict[str, str]:
    tokens, start = [], 0
    while True:
        page = view(VERIFIER, "mt_tokens_for_owner", {"account_id": TREASURY, "from_index": str(start), "limit": 200}, block)
        tokens += [t["token_id"] for t in page]
        if len(page) < 200:
            break
        start += len(page)
    if not tokens:
        return {}
    amounts = view(VERIFIER, "mt_batch_balance_of", {"account_id": TREASURY, "token_ids": tokens}, block)
    return {t: a for t, a in zip(tokens, amounts) if a != "0"}


def main() -> None:
    days = load()
    today = dt.datetime.now(dt.timezone.utc).date()
    day = LAUNCH
    hint = None
    while day <= today:
        key = day.isoformat()
        if key in days:
            hint = days[key]["block"] + BLOCKS_PER_DAY
            day += dt.timedelta(days=1)
            continue
        block = first_block_of_day(day, hint)
        ts_ns = block_header(block)["timestamp"]
        days[key] = {"date": key, "block": block, "timestamp_ns": str(ts_ns), "balances": read_treasury(block)}
        print(key, block, len(days[key]["balances"]), flush=True)
        hint = block + BLOCKS_PER_DAY
        day += dt.timedelta(days=1)
        save(days)
    print("treasury days:", len(days), file=sys.stderr)


if __name__ == "__main__":
    main()
