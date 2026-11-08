"""Every formula is checked on small inputs worked out by hand, so a bug cannot hide in real data."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "pipeline"))

import falsifiers  # noqa: E402
import metrics as M  # noqa: E402
from build_site import fill  # noqa: E402
from fetch_control import base58_to_hex  # noqa: E402

ASSETS = {
    "a": {"symbol": "AAA", "decimals": "6", "coingecko_id": "aaa"},
    "b": {"symbol": "BBB", "decimals": "18", "coingecko_id": ""},
    "c": {"symbol": "CCC", "decimals": "2", "coingecko_id": "ccc"},
}


class ValueTreasury(unittest.TestCase):
    def test_sums_priced_tokens(self):
        prices = {"aaa": {"2026-01-01": 2.0}, "ccc": {"2026-01-01": 10.0}}
        out = M.value_treasury({"a": "3000000", "c": "500"}, ASSETS, prices, "2026-01-01")
        self.assertAlmostEqual(out["usd"], 3 * 2 + 5 * 10)
        self.assertEqual(out["by_symbol"], {"AAA": 6.0, "CCC": 50.0})
        self.assertEqual(out["unpriced_tokens"], 0)

    def test_unpriced_tokens_are_counted_not_guessed(self):
        out = M.value_treasury({"a": "1000000", "b": "1", "unknown": "1"}, ASSETS, {"aaa": {}}, "2026-01-01")
        self.assertEqual(out["usd"], 0.0)
        self.assertEqual(out["unpriced_tokens"], 3)
        self.assertEqual(out["tokens"], 3)

    def test_address_price_is_the_fallback(self):
        prices = {"asset:b": {"2026-01-01": 4.0}}
        out = M.value_treasury({"b": str(2 * 10 ** 18)}, ASSETS, prices, "2026-01-01")
        self.assertAlmostEqual(out["usd"], 8.0)


class Tracking(unittest.TestCase):
    def test_error_is_absolute_and_relative_to_the_reported_figure(self):
        out = M.tracking_error([(90.0, 100.0), (110.0, 100.0), (100.0, 100.0)])
        self.assertAlmostEqual(out["median_abs_pct"], 10.0)
        self.assertEqual(out["days"], 3)

    def test_empty(self):
        self.assertEqual(M.tracking_error([]), {"days": 0})

    def test_correlation_of_a_line_is_one(self):
        self.assertAlmostEqual(M.correlation([1, 2, 3], [2, 4, 6]), 1.0)


def pay(ts, amount, usd=100.0):
    return {"ts_ms": ts, "yocto": amount, "usd": usd, "wallet": "w", "tx": "t"}


def out(ts, amount, other="sweeper"):
    return {"ts_ms": str(ts), "amount": "-" + amount, "other": other}


class MatchPayments(unittest.TestCase):
    HOUR = 3_600_000

    def test_exact_amount_shortly_before_is_private(self):
        res = M.match_payments([pay(10 * self.HOUR, "123")], [out(9 * self.HOUR, "123")])
        self.assertTrue(res[0]["private"])
        self.assertEqual(res[0]["via"], "sweeper")

    def test_a_different_amount_is_not_private(self):
        res = M.match_payments([pay(10 * self.HOUR, "123")], [out(9 * self.HOUR, "124")])
        self.assertFalse(res[0]["private"])

    def test_an_outflow_after_the_payment_cannot_explain_it(self):
        res = M.match_payments([pay(10 * self.HOUR, "123")], [out(11 * self.HOUR, "123")])
        self.assertFalse(res[0]["private"])

    def test_an_outflow_too_long_before_cannot_explain_it(self):
        res = M.match_payments([pay(10 * self.HOUR, "123")], [out(3 * self.HOUR, "123")])
        self.assertFalse(res[0]["private"])

    def test_one_outflow_explains_one_payment_only(self):
        res = M.match_payments(
            [pay(10 * self.HOUR, "123"), pay(10 * self.HOUR + 1, "123")],
            [out(9 * self.HOUR, "123")],
        )
        self.assertEqual([r["private"] for r in res], [True, False])

    def test_two_equal_outflows_explain_two_payments(self):
        res = M.match_payments(
            [pay(10 * self.HOUR, "123"), pay(10 * self.HOUR + 1, "123")],
            [out(9 * self.HOUR, "123"), out(9 * self.HOUR + 5, "123")],
        )
        self.assertEqual([r["private"] for r in res], [True, True])


def leg(account, ts, usd, asset="x"):
    return {"other": account, "ts_ms": str(ts), "usd": str(usd), "asset": asset}


class PairAccounts(unittest.TestCase):
    SYMBOLS = {"x": "USDC", "y": "BTC"}

    def test_cost_is_the_share_lost_between_entry_and_exit(self):
        rows = [leg("abc", 1000, 1000.0, "x"), leg("abc", 2000, -990.0, "y")]
        pair = M.pair_accounts(rows, self.SYMBOLS)[0]
        self.assertAlmostEqual(pair["bps"], 100.0)
        self.assertEqual((pair["from"], pair["to"]), ("USDC", "BTC"))
        self.assertAlmostEqual(pair["seconds"], 1.0)

    def test_solvers_are_skipped(self):
        rows = [leg("solver-priv-liq.near", 1000, 1000.0), leg("solver-priv-liq.near", 2000, -990.0)]
        self.assertEqual(M.pair_accounts(rows, self.SYMBOLS), [])

    def test_only_one_in_and_one_out_counts(self):
        rows = [leg("abc", 1000, 500.0), leg("abc", 1100, 500.0), leg("abc", 2000, -990.0)]
        self.assertEqual(M.pair_accounts(rows, self.SYMBOLS), [])

    def test_an_exit_before_the_entry_is_not_a_swap(self):
        rows = [leg("abc", 2000, 1000.0), leg("abc", 1000, -990.0)]
        self.assertEqual(M.pair_accounts(rows, self.SYMBOLS), [])

    def test_legs_too_far_apart_are_not_paired(self):
        rows = [leg("abc", 0, 1000.0), leg("abc", 4_000_000, -990.0)]
        self.assertEqual(M.pair_accounts(rows, self.SYMBOLS), [])


class Classify(unittest.TestCase):
    def test_accounts(self):
        self.assertEqual(M.account_class("solver-multichain-asset.near"), "solver")
        self.assertEqual(M.account_class("a" * 64), "implicit")
        self.assertEqual(M.account_class("0x" + "b" * 40), "evm")
        self.assertEqual(M.account_class("alice.near"), "named")

    def test_assets(self):
        self.assertEqual(M.asset_class("USDC"), "stable")
        self.assertEqual(M.asset_class("ZEC"), "privacy")
        self.assertEqual(M.asset_class("BTC"), "major")
        self.assertEqual(M.asset_class("PEPE"), "other")


class Costs(unittest.TestCase):
    def test_summary_weights_by_dollars(self):
        pairs = [{"bps": 10.0, "usd_in": 100.0}, {"bps": 100.0, "usd_in": 900.0}]
        out_ = M.summarize_costs(pairs)
        self.assertAlmostEqual(out_["weighted_bps"], 91.0)
        self.assertAlmostEqual(out_["median_bps"], 55.0)
        self.assertAlmostEqual(out_["weighted_median_bps"], 100.0)

    def test_empty(self):
        self.assertEqual(M.summarize_costs([]), {"n": 0})


class Weekly(unittest.TestCase):
    def test_only_whole_weeks_count(self):
        days = {f"2026-03-{d:02d}": float(d) for d in range(2, 12)}  # Monday 2 March to Wednesday 11 March
        out = M.weekly(days)
        self.assertEqual(list(out), ["2026-03-02"])
        self.assertAlmostEqual(out["2026-03-02"], 5.0)
        self.assertAlmostEqual(M.weekly(days, "sum")["2026-03-02"], 35.0)


class RankCorrelation(unittest.TestCase):
    def test_ties_share_a_rank(self):
        self.assertEqual(M.ranks([10, 20, 20, 30]), [1.0, 2.5, 2.5, 4.0])

    def test_one_huge_outlier_does_not_decide_it(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        ys = [1.0, 2.0, 3.0, 4.0, 5.0, 1e9]
        self.assertAlmostEqual(M.spearman(xs, ys), 1.0)
        self.assertLess(M.correlation(xs, ys), 0.7)


class LeadLag(unittest.TestCase):
    def test_a_series_that_copies_with_a_delay_peaks_at_that_delay(self):
        rng = __import__("random").Random(3)
        leader = [100.0]
        for _ in range(80):
            leader.append(leader[-1] * (1 + rng.uniform(-0.1, 0.1)))
        follower = [50.0, 50.0, 50.0] + [v / 2 for v in leader[:-3]]
        profile = M.lag_profile(leader, follower, 6)
        best = max(profile, key=lambda p: p["r"])
        self.assertEqual(best["lag"], 3)
        self.assertGreater(best["r"], 0.95)

    def test_a_true_leader_beats_noise(self):
        rng = __import__("random").Random(5)
        volume = [100.0]
        for _ in range(120):
            volume.append(volume[-1] * (1 + rng.uniform(-0.08, 0.08)))
        usage = [40.0] * 4 + [v * 0.4 for v in volume[:-4]]
        price = [10.0]
        for _ in range(120):
            price.append(price[-1] * (1 + rng.uniform(-0.08, 0.08)))
        res = M.leading_test(volume, price, usage, reps=200)
        self.assertGreater(res["volume_r"], 0.8)
        self.assertGreater(res["difference"], 0.4)
        self.assertGreater(res["difference_low"], 0)


class LongTerm(unittest.TestCase):
    def test_trend_recovers_steady_growth(self):
        self.assertAlmostEqual(M.log_trend([100 * 1.03 ** i for i in range(12)]), 0.03)

    def test_project_year_zero_is_today(self):
        row = M.project(1e8, 0.5, 5.0, 1000.0, 2.0, 0.025, 0.016)[0]
        self.assertAlmostEqual(row["volume_per_day"], 1e8)
        self.assertAlmostEqual(row["revenue_per_year"], 5e4 * 365)
        self.assertAlmostEqual(row["new_near_usd_per_day"], 1000 * 0.025 / 365 * 2)

    def test_project_ramps_issuance_then_holds(self):
        rows = M.project(1e8, 0.0, 5.0, 1000.0, 2.0, 0.025, 0.016, ramp_years=2)
        self.assertAlmostEqual(rows[1]["issuance_rate"], 0.0205)
        self.assertAlmostEqual(rows[2]["issuance_rate"], 0.016)
        self.assertAlmostEqual(rows[5]["issuance_rate"], 0.016)
        self.assertEqual(len(rows), 6)

    def test_required_growth_lands_on_full_cover(self):
        g = M.required_growth(1e8, 5.0, 1e9, 3.0, 0.016)
        rows = M.project(1e8, g, 5.0, 1e9, 3.0, 0.016, 0.016)
        self.assertAlmostEqual(rows[5]["coverage"], 1.0)


class ChangePoint(unittest.TestCase):
    def test_finds_a_clean_step(self):
        self.assertEqual(M.change_point([2.0] * 8 + [5.0] * 8), 8)

    def test_noise_does_not_move_it_far(self):
        values = [2.1, 1.9, 2.2, 2.0, 1.8, 2.3, 5.1, 4.8, 5.2, 4.9, 5.0, 5.3]
        self.assertEqual(M.change_point(values), 6)

    def test_too_short_has_no_answer(self):
        self.assertIsNone(M.change_point([1.0, 2.0, 3.0]))


class Fingerprint(unittest.TestCase):
    def test_finds_the_middle_of_each_bunch(self):
        pairs = [{"bps": b} for b in (70, 75, 80, 140, 145, 150, 5)]
        out = M.fee_fingerprint(pairs)
        self.assertEqual(out["low_bps"], 75)
        self.assertEqual(out["high_bps"], 145)
        self.assertAlmostEqual(out["low_share"], 3 / 7)

    def test_values_outside_the_range_land_in_the_end_bins(self):
        out = M.fee_fingerprint([{"bps": -500}, {"bps": 900}])
        self.assertEqual(out["bins"][0]["n"], 1)
        self.assertEqual(out["bins"][-1]["n"], 1)

    def test_no_swaps(self):
        self.assertIsNone(M.fee_fingerprint([])["low_bps"])


class BreakEven(unittest.TestCase):
    def test_volume_pays_for_new_near(self):
        res = M.break_even(1000.0, 2.0, 1.0, 4.0)
        self.assertAlmostEqual(res["usd_per_day_needed"], 2000.0)
        self.assertAlmostEqual(res["blended_bps"], 5.0)
        self.assertAlmostEqual(res["volume_per_day"], 4_000_000.0)

    def test_halving_the_private_part_needs_two_thirds_more_volume(self):
        res = M.break_even(1000.0, 2.0, 1.0, 4.0, kept=0.5)
        self.assertAlmostEqual(res["blended_bps"], 3.0)
        self.assertAlmostEqual(res["volume_per_day"], 2000.0 / 3e-4)

    def test_no_revenue_never_breaks_even(self):
        self.assertEqual(M.break_even(1000.0, 2.0, 0.0, 4.0, kept=0.0)["volume_per_day"], float("inf"))

class Regression(unittest.TestCase):
    def test_ols_recovers_known_slopes(self):
        xs = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [2.0, 1.0]]
        ys = [3.0, 5.0, 8.0, 11.0]
        a, b = M.ols(xs, ys)
        self.assertAlmostEqual(a, 3.0)
        self.assertAlmostEqual(b, 5.0)

    def test_bootstrap_brackets_the_estimate(self):
        xs = [[float(i % 7 + 1), float(i % 5 + 1)] for i in range(60)]
        ys = [3 * x[0] + 5 * x[1] + (i % 3 - 1) * 0.2 for i, x in enumerate(xs)]
        fit = M.block_bootstrap_ols(xs, ys, reps=200)
        for term, truth in zip(fit["terms"], (3.0, 5.0)):
            self.assertLessEqual(term["low"], term["estimate"])
            self.assertLessEqual(term["estimate"], term["high"])
            self.assertAlmostEqual(term["estimate"], truth, delta=0.1)

    def test_bootstrap_repeats_exactly(self):
        xs = [[float(i + 1)] for i in range(30)]
        ys = [2.0 * x[0] + (i % 2) for i, x in enumerate(xs)]
        self.assertEqual(M.block_bootstrap_ols(xs, ys, reps=50), M.block_bootstrap_ols(xs, ys, reps=50))


def results(gap=2.0, share=0.7, before=2.5, after=4.5, peak=200.0, now=150.0, keys=1, late=5.0, trend=0.46):
    return {
        "long_term": {"needed_growth_floor": 0.3, "observed_growth": trend},
        "coverage_now": 0.2,
        "weigh": {"recent_gap_pct": gap, "latest": {"weighed": now}, "series": [{"weighed": peak}, {"weighed": now}]},
        "provenance": {"last_30_days_share": share},
        "revenue": {"before": {"bps": before}, "after": {"bps": after},
                    "late_before": {"bps": 5.0}, "late_after": {"bps": late}},
        "control": {"verifier_keys_now": ["k"] * keys},
    }


MANUAL = {
    "custody_published": {"found": False, "checked": "d"},
    "private_totals_published": {"found": False, "checked": "d"},
}


def states(r, manual=MANUAL):
    return {t["id"]: t["state"] for t in falsifiers.evaluate(r, manual)}


class Falsifiers(unittest.TestCase):
    def test_all_hold(self):
        found = states(results())
        self.assertEqual(found.pop("T9"), "pending")
        self.assertTrue(all(v == "holding" for v in found.values()))

    def test_t8_volume_trend(self):
        self.assertEqual(states(results(trend=0.33))["T8"], "watch")
        self.assertEqual(states(results(trend=0.2))["T8"], "broken")

    def test_t1_weighing_breaks_when_the_gap_grows(self):
        self.assertEqual(states(results(gap=12))["T1"], "watch")
        self.assertEqual(states(results(gap=20))["T1"], "broken")

    def test_t2_share(self):
        self.assertEqual(states(results(share=0.3))["T2"], "watch")
        self.assertEqual(states(results(share=0.2))["T2"], "broken")

    def test_t3_revenue_per_dollar(self):
        self.assertEqual(states(results(after=3.0))["T3"], "watch")
        self.assertEqual(states(results(after=2.0))["T3"], "broken")

    def test_t7_private_swaps_keep_paying(self):
        self.assertEqual(states(results(late=4.6))["T7"], "holding")
        self.assertEqual(states(results(late=4.0))["T7"], "watch")
        self.assertEqual(states(results(late=2.9))["T7"], "broken")

    def test_t4_size(self):
        self.assertEqual(states(results(now=100.0))["T4"], "watch")
        self.assertEqual(states(results(now=50.0))["T4"], "broken")

    def test_t5_second_key(self):
        self.assertEqual(states(results(keys=2))["T5"], "broken")

    def test_t6_published_totals(self):
        manual = {**MANUAL, "private_totals_published": {"found": True, "checked": "d"}}
        self.assertEqual(states(results(), manual)["T6"], "broken")

    def test_missing_data_is_not_a_pass(self):
        self.assertEqual(states(results(share=None))["T2"], "unknown")


class Templates(unittest.TestCase):
    def test_fill(self):
        self.assertEqual(fill("a {{x_1}} b", {"x_1": 5}), "a 5 b")

    def test_a_missing_number_stops_the_build(self):
        with self.assertRaises(KeyError):
            fill("{{nope}}", {})


class Keys(unittest.TestCase):
    def test_the_treasury_key_is_its_own_implicit_account(self):
        self.assertEqual(
            base58_to_hex("6Wk4sb8Gc449VB4LoofP3AM8hMSMgbAwwUEc4RhBodV7"),
            "51e8f94d77b5e90dc9852ca6113771e11e8382ce69473a75e313e41665de7cbe",
        )


if __name__ == "__main__":
    unittest.main()
