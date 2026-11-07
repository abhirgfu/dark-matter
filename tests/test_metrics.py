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


class BreakEven(unittest.TestCase):
    def test_all_public(self):
        res = M.break_even(1000.0, 2.0, 5.0, 0.0, 0.5)
        self.assertAlmostEqual(res["usd_per_day_needed"], 2000.0)
        self.assertAlmostEqual(res["blended_bps"], 5.0)
        self.assertAlmostEqual(res["volume_per_day"], 4_000_000.0)

    def test_half_private_at_half_value_needs_a_third_more(self):
        res = M.break_even(1000.0, 2.0, 5.0, 0.5, 0.5)
        self.assertAlmostEqual(res["blended_bps"], 3.75)
        self.assertAlmostEqual(res["volume_per_day"], 4_000_000.0 / 0.75)

    def test_private_paying_nothing_with_everything_private_never_breaks_even(self):
        res = M.break_even(1000.0, 2.0, 5.0, 1.0, 0.0)
        self.assertEqual(res["volume_per_day"], float("inf"))


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


def results(gap=2.0, share=0.7, before=5.0, after=4.5, peak=200.0, now=150.0, keys=1):
    return {
        "weigh": {"recent_gap_pct": gap, "latest": {"weighed": now}, "series": [{"weighed": peak}, {"weighed": now}]},
        "provenance": {"last_30_days_share": share},
        "revenue": {"before": {"bps": before}, "after": {"bps": after}},
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
        self.assertTrue(all(v == "holding" for v in states(results()).values()))

    def test_t1_weighing_breaks_when_the_gap_grows(self):
        self.assertEqual(states(results(gap=12))["T1"], "watch")
        self.assertEqual(states(results(gap=20))["T1"], "broken")

    def test_t2_share(self):
        self.assertEqual(states(results(share=0.3))["T2"], "watch")
        self.assertEqual(states(results(share=0.2))["T2"], "broken")

    def test_t3_revenue_per_dollar(self):
        self.assertEqual(states(results(after=3.0))["T3"], "watch")
        self.assertEqual(states(results(after=2.0))["T3"], "broken")

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
