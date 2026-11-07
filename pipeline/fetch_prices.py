"""Daily USD prices for every token the treasury has held, from DefiLlama's free coins API.

data/static/assets.csv is the token registry: asset id, symbol, decimals, CoinGecko id. These are
static facts about each token, taken once from the public 1Click token list. We keep no quote or
price from 1Click. A token with no CoinGecko id or no DefiLlama price stays unpriced and is counted
as unpriced, never guessed.

    python pipeline/fetch_prices.py registry   # refresh data/static/assets.csv
    python pipeline/fetch_prices.py prices     # refresh data/raw/prices_daily.json
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import sys
import time

from common import RAW, STATIC, HttpFailed, get_json, write_json

REGISTRY = STATIC / "assets.csv"
HISTORY = RAW / "treasury_daily.jsonl"
PRICES = RAW / "prices_daily.json"
START = dt.datetime(2026, 2, 19, tzinfo=dt.timezone.utc)


def registry() -> None:
    tokens = get_json("https://1click.chaindefuser.com/v0/tokens")
    rows = sorted(
        (t["assetId"], t["symbol"], t["decimals"], t.get("blockchain") or "", t.get("coingeckoId") or "")
        for t in tokens
    )
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY, "w", newline="", encoding="utf-8") as fh:
        out = csv.writer(fh, lineterminator="\n")
        out.writerow(("asset_id", "symbol", "decimals", "chain", "coingecko_id"))
        out.writerows(rows)
    print("assets", len(rows))


def load_registry() -> dict[str, dict]:
    with open(REGISTRY, newline="", encoding="utf-8") as fh:
        return {r["asset_id"]: r for r in csv.DictReader(fh)}


def held_tokens() -> list[str]:
    """Every token that appears in any day's treasury balances."""
    seen: set[str] = set()
    with open(HISTORY, encoding="utf-8") as fh:
        for line in fh:
            seen.update(json.loads(line)["balances"])
    return sorted(seen)


def held_ids() -> list[str]:
    """CoinGecko ids of the tokens the treasury has held."""
    assets = load_registry()
    return sorted({assets[t]["coingecko_id"] for t in held_tokens() if t in assets and assets[t]["coingecko_id"]})


def prices() -> None:
    # "custom:..." ids are private labels in the 1Click list, with no public price history.
    ids = [c for c in held_ids() if ":" not in c]
    print("coingecko ids", len(ids))
    span = (dt.datetime.now(dt.timezone.utc) - START).days + 2
    out: dict[str, dict[str, float]] = {}

    def fetch(names: list[str]) -> None:
        chunk = ",".join(f"coingecko:{c}" for c in names)
        url = f"https://coins.llama.fi/chart/{chunk}?start={int(START.timestamp())}&span={span}&period=1d"
        try:
            res = get_json(url, tries=3).get("coins", {})
        except HttpFailed:
            if len(names) > 1:  # one bad id fails the whole request, so split and try again
                mid = len(names) // 2
                fetch(names[:mid])
                fetch(names[mid:])
            return
        for key, value in res.items():
            series = out.setdefault(key.split(":", 1)[1], {})
            for point in value.get("prices", []):
                # Points land within a minute of midnight on either side: round to the nearest.
                midnight = round(point["timestamp"] / 86400) * 86400
                series[dt.datetime.fromtimestamp(midnight, dt.timezone.utc).strftime("%Y-%m-%d")] = point["price"]
        time.sleep(0.3)

    for i in range(0, len(ids), 20):
        fetch(ids[i:i + 20])

    # Tokens with no CoinGecko id may still have a price by contract address.
    assets = load_registry()
    chains = {"eth": "ethereum", "base": "base", "arb": "arbitrum", "gnosis": "xdai", "bera": "berachain"}
    for token in held_tokens():
        info = assets.get(token)
        if info and info["coingecko_id"] in out:
            continue
        key = None
        name = token.removeprefix("nep141:")
        if "-0x" in name:
            prefix, rest = name.split("-", 1)
            if prefix in chains:
                key = f"{chains[prefix]}:{rest.split('.')[0]}"
        elif name.endswith(".near") and ":" not in name and "omft" not in name:
            key = f"near:{name}"
        if not key:
            continue
        url = f"https://coins.llama.fi/chart/{key}?start={int(START.timestamp())}&span={span}&period=1d"
        try:
            coins = get_json(url, tries=2).get("coins", {})
        except HttpFailed:
            continue
        for value in coins.values():
            series = out.setdefault(f"asset:{token}", {})
            for point in value.get("prices", []):
                midnight = round(point["timestamp"] / 86400) * 86400
                series[dt.datetime.fromtimestamp(midnight, dt.timezone.utc).strftime("%Y-%m-%d")] = point["price"]
        time.sleep(0.2)
    write_json(PRICES, out)
    print("priced", len(out), "; by address:", sum(k.startswith("asset:") for k in out))


if __name__ == "__main__":
    {"registry": registry, "prices": prices}[sys.argv[1]]()
