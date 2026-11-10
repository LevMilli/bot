"""Phase 4 calib/CLV gate — journal, INX lock, BTC publish, learn v2."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_more
import desk_roi_plan


class Phase4CalibGate(unittest.TestCase):
    def test_gate_passes_on_empty_desk(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.phase4_calib_gate(tmp, bots=[])
            self.assertTrue(out["pass"], msg=out.get("label"))
            self.assertTrue(out["paper_only"])
            self.assertTrue(out["observe_only"])
            self.assertFalse(out["auto_promote"])
            self.assertFalse(out["auto_write_phi"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertFalse(out["board_chip"])
            self.assertEqual(out["phase"], "P4")
            self.assertEqual(out["decision"], "phase4_calib_gate_pass")
            self.assertTrue(out["clv_journal"]["pass"])
            self.assertEqual(out["clv_journal"]["bar"], 0.52)
            self.assertTrue(out["inx_band_lock"]["pass"])
            self.assertEqual(out["inx_band_lock"]["live_band"], "80_90")
            self.assertTrue(out["btc_calibration"]["pass"])
            self.assertTrue(out["learning_skip_v2"])
            self.assertTrue(out["adverse_cool"])
            self.assertTrue(out["depth_need"]["pass"])

    def test_clv_bar_fails_when_settled_below_52(self):
        self.assertEqual(desk_roi_plan.SPORTS_CLV_BAR, 0.52)
        self.assertEqual(desk_roi_plan.SPORTS_CLV_MIN_N, 20)
        self.assertEqual(desk_roi_plan.INX_LIVE_BAND_DEFAULT, "80_90")
        with tempfile.TemporaryDirectory() as tmp:
            # 20 line CLVs with only 5 beats → 25% < 52% bar.
            for i in range(20):
                beat = i < 5
                desk_more.record_sports_clv(
                    tmp,
                    ticker=f"T{i}",
                    side="YES",
                    fair_entry=0.60 if beat else 0.55,
                    close_fair=0.50 if beat else 0.62,
                    league="NFL",
                    exit_reason="gap closed",
                    clv_kind="line",
                )
            out = desk_roi_plan.phase4_calib_gate(tmp, bots=[])
            self.assertFalse(out["pass"], msg=out.get("label"))
            self.assertFalse(out["clv_journal"]["bar_ok"])
            self.assertEqual(out["decision"], "phase4_calib_gate_fail")
            self.assertGreaterEqual(out["clv_journal"]["beat_close_n"], 20)
            self.assertLess(out["clv_journal"]["beat_close_rate"], 0.52)

    def test_leagues_board_lists_six(self):
        board = desk_more.clv_by_league(None)
        ids = {r["league"] for r in board["leagues"]}
        self.assertTrue({"NFL", "NCAAF", "NBA", "WNBA", "MLB", "NHL"}.issubset(ids))
        self.assertEqual(board["beat_bar"], 0.52)

    def test_calib_reports_never_auto_write_phi(self):
        for report in (
            desk_roi_plan.btc_calibration_report([]),
            desk_roi_plan.eth_calibration_report([]),
            desk_roi_plan.sports_calibration_report([]),
            desk_roi_plan.commodity_calibration_report([]),
        ):
            self.assertIs(report.get("auto_write_phi"), False)

    def test_depth_need_locked_at_10(self):
        self.assertEqual(float(desk_more.DEFAULT_DEPTH_NEED), 10.0)

    def test_inx_lock_constant(self):
        lock = desk_roi_plan.PHASE4_INX_BAND_LOCK
        self.assertEqual(lock["live_band"], "80_90")
        self.assertIn("80_90", lock["research_bands"])
        self.assertGreaterEqual(int(lock["promote_min_n"]), 20)

    def test_masters_and_plan_summary_wire(self):
        bots = [
            {"id": "sports-gap", "today": 1, "open_risk": 5, "history": [], "gate_a": {}},
            {"id": "btc15m", "today": 1, "open_risk": 5, "history": [], "gate_a": {}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=bots,
                cfg={
                    "max_open_risk": 100,
                    "tower_risk_budgets": {"sports-gap": 0.35, "btc15m": 0.3},
                },
            )
            p4 = (summary.get("roi_plan") or {}).get("phase4_calib")
            self.assertIsInstance(p4, dict)
            self.assertTrue(p4.get("pass"), msg=p4.get("label") if p4 else "missing")
            calib = (summary.get("roi_plan") or {}).get("calib_clv")
            self.assertIsInstance(calib, dict)
            self.assertIs(calib.get("auto_write_phi"), False)
            plan = desk_roi_plan.plan_summary(tmp, bots=bots)
            self.assertIn("phase4_calib", plan)
            self.assertTrue(plan["phase4_calib"]["pass"])


if __name__ == "__main__":
    unittest.main()
