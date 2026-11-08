"""INX independent Φ fair re-entry — residual refuse until fee-clear fair."""

from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import desk_inx

CT = ZoneInfo("America/Chicago")


class InxFairReentryTests(unittest.TestCase):
    def test_deep_itm_yes_clears_venue(self):
        now = datetime(2026, 11, 10, 13, 0, tzinfo=CT)
        fair = desk_inx.fair_evaluate(
            {"ticker": "KX", "side": "yes", "ask": 0.85, "strike": 7200},
            venue_edge=0.02,
            spot=7500.0,
            now=now,
        )
        self.assertTrue(fair["ok"])
        self.assertGreaterEqual(float(fair["edge"]), 0.02)
        self.assertGreaterEqual(float(fair["p"]), 0.80)
        self.assertTrue(fair["fee_floors_locked"])

    def test_missing_spot_refuses_residual(self):
        now = datetime(2026, 11, 10, 13, 0, tzinfo=CT)
        fair = desk_inx.fair_evaluate(
            {"ticker": "KX", "side": "yes", "ask": 0.85, "strike": 7200},
            venue_edge=0.02,
            spot=-1.0,
            now=now,
        )
        self.assertFalse(fair["ok"])
        self.assertIn("residual", fair["reason"].lower())

    def test_thin_fair_skips(self):
        now = datetime(2026, 11, 10, 13, 0, tzinfo=CT)
        fair = desk_inx.fair_evaluate(
            {"ticker": "KX", "side": "yes", "ask": 0.90, "strike": 7495},
            venue_edge=0.02,
            spot=7500.0,
            now=now,
        )
        self.assertFalse(fair["ok"])
        self.assertTrue(
            "fair" in fair["reason"].lower() or "edge" in fair["reason"].lower()
            or "z" in fair["reason"].lower()
        )

    def test_no_side_symmetric(self):
        now = datetime(2026, 11, 10, 13, 0, tzinfo=CT)
        # Spot well below strike → NO is deep ITM.
        fair = desk_inx.fair_evaluate(
            {"ticker": "KX", "side": "no", "ask": 0.85, "strike": 7800},
            venue_edge=0.02,
            spot=7500.0,
            now=now,
        )
        self.assertTrue(fair["ok"])
        self.assertGreaterEqual(float(fair["p"]), 0.80)

    def test_pick_by_fair_prefers_value_over_rich_ask(self):
        now = datetime(2026, 11, 10, 13, 0, tzinfo=CT)
        # Highest ask RICH fails fair; VALUE clears — must pick VALUE.
        board = [
            {"ticker": "RICH", "side": "yes", "ask": 0.90, "strike": 7480},
            {"ticker": "VALUE", "side": "yes", "ask": 0.82, "strike": 7200},
        ]
        chosen = desk_inx.pick_by_fair(
            board, venue_edge=0.02, spot=7500.0, now=now,
        )
        self.assertTrue(chosen["ok"])
        self.assertEqual(chosen["pick"]["ticker"], "VALUE")
        self.assertGreaterEqual(int(chosen["n_ok"]), 1)
        self.assertGreaterEqual(float(chosen["fair"]["edge"]), 0.02)

    def test_rank_by_fair_orders_siblings_for_ob_retry(self):
        now = datetime(2026, 11, 10, 13, 0, tzinfo=CT)
        # Two fee-clear YES sides: deeper ITM should rank first; both stay available
        # so OB miss on top does not day-skip the sibling.
        board = [
            {"ticker": "MID", "side": "yes", "ask": 0.84, "strike": 7300},
            {"ticker": "DEEP", "side": "yes", "ask": 0.82, "strike": 7200},
            {"ticker": "RICH", "side": "yes", "ask": 0.90, "strike": 7480},
        ]
        ranked = desk_inx.rank_by_fair(
            board, venue_edge=0.02, spot=7500.0, now=now,
        )
        self.assertTrue(ranked["ok"])
        tickers = [row["pick"]["ticker"] for row in ranked["picks"]]
        self.assertIn("DEEP", tickers)
        self.assertIn("MID", tickers)
        self.assertNotIn("RICH", tickers)
        self.assertEqual(tickers[0], "DEEP")
        self.assertGreaterEqual(int(ranked["n_ok"]), 2)

    def test_learn_corr_continues_to_fee_clear_sibling(self):
        # Cold YES bucket must not day-skip a fee-clear NO sibling.
        ranked = [
            {"pick": {"ticker": "YES-COLD", "side": "yes", "ask": 0.85}, "edge": 0.10},
            {"pick": {"ticker": "NO-OK", "side": "no", "ask": 0.82}, "edge": 0.08},
        ]

        def policy(pick, edge):
            if pick.get("side") == "yes":
                return "learning: S&P yes cold bucket"
            return ""

        chosen = desk_inx.first_policy_ok_pick(ranked, policy_reason=policy)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["pick"]["ticker"], "NO-OK")

    def test_inx_learn_corr_reason_wires_desk(self):
        class _Desk:
            def load_learning(self, root):
                return []

            def prob_bucket(self, ask):
                return "0.8-0.9"

            def learning_skip(self, rows, market, bucket, side=None, hour_ct=None):
                if str(side).lower() == "yes":
                    return "learning: cold yes"
                return ""

            def correlation_blocks(self, root, bot_id, side, edge):
                return ""

        desk = _Desk()
        yes = desk_inx.inx_learn_corr_reason(
            desk, None, market="S&P", bot_id="kalshi-sp",
            pick={"side": "yes", "ask": 0.85}, edge=0.05, hour_ct=13,
        )
        no = desk_inx.inx_learn_corr_reason(
            desk, None, market="S&P", bot_id="kalshi-sp",
            pick={"side": "no", "ask": 0.82}, edge=0.05, hour_ct=13,
        )
        self.assertIn("cold yes", yes)
        self.assertEqual(no, "")

    def test_self_check(self):
        desk_inx.self_check()


if __name__ == "__main__":
    unittest.main()
