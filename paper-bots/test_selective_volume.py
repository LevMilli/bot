"""ROI path: starve losers, lock venue floors, selective fee-clear volume."""

import unittest

import desk_more
import desk_profit


class SelectiveVolumeTests(unittest.TestCase):
    def test_venue_floors_cannot_soften(self):
        ok, err = desk_profit.parse_venue_min_edge({"kalshi_btc15m": 0.01})
        self.assertIsNone(ok)
        self.assertIn("locked floor", err)
        parsed, err2 = desk_profit.parse_venue_min_edge({"kalshi_sports": 0.08})
        self.assertIsNone(err2)
        self.assertEqual(parsed["kalshi_sports"], 0.08)
        # Runtime clamps below-floor config up to the lock.
        live = desk_profit.venue_min_edge(
            "kalshi_btc15m", {"venue_min_edge": {"kalshi_btc15m": 0.01}}
        )
        self.assertGreaterEqual(live, desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"])
        snap = desk_profit.venue_floors_locked({})
        self.assertTrue(snap["all_ok"])
        self.assertTrue(snap["locked"])

    def test_starve_defaults_tighter(self):
        exp = {"n": 4, "expectancy": -1.5}
        starve = desk_profit.starve_state(exp, {})
        self.assertTrue(starve["starved"])
        self.assertAlmostEqual(starve["starve_factor"], 0.15)
        not_yet = desk_profit.starve_state({"n": 3, "expectancy": -2.0}, {})
        self.assertFalse(not_yet["starved"])

    def test_loser_budgets_feed_fee_clear(self):
        shares = desk_more.effective_tower_shares(
            {"tower_risk_budgets": dict(desk_more.DEFAULT_TOWER_BUDGET_SHARE)},
            meme_today=-10.58,
            today_by_bot={"sports-gap": -16.25},
            cash_by_bot={"kalshi-sp": 444.37, "kalshi-sized": 500.0},
        )
        self.assertAlmostEqual(shares["memecoin"], desk_more.MEME_RED_SHARE)
        self.assertAlmostEqual(
            shares["kalshi-sp"], desk_more.DEFAULT_TOWER_BUDGET_SHARE["kalshi-sp"]
        )
        self.assertAlmostEqual(
            shares["kalshi-sized"], desk_more.DEFAULT_TOWER_BUDGET_SHARE["kalshi-sized"]
        )
        self.assertAlmostEqual(shares["sports-gap"], desk_more.SPORTS_RED_SHARE)
        self.assertGreater(shares["btc15m"], desk_more.DEFAULT_TOWER_BUDGET_SHARE["btc15m"])
        self.assertGreater(
            shares["commodity-15m"], desk_more.DEFAULT_TOWER_BUDGET_SHARE["commodity-15m"]
        )

    def test_selective_max_buys_green_only(self):
        self.assertEqual(desk_more.selective_max_buys("btc15m", base=3, today=0.0), 4)
        self.assertEqual(desk_more.selective_max_buys("commodity-15m", base=3, today=2.0), 4)
        self.assertEqual(desk_more.selective_max_buys("btc15m", base=3, today=-0.5), 3)
        self.assertEqual(
            desk_more.selective_max_buys("sports-gap", base=4, today=5.0, green_boost=0), 4
        )
        self.assertEqual(desk_more.selective_max_buys("memecoin", base=2, today=10.0), 2)


if __name__ == "__main__":
    unittest.main()
