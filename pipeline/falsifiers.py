"""The tests the thesis can fail. Rules and limits live here so that their hash can go on chain.

Each test reads the derived results and returns a value and a state:

    holding   the claim stands
    watch     the value is inside the warning band
    broken    the claim has failed
    unknown   the data for this test is missing

`manual` tests depend on a public statement that no query can detect. Their state comes from
data/static/manual_checks.json, which records the date each one was last checked by hand.
"""
from __future__ import annotations


def _state(value, broken_below=None, watch_below=None, broken_above=None, watch_above=None) -> str:
    if value is None:
        return "unknown"
    if broken_below is not None and value < broken_below:
        return "broken"
    if broken_above is not None and value > broken_above:
        return "broken"
    if watch_below is not None and value < watch_below:
        return "watch"
    if watch_above is not None and value > watch_above:
        return "watch"
    return "holding"


def evaluate(r: dict, manual: dict) -> list[dict]:
    tests = []

    gap = r["weigh"]["recent_gap_pct"]
    tests.append({
        "id": "T1", "name": "The treasury can be weighed from the public chain",
        "breaks_if": "Our figure sits more than 15% from NEAR's on a typical day in the last 60",
        "value": gap, "shown": None if gap is None else f"{gap:.1f}% median gap",
        "state": _state(gap, broken_above=15, watch_above=10),
    })

    share = r["provenance"]["last_30_days_share"]
    tests.append({
        "id": "T2", "name": "Most of NEAR's revenue comes through the private treasury",
        "breaks_if": "Under 25% of the last 30 days' revenue left the treasury first",
        "value": share, "shown": None if share is None else f"{share * 100:.0f}% in the last 30 days",
        "state": _state(share, broken_below=0.25, watch_below=0.4),
    })

    before, after = r["revenue"]["before"]["bps"], r["revenue"]["after"]["bps"]
    ratio = after / before if before and after else None
    tests.append({
        "id": "T3", "name": "NEAR keeps more than it did before",
        "breaks_if": "Revenue per dollar falls back to its level before the step",
        "value": ratio, "shown": None if ratio is None else f"{ratio:.1f}× the earlier level",
        "state": _state(ratio, broken_below=1.0, watch_below=1.25),
    })

    late_before, late_after = r["revenue"]["late_before"]["bps"], r["revenue"]["late_after"]["bps"]
    held = late_after / late_before if late_before and late_after else None
    tests.append({
        "id": "T7", "name": "Private swaps pay NEAR as public swaps did",
        "breaks_if": "Since 27 October, revenue per dollar falls below 60% of the 30 days before",
        "value": held, "shown": None if held is None else f"{held * 100:.0f}% of the earlier level",
        "state": _state(held, broken_below=0.6, watch_below=0.9),
    })

    weight = r["weigh"]["latest"]["weighed"]
    peak = max(x["weighed"] for x in r["weigh"]["series"])
    kept = weight / peak if peak else None
    tests.append({
        "id": "T4", "name": "The private economy holds its size",
        "breaks_if": "The treasury falls more than 60% from its peak",
        "value": kept, "shown": None if kept is None else f"{kept * 100:.0f}% of peak",
        "state": _state(kept, broken_below=0.4, watch_below=0.6),
    })

    keys = len(r["control"]["verifier_keys_now"])
    tests.append({
        "id": "T5", "name": "One key signs for the treasury",
        "breaks_if": "More than one key is registered, or the custody setup is published",
        "value": keys, "shown": f"{keys} key",
        "state": "holding" if keys == 1 and manual["custody_published"]["found"] is False else "broken",
    })

    tests.append({
        "id": "T6", "name": "Private totals cannot be audited from outside",
        "breaks_if": "NEAR or Intents Technology publishes private volume and fees that an auditor can check",
        "value": None, "shown": f"none found, checked {manual['private_totals_published']['checked']}",
        "state": "broken" if manual["private_totals_published"]["found"] else "holding",
    })
    return tests
