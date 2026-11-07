"""Pure calculations. No network and no files, so every formula can be tested on hand-made inputs."""
from __future__ import annotations

import bisect
import collections
import math
import re
from statistics import median

SOLVER_NAME = re.compile(r"solver", re.I)
IMPLICIT = re.compile(r"[0-9a-f]{64}")
EVM = re.compile(r"0x[0-9a-f]{40}")
STABLES = {"USDC", "USDT", "USDT0", "DAI", "USDe", "USD1", "PYUSD", "FDUSD", "USDD", "TUSD", "USDS", "USDf"}
MAJORS = {"BTC", "ETH", "SOL", "wNEAR", "NEAR", "XRP", "BNB", "cbBTC", "wBTC", "WBTC", "nBTC", "XBTC", "TRX", "DOGE", "AVAX", "ADA", "LTC", "BCH", "SUI", "POL", "ARB", "OP", "WETH"}
PRIVACY = {"ZEC", "XMR", "DASH", "ALEO", "QTC"}


def account_class(account: str) -> str:
    """Rough type of a counterparty, from its name alone."""
    if SOLVER_NAME.search(account):
        return "solver"
    if IMPLICIT.fullmatch(account):
        return "implicit"
    if EVM.fullmatch(account):
        return "evm"
    return "named"


def asset_class(symbol: str) -> str:
    if symbol in STABLES:
        return "stable"
    if symbol in PRIVACY:
        return "privacy"
    if symbol in MAJORS:
        return "major"
    return "other"


def value_treasury(balances: dict[str, str], assets: dict[str, dict], prices: dict[str, dict[str, float]], day: str) -> dict:
    """USD value of one day's balances. Unpriced tokens are counted, never guessed."""
    total, by_symbol, unpriced = 0.0, collections.Counter(), 0
    for token, raw in balances.items():
        info = assets.get(token)
        if not info:
            unpriced += 1
            continue
        price = prices.get(info.get("coingecko_id") or "", {}).get(day)
        if price is None:
            price = prices.get(f"asset:{token}", {}).get(day)
        if price is None:
            unpriced += 1
            continue
        value = int(raw) / 10 ** int(info["decimals"]) * price
        total += value
        by_symbol[info["symbol"]] += value
    return {"usd": total, "by_symbol": dict(by_symbol), "unpriced_tokens": unpriced, "tokens": len(balances)}


def tracking_error(pairs: list[tuple[float, float]]) -> dict:
    """How far our figure is from a reported one, as absolute percentages."""
    errors = sorted(abs(a - b) / b for a, b in pairs if b > 0)
    if not errors:
        return {"days": 0}
    return {
        "days": len(errors),
        "median_abs_pct": median(errors) * 100,
        "p90_abs_pct": errors[int(len(errors) * 0.9)] * 100,
        "max_abs_pct": errors[-1] * 100,
    }


def correlation(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / math.sqrt(sxx * syy)


def match_payments(payments: list[dict], outflows: list[dict], window_ms: int = 6 * 3_600_000) -> list[dict]:
    """Mark each revenue payment that left the treasury first.

    A payment counts as private when a transfer of exactly the same number of yoctoNEAR left the
    treasury in the hours before it. Amounts have up to 28 significant digits, so an exact match by
    chance is not a realistic worry. Each outflow can explain one payment only. A sweep that merges
    two outflows will not match, so this is a lower bound on the private share."""
    by_amount: dict[str, list[list]] = collections.defaultdict(list)
    for row in outflows:
        by_amount[row["amount"].lstrip("-")].append([int(row["ts_ms"]), row["other"], False])
    for rows in by_amount.values():
        rows.sort(key=lambda r: r[0])
    out = []
    for pay in sorted(payments, key=lambda p: p["ts_ms"]):
        hit = None
        for candidate in by_amount.get(pay["yocto"], ()):
            age = pay["ts_ms"] - candidate[0]
            if not candidate[2] and 0 <= age <= window_ms:
                candidate[2] = True
                hit = candidate
                break
        out.append({**pay, "private": hit is not None, "via": hit[1] if hit else None})
    return out


def pair_accounts(rows: list[dict], assets_by_short: dict[str, str], gap_ms: int = 3_600_000) -> list[dict]:
    """Find private swaps at the boundary: an account that sends one token in and later gets a
    different token back, or the same token back, within `gap_ms`.

    Solvers are skipped: they move inventory and do not swap. Only accounts with exactly one
    transfer each way are used, so nothing has to be guessed about which leg belongs to which."""
    by_account: dict[str, list[dict]] = collections.defaultdict(list)
    for row in rows:
        if account_class(row["other"]) != "solver":
            by_account[row["other"]].append(row)
    pairs = []
    for account, legs in by_account.items():
        incoming = [r for r in legs if float(r["usd"]) > 0]
        outgoing = [r for r in legs if float(r["usd"]) < 0]
        if len(incoming) != 1 or len(outgoing) != 1:
            continue
        leg_in, leg_out = incoming[0], outgoing[0]
        if not 0 <= int(leg_out["ts_ms"]) - int(leg_in["ts_ms"]) <= gap_ms:
            continue
        usd_in, usd_out = float(leg_in["usd"]), -float(leg_out["usd"])
        if usd_in <= 0:
            continue
        pairs.append({
            "account": account,
            "usd_in": usd_in,
            "usd_out": usd_out,
            "bps": (usd_in - usd_out) / usd_in * 1e4,
            "from": assets_by_short.get(leg_in["asset"], "?"),
            "to": assets_by_short.get(leg_out["asset"], "?"),
            "seconds": (int(leg_out["ts_ms"]) - int(leg_in["ts_ms"])) / 1000,
        })
    return pairs


def weighted_median(values: list[float], weights: list[float]) -> float:
    order = sorted(range(len(values)), key=lambda i: values[i])
    half = sum(weights) / 2
    seen = 0.0
    for i in order:
        seen += weights[i]
        if seen >= half:
            return values[i]
    return float("nan")


def percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return float("nan")
    return sorted_values[min(len(sorted_values) - 1, int(q * len(sorted_values)))]


def summarize_costs(pairs: list[dict]) -> dict:
    if not pairs:
        return {"n": 0}
    bps = sorted(p["bps"] for p in pairs)
    usd = sum(p["usd_in"] for p in pairs)
    return {
        "n": len(pairs),
        "usd": usd,
        "median_bps": median(bps),
        "weighted_bps": sum(p["bps"] * p["usd_in"] for p in pairs) / usd,
        "weighted_median_bps": weighted_median([p["bps"] for p in pairs], [p["usd_in"] for p in pairs]),
        "p10_bps": percentile(bps, 0.1),
        "p90_bps": percentile(bps, 0.9),
    }


def rolling_share(items: list[tuple[str, float, float]], window: int) -> list[dict]:
    """Trailing share of `part` in `whole` over `window` rows of (date, part, whole)."""
    out = []
    for i in range(len(items)):
        chunk = items[max(0, i - window + 1):i + 1]
        whole = sum(c[2] for c in chunk)
        out.append({"date": items[i][0], "share": sum(c[1] for c in chunk) / whole if whole else None})
    return out


def ols(xs: list[list[float]], ys: list[float]) -> list[float]:
    """Ordinary least squares with no intercept, solved by Gaussian elimination."""
    k = len(xs[0])
    a = [[sum(x[i] * x[j] for x in xs) for j in range(k)] for i in range(k)]
    b = [sum(x[i] * y for x, y in zip(xs, ys)) for i in range(k)]
    for i in range(k):
        pivot = max(range(i, k), key=lambda r: abs(a[r][i]))
        a[i], a[pivot] = a[pivot], a[i]
        b[i], b[pivot] = b[pivot], b[i]
        for r in range(k):
            if r != i:
                f = a[r][i] / a[i][i]
                a[r] = [v - f * w for v, w in zip(a[r], a[i])]
                b[r] -= f * b[i]
    return [b[i] / a[i][i] for i in range(k)]


def block_bootstrap_ols(xs: list[list[float]], ys: list[float], block: int = 7, reps: int = 2000, seed: int = 20261107) -> dict:
    """OLS with a moving-block bootstrap, because daily revenue is not independent day to day."""
    import random

    rng = random.Random(seed)
    n = len(xs)
    point = ols(xs, ys)
    draws: list[list[float]] = [[] for _ in point]
    starts = max(1, n - block + 1)
    for _ in range(reps):
        idx: list[int] = []
        while len(idx) < n:
            s = rng.randrange(starts)
            idx.extend(range(s, min(s + block, n)))
        idx = idx[:n]
        try:
            fit = ols([xs[i] for i in idx], [ys[i] for i in idx])
        except ZeroDivisionError:
            continue
        for slot, value in zip(draws, fit):
            slot.append(value)
    out = []
    for value, slot in zip(point, draws):
        slot.sort()
        out.append({"estimate": value, "low": percentile(slot, 0.05), "high": percentile(slot, 0.95)})
    return {"terms": out, "n": n, "block": block}


def break_even(issued_near_per_day: float, price: float, public_bps: float, private_bps: float, kept: float = 1.0) -> dict:
    """Daily volume at which revenue would pay for each day's new NEAR.

    public_bps and private_bps are what NEAR keeps per dollar of total volume by each route. `kept`
    scales the private part, which is set off-chain: 1.0 is today, 0.5 is half of today."""
    blended = public_bps + private_bps * kept
    usd_needed = issued_near_per_day * price
    volume = usd_needed / (blended / 1e4) if blended > 0 else float("inf")
    return {"blended_bps": blended, "usd_per_day_needed": usd_needed, "volume_per_day": volume}

def change_point(values: list[float], min_side: int = 4) -> int | None:
    """Index where a series best splits into two flat levels: the split that leaves the smallest
    sum of squared errors. Returns the first index of the second level."""
    best, best_cost = None, float("inf")
    for i in range(min_side, len(values) - min_side + 1):
        left, right = values[:i], values[i:]
        mean_l, mean_r = sum(left) / len(left), sum(right) / len(right)
        cost = sum((v - mean_l) ** 2 for v in left) + sum((v - mean_r) ** 2 for v in right)
        if cost < best_cost:
            best, best_cost = i, cost
    return best


def nearest_index(sorted_days: list[str], day: str) -> int:
    return min(bisect.bisect_left(sorted_days, day), len(sorted_days) - 1)
