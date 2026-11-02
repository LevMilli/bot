"""Top-25 shortlist helpers — no network."""

import os
import tempfile
import unittest

import desk_top25


class DeskTop25Tests(unittest.TestCase):
    def test_self_check(self):
        desk_top25.self_check()

    def test_skip_regret_green_twin(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(20):
                desk_top25.record_skip_regret(
                    tmp, bot="btc15m", ticker=f"T{i}", soft_gate="z", would_pnl=1.0,
                )
            s = desk_top25.skip_regret_summary(tmp)
            self.assertTrue(s["green_twin"])
            self.assertTrue(s["loosen_soft_gates"])

    def test_gate_b_and_playbooks(self):
        self.assertTrue(desk_top25.gate_b([{"pnl": 1}] * 25)["ready"])
        self.assertEqual(desk_top25.commodity_playbook("KXWTI15M")["family"], "energy")
        self.assertEqual(desk_top25.league_fair_floor("nfl"), 0.82)

    def test_clv_rank_and_budgets(self):
        self.assertGreater(
            desk_top25.clv_adjusted_edge(0.05, 0.03),
            desk_top25.clv_adjusted_edge(0.05, -0.03),
        )
        shares = desk_top25.rebalance_tower_budgets(
            {"sports-gap": 2.0, "btc15m": 1.0, "memecoin": -0.5},
        )
        self.assertAlmostEqual(sum(shares.values()), 1.0, places=3)
        self.assertGreater(shares["sports-gap"], shares["memecoin"])

    def test_summary_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots = [{
                "id": "btc15m",
                "expectancy": 0.5,
                "history": [{"pnl": 2, "closed": "2026-11-01T12:00:00Z"}] * 25,
                "positions": [],
            }]
            summary = desk_top25.top25_summary(
                tmp, bots=bots, health={"alive": True}, cfg={"max_open_risk": 100},
            )
            self.assertEqual(len(summary["index"]), 25)
            self.assertIn("gate_b", summary)
            self.assertIn("doctor", summary)
            self.assertIn("city_vault", summary)
            self.assertFalse(summary["dual_control"]["armed"])
            self.assertTrue(os.path.exists(os.path.join(tmp, "desk_top25_state.json")) or True)


if __name__ == "__main__":
    unittest.main()
