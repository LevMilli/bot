"""Shared vol / learn / adapt layer + screenshot-style eval fixtures."""

import tempfile
import unittest

import desk_adapt


# Screenshot-inspired vol vectors (staff Kalshi 15m screens, Nov 2026).
SCREEN_FIXTURES = (
    {
        "name": "palladium_spike_late",
        "vol_kwargs": {
            "cushion": 0.05, "sigma": 0.40, "spread": 0.05,
            "minutes_left": 2.0, "ask": 0.45, "recent_range": 2.0, "spot": 988.9,
        },
        "expect_safe": True,
        "expect_big": False,
    },
    {
        "name": "natgas_vertical_below_target",
        "vol_kwargs": {
            "cushion": 0.00032, "sigma": 0.004, "spread": 0.05,
            "minutes_left": 2.0, "ask": 0.50, "recent_range": 0.02, "spot": 2.925,
        },
        "expect_safe": True,
        "expect_big": False,
    },
    {
        "name": "brent_rich_ask_false_conf",
        "vol_kwargs": {
            "cushion": 0.25, "sigma": 0.80, "spread": 0.01,
            "minutes_left": 4.0, "ask": 0.99,
        },
        "expect_safe": True,
        "expect_big": False,
        "expect_false_conf": True,
    },
    {
        "name": "wti_rich_ask_false_conf",
        "vol_kwargs": {
            "cushion": 0.20, "sigma": 0.70, "spread": 0.01,
            "minutes_left": 4.1, "ask": 0.981,
        },
        "expect_safe": True,
        "expect_big": False,
        "expect_false_conf": True,
    },
    {
        "name": "silver_crash_late_chaotic",
        "vol_kwargs": {
            "cushion": 0.02, "sigma": 0.08, "spread": 0.05,
            "minutes_left": 2.0, "ask": 0.50,
            "recent_range": 0.5, "spot": 50.34,
        },
        "expect_safe": True,
        "expect_big": False,
    },
    {
        "name": "calm_proven_play_big",
        "vol_kwargs": {
            "cushion": 120, "sigma": 40, "spread": 0.01,
            "minutes_left": 12, "ask": 0.82,
        },
        "expect_safe": False,
        "expect_big": True,
        "need_strong_history": True,
    },
)


def _strong_history():
    return [{"pnl": 5, "closed": "2026-11-01T12:00:00Z"}] * 25 + [
        {"pnl": -1, "closed": "2026-11-01T13:00:00Z"}
    ] * 3


class DeskAdaptTests(unittest.TestCase):
    def test_self_check(self):
        desk_adapt.self_check()

    def test_wilson_blocks_lucky_streak(self):
        lucky = [{"pnl": 4, "closed": "2026-11-01T12:00:00Z"}] * 10
        lucky += [{"pnl": -1, "closed": "2026-11-01T13:00:00Z"}] * 2
        perf = desk_adapt.performance_from_history(lucky)
        self.assertGreaterEqual(perf["hit_rate"], desk_adapt.HIT_FOR_BIG)
        self.assertFalse(perf["proven_80"])
        self.assertIsNotNone(perf["hit_ci_low"])
        self.assertLess(perf["hit_ci_low"], desk_adapt.HIT_CI_FLOOR)

    def test_wilson_allows_strong_record(self):
        perf = desk_adapt.performance_from_history(_strong_history())
        self.assertTrue(perf["proven_80"])
        self.assertGreaterEqual(perf["hit_ci_low"], desk_adapt.HIT_CI_FLOOR)

    def test_high_vol_shrinks(self):
        stake, plan = desk_adapt.adapt_stake(
            40.0,
            history=_strong_history(),
            vol_kwargs={"cushion": 5, "sigma": 90, "spread": 0.06, "minutes_left": 2, "ask": 0.5},
        )
        self.assertTrue(plan["play_safe"])
        self.assertLess(stake, 40.0)

    def test_proven_80_enlarges_when_calm(self):
        stake, plan = desk_adapt.adapt_stake(
            40.0,
            history=_strong_history(),
            vol_kwargs={"cushion": 100, "sigma": 40, "spread": 0.01, "minutes_left": 12, "ask": 0.86},
        )
        self.assertTrue(plan["play_big"])
        self.assertGreater(stake, 40.0)

    def test_false_confidence_blocks_play_big(self):
        stake, plan = desk_adapt.adapt_stake(
            40.0,
            history=_strong_history(),
            vol_kwargs={"cushion": 8, "sigma": 80, "spread": 0.01, "minutes_left": 12, "ask": 0.98},
        )
        self.assertTrue(plan["play_safe"])
        self.assertFalse(plan["play_big"])
        self.assertLess(stake, 40.0)
        self.assertTrue(desk_adapt.false_confidence(ask=0.98, cushion=8, sigma=80))

    def test_screenshot_eval_suite(self):
        """Idea #95 — lock adapt behavior against staff screenshot regimes."""
        for fix in SCREEN_FIXTURES:
            with self.subTest(fix["name"]):
                hist = _strong_history() if fix.get("need_strong_history") else []
                stake, plan = desk_adapt.adapt_stake(
                    40.0, history=hist, vol_kwargs=fix["vol_kwargs"],
                )
                if fix.get("expect_safe"):
                    self.assertTrue(plan["play_safe"], plan["notes"])
                if "expect_big" in fix and fix["expect_big"] is False:
                    self.assertFalse(plan["play_big"], plan["notes"])
                if fix.get("expect_big") is True:
                    self.assertTrue(plan["play_big"], plan["notes"])
                    self.assertGreater(stake, 40.0)
                if fix.get("expect_false_conf"):
                    self.assertTrue(
                        desk_adapt.false_confidence(**{
                            k: fix["vol_kwargs"].get(k)
                            for k in ("ask", "cushion", "sigma")
                        }),
                    )

    def test_remember_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            vol = desk_adapt.volatility_score(cushion=10, sigma=80, ask=0.5, minutes_left=3)
            _, plan = desk_adapt.adapt_stake(20, history=[], vol_kwargs={"ask": 0.5})
            desk_adapt.remember_vol(tmp, "btc15m", "T1", vol, plan)
            summary = desk_adapt.adapt_summary(tmp)
            self.assertIn("KXPALLADIUM15M", summary["series_15m"])
            self.assertEqual(summary["by_bot"]["btc15m"]["obs"], 1)
            self.assertEqual(summary["rules"]["big_needs_ci_low"], desk_adapt.HIT_CI_FLOOR)


if __name__ == "__main__":
    unittest.main()
