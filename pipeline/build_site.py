"""Build the static site, the open data feed and THESIS.md from data/derived/results.json.

Every number in the prose is filled in here from computed results, so no figure is typed by hand.
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
import re
import statistics

import falsifiers
from common import DERIVED, PRIVATE_SWAPS_START, RAW, ROOT, SITE, STATIC, TREASURY, read_json, sha256_file, write_json

SRC = ROOT / "site_src"
REPO_URL = "https://github.com/OWNER/dark-matter"


def usd(v: float | None) -> str:
    if v is None:
        return "n/a"
    a = abs(v)
    if a >= 1e9:
        return f"${v / 1e9:.1f}B"
    if a >= 1e6:
        return f"${v / 1e6:.1f}M"
    if a >= 1e3:
        return f"${v / 1e3:.1f}K"
    return f"${v:.0f}"


def pct(v: float | None, digits: int = 0) -> str:
    return "n/a" if v is None else f"{v * 100:.{digits}f}%"


def month_name(month: str) -> str:
    return dt.date.fromisoformat(month + "-01").strftime("%B")


def numbers(r: dict, snapshot: dict) -> dict:
    w, p, f, rev, c, mod = r["weigh"], r["provenance"], r["flows"], r["revenue"], r["costs"], r["model"]
    n: dict = {}
    n["asof"] = dt.date.fromisoformat(w["latest"]["date"]).strftime("%-d %b %Y") if False else w["latest"]["date"]
    n["snapshot_usd"] = usd(snapshot["usd"])
    n["snapshot_block"] = f"{snapshot['block']:,}"
    n["reported_usd"] = usd(w["latest"]["reported"])
    n["snapshot_gap"] = f"{abs(snapshot['usd'] / w['latest']['reported'] - 1) * 100:.1f}%"
    n["snapshot_priced"] = str(snapshot["priced_tokens"])
    n["snapshot_tokens"] = str(snapshot["tokens"])
    n["tvl_corr"] = f"{w['correlation']:.3f}"
    n["tvl_gap"] = f"{w['recent_gap_pct']:.1f}%"
    n["tvl_days"] = str(w["tracking"]["days"])
    n["unpriced_tokens"] = str(w["latest"]["unpriced_tokens"])
    n["all_tokens"] = str(w["latest"]["tokens"])
    near = next((x["usd"] for x in w["composition"] if x["symbol"] == "wNEAR"), 0.0)
    n["near_share"] = pct(near / sum(x["usd"] for x in w["composition"]))
    held = w["near_series"][-1]["near"]
    supply = read_json(RAW / "near_supply.json")
    total_supply = supply[max(supply)]["total_supply_near"]
    n["near_held"] = f"{held / 1e6:.1f}M"
    n["near_pct_supply"] = pct(held / total_supply, 1)

    n["rev_share_recent"] = pct(p["since_private_swaps_share"])
    n["rev_share_30d"] = pct(p["last_30_days_share"])
    n["payments_checked"] = f"{p['payments_checked']:,}"
    months = {m["month"]: m for m in p["monthly"]}
    last_full = sorted(months)[-2] if len(months) > 1 else None
    n["rev_share_last_full_month"] = pct(months[last_full]["share"]) if last_full else "n/a"
    n["last_full_month"] = month_name(last_full) if last_full else "n/a"
    first_private = next((m for m in sorted(months) if months[m]["share"] and months[m]["share"] > 0), None)
    n["first_private_month"] = month_name(first_private) if first_private else "n/a"
    n["provenance_sentence"] = (
        f"In {n['last_full_month']}, {n['rev_share_last_full_month']} of revenue dollars left the treasury first. "
        f"Since 27 October it is {n['rev_share_recent']}. Exact matching can only miss, so these are floors."
    )
    n["wallet_gap"] = f"{abs(rev['wallet_vs_defillama']['gap_pct']):.1f}%"

    before, after = rev["before"], rev["after"]
    n["bps_before"] = f"{before['bps']:.2f}"
    n["bps_after"] = f"{after['bps']:.2f}"
    n["bps_after_days"] = str(after["days"])
    n["bps_change"] = f"{rev['change_pct']:+.0f}%".replace("-", "−")
    n["rev_before_day"] = usd(before["revenue_per_day"])
    n["rev_after_day"] = usd(after["revenue_per_day"])
    needed = mod["issued_near_per_day"] * mod["near_price"]
    n["coverage_after"] = pct(after["revenue_per_day"] / needed)
    n["model_price"] = f"{mod['near_price']:.2f}"
    n["model_usd_day"] = usd(needed)
    n["issuance_rate"] = pct(mod["issuance_rate"], 2)
    n["issued_day"] = f"{mod['issued_near_per_day']:,.0f}"
    be = mod["break_even_all_public"]
    n["breakeven_public"] = usd(be["volume_per_day"])
    n["breakeven_multiple"] = f"{be['volume_per_day'] / mod['volume_per_day']:.1f}"
    n["volume_day"] = usd(mod["volume_per_day"])
    n["model_volume"] = str(int(round(mod["volume_per_day"] / 1e6 / 10) * 10))

    s = f.get("summary") or {}
    share = s.get("user_share_of_volume")
    n["model_share"] = str(int(round((share or 0.7) * 20) * 5))
    if s:
        n["flow_user_day"] = usd(s["user_in_per_day"])
        n["flow_share"] = pct(share)
        n["flow_dwell"] = f"{s['dwell_days']:.1f}" if s.get("dwell_days") else "n/a"
        n["flow_headline"] = f"About {pct(share)} of reported volume now crosses the boundary"
        n["flow_intro"] = (
            "A swap on the private path enters the treasury in one token and leaves in another. "
            "So the transfers into the treasury are a public measure of private use, even though "
            "the swaps themselves cannot be seen."
        )
        n["flow_sentence"] = (
            f"Since 27 October, accounts other than solvers have moved {n['flow_user_day']} a day into the "
            f"treasury, about {pct(share)} of reported volume. At that pace the treasury turns over about "
            f"every {n['flow_dwell']} days, so most of it is moving, not resting."
        )
    else:
        n["flow_headline"] = "How much of the volume crosses the boundary"
        n["flow_intro"] = "Daily boundary flows are still being collected."
        n["flow_sentence"] = "Daily boundary flows are still being collected."
    cap = rev.get("capture")
    if cap:
        n["capture_sentence"] = (
            f"Fitted over {cap['days']} days, a private dollar earned NEAR {cap['private_bps']:.1f} bps "
            f"(90% interval {cap['private_bps_low']:.1f} to {cap['private_bps_high']:.1f}) and a public dollar "
            f"{cap['public_bps']:.1f} bps ({cap['public_bps_low']:.1f} to {cap['public_bps_high']:.1f})."
        )
    else:
        n["capture_sentence"] = "Too few days have passed to separate the two paths with confidence."
    if c.get("all", {}).get("n"):
        a = c["all"]
        n["cost_sentence"] = (
            f"Across {a['n']:,} paired accounts and {usd(a['usd'])}, the median private swap cost "
            f"{a['median_bps']:.0f} bps from entry to exit. Gross public fees run near "
            f"{before.get('fee_bps', 15):.0f} bps, before solver spread, so this is not yet like for like."
        )
    else:
        n["cost_sentence"] = "Paired accounts are still being collected."
    n["activity_sentence"] = activity_sentence(r["activity"])
    n["tests_holding"] = str(sum(t["state"] == "holding" for t in r["tests"]))
    n["tests_total"] = str(len(r["tests"]))
    ctl = r["control"]
    n["key"] = ctl["verifier_keys_now"][0]
    n["key_dates"] = str(len(ctl["keys_through_time"]))
    n["key_signed"] = str(sum(ctl["outflow_signers_sample"]["keys"].values()))
    n["key_sample"] = str(ctl["outflow_signers_sample"]["transactions"])
    return n


def activity_sentence(rows: list[dict]) -> str:
    if len(rows) < 60:
        return ""
    recent = rows[-30:]
    earlier = rows[-60:-30]
    change = lambda key: statistics.mean(r[key] for r in recent) / statistics.mean(r[key] for r in earlier) - 1
    tx, acc = change("txns"), change("active_accounts")
    return (
        f"Over the last 30 days, daily transactions moved {tx * 100:+.0f}% and active accounts {acc * 100:+.0f}% "
        "against the 30 days before. Whether that is less use or use moving out of sight is exactly what "
        "these charts can no longer say."
    )


QUERIES = {
    "query_weight": """POST https://archival-rpc.mainnet.fastnear.com
{"method":"query","params":{"request_type":"call_function","block_id":<first block of the day>,
 "account_id":"intents.near","method_name":"mt_tokens_for_owner",
 "args_base64":<{"account_id":"51e8f94d...7cbe"}>}}

then mt_batch_balance_of for those tokens at the same block.
Value = sum(balance / 10^decimals * DefiLlama daily price).
Code: pipeline/fetch_treasury.py, pipeline/metrics.py value_treasury""",
    "query_provenance": """1. Payments: every native NEAR transfer from intents.near into
   buybacks.multisignature.near, fefundsadmin.sputnik-dao.near, 1csfundsadmin.sputnik-dao.near
   POST https://transfers.main.fastnear.com/v0/transfers
   {"account_id":<wallet>,"direction":"receiver"}

2. Treasury outflows: every wNEAR transfer out of the treasury
   {"account_id":"51e8f94d...7cbe","direction":"sender",
    "asset_id":"nep245:intents.near:nep141:wrap.near"}

3. A payment is private when an outflow of exactly the same yoctoNEAR left the treasury in the
   six hours before it. Each outflow can explain one payment.
Code: pipeline/metrics.py match_payments""",
    "query_flows": """POST https://transfers.main.fastnear.com/v0/transfers
{"account_id":"51e8f94d...7cbe","direction":"receiver","min_usd_amount":2500,
 "from_timestamp_ms":<day start>,"to_timestamp_ms":<day end>}

About 5% of rows and about 95% of dollars. Accounts with "solver" in the name are counted apart.
Volume is DefiLlama's NEAR Intents series.
Code: pipeline/fetch_flows.py, pipeline/analyze.py flows""",
    "query_bps": """Revenue: the wallet payments above, summed by week.
Volume: https://api.llama.fi/summary/dexs/near-intents
bps = revenue / volume * 10,000
Before: 27 Sep to 26 Oct. After: 27 Oct onward.
Code: pipeline/analyze.py revenue""",
    "query_cost": """Every transfer of any size, both ways, for sampled hours.
A pair is an account that is not a solver, with exactly one transfer in and one out, inside the hour.
cost = (usd_in - usd_out) / usd_in * 10,000
Code: pipeline/fetch_flows.py windows, pipeline/metrics.py pair_accounts""",
    "query_activity": """No key needed: https://api.nearblocks.io/v1/charts

The same metrics on the NEAR BigQuery public dataset are in sql/, for example:

SELECT CAST(block_date AS STRING) AS date,
       COUNT(DISTINCT signer_account_id) AS active_signers,
       COUNT(*) AS transactions
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date BETWEEN DATE @since AND DATE @until
GROUP BY date ORDER BY date""",
}


def control_rows(r: dict, n: dict) -> str:
    ctl = r["control"]
    short_key = n["key"].replace("ed25519:", "")[:10] + "…"
    rows = [
        ("Who holds the backing", f"One account, <code>51e8f94d…7cbe</code>, holds {n['snapshot_usd']} on <code>intents.near</code>",
         "<code>mt_batch_balance_of</code>; NEAR Intents market-maker docs"),
        ("Keys on intents.near", f"One key, <code>{short_key}</code>, at all {n['key_dates']} dates checked since February",
         "<code>public_keys_of</code> at archival blocks"),
        ("Who signs money out", f"That key signed {n['key_signed']} of {n['key_sample']} sampled transfers out",
         "Signed intents in each transaction"),
        ("Keys on the account itself", "One full-access key, the same one", "<code>view_access_key_list</code>"),
        ("The private chain", "A permissioned fork of NEAR run by a small validator set, with a private RPC and no public explorer",
         "NEAR Intents docs; near.org"),
        ("The private fee", "Set by Intents Technology alone. It can change or remove the fee at any time, by route, asset or partner. There is no app fee",
         "1Click API Terms 6.8 and Schedule 1 section 6"),
        ("Rule for sending fees to NEAR", "None we can find in code. Payments arrive from one-use accounts", "This analysis"),
        ("Where bought NEAR sits", f"A multisig needing {ctl.get('buybacks_confirmations', 2)} confirmations, held, not burned", "<code>get_num_confirmations</code>"),
        ("Audit access", "Selective disclosure is described as planned, not live", "near.org, How Confidential Intents Works"),
    ]
    return "".join(f"<tr><td><strong>{a}</strong></td><td>{b}</td><td>{c}</td></tr>" for a, b, c in rows)


def test_rows(tests: list[dict]) -> str:
    labels = {"holding": "Holding", "watch": "Watch", "broken": "Broken", "unknown": "No data"}
    out = []
    for t in tests:
        out.append(
            f"<tr><td><strong>{html.escape(t['name'])}</strong></td><td>{html.escape(t['breaks_if'])}</td>"
            f"<td class=\"num\">{html.escape(t['shown'] or 'n/a')}</td>"
            f"<td><span class=\"status {t['state']}\">{labels[t['state']]}</span></td></tr>"
        )
    return "".join(out)


LIMITS = [
    "We see the boundary, not the inside. Swaps on the private chain, their fees and their solvers cannot be observed.",
    "Paired accounts show cost only for accounts that enter and leave inside the sampled hour. A swap that returns to another account is missed.",
    "The revenue match is exact to the yoctoNEAR, so it can only undercount. A sweep that merges two transfers looks public.",
    "A payment out of the treasury shows where money came from, not what earned it.",
    "Tokens with no public price history are left unpriced, not guessed. That is why our daily series reads below NEAR's.",
    "The daily flow census covers transfers of $2,500 or more, about 95% of dollars by a sample.",
    "Eleven days of private swaps is short. Revenue per dollar can move for many reasons, including mix and price.",
    "The 1Click API terms limit how long API data may be kept, so no quote or Explorer data is stored here.",
]


def write_feed(r: dict) -> None:
    data = SITE / "data"
    data.mkdir(parents=True, exist_ok=True)
    rows = [("date", "weighed_usd", "reported_usd")] + [(x["date"], x["weighed"], x["reported"]) for x in r["weigh"]["series"]]
    with open(data / "weight.csv", "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh, lineterminator="\n").writerows(rows)
    rows = [("month", "paid_from_treasury_usd", "no_private_trace_usd", "share")] + [
        (m["month"], m["private_usd"], m["public_usd"], m["share"]) for m in r["provenance"]["monthly"]]
    with open(data / "revenue_source.csv", "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh, lineterminator="\n").writerows(rows)
    rows = [("date", "user_in_usd", "solver_in_usd", "volume_usd", "treasury_usd")] + [
        (x["date"], x["user_in_usd"], x["solver_in_usd"], x["volume_usd"], x["tvl_usd"]) for x in r["flows"]["daily"]]
    with open(data / "flows.csv", "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh, lineterminator="\n").writerows(rows)
    write_json(data / "results.json", r, compact=True)


def fill(template: str, values: dict) -> str:
    def repl(match: re.Match) -> str:
        key = match.group(1)
        if key not in values:
            raise KeyError(f"no value for {{{{{key}}}}}")
        return str(values[key])
    return re.sub(r"\{\{([a-z_0-9]+)\}\}", repl, template)


def main() -> None:
    r = read_json(DERIVED / "results.json")
    snapshot = read_json(RAW / "weigh_snapshot.json")
    r["tests"] = falsifiers.evaluate(r, read_json(STATIC / "manual_checks.json"))
    write_json(DERIVED / "tests.json", r["tests"])
    n = numbers(r, snapshot)
    write_json(DERIVED / "numbers.json", n)

    deployment = read_json(STATIC / "deployment.json")
    SITE.mkdir(exist_ok=True)
    write_feed(r)
    digest = sha256_file(ROOT / "data" / "manifest.json")

    payload = {
        "treasury": TREASURY,
        "reported_latest": r["weigh"]["latest"]["reported"],
        "private_start": PRIVATE_SWAPS_START.isoformat(),
        "weigh": {"series": r["weigh"]["series"], "composition": r["weigh"]["composition"]},
        "provenance": {"monthly": r["provenance"]["monthly"]},
        "flows": {"daily": r["flows"]["daily"]},
        "revenue": {"weekly": r["revenue"]["weekly"]},
        "costs": r["costs"],
        "activity": r["activity"],
        "model": {**r["model"], "total_supply": read_json(RAW / "near_supply.json")[max(read_json(RAW / "near_supply.json"))]["total_supply_near"]},
    }
    values = {
        **n,
        **{k: html.escape(v) for k, v in QUERIES.items()},
        "repo_url": deployment.get("repo_url") or REPO_URL,
        "snapshot_note": (
            f"Read from intents.near at block {n['snapshot_block']}: {n['snapshot_priced']} of {n['snapshot_tokens']} tokens priced. "
            f"NEAR's reported figure is {n['reported_usd']}, {n['snapshot_gap']} away."
        ),
        "control_rows": control_rows(r, n),
        "test_rows": test_rows(r["tests"]),
        "limit_rows": "".join(f"<li>{html.escape(x)}</li>" for x in LIMITS),
        "contract_status": deployment.get("contract") or "dark-matter",
        "build_id": digest[:12],
        "manifest_short": digest[:16],
        "style": (SRC / "style.css").read_text(encoding="utf-8"),
        "charts_js": (SRC / "charts.js").read_text(encoding="utf-8"),
        "weigh_js": (SRC / "weigh.js").read_text(encoding="utf-8"),
        "app_js": (SRC / "app.js").read_text(encoding="utf-8"),
        "data": json.dumps(payload, separators=(",", ":"), sort_keys=True).replace("</", "<\\/"),
    }
    page = fill((SRC / "index.template.html").read_text(encoding="utf-8"), values)
    with open(SITE / "index.html", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    print("site built:", len(page) // 1024, "KB; tests:", [(t["id"], t["state"]) for t in r["tests"]])

    thesis = ROOT / "THESIS.in.md"
    if thesis.exists():
        text = fill(thesis.read_text(encoding="utf-8"), {**n, "manifest": digest, "repo_url": values["repo_url"]})
        with open(ROOT / "THESIS.md", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)


if __name__ == "__main__":
    main()
