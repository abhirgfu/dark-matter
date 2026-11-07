"""Who can move the money. Reads the public chain only, with no key.

 - the keys registered for the treasury on intents.near, and on the treasury's own NEAR account
 - whether that key was the same at earlier dates
 - which key actually signed a sample of recent transfers out of the treasury
 - the protocol fee and fee collector on intents.near
 - the confirmations the buybacks multisig needs
"""
from __future__ import annotations

import base64
import csv
import gzip
import json

from common import RAW, TREASURY, VERIFIER, read_json, rpc, view, write_json

BUYBACKS = "buybacks.multisignature.near"
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58_to_hex(text: str) -> str:
    number = 0
    for ch in text:
        number = number * 58 + ALPHABET.index(ch)
    return number.to_bytes(32, "big").hex()


def signers_of(tx_hash: str) -> list[str]:
    """Public keys that signed intents for the treasury in one transaction."""
    res = rpc("EXPERIMENTAL_tx_status", {"tx_hash": tx_hash, "sender_account_id": VERIFIER, "wait_until": "NONE"})
    keys = []
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
            if message.get("signer_id") == TREASURY:
                keys.append(signed.get("public_key"))
    return keys


def main() -> None:
    days = {}
    with open(RAW / "treasury_daily.jsonl", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            days[row["date"]] = row["block"]
    dates = sorted(days)
    sample_days = dates[:: max(1, len(dates) // 8)] + dates[-1:]

    out = {
        "treasury": TREASURY,
        "verifier_keys_now": view(VERIFIER, "public_keys_of", {"account_id": TREASURY}),
        "account_keys_now": [
            {"public_key": k["public_key"], "permission": k["access_key"]["permission"]}
            for k in rpc("query", {"request_type": "view_access_key_list", "finality": "final", "account_id": TREASURY})["keys"]
        ],
        "protocol_fee_pips": view(VERIFIER, "fee", {}),
        "fee_collector": view(VERIFIER, "fee_collector", {}),
        "keys_through_time": {},
    }
    for day in sample_days:
        out["keys_through_time"][day] = view(VERIFIER, "public_keys_of", {"account_id": TREASURY}, days[day])
        print("keys at", day, out["keys_through_time"][day], flush=True)
    key = out["verifier_keys_now"][0].split(":", 1)[1]
    out["key_is_the_implicit_account_key"] = base58_to_hex(key) == TREASURY

    try:
        out["buybacks_confirmations"] = view(BUYBACKS, "get_num_confirmations", {})
        out["buybacks_members"] = len(view(BUYBACKS, "get_members", {}))
    except Exception as exc:  # the multisig's interface is not ours to rely on
        out["buybacks_note"] = repr(exc)[:160]

    # Which key signed recent transfers out?
    sample = []
    folder = RAW / "wnear_out"
    for path in sorted(folder.glob("*.csv.gz"))[-3:]:
        with gzip.open(path, "rt", newline="") as fh:
            rows = list(csv.DictReader(fh))
        sample += [r["tx"] for r in rows[:: max(1, len(rows) // 7)] if r["tx"]][:8]
    signed: dict[str, int] = {}
    for tx in sample:
        try:
            for k in signers_of(tx):
                signed[k] = signed.get(k, 0) + 1
        except Exception as exc:
            print("skip", tx, repr(exc)[:100], flush=True)
    out["outflow_signers_sample"] = {"transactions": len(sample), "keys": signed}
    write_json(RAW / "control.json", out)
    print(json.dumps(out, indent=1)[:1500])


if __name__ == "__main__":
    main()
