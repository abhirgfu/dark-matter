"""Public series that we compare our measurements with. None of them needs a key.

- DefiLlama: NEAR Intents daily volume, gross fees and captured revenue.
- revenue.near.org: the series NEAR publishes, embedded in the page, including daily confidential
  TVL. This is the number our weighing has to reproduce.
- NEAR RPC: total supply today and a year ago, for the issuance rate.
"""
from __future__ import annotations

import datetime as dt
import json
import re

from common import RAW, block_header, first_block_of_day, get_json, http, write_json

LLAMA = {
    "volume": "https://api.llama.fi/summary/dexs/near-intents",
    "fees": "https://api.llama.fi/summary/fees/near-intents?dataType=dailyFees",
    "revenue": "https://api.llama.fi/summary/fees/near-intents?dataType=dailyRevenue",
}


def defillama() -> None:
    out = {}
    for name, url in LLAMA.items():
        chart = get_json(url).get("totalDataChart") or []
        out[name] = {
            dt.datetime.fromtimestamp(int(t), dt.timezone.utc).strftime("%Y-%m-%d"): float(v)
            for t, v in chart
        }
        print("defillama", name, len(out[name]))
    write_json(RAW / "defillama_near_intents.json", out)


def near_reported() -> None:
    html = http("https://revenue.near.org").decode("utf-8", "replace").replace('\\"', '"')
    series = {}
    for name in ("tvlChartSeries", "emissionsMonthly", "absoluteRevEmissions"):
        match = re.search(rf'"{name}":(\[\{{.*?\}}\])', html)
        if match:
            series[name] = json.loads(match.group(1))
            print("revenue.near.org", name, len(series[name]))
    if "tvlChartSeries" not in series:
        raise SystemExit("revenue.near.org no longer embeds tvlChartSeries: check the page")
    write_json(RAW / "near_reported.json", series)


def supply() -> None:
    """Total supply at the first block of the latest day, 30 days back and 365 days back."""
    today = dt.datetime.now(dt.timezone.utc).date()
    points = {}
    for back in (0, 30, 365):
        day = today - dt.timedelta(days=back)
        block = first_block_of_day(day)
        header = block_header(block)
        points[day.isoformat()] = {"block": block, "total_supply_near": int(header["total_supply"]) / 1e24}
        print("supply", day, points[day.isoformat()])
    write_json(RAW / "near_supply.json", points)


def network() -> None:
    """Daily active accounts, transactions and contracts for the whole chain, from NearBlocks.

    sql/ holds the same metrics for the NEAR BigQuery dataset. BigQuery needs a Google account, so
    this keyless series lets anyone rebuild the charts, and the two can be compared."""
    charts = get_json("https://api.nearblocks.io/v1/charts").get("charts", [])
    keep = {}
    for row in charts:
        date = row["date"][:10]
        if date < "2025-11-01":
            continue
        keep[date] = {
            "txns": int(row["txns"]),
            "active_accounts": int(row["active_accounts"]),
            "active_contracts": int(row["active_contracts"]),
            "near_price": float(row["near_price"]),
            "market_cap": float(row["market_cap"]),
            "total_supply_near": int(row["total_supply"]) / 1e24,
            "circulating_supply_near": int(row["circulating_supply"]) / 1e24,
        }
    print("nearblocks days", len(keep))
    write_json(RAW / "network_daily.json", keep)


if __name__ == "__main__":
    defillama()
    near_reported()
    network()
    supply()
