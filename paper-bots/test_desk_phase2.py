"""Phase 2 quality track — no network."""

import tempfile
import unittest

import desk_adapt
import desk_phase2


class DeskPhase2Tests(unittest.TestCase):
    def test_self_check(self):
        desk_phase2.self_check()

    def test_regime_filter_blocks_extreme_from_proven(self):
        # Extreme losses shouldn't poison / help proven sample the same way.
        hist = [{"pnl": 5, "vol_regime": "calm", "closed": "2026-11-01T12:00:00Z"}] * 20
        hist += [{"pnl": -5, "vol_regime": "extreme", "closed": "2026-11-01T13:00:00Z"}] * 10
        perf = desk_phase2.proven_80_regime_aware(hist)
        self.assertEqual(perf["n_filtered"], 20)
        self.assertTrue(perf["proven_80"])

    def test_adapt_uses_regime_aware(self):
        strong = [{"pnl": 5, "vol_regime": "calm", "closed": "2026-11-01T12:00:00Z"}] * 25
        strong += [{"pnl": -1, "vol_regime": "calm", "closed": "2026-11-01T13:00:00Z"}] * 3
        stake, plan = desk_adapt.adapt_stake(
            40.0,
            history=strong,
            vol_kwargs={"cushion": 100, "sigma": 40, "spread": 0.01, "minutes_left": 12, "ask": 0.85},
        )
        self.assertTrue(plan["play_big"])
        self.assertGreater(stake, 40.0)

    def test_ab_ledger_and_gap_decay(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_phase2.record_adapt_ab(
                tmp, bot="sports-gap", ticker="T", stake_flat=40, stake_adapt=70,
                mult=1.75, play_big=True, fill_id="abc",
            )
            desk_phase2.attach_ab_pnl(tmp, "abc", 7.0)
            s = desk_phase2.adapt_ab_summary(tmp)
            self.assertEqual(s["n_settled"], 1)
            self.assertTrue(s["adapt_wins"] or s["adapt_edge_vs_flat"] is not None)
            summary = desk_phase2.phase2_summary(tmp)
            self.assertIn("adapt_ab", summary)


if __name__ == "__main__":
    unittest.main()
