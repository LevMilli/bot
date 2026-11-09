"""INX stop-bleed: refuse late Φ entry when σ would collapse into fake edge."""

from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import desk_inx

CT = ZoneInfo("America/Chicago")


class InxSigmaCollapseStopBleed(unittest.TestCase):
    def test_sigma_minutes_floor_is_at_least_60(self):
        self.assertGreaterEqual(float(desk_inx.INX_SIGMA_MIN_MINUTES), 60.0)
        # 10m clock must not shrink σ below the 60m floor (old bug used 15).
        sig_10 = desk_inx.inx_sigma(7500.0, 10.0)
        sig_60 = desk_inx.inx_sigma(7500.0, 60.0)
        self.assertAlmostEqual(sig_10, sig_60, places=6)

    def test_late_scan_refuses_entry_floor(self):
        """14:45 CT: minutes_left=15 — must refuse, not arm p≈1 on mild ITM."""
        late = datetime(2026, 11, 10, 14, 45, tzinfo=CT)
        fair = desk_inx.fair_evaluate(
            {"ticker": "KX", "side": "yes", "ask": 0.85, "strike": 7450},
            venue_edge=0.02,
            spot=7500.0,
            now=late,
        )
        self.assertFalse(fair["ok"])
        reason = (fair.get("reason") or "").lower()
        self.assertIn("entry floor", reason)
        self.assertTrue("collapse" in reason or "floor" in reason)

    def test_midday_deep_itm_still_clears(self):
        """13:00 CT still allows fee-clear deep ITM (stop bleed ≠ full pause)."""
        noonish = datetime(2026, 11, 10, 13, 0, tzinfo=CT)
        fair = desk_inx.fair_evaluate(
            {"ticker": "KX", "side": "yes", "ask": 0.85, "strike": 7300},
            venue_edge=0.02,
            spot=7500.0,
            now=noonish,
        )
        self.assertTrue(fair["ok"])
        self.assertGreaterEqual(float(fair["edge"]), 0.02)
        self.assertGreaterEqual(float(fair["minutes_left"]), 60.0)

    def test_mild_itm_midday_still_refuses_without_late_invent(self):
        """Same mild ITM that late used to arm must stay refused at 12:30."""
        early = datetime(2026, 11, 10, 12, 30, tzinfo=CT)
        fair = desk_inx.fair_evaluate(
            {"ticker": "KX", "side": "yes", "ask": 0.85, "strike": 7450},
            venue_edge=0.02,
            spot=7500.0,
            now=early,
        )
        self.assertFalse(fair["ok"])

    def test_rank_by_fair_late_board_empty(self):
        late = datetime(2026, 11, 10, 14, 30, tzinfo=CT)
        board = [
            {"ticker": "A", "side": "yes", "ask": 0.85, "strike": 7450},
            {"ticker": "B", "side": "yes", "ask": 0.82, "strike": 7400},
        ]
        ranked = desk_inx.rank_by_fair(
            board, venue_edge=0.02, spot=7500.0, now=late,
        )
        self.assertFalse(ranked["ok"])
        self.assertEqual(int(ranked["n_ok"]), 0)
        self.assertIn("entry floor", (ranked.get("reason") or "").lower())

    def test_asymmetric_payoff_still_documented(self):
        """Amplifier behind sticky −$55: ~+$4 win / −$25 loss — not softened here."""
        import importlib.util
        import os

        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "kalshi-sp500-paper",
            "paper_sim.py",
        )
        spec = importlib.util.spec_from_file_location("inx_paper_sim_asym", path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        fee = mod.taker_fee(29, 0.85)
        win = mod.trade_pnl("yes", True, 29, 0.85, fee)
        loss = mod.trade_pnl("yes", False, 29, 0.85, fee)
        self.assertAlmostEqual(win, 4.09, places=2)
        self.assertAlmostEqual(loss, -24.91, places=2)

    def test_residual_still_not_edge(self):
        self.assertIn("not edge", desk_inx.refuse_residual_as_edge().lower())
        # Residual still clears venue math in-band — callers must not use it as edge.
        self.assertGreaterEqual(float(desk_inx.residual_edge(0.85) or 0), 0.02)

    def test_self_check(self):
        desk_inx.self_check()


if __name__ == "__main__":
    unittest.main()
