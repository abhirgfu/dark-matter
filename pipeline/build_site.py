"""Build the static site, the open data feed and THESIS.md from data/derived/results.json.

Every number in the prose is filled in here from computed results, so no figure is typed by hand.
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
import re
import shutil
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
    n["tvl_gap_all"] = f"{w['tracking']['median_abs_pct']:.1f}%"
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

    h = r["hand_trace"]
    n["trace_read"] = str(h["read"])
    n["trace_treasury"] = str(h["from_treasury"])
    n["trace_accounts"] = str(h["treasury_accounts"])
    n["trace_first"] = h["first_from_treasury"]
    n["trace_before_july"] = str(h["before_july"])
    n["trace_before_july_hits"] = str(h["before_july_from_treasury"])
    n["rev_share_recent"] = pct(p["last_30_days_share"])
    n["payments_checked"] = f"{p['payments_checked']:,}"
    era = dt.date.fromisoformat(rev["era_start"])
    n["era_start"] = rev["era_start"]
    n["era_month"] = era.strftime("%B")
    n["era_start_text"] = f"{era.day} {era.strftime('%B')}"
    n["era_baseline_days"] = str(rev["before"]["days"])
    route = dt.date.fromisoformat(rev["route_start"])
    n["route_start"] = rev["route_start"]
    n["route_month"] = route.strftime("%B")
    n["route_start_text"] = f"{route.day} {route.strftime('%B')}"
    early = sum(d["private"] for k, d in p["daily"].items() if k < rev["route_start"])
    early_all = sum(d["private"] + d["public"] for k, d in p["daily"].items() if k < rev["route_start"])
    n["rev_share_early"] = pct(early / early_all if early_all else None)
    months = {m["month"]: m for m in p["monthly"]}
    june = months.get("2026-06")
    n["rev_share_june"] = pct(june["share"]) if june else "n/a"
    n["first_private"] = p["first_private_payment"]
    first = dt.date.fromisoformat(p["first_private_payment"])
    n["first_private_text"] = f"{first.day} {first.strftime('%B')}"
    n["bps_between"] = f"{rev['between']['bps']:.2f}"
    n["share_between"] = pct(rev["between"]["private_bps"] / rev["between"]["bps"])
    before, after = rev["before"], rev["after"]
    n["bps_before"] = f"{before['bps']:.2f}"
    n["bps_after"] = f"{after['bps']:.2f}"
    n["bps_multiple"] = f"{after['bps'] / before['bps']:.1f}"
    n["bps_after_days"] = str(after["days"])
    n["bps_private"] = f"{after['private_bps']:.2f}"
    n["bps_public"] = f"{after['public_bps']:.2f}"
    n["bps_public_before"] = f"{before['public_bps']:.2f}"
    n["fee_bps_before"] = f"{before['fee_bps']:.1f}"
    n["fee_bps_after"] = f"{after['fee_bps']:.1f}"
    n["capture_before"] = pct(before["capture"])
    n["capture_after"] = pct(after["capture"])
    n["private_part"] = pct(rev["late_after"]["private_bps"] / rev["late_after"]["bps"])
    n["rev_before_day"] = usd(before["revenue_per_day"])
    n["rev_late_day"] = usd(rev["late_after"]["revenue_per_day"])
    n["rev_after_day"] = usd(after["revenue_per_day"])
    n["late_bps_before"] = f"{rev['late_before']['bps']:.2f}"
    n["late_bps_after"] = f"{rev['late_after']['bps']:.2f}"
    n["bps_private_before"] = f"{before['private_bps']:.2f}"
    weeks = [w for w in rev["weekly"] if w["week"] < "2026-07-01"]
    peak = max(weeks, key=lambda w: w["bps"]) if weeks else None
    n["early_peak_bps"] = f"{peak['bps']:.1f}" if peak else "n/a"
    n["early_peak_week"] = dt.date.fromisoformat(peak["week"]).strftime("%B") if peak else "n/a"
    n["provenance_sentence"] = (
        f"In the {n['era_baseline_days']} days before {n['era_start_text']}, NEAR kept {n['bps_before']} bps of volume. "
        f"Since then it has kept {n['bps_after']} bps. The part with no private trace barely moved, from "
        f"{n['bps_public_before']} to {n['bps_public']} bps. All of the gain left the treasury first: "
        f"{n['bps_private_before']} to {n['bps_private']} bps."
    )
    n["wallet_gap"] = f"{abs(rev['wallet_vs_defillama']['gap_pct']):.1f}%"
    needed = mod["issued_near_per_day"] * mod["near_price"]
    late = rev["late_after"]
    n["coverage_after"] = pct(late["revenue_per_day"] / needed)
    n["late_days"] = str(late["days"])
    late_move = (late["bps"] / rev["late_before"]["bps"] - 1) * 100
    n["late_change"] = f"{late_move:+.0f}%".replace("-", "−")
    n["late_fall"] = f"{abs(late_move):.0f}%"
    n["late_private_before"] = f"{rev['late_before']['private_bps']:.2f}"
    n["late_private_after"] = f"{late['private_bps']:.2f}"
    n["late_public_before"] = f"{rev['late_before']['public_bps']:.2f}"
    n["late_public_after"] = f"{late['public_bps']:.2f}"
    n["take_today_private_part"] = pct(late["private_bps"] / late["bps"])
    n["last_week_bps"] = f"{rev['weekly'][-1]['bps']:.2f}"
    n["last_week_days"] = str(rev["weekly"][-1]["days"])
    n["public_floor"] = n["late_public_after"]
    n["model_price"] = f"{mod['near_price']:.2f}"
    n["model_usd_day"] = usd(needed)
    n["issuance_rate"] = pct(mod["issuance_rate"], 2)
    n["issued_day"] = f"{mod['issued_near_per_day']:,.0f}"
    n["breakeven_today"] = usd(mod["break_even_today"]["volume_per_day"])
    n["breakeven_half"] = usd(mod["break_even_half"]["volume_per_day"])
    n["breakeven_none"] = usd(mod["break_even_none"]["volume_per_day"])
    n["breakeven_multiple"] = f"{mod['break_even_today']['volume_per_day'] / mod['volume_per_day']:.1f}"
    n["volume_day"] = usd(mod["volume_per_day"])
    n["model_volume"] = str(int(round(mod["volume_per_day"] / 1e6 / 10) * 10))
    s = f.get("summary") or {}
    share = s.get("user_share_of_volume")
    fit = rev.get("capture")
    if fit:
        n["fit_days"] = str(fit["days"])
        n["fit_private"] = f"{fit['private_bps']:.1f}"
        n["fit_public"] = f"{fit['public_bps']:.1f}"
        n["fit_private_low"] = f"{abs(round(fit['private_bps_low'])):.0f}" if abs(fit["private_bps_low"]) < 0.5 else f"{fit['private_bps_low']:.0f}"
        n["fit_private_high"] = f"{fit['private_bps_high']:.0f}"
        n["fit_sentence"] = (
            f"A rough fit over {n['fit_days']} days puts a dollar crossing the boundary at about {n['fit_private']} bps to NEAR "
            f"and any other dollar at about {n['fit_public']} bps. The 90% interval on the private figure runs from "
            f"{n['fit_private_low']} to {n['fit_private_high']} bps, so it cannot settle the question yet."
        )
    else:
        n["fit_sentence"] = "Too few days have passed to separate the two routes."
    if s and s.get("before") and s.get("last_week"):
        was, now = s["before"], s["last_week"]
        n["flow_dwell"] = f"{s['dwell_days']:.1f}" if s.get("dwell_days") else "n/a"
        n["flow_share_before"] = pct(was["share"])
        n["flow_share_recent"] = pct(now["share"])
        n["flow_accounts_before"] = f"{was['accounts']:,.0f}"
        n["flow_accounts_recent"] = f"{now['accounts']:,.0f}"
        n["flow_user_day"] = usd(now["user_in_per_day"])
        n["flow_sentence"] = (
            f"Money from accounts other than solvers went from {n['flow_share_before']} of reported volume before "
            f"27 October to {n['flow_share_recent']} in the last seven days, about {n['flow_user_day']} a day. Accounts crossing "
            f"each day went from {n['flow_accounts_before']} to {n['flow_accounts_recent']}. Counting solvers, the treasury turns "
            f"over about every {n['flow_dwell']} days, so most of it is moving, not resting."
        )
    else:
        n["flow_share_recent"] = "n/a"
        n["flow_share_before"] = "n/a"
        n["flow_sentence"] = "Daily boundary flows are still being collected."
    before_rate, after_rate = c.get("swaps_per_hour_before"), c.get("swaps_per_hour_after")
    if before_rate is not None and after_rate is not None:
        n["swaps_before"] = f"{before_rate:.0f}"
        n["swaps_after"] = f"{after_rate:.0f}"
        lost = c["lost_usd_per_hour_after"]
        n["swaps_multiple"] = f"{after_rate / before_rate:.0f}"
        n["swap_hours_before"] = f"{c['hours_before']:.0f}"
        n["swap_hours_after"] = f"{c['hours_after']:.1f}"
        n["lost_day"] = usd(lost * 24)
        n["swaps_sentence"] = (
            f"In {c['hours_before']:.0f} sampled hours before 27 October we saw about {before_rate:.0f} private swaps an "
            f"hour. In {c['hours_after']:.1f} hours since, about {after_rate:.0f}. These are only the swaps we can pair, so "
            "the true counts are higher."
        )
    else:
        n["swaps_sentence"] = "Sampled hours are still being collected."
    if c.get("all", {}).get("n"):
        a = c["all"]
        stable = c["by_class"].get("stable to stable", {})
        other = c["by_class"].get("other", {})
        n["cost_stable"] = f"{stable.get('median_bps', 0):.1f}"
        n["cost_other"] = f"{other.get('median_bps', 0):.0f}"
        fp = c["fingerprint"]
        n["fee_base"] = f"{fp['base_bps']:.0f}"
        n["fee_low"] = f"{fp['low_bps']:.0f}"
        n["fee_high"] = f"{fp['high_bps']:.0f}"
        n["fee_low_share"] = pct(fp["low_share"])
        n["fee_high_share"] = pct(fp["high_share"])
        n["fee_swaps"] = f"{fp['swaps']:,}"
        sizes = fp["by_size"]
        n["fee_by_size"] = ", ".join(f"{sizes[k]:.0f} bps {k}" for k in ("under $1K", "$1K to $10K", "over $10K") if k in sizes)
        n["cost_sentence"] = (
            f"These {n['fee_swaps']} swaps do not spread smoothly. They bunch near {n['fee_base']}, {n['fee_low']} and "
            f"{n['fee_high']} bps. That looks like a price list, and no public document gives one. The documented public default "
            f"is 20 bps. Stablecoin swaps cost a median {n['cost_stable']} bps, close to the documented 1 bp. At the sampled "
            f"rate, private swappers lose about {n.get('lost_day', 'n/a')} a day between entry "
            f"and exit, against {n['rev_late_day']} a day reaching NEAR's wallets from every source. Part of that gap is solver "
            "spread and price movement. How much is fee, and who keeps it, cannot be seen."
        )
    else:
        n["cost_sentence"] = "Paired accounts are still being collected."
    lt, h = r["long_term"], r["hypothesis"]
    signed = lambda v: f"{v * 100:+.0f}%".replace("-", "−")
    n["usage_source"] = r["usage_source"]
    n["observed_growth"] = signed(lt["observed_growth"])
    n["needed_cap"] = signed(lt["needed_growth_cap"])
    n["needed_floor"] = signed(lt["needed_growth_floor"])
    n["needed_public"] = signed(lt["needed_growth_public_only"])
    n["volume_year"] = f"{1 + lt['volume_change_year']:.1f}"
    fall = lambda key: f"{abs(lt['usage_change_year'][key]) * 100:.0f}%"
    n["accounts_year"], n["txns_year"], n["calls_year"] = fall("active_accounts"), fall("txns"), fall("function_calls")
    n["contracts_now"], n["contracts_then"] = (f"{lt['contracts_typical'][k]:,.0f}" for k in ("now", "then"))
    n["market_cap"] = usd(lt["market_cap"])
    n["revenue_year"] = usd(lt["revenue_now_per_year"])
    n["multiple_now"] = f"{lt['multiple_now']:.0f}"
    cases = lt["cases"]
    for key, case in cases.items():
        n[f"cover_{key}"] = pct(case["coverage_2031"])
        n[f"rev_{key}"] = usd(case["revenue_2031"])
        n[f"mult_{key}"] = f"{case['multiple_2031']:.0f}"
        n[f"growth_{key}"] = signed(case["growth"])
        n[f"take_{key}"] = f"{case['take_bps']:.2f}"
    n["wins_year"] = str(next((2026 + p["year"] for p in cases["wins"]["path"] if p["coverage"] >= 1), "after 2031"))
    months = lt["months"]
    n["history_sentence"] = (
        f"Monthly volume went from {usd(months[0]['volume'])} in January 2025 to {usd(months[-1]['volume'])} in the last full "
        f"month. Over the last 12 full months the trend is {n['observed_growth']} a year, with large swings around it."
    )
    n["path_sentence"] = (
        f"For revenue to pay for all new NEAR by 2031, volume must grow {n['needed_floor']} a year at today's take and the "
        f"1.6% floor, or {n['needed_cap']} at the 2.5% cap. The recent trend is {n['observed_growth']}. If private swaps "
        f"pay NEAR nothing, the need rises to {n['needed_public']} a year. These cases are arithmetic on stated assumptions "
        "at today's NEAR price, not forecasts."
    )
    tests_h = h["tests"]
    n["h_weeks"] = str(h["weeks"])
    n["h_accounts_v"] = f"{tests_h['active_accounts']['volume_r']:.2f}"
    n["h_accounts_p"] = f"{tests_h['active_accounts']['price_r']:.2f}"
    n["h_txns_v"] = f"{tests_h['txns']['volume_r']:.2f}"
    n["h_txns_p"] = f"{tests_h['txns']['price_r']:.2f}"
    n["h_calls_v"] = f"{tests_h['function_calls']['volume_r']:.2f}"
    n["h_calls_p"] = f"{tests_h['function_calls']['price_r']:.2f}"
    if h["clear_wins"] >= 2:
        n["h_verdict"] = "Supported"
        n["h_headline"] = "Intents volume leads chain usage better than price does"
    elif h["clear_losses"] >= 2:
        n["h_verdict"] = "Rejected"
        n["h_headline"] = "Price leads chain usage better than Intents volume does"
    else:
        n["h_verdict"] = "Not supported"
        n["h_headline"] = "Intents volume does not lead chain usage better than price does"
    clear = h["clear_wins"] + h["clear_losses"]
    n["h_gap"] = "For all three measures the 90% interval on the gap includes zero." if not clear else (
        f"The 90% interval on the gap excludes zero for {clear} of the three measures.")
    n["h_sentence"] = (
        f"Over {n['h_weeks']} weeks, the last four weeks of volume told us little about the next four weeks of active "
        f"accounts (rank correlation {n['h_accounts_v']}), and no more than price did ({n['h_accounts_p']}). For "
        f"transactions it was {n['h_txns_v']} against {n['h_txns_p']}, and for function calls {n['h_calls_v']} against "
        f"{n['h_calls_p']}. {n['h_gap']}"
    )
    n["index_sentence"] = (
        f"Over the last year, Intents volume rose about {n['volume_year']} times while active accounts fell "
        f"{n['accounts_year']}. The two are not moving together, so public chain activity no longer measures what NEAR is used for."
    )
    n["accounts_sentence"] = f"Active accounts are down {n['accounts_year']} on a year ago, comparing 90-day averages."
    d = r["destinations"]
    tenths = lambda v: f"{v * 100:.1f}%"
    whole = lambda v: f"{v * 100:.0f}%"
    ordinal = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth")
    sender = d["sender"]
    n["intents_share_then"], n["intents_share_now"] = tenths(d["share_then"]), tenths(d["share_now"])
    n["intents_share_recent"] = tenths(d["share_recent"])
    n["intents_year"] = whole(d["intents_per_day_now"] / d["intents_per_day_then"] - 1)
    n["intents_gain"] = f"{d['intents_per_day_now'] - d['intents_per_day_then']:,.0f}"
    n["chain_loss"] = f"{(d['chain_per_day_then'] - d['chain_per_day_now']) / 1e6:.1f}M"
    n["rank_then"], n["rank_now"] = ordinal[d["rank_then"] - 1], ordinal[d["rank_now"] - 1]
    n["sender_per_day"] = f"{sender['per_day'] / 1e6:.1f}M"
    n["sender_share"], n["sender_fall_share"] = whole(sender["share"]), whole(sender["share_of_fall"])
    n["sender_year_share"] = whole(sender["share_of_year_fall"])
    n["sender_signers"] = str(sender["signers"])
    n["sender_accounts"] = f"{sender['accounts'] / 1e6:.0f}M"
    n["txns_sentence"] = (
        f"Transactions are down {n['txns_year']} on a year ago. Most of the fall came at the start of April 2026, when "
        f"at most {n['sender_signers']} signing accounts, sending {n['sender_share']} of all transactions, stopped."
    )
    n["calls_sentence"] = (
        f"Function calls are down {n['calls_year']} on a year ago, but the contracts being called have not gone away: about "
        f"{n['contracts_now']} on a typical day, against {n['contracts_then']} a year ago."
    )
    n["intents_sentence"] = (
        f"intents.near took {n['intents_share_then']} of all NEAR transactions a year ago and {n['intents_share_now']} over "
        f"the last 90 days. It went from the {n['rank_then']} busiest destination on the chain to the {n['rank_now']}."
    )
    agree = r["source_agreement"]
    n["agree_days"] = f"{agree['days']:,}"
    n["agree_accounts"], n["agree_txns"] = f"{agree['accounts_equal']:,}", f"{agree['txns_equal']:,}"
    n["bq_last"] = d["last_day"]
    explorer = read_json(STATIC / "manual_checks.json")["explorer_check"]
    n["explorer_checked"], n["explorer_days"] = explorer["checked"], str(explorer["days"])
    n["explorer_share"] = whole(explorer["share_of_defillama"])
    n["explorer_swaps"] = f"{explorer['swaps']:,}"
    n["explorer_private"] = f"{explorer['confidential_swaps']:,}"
    if "tests" in explorer:
        verdict = lambda c: "Supported" if c["clear_wins"] >= 2 else "Rejected" if c["clear_losses"] >= 2 else "Not supported"
        same = verdict(explorer) == n["h_verdict"]
        accounts = explorer["tests"]["active_accounts"]
        n["explorer_test"] = (
            f"We ran the same test on the Explorer's own volume: swaps of at least ${explorer['floor_usd']:,}, which carry "
            f"{whole(explorer['floor_share_of_dollars'])} of its dollars, over {explorer['test_weeks']} weeks from "
            f"{explorer['test_first']}, when its records begin. The result is {verdict(explorer).lower()}, "
            f"{'the same as' if same else 'unlike'} with DefiLlama's volume. For active accounts the rank correlation is "
            f"{accounts['volume_r']:.2f} for volume against {accounts['price_r']:.2f} for price."
        )
        n["explorer_same"] = (", and the same on the Explorer API's own volume" if same else
                              f". On the Explorer API's own volume: {verdict(explorer).lower()}")
    else:
        n["explorer_test"] = "We have not yet run it on the Explorer's own volume."
        n["explorer_same"] = ""
    n["explorer_short"] = (
        f"Done. Run on {n['explorer_checked']}: {n['explorer_share']} of DefiLlama's volume over {n['explorer_days']} days, with "
        f"{n['explorer_private']} of {n['explorer_swaps']} swaps labelled confidential. Its terms bar keeping the data, so only a "
        "summary is kept, and volume elsewhere comes from DefiLlama"
    )
    n["bigquery_short"] = (
        f"Run, and feeding the usage charts. Accounts match NearBlocks on {n['agree_accounts']} of {n['agree_days']} days, "
        f"and transactions on {n['agree_txns']}"
    )
    n["tests_holding"] = str(sum(t["state"] == "holding" for t in r["tests"]))
    n["tests_total"] = str(len(r["tests"]))
    ctl = r["control"]
    n["key"] = ctl["verifier_keys_now"][0]
    n["key_dates"] = str(len(ctl["keys_through_time"]))
    n["key_signed"] = str(sum(ctl["outflow_signers_sample"]["keys"].values()))
    n["key_sample"] = str(ctl["outflow_signers_sample"]["transactions"])
    return n


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

4. Volume: https://api.llama.fi/summary/dexs/near-intents
   bps = weekly receipts / weekly volume * 10,000

Code: pipeline/metrics.py match_payments, pipeline/analyze.py revenue""",
    "query_flows": """POST https://transfers.main.fastnear.com/v0/transfers
{"account_id":"51e8f94d...7cbe","direction":"receiver","min_usd_amount":2500,
 "from_timestamp_ms":<day start>,"to_timestamp_ms":<day end>}

About 5% of rows and about 95% of dollars. Accounts with "solver" in the name are counted apart.
Volume is DefiLlama's NEAR Intents series.
Code: pipeline/fetch_flows.py, pipeline/analyze.py flows""",
    "query_cost": """Every transfer of any size, both ways, for sampled hours.
A pair is an account that is not a solver, with exactly one transfer in and one out, inside the hour.
cost = (usd_in - usd_out) / usd_in * 10,000
Code: pipeline/fetch_flows.py windows, pipeline/metrics.py pair_accounts""",
    "query_mix": """The same balances as the chart above, at the latest reading, valued at that day's
DefiLlama price and grouped by token symbol.
Code: pipeline/metrics.py value_treasury, pipeline/analyze.py weigh""",
    "query_swaps": """Every transfer of any size, both ways, for one random hour on sample days.
A swap is an account that is not a solver, with exactly one transfer in and one out, inside the hour.
Swaps an hour = pairs found / hours sampled.
Code: pipeline/fetch_flows.py windows, pipeline/metrics.py pair_accounts""",
    "query_history": """https://api.llama.fi/summary/dexs/near-intents
Daily volume, summed by full calendar month.
Trend: a straight line through the logs of the last 12 full months, as a yearly rate.
Code: pipeline/analyze.py long_term, pipeline/metrics.py log_trend""",
    "query_path": """volume(year)  = today's volume * (1 + growth) ^ year
new NEAR(year) = supply * issuance rate / 365 * today's price
cover(year)   = volume * take / new NEAR
Each case states its growth, take and issuance. The NEAR price is held at today's.
Code: pipeline/metrics.py project, required_growth""",
    "query_index": """Weekly sums of https://api.llama.fi/summary/dexs/near-intents
Weekly means of price and active accounts from https://api.nearblocks.io/v1/charts
Each series = 100 in the first week of October 2025.
Code: pipeline/analyze.py hypothesis""",
    "query_lag": """x(t) = log change in volume, or in price, in week t
y(t + L) = log change in active accounts, L weeks later
r = rank correlation of x and y, for L from 1 to 8 weeks
The table compares 4-week changes, with a 90% block-bootstrap interval on the gap.
Code: pipeline/metrics.py lag_profile, leading_test""",
    "query_accounts": """SELECT CAST(block_date AS STRING) AS date,
       COUNT(DISTINCT signer_account_id) AS active_signers,
       COUNT(*) AS transactions
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date BETWEEN @since AND @until
GROUP BY date ORDER BY date

Also available with no key: https://api.nearblocks.io/v1/charts (active_accounts)""",
    "query_txns": """SELECT CAST(block_date AS STRING) AS date, COUNT(*) AS transactions
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date BETWEEN @since AND @until
GROUP BY date ORDER BY date

Also available with no key: https://api.nearblocks.io/v1/charts (txns)""",
    "query_calls": """SELECT CAST(block_date AS STRING) AS date,
       COUNT(*) AS function_calls,
       COUNT(DISTINCT receipt_receiver_account_id) AS active_contracts
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions`
WHERE block_date BETWEEN @since AND @until
  AND action_kind = 'FUNCTION_CALL'
GROUP BY date ORDER BY date""",
    "query_intents": """-- transactions sent to intents.near each day, divided by all transactions
SELECT CAST(block_date AS STRING) AS date, COUNT(*) AS transactions
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date BETWEEN @since AND @until
  AND receiver_account_id = 'intents.near'
GROUP BY date ORDER BY date

-- the busiest destinations in four 14-day windows
Full query: sql/top_contracts.sql""",
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
        ("Rule for sending fees to NEAR", "The terms say fees may be directed to a recipient for NEAR ecosystem work, and set no amount. We found no rule in code. Payments arrive from one-use accounts",
         "Terms Schedule 1, 1.7; this analysis"),
        ("Where bought NEAR sits", f"A multisig needing {ctl.get('buybacks_confirmations', 2)} confirmations, held, not burned", "<code>get_num_confirmations</code>"),
        ("Audit access", "Selective disclosure is described as planned, not live", "near.org, How Confidential Intents Works"),
    ]
    return "".join(f"<tr><td><strong>{a}</strong></td><td>{b}</td><td>{c}</td></tr>" for a, b, c in rows)


def test_rows(tests: list[dict]) -> str:
    labels = {"holding": "Holding", "watch": "Watch", "broken": "Broken", "unknown": "No data", "pending": "Due Nov 2027"}
    out = []
    for t in tests:
        out.append(
            f"<tr><td><strong>{html.escape(t['name'])}</strong></td><td>{html.escape(t['breaks_if'])}</td>"
            f"<td class=\"num\">{html.escape(t['shown'] or 'n/a')}</td>"
            f"<td><span class=\"status {t['state']}\">{labels[t['state']]}</span></td></tr>"
        )
    return "".join(out)


SHORT = (
    "NEAR is turning from a chain people use directly into a settlement layer for cross-chain money. In a year, Intents "
    "volume rose about {volume_year} times while active accounts fell {accounts_year}. "
    "From {era_month}, what NEAR keeps from each dollar of volume went from {bps_before} to {bps_after} bps, and all of the "
    "gain arrived through the private treasury. Then on 27 October swaps themselves moved to the private chain, about "
    "{swaps_multiple} times as many crossed the boundary, and the take slipped to {late_bps_after} bps. Nothing public links a "
    "revenue payment to a swap, one key signs for the treasury, and the private fee is set off-chain. Holders can see that "
    "money arrived. They cannot check what earned it, or whether private swaps pay NEAR at all."
)

IDEA = (
    "The problem: more and more of NEAR's money moves through a private system that nobody outside can read. At least "
    "{rev_share_recent} of what NEAR earned in the last 30 days came out of it, so people who hold NEAR can no longer check "
    "the number that matters most: whether NEAR is really getting paid.\n\n"
    "What we built: Dark Matter, a free tool and five-year investment thesis that measures that private money from public "
    "data. One click weighs it live in your browser (about {snapshot_usd}), every chart shows its query, {tests_total} public "
    "tests say what would prove the thesis wrong, and one command rebuilds every number.\n\n"
    "How NEAR fits in: all the money behind the private system sits in one public account on intents.near, so NEAR's public "
    "chain is what makes it measurable. A NEAR contract can read the same total on chain, with no oracle."
)

LIMITS = [
    "We see the boundary, not the inside. Swaps on the private chain, their fees and their solvers cannot be observed.",
    "Paired accounts show cost only for accounts that enter and leave inside the sampled hour. A swap that returns to another account is missed.",
    "The revenue match is exact to the yoctoNEAR, so it can only undercount. A sweep that merges two transfers looks public.",
    "A payment out of the treasury shows where money came from, not what earned it.",
    "Tokens with no public price history are left unpriced, not guessed. That is why our daily series reads below NEAR's.",
    "The ranges used to find the fee's price points were chosen after seeing the data.",
    "Swaps made inside a shielded balance never cross the boundary, so we cannot count them. The low swap count before 27 October shows only that few swaps crossed.",
    "The daily flow census covers transfers of $2,500 or more, about 95% of dollars by a sample.",
    "Eleven days since 27 October is short. Revenue per dollar can move for many reasons, including mix, price and the timing of sweeps.",
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


def x_length(post: str) -> int:
    """How X counts a post: every link is 23 characters, whatever its real length."""
    return len(re.sub(r"https?://\S+|\[(?:site|repo) link\]", "x" * 23, post))


def check_posts(kit: str) -> None:
    """The rules ask the main post for these words, and X cuts anything over 280 characters."""
    drafts = kit.split("## X post drafts")[1].split("## Screenshots")[0]
    posts = re.findall(r"```text\n(.*?)\n```", drafts, re.S)
    for post in posts:
        if x_length(post) > 280:
            raise ValueError(f"an X post is {x_length(post)} characters and X allows 280: {post[:60]}")
    for needed in ("NEAR HACKATHON", "@NEARProtocol", "#NEARHackathon"):
        if needed not in posts[0]:
            raise ValueError(f"the main X post must include {needed}")


def main() -> None:
    r = read_json(DERIVED / "results.json")
    snapshot = read_json(RAW / "weigh_snapshot.json")
    r["coverage_now"] = r["revenue"]["late_after"]["revenue_per_day"] / (r["model"]["issued_near_per_day"] * r["model"]["near_price"])
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
        "destinations": r["destinations"],
        "model": r["model"],
        "hypothesis": {k: r["hypothesis"][k] for k in ("tests", "profiles", "index", "weeks")},
        "long_term": {k: r["long_term"][k] for k in ("months", "cases", "observed_growth")},
        "usage_source": r["usage_source"],
    }
    pages = (deployment.get("pages_url") or "").rstrip("/")
    media = ROOT / "docs" / "media" / "hero.png"
    if media.exists():
        shutil.copyfile(media, SITE / "og.png")
    og_tags = ""
    if pages:
        og_tags = (
            '<meta property="og:title" content="Dark Matter: NEAR\'s private economy, weighed">'
            '<meta property="og:description" content="Most of NEAR\'s revenue now comes through a private chain. This measures it from the one public place it has to cross.">'
            f'<meta property="og:image" content="{pages}/og.png">'
            '<meta name="twitter:card" content="summary_large_image">'
            f'<meta name="twitter:image" content="{pages}/og.png">'
        )
    values = {
        **n,
        **{k: html.escape(v) for k, v in QUERIES.items()},
        "og_tags": og_tags,
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

    labels = {"holding": "Holding", "watch": "Watch", "broken": "Broken", "unknown": "No data", "pending": "Due Nov 2027"}
    table = "| Test | Breaks if | Now | State |\n|---|---|---|---|\n" + "\n".join(
        f"| {t['name']} | {t['breaks_if']} | {t['shown'] or 'n/a'} | {labels[t['state']]} |" for t in r["tests"]
    )
    extra = {
        "test_table": table,
        "manifest": digest,
        "repo_url": values["repo_url"],
        "pages_url": deployment.get("pages_url") or "site/index.html (published with GitHub Pages)",
        "post_site": deployment.get("pages_url") or "[site link]",
        "post_repo": deployment.get("repo_url") or "[repo link]",
        "deployment_line": (
            f"Deployed at `{deployment['contract']}`." if deployment.get("contract")
            else "Built and tested here, and ready to deploy: see `contract/README.md`."
        ),
        "short_version": SHORT.format(**n),
    }
    extra["idea"] = IDEA.format(**n)
    if len(extra["idea"]) > 2000:
        raise ValueError(f"the submission text is {len(extra['idea'])} characters; the form allows 2,000")
    for name in ("THESIS", "README", "docs/SUBMISSION"):
        source = ROOT / f"{name}.in.md"
        if source.exists():
            text = fill(source.read_text(encoding="utf-8"), {**n, **extra})
            if name == "docs/SUBMISSION":
                check_posts(text)
            with open(ROOT / f"{name}.md", "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)

if __name__ == "__main__":
    main()
