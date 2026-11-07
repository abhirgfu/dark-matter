"""Shared constants and small HTTP helpers. Standard library only, so that anyone with
Python 3.10+ can rebuild every number without installing anything."""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import pathlib
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"
STATIC = ROOT / "data" / "static"
SITE = ROOT / "site"

# The account on intents.near that backs every shielded balance. Named as
# PRIVATE_TREASURY_ACCOUNT_ID in the Confidential Intents market-maker docs.
TREASURY = "51e8f94d77b5e90dc9852ca6113771e11e8382ce69473a75e313e41665de7cbe"
VERIFIER = "intents.near"
REVENUE_WALLETS = (
    "buybacks.multisignature.near",
    "fefundsadmin.sputnik-dao.near",
    "1csfundsadmin.sputnik-dao.near",
)
LAUNCH = dt.date(2026, 2, 20)  # first week with any shielded balance is 22 Feb 2026
PRIVATE_SWAPS_START = dt.date(2026, 10, 27)  # swaps settle on intents.far from this date

ARCHIVES = (
    "https://archival-rpc.mainnet.fastnear.com",
    "https://near-mainnet.gateway.tatum.io",
    "https://archival-rpc.mainnet.near.org",
)
_archive_at = 0
TRANSFERS_API = "https://transfers.main.fastnear.com/v0/transfers"
UA = {"User-Agent": "dark-matter-research/1.0", "Content-Type": "application/json"}


class HttpFailed(RuntimeError):
    pass


# Seconds between calls to one host. These are free public services, so we stay well under their
# limits. The transfers API allows roughly ten calls a minute from one address.
PACE = {
    "transfers.main.fastnear.com": 6.5,
    "archival-rpc.mainnet.fastnear.com": 0.4,
    "archival-rpc.mainnet.near.org": 1.0,
    "near-mainnet.gateway.tatum.io": 1.2,
}
_last_call: dict[str, float] = {}


def _pace(url: str) -> None:
    host = url.split("/")[2]
    gap = PACE.get(host, 0.0)
    wait = _last_call.get(host, 0.0) + gap - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_call[host] = time.monotonic()


def http(url: str, body: dict | None = None, tries: int = 7, timeout: int = 45) -> bytes:
    """GET or POST with patient backoff. Public endpoints rate-limit, so we wait, not hammer."""
    data = None if body is None else json.dumps(body).encode()
    last = None
    for attempt in range(tries):
        _pace(url)
        try:
            req = urllib.request.Request(url, data=data, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in (408, 425, 429, 500, 502, 503, 504):
                raise HttpFailed(f"{url}: HTTP {exc.code}") from exc
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            wait = min(float(retry_after), 20.0) if retry_after and retry_after.isdigit() else min(2 + 5 * attempt, 45)
            if attempt + 1 < tries:
                time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
            time.sleep(3 + 4 * attempt)
    raise HttpFailed(f"{url}: gave up after {tries} tries: {last!r}")


def get_json(url: str, **kw):
    return json.loads(http(url, **kw))


def post_json(url: str, body: dict, **kw):
    return json.loads(http(url, body, **kw))


def rpc(method: str, params, url: str | None = None):
    """One RPC call. Without a `url` it spreads over the free archival nodes and moves to the next
    when one is busy, so a shared IP address does not stop a long fetch."""
    global _archive_at
    payload = {"jsonrpc": "2.0", "id": "dm", "method": method, "params": params}
    if url:
        res = post_json(url, payload)
        if "result" not in res:
            raise HttpFailed(f"rpc {method}: {str(res)[:240]}")
        return res["result"]
    last = None
    for attempt in range(len(ARCHIVES) * 4):
        node = ARCHIVES[_archive_at % len(ARCHIVES)]
        _archive_at += 1
        try:
            res = post_json(node, payload, tries=1)
        except HttpFailed as exc:
            last = exc
            time.sleep(1 + attempt)
            continue
        if "result" in res:
            return res["result"]
        # A real answer that says "no such block" is final: other nodes would say the same.
        text = str(res)
        if "UNKNOWN_BLOCK" in text or "UnknownBlock" in text or "does not exist" in text:
            raise HttpFailed(f"rpc {method}: {text[:240]}")
        last = HttpFailed(f"rpc {method}: {text[:240]}")
    raise HttpFailed(f"rpc {method}: all nodes failed: {last!r}")


def view(account: str, method: str, args: dict, block: int | None = None, url: str | None = None):
    """Call a contract view method, at a given block or at the latest final block."""
    params = {
        "request_type": "call_function",
        "account_id": account,
        "method_name": method,
        "args_base64": base64.b64encode(json.dumps(args).encode()).decode(),
    }
    if block is None:
        params["finality"] = "final"
    else:
        params["block_id"] = block
    res = rpc("query", params, url=url)
    return json.loads(bytes(res["result"]))


def block_header(block: int | None = None) -> dict:
    params = {"finality": "final"} if block is None else {"block_id": block}
    return rpc("block", params)["header"]


def first_block_of_day(day: dt.date, hint: int | None = None, slack_s: int = 240) -> int:
    """Height of a block in the first `slack_s` seconds of UTC day `day`.

    Blocks come about every 0.6 s, so a straight-line guess lands close and one or two corrections
    finish the job. Four minutes either way does not matter for a daily balance, and it saves the
    many calls an exact search would make. Each day's stored timestamp is the exact one."""
    target = dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc).timestamp()
    rate = 0.6
    if hint is None:
        head = block_header()
        if target > head["timestamp"] / 1e9:
            raise ValueError(f"{day} is in the future")
        hint = int(head["height"] - (head["timestamp"] / 1e9 - target - slack_s / 2) / rate)
    height = hint
    for _ in range(10):
        try:
            hdr = block_header(height)
        except HttpFailed as exc:  # NEAR skips some heights
            if "UNKNOWN_BLOCK" not in str(exc) and "does not exist" not in str(exc):
                raise
            height -= 1
            continue
        late = hdr["timestamp"] / 1e9 - target
        if 0 <= late <= slack_s:
            return hdr["height"]
        height = hdr["height"] + int((slack_s / 2 - late) / rate)
    raise HttpFailed(f"could not place a block on {day}")


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: pathlib.Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: pathlib.Path, obj, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":") if compact else None, indent=None if compact else 1)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text + "\n")


def day_of_ns(ns: int | str) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(int(ns) / 1e9))


def day_ms(day: dt.date) -> int:
    return int(dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc).timestamp() * 1000)
