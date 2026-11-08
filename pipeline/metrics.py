"""Pure calculations. No network and no files, so every formula can be tested on hand-made inputs."""
from __future__ import annotations

import bisect
import collections
import datetime as dt
import math
import random
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


def fee_fingerprint(pairs: list[dict], step: int = 10, low: int = -20, high: int = 260) -> dict:
    """Do swap costs bunch at set prices? Histogram of cost, and the middle of each bunch.

    A smooth spread would suggest market spreads. Tight bunches suggest a price list. The three
    ranges come from reading the histogram, which has clear gaps near 40 and 110 bps."""
    bins = {b: 0 for b in range(low, high + step, step)}
    for pair in pairs:
        at = int(min(max(pair["bps"], low), high) // step) * step
        bins[at] += 1
    base = sorted(p["bps"] for p in pairs if 0 <= p["bps"] < 40)
    first = sorted(p["bps"] for p in pairs if 40 <= p["bps"] < 110)
    second = sorted(p["bps"] for p in pairs if 110 <= p["bps"] < 200)
    total = len(pairs) or 1
    return {
        "bins": [{"bps": b, "n": n} for b, n in sorted(bins.items())],
        "swaps": len(pairs),
        "base_bps": median(base) if base else None,
        "base_share": len(base) / total,
        "low_bps": median(first) if first else None,
        "low_share": len(first) / total,
        "high_bps": median(second) if second else None,
        "high_share": len(second) / total,
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


def weekly(daily: dict[str, float], how: str = "mean") -> dict[str, float]:
    """Monday-start weeks. Only whole weeks count, so a part week cannot look like a fall."""
    buckets: dict[str, list[float]] = collections.defaultdict(list)
    for day, value in daily.items():
        d = dt.date.fromisoformat(day)
        buckets[(d - dt.timedelta(days=d.weekday())).isoformat()].append(value)
    return {w: (sum(v) if how == "sum" else sum(v) / len(v)) for w, v in sorted(buckets.items()) if len(v) == 7}


def ranks(values: list[float]) -> list[float]:
    """Ranks from 1, with tied values sharing their average rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(xs: list[float], ys: list[float]) -> float:
    """Rank correlation. One week of spam or a clean-up cannot dominate it, as it can a plain one."""
    return correlation(ranks(xs), ranks(ys))


def lag_profile(leader: list[float], follower: list[float], max_lag: int = 8) -> list[dict]:
    """Rank correlation of this week's change in `leader` with the change in `follower` L weeks later."""
    a = [math.log(b / c) for c, b in zip(leader, leader[1:])]
    f = [math.log(b / c) for c, b in zip(follower, follower[1:])]
    return [{"lag": lag, "r": spearman(a[:len(a) - lag], f[lag:])} for lag in range(1, max_lag + 1)]


def leading_test(volume: list[float], price: list[float], usage: list[float], horizon: int = 4,
                 block: int = 8, reps: int = 2000, seed: int = 20261107) -> dict:
    """Which predicts the next `horizon` weeks of usage better: the last `horizon` weeks of volume, or of price?

    All three lists are weekly levels on the same dates. The interval on the difference comes from a
    moving-block bootstrap, because overlapping changes are not independent."""
    lv, lp, lu = [[math.log(x) for x in s] for s in (volume, price, usage)]
    index = range(horizon, len(lu) - horizon)
    past_v = [lv[t] - lv[t - horizon] for t in index]
    past_p = [lp[t] - lp[t - horizon] for t in index]
    past_u = [lu[t] - lu[t - horizon] for t in index]
    next_u = [lu[t + horizon] - lu[t] for t in index]
    next_v = [lv[t + horizon] - lv[t] for t in index]
    n = len(next_u)
    rng = random.Random(seed)
    diffs = []
    starts = max(1, n - block + 1)
    for _ in range(reps):
        pick: list[int] = []
        while len(pick) < n:
            s = rng.randrange(starts)
            pick.extend(range(s, min(s + block, n)))
        pick = pick[:n]
        u = [next_u[i] for i in pick]
        v = [past_v[i] for i in pick]
        p = [past_p[i] for i in pick]
        if len(set(u)) > 1 and len(set(v)) > 1 and len(set(p)) > 1:
            diffs.append(spearman(v, u) - spearman(p, u))
    diffs.sort()
    r_v, r_p = spearman(past_v, next_u), spearman(past_p, next_u)
    return {
        "weeks": n,
        "volume_r": r_v,
        "price_r": r_p,
        "difference": r_v - r_p,
        "difference_low": percentile(diffs, 0.05),
        "difference_high": percentile(diffs, 0.95),
        "usage_leads_volume_r": spearman(past_u, next_v),
    }


def log_trend(values: list[float]) -> float:
    """Growth per step from a straight line through the logs of a series."""
    ys = [math.log(v) for v in values]
    n = len(ys)
    mean_x, mean_y = (n - 1) / 2, sum(ys) / n
    slope = sum((i - mean_x) * (y - mean_y) for i, y in enumerate(ys)) / sum((i - mean_x) ** 2 for i in range(n))
    return math.exp(slope) - 1


def project(volume_per_day: float, growth: float, take_bps: float, supply: float, price: float,
            rate_now: float, rate_end: float, ramp_years: int = 2, years: int = 5) -> list[dict]:
    """Year-by-year arithmetic at a constant NEAR price. Assumptions in, consequences out: not a forecast."""
    rows = []
    for year in range(years + 1):
        volume = volume_per_day * (1 + growth) ** year
        rate = rate_end if year >= ramp_years else rate_now + (rate_end - rate_now) * year / ramp_years
        revenue = volume * take_bps / 1e4
        new_usd = supply * rate / 365 * price
        rows.append({"year": year, "volume_per_day": volume, "revenue_per_year": revenue * 365,
                     "issuance_rate": rate, "new_near_usd_per_day": new_usd, "coverage": revenue / new_usd})
        supply *= 1 + rate
    return rows


def required_growth(volume_per_day: float, take_bps: float, supply: float, price: float, rate: float, years: int = 5) -> float:
    """Yearly volume growth needed for revenue to pay for new NEAR in `years`, at a constant price."""
    later_supply = supply * (1 + rate) ** years
    needed = later_supply * rate / 365 * price / (take_bps / 1e4)
    return (needed / volume_per_day) ** (1 / years) - 1


def nearest_index(sorted_days: list[str], day: str) -> int:
    return min(bisect.bisect_left(sorted_days, day), len(sorted_days) - 1)
