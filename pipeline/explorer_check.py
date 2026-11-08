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
    checks = read_json(STATIC / "manual_checks.json")
    check = checks.get("explorer_check", {})
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    history_path, daily_path = LOCAL / "explorer_history.json", LOCAL / "explorer_daily.json"
    history = read_json(history_path) if history_path.exists() else None
    partial = history is not None and "_oldest" in history
    if history is not None:
        history.pop("_oldest", None)

    if daily_path.exists():
        recent = read_json(daily_path)
        if "_oldest" in recent:
            raise SystemExit("explorer_daily.json is from a run that stopped part way: run fetch_explorer.py again")
        llama = read_json(RAW / "defillama_near_intents.json")["volume"]
        days = [d for d in sorted(recent)[1:-1] if d in llama]  # the first and last days are partial
        explorer_usd = sum(total(recent[d], "usd") for d in days)
        check.update({
            "checked": dt.datetime.fromtimestamp(daily_path.stat().st_mtime, dt.timezone.utc).date().isoformat(),
            "days": len(days), "first": days[0], "last": days[-1],
            "share_of_defillama": round(explorer_usd / sum(llama[d] for d in days), 3),
            "swaps": sum(total(recent[d], "swaps") for d in days),
            "confidential_swaps": sum(recent[d].get("confidential_swaps", 0) for d in days),
            "confidential_usd": round(sum(recent[d].get("confidential_usd", 0) for d in days)),
        })
        if history is not None and all(d in history for d in days):
            check["floor_usd"] = 2500
            check["floor_share_of_dollars"] = round(sum(total(history[d], "usd") for d in days) / explorer_usd, 3)

    if history is not None and not partial:
        network = bigquery_usage(read_json(RAW / "network_daily.json"))
        test = hypothesis({d: total(v, "usd") for d, v in history.items() if d < today}, network)
        check.update({
            "history_first": min(history),
            "test_first": test["first"], "test_last": test["last"], "test_weeks": test["weeks"],
            "clear_wins": test["clear_wins"], "clear_losses": test["clear_losses"],
            "tests": {k: {x: round(t[x], 3) for x in ("volume_r", "price_r", "difference", "difference_low", "difference_high")}
                      for k, t in test["tests"].items()},
        })

    if "checked" not in check:
        raise SystemExit("run fetch_explorer.py first")
    checks["explorer_check"] = check
    write_json(STATIC / "manual_checks.json", checks)
    print(check)
    if partial:
        print("The history pull has not finished, so the test on it was not run.")


if __name__ == "__main__":
    main()
