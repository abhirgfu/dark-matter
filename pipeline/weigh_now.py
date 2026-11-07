"""Weigh the treasury once at the latest final block, with live prices, and keep only the total.

This is the same calculation the "Weigh it yourself" button runs in a browser. Prices come from the
public 1Click token list, which covers more of the treasury than any free price history. The API
terms limit how long API data may be kept, so we keep one derived total per run and no prices.
"""
from __future__ import annotations

from common import RAW, TREASURY, VERIFIER, block_header, get_json, view, write_json


def main() -> None:
    height = block_header()["height"]
    tokens, start = [], 0
    while True:
        page = view(VERIFIER, "mt_tokens_for_owner", {"account_id": TREASURY, "from_index": str(start), "limit": 200}, height)
        tokens += [t["token_id"] for t in page]
        if len(page) < 200:
            break
        start += len(page)
    amounts = view(VERIFIER, "mt_batch_balance_of", {"account_id": TREASURY, "token_ids": tokens}, height)
    info = {t["assetId"]: t for t in get_json("https://1click.chaindefuser.com/v0/tokens")}
    usd, priced = 0.0, 0
    for token, amount in zip(tokens, amounts):
        entry = info.get(token)
        if entry and entry.get("price") is not None:
            usd += int(amount) / 10 ** entry["decimals"] * entry["price"]
            priced += 1
    header = block_header(height)
    out = {"block": height, "timestamp_ns": str(header["timestamp"]), "usd": round(usd, 2), "tokens": len(tokens), "priced_tokens": priced}
    write_json(RAW / "weigh_snapshot.json", out)
    print(out)


if __name__ == "__main__":
    main()
