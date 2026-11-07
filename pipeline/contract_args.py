"""Write the arguments for the contract's `new` call: the treasury's largest tokens by value.

    python pipeline/contract_args.py <owner.near>
"""
from __future__ import annotations

import json
import sys

import metrics as M
from common import RAW, ROOT, TREASURY, VERIFIER, read_json
from analyze import load_assets, load_treasury

TOKENS = 32
DAY_MS = 86_400_000


def main() -> None:
    owner = sys.argv[1] if len(sys.argv) > 1 else "OWNER.near"
    assets = load_assets()
    prices = read_json(RAW / "prices_daily.json")
    days = load_treasury()
    latest = max(days)
    ranked = []
    for token, raw in days[latest]["balances"].items():
        value = M.value_treasury({token: raw}, assets, prices, latest)
        ranked.append((value["usd"], token))
    ranked.sort(reverse=True)
    args = {
        "owner": owner,
        "verifier": VERIFIER,
        "treasury": TREASURY,
        "tokens": [t for _, t in ranked[:TOKENS]],
        "min_interval_ms": DAY_MS,
        "alert_bps": 2000,
    }
    path = ROOT / "contract" / "init_args.json"
    path.write_text(json.dumps(args, indent=1) + "\n", encoding="utf-8", newline="\n")
    covered = sum(v for v, _ in ranked[:TOKENS]) / sum(v for v, _ in ranked)
    print(f"{path.name}: {len(args['tokens'])} tokens, {covered:.1%} of priced value")


if __name__ == "__main__":
    main()
