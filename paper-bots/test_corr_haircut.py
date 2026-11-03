"""Firm correlation matrix + WTI↔Brent series haircut."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_profit


class SeriesHaircut(unittest.TestCase):
    def test_wti_brent_haircut_on_sibling(self):
        hair = desk_profit.series_corr_haircut(
            "KXWTI15M",
            open_series=[],
            closed_today_series=["KXBRENT15M"],
        )
        self.assertTrue(hair["apply"])
        self.assertEqual(hair["mult"], 0.5)
        self.assertIn("KXBRENT15M", hair["hit"])

    def test_no_haircut_without_sibling(self):
        hair = desk_profit.series_corr_haircut(
            "KXWTI15M",
            open_series=["KXGOLD15M"],
            closed_today_series=[],
        )
        self.assertFalse(hair["apply"])
        self.assertEqual(hair["mult"], 1.0)


class CorrelationMatrix(unittest.TestCase):
    def test_btc_inx_heat_flagged(self):
        bots = [
            {
                "id": "btc15m",
                "positions": [{"side": "yes", "edge": 0.08, "risk": 20, "ticker": "BTC"}],
            },
            {
                "id": "kalshi-sp",
                "positions": [{"side": "yes", "edge": 0.05, "risk": 25, "ticker": "INX"}],
            },
        ]
        matrix = desk_profit.correlation_matrix(bots)
        self.assertTrue(matrix["btc_inx_veto"])
        self.assertTrue(matrix["meme_isolated"])
        heat = [p for p in matrix["veto_pairs"] if p.get("heat")]
        self.assertTrue(heat)
        self.assertEqual(matrix["series_haircuts"][0]["pair"], ["KXWTI15M", "KXBRENT15M"])

    def test_veto_still_blocks_btc_vs_inx(self):
        open_rows = desk_profit.open_risk_factor_rows([
            {
                "id": "kalshi-sp",
                "positions": [{"side": "yes", "edge": 0.06, "risk": 25}],
            }
        ])
        msg = desk_profit.correlation_veto_reason(
            "btc15m", "yes", 0.05, open_rows,
        )
        self.assertIn("correlation veto", msg)

    def test_master_exposes_correlation(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("correlation", plan)
            self.assertTrue((plan.get("correlation") or {}).get("btc_inx_veto"))


if __name__ == "__main__":
    unittest.main()
