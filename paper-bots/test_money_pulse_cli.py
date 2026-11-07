"""Money-path pulse CLI surfaces — firm queue / completions / feature densify."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_living
import desk_roi_plan


class MoneyPulseSurfaces(unittest.TestCase):
    def test_firm_queue_status_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = desk_roi_plan.firm_queue_status(tmp)
            self.assertTrue(st.get("fee_floors_locked") or st.get("paper_only"))
            self.assertTrue(st.get("observe_only"))
            self.assertFalse(st.get("live_orders_enabled"))
            self.assertIn("towers", st)
            self.assertIn("deferred_sample", st)
            chip = desk_living.firm_queue_chip(tmp)
            self.assertTrue(chip.get("observe_only"))

    def test_completions_summary_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_living.record_completion(
                tmp, bot="btc15m", ticker="T1", pnl=0.4, eligible=True
            )
            desk_living.record_completion(
                tmp, bot="memecoin", ticker="M1", pnl=-1.0, eligible=True
            )
            st = desk_living.completions_summary(tmp)
            self.assertTrue(st["fee_floors_locked"])
            self.assertTrue(st.get("observe_only"))
            self.assertEqual(st["eligible_completions_today"], 1)  # meme not fee-clear
            self.assertIn("btc15m", st["eligible_by_bot"])
            self.assertNotIn("memecoin", st["eligible_by_bot"])

    def test_feature_store_densify(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_living.record_eval_features(
                tmp,
                bot="sports-gap",
                action="skip",
                ev={
                    "ask": 0.55,
                    "bid": 0.52,
                    "fee": 0.02,
                    "p": 0.58,
                    "z": 1.1,
                    "edge": 0.03,
                    "depth": 4,
                    "league": "NFL",
                    "lane": "accurate",
                    "minutes_left": 40,
                },
                reasons=["EDGE"],
            )
            row = out["row"]
            self.assertEqual(row.get("schema"), "feature_v1_dense")
            for key in desk_living.FEATURE_DENSE_KEYS:
                self.assertIn(key, row)
            self.assertAlmostEqual(row["spread"], 0.03)
            score = desk_living.feature_row_densify_score(row)
            self.assertTrue(score["pass"])
            cov = desk_living.feature_store_coverage(tmp)
            self.assertEqual(cov["n"], 1)
            self.assertTrue(cov.get("densify_pass"))
            self.assertEqual(cov.get("dense_schema_n"), 1)
            quiet = desk_living.feature_store_quiet_alert(tmp)
            self.assertIsInstance(quiet, dict)

    def test_promote_distance_observe(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.promote_distance_observe(tmp, bots=[])
            self.assertTrue(out["observe_only"])
            self.assertTrue(out["fee_floors_locked"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertFalse(out["auto_promote"])
            self.assertTrue(out["evidence_thin"])
            self.assertGreaterEqual(out["thin_n"], 1)
            gates = {r["gate"] for r in out["gates"]}
            for need in (
                "inx_band", "hard_stop", "green_boost", "near_miss",
                "near_miss_soft_p", "edge08", "helper_gate_a",
            ):
                self.assertIn(need, gates)
            self.assertIn("thin=", out["label"])

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertAlmostEqual(floors["venues"]["kalshi_sports"]["floor"], 0.06)
        self.assertAlmostEqual(floors["venues"]["kalshi_btc15m"]["floor"], 0.05)
        self.assertAlmostEqual(floors["venues"]["kalshi_inx"]["floor"], 0.02)


if __name__ == "__main__":
    unittest.main()
