#!/usr/bin/env python3
"""Dark Matter for AI agents: a Model Context Protocol server over stdio.

Standard library only, no key. Point any MCP client at it:

    {"mcpServers": {"dark-matter": {"command": "python", "args": ["mcp/server.py"]}}}

Tools:
    weigh_treasury       read the private treasury from NEAR now, with live prices
    treasury_keys        the keys registered for the treasury on intents.near now
    revenue_source       how much of NEAR's revenue left the treasury first, by month
    daily_series         a daily series: weight, flows or activity
    thesis_tests         each test of the thesis, with its current value and state
"""
from __future__ import annotations

import base64
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "derived" / "results.json"
TESTS = ROOT / "data" / "derived" / "tests.json"
TREASURY = "51e8f94d77b5e90dc9852ca6113771e11e8382ce69473a75e313e41665de7cbe"
VERSION = "2025-06-18"
UA = {"Content-Type": "application/json", "User-Agent": "dark-matter-mcp/1.0"}


def call(url: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=30) as resp:
        return json.loads(resp.read())


def view(method: str, args: dict):
    res = call("https://free.rpc.fastnear.com", {
        "jsonrpc": "2.0", "id": "dm", "method": "query",
        "params": {"request_type": "call_function", "finality": "final", "account_id": "intents.near",
                   "method_name": method, "args_base64": base64.b64encode(json.dumps(args).encode()).decode()},
    })["result"]
    return json.loads(bytes(res["result"])), res["block_height"]


def weigh_treasury(_: dict) -> dict:
    tokens, height = view("mt_tokens_for_owner", {"account_id": TREASURY, "limit": 500})
    ids = [t["token_id"] for t in tokens]
    amounts, _ = view("mt_batch_balance_of", {"account_id": TREASURY, "token_ids": ids})
    info = {t["assetId"]: t for t in call("https://1click.chaindefuser.com/v0/tokens")}
    usd, priced, top = 0.0, 0, []
    for token, amount in zip(ids, amounts):
        entry = info.get(token)
        if entry and entry.get("price") is not None:
            value = int(amount) / 10 ** entry["decimals"] * entry["price"]
            usd += value
            priced += 1
            top.append((entry["symbol"], value))
    top.sort(key=lambda kv: -kv[1])
    return {"usd": round(usd, 2), "block": height, "tokens": len(ids), "priced_tokens": priced,
            "largest": [{"symbol": s, "usd": round(v, 2)} for s, v in top[:8]]}


def treasury_keys(_: dict) -> dict:
    keys, height = view("public_keys_of", {"account_id": TREASURY})
    return {"treasury": TREASURY, "keys": keys, "block": height}


def results() -> dict:
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def revenue_source(_: dict) -> dict:
    p = results()["provenance"]
    return {k: p[k] for k in ("monthly", "since_private_swaps_share", "last_30_days_share")}


def daily_series(args: dict) -> dict:
    r = results()
    name = args.get("name", "weight")
    series = {"weight": r["weigh"]["series"], "flows": r["flows"]["daily"], "activity": r["activity"]}
    if name not in series:
        raise ValueError(f"name must be one of {sorted(series)}")
    return {"name": name, "rows": series[name][-int(args.get("days", 90)):]}


def thesis_tests(_: dict) -> list:
    return json.loads(TESTS.read_text(encoding="utf-8"))


NO_ARGS = {"type": "object", "properties": {}}
TOOLS = {
    "weigh_treasury": (weigh_treasury, "Read NEAR Confidential Intents' private treasury from intents.near now and value it with live prices.", NO_ARGS),
    "treasury_keys": (treasury_keys, "List the keys registered for the private treasury on intents.near now.", NO_ARGS),
    "revenue_source": (revenue_source, "How much of NEAR's revenue left the private treasury first, by month, from data in this repository.", NO_ARGS),
    "daily_series": (daily_series, "A daily series from this repository: weight, flows or activity.", {
        "type": "object",
        "properties": {"name": {"type": "string", "enum": ["weight", "flows", "activity"]}, "days": {"type": "integer"}},
        "required": ["name"],
    }),
    "thesis_tests": (thesis_tests, "Each test of the Dark Matter thesis, with its limit, current value and state.", NO_ARGS),
}


def handle(msg: dict) -> dict | None:
    method, msg_id = msg.get("method"), msg.get("id")
    if msg_id is None:  # a notification needs no answer
        return None
    if method == "initialize":
        result = {"protocolVersion": msg.get("params", {}).get("protocolVersion", VERSION),
                  "capabilities": {"tools": {}},
                  "serverInfo": {"name": "dark-matter", "version": "1.0.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [{"name": n, "description": d, "inputSchema": s} for n, (_, d, s) in TOOLS.items()]}
    elif method == "tools/call":
        params = msg.get("params", {})
        name = params.get("name")
        if name not in TOOLS:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": f"unknown tool {name}"}}
        try:
            text = json.dumps(TOOLS[name][0](params.get("arguments") or {}))
            result = {"content": [{"type": "text", "text": text}]}
        except Exception as exc:  # tool errors go back to the model, not the transport
            result = {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"no method {method}"}}
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            reply = handle(json.loads(line))
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
