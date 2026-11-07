"""Every payment into NEAR's three revenue wallets, and who paid it.

Step 1 lists each native NEAR transfer into the wallets from FastNear's Transfers API.

Step 2 reads the transaction behind a payment. Revenue reaches a wallet through a `native_withdraw`
intent, signed by an account inside intents.near. The transaction tells us that account, the
"sweeper", and the key that signed.

Step 3 asks who funded the sweeper. A treasury payment shows up as a transfer of exactly the same
number of yoctoNEAR out of the treasury just before the sweep, so this step needs no extra calls:
it is answered from the census in data/raw/flows and data/raw/treasury_wnear.csv.gz.

    python pipeline/fetch_wallets.py inflows    # list the payments
    python pipeline/fetch_wallets.py sweepers   # decode each payment's transaction
"""
from __future__ import annotations

import base64
import json
import sys

from common import RAW, REVENUE_WALLETS, TRANSFERS_API, VERIFIER, post_json, read_json, rpc, write_json

INFLOWS = RAW / "wallet_inflows.json"
SWEEPERS = RAW / "wallet_sweepers.json"
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


def decode(tx_hash: str, wallet: str) -> dict | None:
    """Find the native_withdraw intent that paid `wallet` in this transaction."""
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
                    return {"sweeper": message.get("signer_id"), "signing_key": signed.get("public_key")}
    return None


def sweepers() -> None:
    payments = read_json(INFLOWS)
    done = read_json(SWEEPERS) if SWEEPERS.exists() else {}
    todo = [p for p in payments if p["from"] == VERIFIER and p["tx"] and f"{p['tx']}|{p['wallet']}" not in done]
    print("to decode:", len(todo), flush=True)
    for i, p in enumerate(todo):
        key = f"{p['tx']}|{p['wallet']}"
        try:
            done[key] = decode(p["tx"], p["wallet"])
        except Exception as exc:  # one unreadable transaction must not stop the run
            done[key] = None
            print("skip", p["tx"], repr(exc)[:120], flush=True)
        if i % 50 == 0:
            write_json(SWEEPERS, done)
            print(i, flush=True)
    write_json(SWEEPERS, done)


if __name__ == "__main__":
    {"inflows": inflows, "sweepers": sweepers}[sys.argv[1]]()
