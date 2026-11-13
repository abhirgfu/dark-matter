"""The spoken numbers must say what the computed numbers say."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "pipeline"))

import demo_script as D  # noqa: E402
from build_site import check_posts, x_length  # noqa: E402
from common import DERIVED, read_json  # noqa: E402


class SpokenNumbers(unittest.TestCase):
    def test_words(self):
        self.assertEqual(D.words(7), "seven")
        self.assertEqual(D.words(46), "forty-six")
        self.assertEqual(D.words(140), "a hundred and forty")
        self.assertEqual(D.words(200), "two hundred")

    def test_figures(self):
        self.assertEqual(D.bare("76%"), "seventy-six")
        self.assertEqual(D.bare("+30%"), "thirty")
        self.assertEqual(D.bare("−14%"), "fourteen")
        self.assertEqual(D.millions("$140.3M"), "a hundred and forty million dollars")

    def test_cash(self):
        self.assertEqual(D.cash("2.83"), "two dollars eighty-three")
        self.assertEqual(D.cash("5.06"), "five dollars and six cents")
        self.assertEqual(D.cash("1.00"), "one dollar")

    def test_part_of_month(self):
        self.assertEqual(D.part_of_month("2026-09-21"), "late")
        self.assertEqual(D.part_of_month("2026-09-05"), "early")


class Script(unittest.TestCase):
    def setUp(self):
        self.n = read_json(DERIVED / "numbers.json")
        self.tests = read_json(DERIVED / "tests.json")

    def test_every_line_has_a_known_mood(self):
        # The nightly refresh can change the results. When the script no longer fits them it needs rewriting,
        # which is a job for a person, so this skips rather than failing the refresh.
        try:
            script = D.takes(self.n, self.tests)
        except SystemExit as reason:
            self.skipTest(str(reason))
        for take in script:
            for entry in take["lines"]:
                self.assertIn(entry["mood"], D.MOODS)

    def test_a_new_result_stops_the_script(self):
        changed = dict(self.n, h_verdict="Supported")
        with self.assertRaises(SystemExit):
            D.takes(changed, self.tests)


class Posts(unittest.TestCase):
    def test_a_link_counts_as_23(self):
        self.assertEqual(x_length("a https://github.com/some/very/long/path b"), 27)
        self.assertEqual(x_length("[site link]"), 23)

    def test_the_rules_are_enforced(self):
        kit = "## X post\n```text\n{}\n```\n## Screenshots"
        good = "Built at NEAR HACKATHON @NEARProtocol #NEARHackathon"
        check_posts(kit.format(good))
        with self.assertRaises(ValueError):
            check_posts(kit.format("no tags here"))
        with self.assertRaises(ValueError):
            check_posts(kit.format(good + " " + "x" * 300))


if __name__ == "__main__":
    unittest.main()
