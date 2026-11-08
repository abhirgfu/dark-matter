"""Compare the Explorer API's swap volume with DefiLlama's, and run the track's test on it.

The API terms do not allow keeping its data for more than 24 hours, so the daily files stay in data/local,
which git ignores. Only this summary is kept, in data/static/manual_checks.json. To repeat it, with your own
key in .env:

    python pipeline/fetch_explorer.py --days 14
    python pipeline/fetch_explorer.py --since 2025-01-01 --min-usd 2500
    python pipeline/explorer_check.py
    python pipeline/manifest.py write
    python rebuild.py
"""
from __future__ import annotations

import datetime as dt

from analyze import bigquery_usage, hypothesis
from common import RAW, ROOT, STATIC, read_json, write_json

LOCAL = ROOT / "data" / "local"


def total(day: dict, field: str) -> float:
    return day.get(f"public_{field}", 0) + day.get(f"confidential_{field}", 0)


def main() -> None:
    recent = read_json(LOCAL / "explorer_daily.json")
    if "_oldest" in recent:
        raise SystemExit("explorer_daily.json is from a run that stopped part way: run fetch_explorer.py again")
    llama = read_json(RAW / "defillama_near_intents.json")["volume"]
    days = sorted(recent)[1:-1]  # the first and last days are partial
    days = [d for d in days if d in llama]
    explorer_usd = sum(total(recent[d], "usd") for d in days)
    swaps = sum(total(recent[d], "swaps") for d in days)
    private_usd = sum(recent[d].get("confidential_usd", 0) for d in days)
    private_swaps = sum(recent[d].get("confidential_swaps", 0) for d in days)

    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    pulled = dt.datetime.fromtimestamp((LOCAL / "explorer_daily.json").stat().st_mtime, dt.timezone.utc).date().isoformat()
    check = {
        "checked": pulled,
        "days": len(days), "first": days[0], "last": days[-1],
        "share_of_defillama": round(explorer_usd / sum(llama[d] for d in days), 3),
        "swaps": swaps,
        "confidential_swaps": private_swaps,
        "confidential_usd": round(private_usd),
    }
    if (LOCAL / "explorer_history.json").exists():
        history = read_json(LOCAL / "explorer_history.json")
        if "_oldest" in history:
            raise SystemExit("explorer_history.json is from a run that stopped part way: run it again with --resume")
        network = bigquery_usage(read_json(RAW / "network_daily.json"))
        test = hypothesis({d: total(v, "usd") for d, v in history.items() if d < today}, network)
        check.update({
            "floor_usd": 2500,
            "floor_share_of_dollars": round(sum(total(history[d], "usd") for d in days if d in history) / explorer_usd, 3),
            "history_first": min(history),
            "test_first": test["first"], "test_last": test["last"], "test_weeks": test["weeks"],
            "clear_wins": test["clear_wins"], "clear_losses": test["clear_losses"],
            "tests": {k: {x: round(t[x], 3) for x in ("volume_r", "price_r", "difference", "difference_low", "difference_high")}
                      for k, t in test["tests"].items()},
        })
    checks = read_json(STATIC / "manual_checks.json")
    checks["explorer_check"] = check
    write_json(STATIC / "manual_checks.json", checks)
    print(check)


if __name__ == "__main__":
    main()
