"""Every payment into NEAR's three revenue wallets, and a hand trace of who paid a sample of them.

`inflows` lists each native NEAR transfer into the wallets from FastNear's Transfers API.

`trace` reads the transaction behind four payments a week: the two largest and two at random.
Revenue reaches a wallet through a `native_withdraw` intent, signed by an account inside
intents.near. The transaction names that account, the "sweeper". Then we ask who sent it wNEAR.
This is how the pattern was found. `metrics.match_payments` then checks every payment against it.

    python pipeline/fetch_wallets.py inflows
    python pipeline/fetch_wallets.py trace
"""
from __future__ import annotations

import base64
import collections
import json
import random
import sys
import time

from common import RAW, REVENUE_WALLETS, TRANSFERS_API, VERIFIER, post_json, read_json, rpc, write_json

INFLOWS = RAW / "wallet_inflows.json"
TRACE = RAW / "hand_trace.json"
SINCE_MS = 1_767_225_600_000  # 2026-01-01


def inflows() -> None:
    rows = []
    for wallet in REVENUE_WALLETS:
        token = None
        while True:
            body = {"account_id": wallet, "direction": "receiver", "limit": 100, "desc": False,
                    "from_timestamp_ms": SINCE_MS}
            if token:
                body["resume_token"] = token
            page = post_json(TRANSFERS_API, body)
            batch = page.get("transfers", [])
            for t in batch:
                if t.get("asset_id") != "native:near" or int(t["amount"]) <= 0:
                    continue
                rows.append({
                    "wallet": wallet,
                    "ts_ms": int(int(t["block_timestamp"]) / 1_000_000),
                    "tx": t.get("transaction_id") or "",
                    "from": t.get("other_account_id") or "",
                    "yocto": t["amount"],
                    "usd": round(float(t.get("usd_amount") or 0), 2),
                })
            token = page.get("resume_token")
            if not batch or not token:
                break
        print(wallet, "payments so far", len(rows), flush=True)
    rows.sort(key=lambda r: (r["ts_ms"], r["tx"], r["wallet"]))
    write_json(INFLOWS, rows)


def sweeper_of(tx_hash: str, wallet: str) -> str | None:
    """The account inside intents.near that paid `wallet` in this transaction."""
    res = rpc("EXPERIMENTAL_tx_status", {"tx_hash": tx_hash, "sender_account_id": VERIFIER, "wait_until": "NONE"})
    for action in res.get("transaction", {}).get("actions", []):
        call = action.get("FunctionCall") if isinstance(action, dict) else None
        if not call:
            continue
        try:
            args = json.loads(base64.b64decode(call["args"]))
        except (ValueError, TypeError):
            continue
        for signed in args.get("signed", []):
            try:
                message = json.loads(signed["payload"]["message"])
            except (KeyError, ValueError, TypeError):
                continue
            for intent in message.get("intents", []):
                if intent.get("intent") == "native_withdraw" and intent.get("receiver_id") == wallet:
                    return message.get("signer_id")
    return None


def trace() -> None:
    payments = [p for p in read_json(INFLOWS) if p["from"] == VERIFIER]
    weeks: dict[str, list[dict]] = collections.defaultdict(list)
    for pay in payments:
        weeks[time.strftime("%Y-%W", time.gmtime(pay["ts_ms"] / 1000))].append(pay)
    rng = random.Random(20261107)
    out = []
    for week in sorted(weeks):
        items = sorted(weeks[week], key=lambda p: -p["usd"])
        for pay in items[:2] + rng.sample(items[2:], min(2, max(0, len(items) - 2))):
            sweeper = sweeper_of(pay["tx"], pay["wallet"])
            funders = None
            if sweeper:
                page = post_json(TRANSFERS_API, {"account_id": sweeper, "limit": 100, "desc": True, "direction": "receiver"})
                totals: collections.Counter = collections.Counter()
                for row in page.get("transfers", []):
                    if "wrap.near" in (row.get("asset_id") or ""):
                        totals[row.get("other_account_id")] += abs(row.get("usd_amount") or 0)
                funders = totals.most_common(3)
            out.append({"week": week, "date": time.strftime("%Y-%m-%d", time.gmtime(pay["ts_ms"] / 1000)),
                        "wallet": pay["wallet"][:10], "usd": pay["usd"], "signer": sweeper, "src": funders})
            print(out[-1], flush=True)
    write_json(TRACE, out)


if __name__ == "__main__":
    {"inflows": inflows, "trace": trace}[sys.argv[1]]()
