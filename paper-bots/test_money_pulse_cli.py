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
                "inx_band", "hard_stop", "commodity_time_stop", "sports_time_final",
                "green_boost", "near_miss", "near_miss_soft_p", "edge08",
                "helper_gate_a",
            ):
                self.assertIn(need, gates)
            self.assertIn("thin=", out["label"])

    def test_firm_health_observe(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots = [
                {"id": "sports-gap", "today": 2.0, "open_risk": 10.0, "gate_a": {"ready": True}},
                {"id": "memecoin", "today": -1.0, "open_risk": 5.0, "gate_a": {"ready": False}},
            ]
            desk_roi_plan.capture_bleed_week(tmp, bots=bots)
            out = desk_roi_plan.firm_health_observe(tmp, bots=bots, cfg={"max_open_risk": 100})
            self.assertTrue(out["observe_only"])
            self.assertTrue(out["fee_floors_locked"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertIn("bleed", out)
            self.assertIn("capital_os", out)
            self.assertIn("profit_lock", out)
            self.assertIn("opp_cost", out)
            self.assertIn("fee_ledger", out)
            self.assertIn("firm_health=", out["label"])

    def test_ops_observe(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.ops_observe(tmp, bots=[])
            self.assertTrue(out["observe_only"])
            self.assertTrue(out["fee_floors_locked"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertTrue(out["dual_control"]["deferred"])
            self.assertIn("incubation", out)
            self.assertIn("ruin_drill", out)
            self.assertIn("cold_harvest", out)
            self.assertIn("graduation", out)
            self.assertIn("btc_calibration", out)
            self.assertIn("ops=", out["label"])

    def test_guardrails_observe(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_adverse_fill(
                tmp, bot="btc15m", ticker="KX", entry_price=0.60, mark_price=0.50,
            )
            desk_roi_plan.record_anti_revenge(
                tmp, bot="sports-gap", ticker="GAME1", reason="stop",
            )
            out = desk_roi_plan.guardrails_observe(tmp, bots=[{"id": "btc15m"}])
            self.assertTrue(out["observe_only"])
            self.assertTrue(out["fee_floors_locked"])
            self.assertIn("adverse_cool", out["alerts"])
            self.assertIn("anti_revenge", out["alerts"])
            self.assertEqual(out["adverse_cool"]["active_n"], 1)
            self.assertEqual(out["anti_revenge"]["active_n"], 1)
            self.assertIn("guardrails=", out["label"])

    def test_review_observe(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.review_observe(tmp, bots=[])
            self.assertTrue(out["observe_only"])
            self.assertTrue(out["fee_floors_locked"])
            self.assertIn("idea_review", out)
            self.assertIn("quarterly_rebaseline", out)
            self.assertIn("correlation", out)
            self.assertTrue(out["correlation"].get("btc_inx_veto"))
            self.assertIn("quarterly_missing", out["alerts"])
            self.assertIn("review=", out["label"])

    def test_calib_clv_observe(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots = [
                {
                    "id": "memecoin",
                    "today": -4.0,
                    "open_risk": 12.0,
                    "gate_a": {"ready": False},
                },
            ]
            out = desk_roi_plan.calib_clv_observe(tmp, bots=bots)
            self.assertTrue(out["observe_only"])
            self.assertTrue(out["fee_floors_locked"])
            self.assertFalse(out["auto_write_phi"])
            self.assertIn("btc_calibration", out)
            self.assertIn("sports_calibration", out)
            self.assertIn("commodity_calibration", out)
            self.assertIn("clv", out)
            self.assertIn("sticky_sla", out)
            self.assertIn("green_or_gone", out)
            self.assertIn("selective_throughput", out)
            self.assertIn("green_or_gone", out["alerts"])
            self.assertIn("calib_clv=", out["label"])

    def test_baseline_fee_observe(self):
        with tempfile.TemporaryDirectory() as tmp:
            thin = desk_roi_plan.baseline_fee_observe(tmp, bots=[])
            self.assertTrue(thin["observe_only"])
            self.assertIn("baseline_missing", thin["alerts"])
            self.assertFalse(thin["baseline"]["has_baseline"])
            captured = desk_roi_plan.baseline_fee_observe(
                tmp,
                bots=[{"id": "btc15m", "today": 0, "cash": 100, "open_risk": 0}],
                cfg={"max_open_risk": 100},
                capture=True,
                label="W0",
            )
            self.assertTrue(captured["baseline"]["has_baseline"])
            self.assertEqual(captured["baseline"]["latest_label"], "W0")
            self.assertNotIn("baseline_missing", captured["alerts"])
            self.assertIn("fee_ledger", captured)
            self.assertIn("baseline_fee=", captured["label"])

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertAlmostEqual(floors["venues"]["kalshi_sports"]["floor"], 0.06)
        self.assertAlmostEqual(floors["venues"]["kalshi_btc15m"]["floor"], 0.05)
        self.assertAlmostEqual(floors["venues"]["kalshi_inx"]["floor"], 0.02)


if __name__ == "__main__":
    unittest.main()
