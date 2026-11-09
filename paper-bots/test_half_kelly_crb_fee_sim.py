"""Money-machine plan slice 1: half-Kelly CRB + fee-sim observe (paper only)."""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_profit
import desk_roi_plan


class HalfKellyCrbFeeSim(unittest.TestCase):
    def test_fee_sim_probe_clears_and_fails(self):
        ok = desk_roi_plan.fee_sim_probe(
            venue="kalshi_sports", fair=0.62, ask=0.52,
        )
        self.assertTrue(ok["clear"])
        self.assertGreaterEqual(ok["edge_after_fee"], 0.06 - 1e-9)
        self.assertEqual(ok["floor"], 0.06)
        self.assertTrue(ok["fee_floors_locked"])
        self.assertFalse(ok["live_orders_enabled"])

        thin = desk_roi_plan.fee_sim_probe(
            venue="kalshi_sports", fair=0.55, ask=0.52,
        )
        self.assertFalse(thin["clear"])
        self.assertLess(thin["edge_after_fee"], 0.06)

    def test_fee_sim_observe_board(self):
        out = desk_roi_plan.fee_sim_observe(".")
        self.assertTrue(out["observe_only"])
        self.assertTrue(out["paper_only"])
        self.assertFalse(out["auto_promote"])
        self.assertGreaterEqual(out["n"], 4)
        self.assertGreaterEqual(out["clears_n"], 1)

    def test_half_kelly_crb_is_counterfactual_only(self):
        cfg = {
            "max_open_risk": 100.0,
            "stake_lo_max": 20.0,
            "stake_hi_min": 20.0,
            "stake_hi_max": 100.0,
            "stake_hi_prob": 0.8,
            "sizing": "kelly_lite",
            "kelly_fraction": 0.25,
        }
        bots = [
            {"id": "sports-gap", "open_risk": 10.0, "shadow_only": False},
            {"id": "btc15m", "open_risk": 5.0, "shadow_only": False},
            {"id": "commodity-15m", "open_risk": 0.0, "shadow_only": False},
            {"id": "coinbase-spot", "open_risk": 25.0, "shadow_only": True},
        ]
        out = desk_roi_plan.half_kelly_crb_observe(".", bots=bots, cfg=cfg)
        self.assertTrue(out["observe_only"])
        self.assertEqual(out["live_kelly_fraction"], 0.25)
        self.assertEqual(out["observe_kelly_fraction"], 0.50)
        self.assertFalse(out["live_orders_enabled"])
        self.assertFalse(out["auto_promote"])
        self.assertAlmostEqual(out["desk_open_risk"], 15.0, places=2)
        # Shadow cash must not count toward CRB open risk.
        self.assertEqual(len(out["towers"]), 3)
        # Half-Kelly stake ≥ live stake for the same fee-clear probe.
        self.assertGreaterEqual(out["half_kelly_stake"], out["live_kelly_stake"])
        # Live cfg must stay at 0.25 — observe never mutates desk_profit defaults.
        self.assertEqual(
            float(cfg.get("kelly_fraction")),
            desk_roi_plan.LIVE_KELLY_FRACTION,
        )
        live = desk_profit.kelly_lite_dollars(
            0.62, 0.08, {**cfg, "kelly_fraction": 0.25},
            open_risk_used=15.0, ask=0.52,
        )
        self.assertEqual(out["live_kelly_stake"], live)

    def test_dutch_book_underround_and_overround(self):
        under = desk_roi_plan.dutch_book_probe(
            [{"side": "home", "ask": 0.44}, {"side": "away", "ask": 0.44}],
            venue="kalshi_sports",
        )
        self.assertTrue(under["clear"])
        self.assertGreaterEqual(under["edge"], 0.06 - 1e-9)
        over = desk_roi_plan.dutch_book_probe(
            [{"side": "home", "ask": 0.52}, {"side": "away", "ask": 0.52}],
            venue="kalshi_sports",
        )
        self.assertFalse(over["clear"])
        self.assertIn("overround", over["reason"].lower())
        board = desk_roi_plan.dutch_book_observe(".")
        self.assertTrue(board["observe_only"])
        self.assertGreaterEqual(board["clears_n"], 1)
        self.assertFalse(board["live_orders_enabled"])

    def test_poly_arb_fee_wall_and_fat_gap(self):
        thin = desk_roi_plan.cross_venue_arb_probe({
            "label": "thin",
            "kalshi_venue": "kalshi_sports",
            "poly_category": "sports",
            "kalshi_yes_ask": 0.48,
            "poly_no_ask": 0.50,
        })
        self.assertTrue(thin["ok"])
        self.assertFalse(thin["clear"])
        self.assertIn("fee wall", thin["reason"].lower())
        fat = desk_roi_plan.cross_venue_arb_probe({
            "label": "fat",
            "kalshi_venue": "kalshi_econ",
            "poly_category": "geopolitics",
            "kalshi_yes_ask": 0.40,
            "poly_no_ask": 0.48,
        })
        self.assertTrue(fat["clear"])
        self.assertGreaterEqual(fat["edge"], 0.05 - 1e-9)
        incomplete = desk_roi_plan.cross_venue_arb_probe({
            "kalshi_yes_ask": 0.45,
        })
        self.assertFalse(incomplete["ok"])
        self.assertIn("no invent", incomplete["reason"].lower())
        board = desk_roi_plan.cross_venue_arb_observe(".")
        self.assertTrue(board["idea_bank_only"])
        self.assertTrue(board["observe_only"])
        self.assertFalse(board["live_orders_enabled"])
        self.assertGreaterEqual(board["clears_n"], 1)


if __name__ == "__main__":
    unittest.main()
