"""Phase 4 — KXETH15M calibration slice separate from KXBTC15M."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_roi_plan


def _bots():
    return [{
        "id": "btc15m",
        "history": [
            {"series": "KXBTC15M", "prob": 0.85, "pnl": 1.0},
            {"series": "KXBTC15M", "prob": 0.82, "pnl": -1.0},
            {"series": "KXETH15M", "prob": 0.88, "pnl": -1.0},
            {"series": "KXETH15M", "ticker": "KXETH15M-1", "prob": 0.81, "pnl": -1.0},
            {"series": "KXETH15M", "prob": 0.90, "pnl": 1.0},
        ],
    }]


class EthCalib(unittest.TestCase):
    def test_eth_slice_excludes_btc(self):
        eth = desk_roi_plan.eth_calibration_report(_bots())
        btc = desk_roi_plan.btc_calibration_report(_bots())
        self.assertEqual(eth["series"], "KXETH15M")
        self.assertEqual(btc["series"], "KXBTC15M")
        self.assertEqual(eth["n"], 3)
        self.assertEqual(btc["n"], 2)
        self.assertFalse(eth.get("auto_write_phi"))

    def test_capture_and_master(self):
        with tempfile.TemporaryDirectory() as tmp:
            card = desk_roi_plan.capture_eth_calibration(tmp, bots=_bots(), label="2026-11-07")
            self.assertEqual(card["n"], 3)
            latest = desk_roi_plan.latest_eth_calibration(tmp)
            self.assertEqual(latest["label"], "2026-11-07")
            summary = desk_master.master_summary(
                tmp,
                bots=_bots() + [{"id": "sports-gap", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("eth_calibration", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_calib_clv_observe_includes_eth(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.calib_clv_observe(tmp, bots=_bots())
            self.assertIn("eth_calibration", out)
            self.assertEqual(out["eth_calibration"]["n"], 3)

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertAlmostEqual(floors["venues"]["kalshi_btc15m"]["floor"], 0.05)


if __name__ == "__main__":
    unittest.main()
