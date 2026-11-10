"""Gate A pilot + eligible-fill + throughput vs M1 + opp-cost smoke."""
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


class E3E4Boards(unittest.TestCase):
    def test_gate_a_pilot(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(5):
                desk_roi_plan.record_helper_fill(
                    tmp, helper="calendar_scanner", bot="btc15m",
                    pnl=0.2, contracts=1, fill_id=f"f{i}",
                )
            board = desk_roi_plan.gate_a_pilot_btc_calendar(tmp)
            self.assertEqual(board["n"], 5)
            self.assertEqual(board["n_to_ready"], 15)
            self.assertFalse(board["staff_arm"])
            self.assertIsNotNone(board["taxed_ev"])

    def test_gate_a_pilot_sports_clv(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(6):
                desk_roi_plan.record_helper_fill(
                    tmp, helper="clv_closer", bot="sports-gap",
                    pnl=0.15, contracts=1, fill_id=f"s{i}",
                )
            board = desk_roi_plan.gate_a_pilot_sports_clv(tmp)
            self.assertEqual(board["n"], 6)
            self.assertEqual(board["helper"], "clv_closer")
            self.assertFalse(board["staff_arm"])
            pilots = desk_roi_plan.gate_a_pilots_board(tmp)
            self.assertIn("sports_clv", pilots)
            self.assertEqual(pilots["sports_clv"]["n"], 6)

    def test_helper_advice_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = desk_roi_plan.record_helper_advice_decision(
                tmp, helper="calendar_scanner", decision="accept",
                advice={"ttl": 30},  # missing floors_locked
            )
            self.assertFalse(bad.get("ok"))
            ok = desk_roi_plan.record_helper_advice_decision(
                tmp, helper="calendar_scanner", bot="btc15m",
                decision="accept", reason="pilot",
                advice={"floors_locked": True, "ttl": 30},
            )
            self.assertTrue(ok.get("ok"))
            rej = desk_roi_plan.record_helper_advice_decision(
                tmp, helper="clv_closer", bot="sports-gap",
                decision="reject", reason="edge thin",
            )
            self.assertTrue(rej.get("ok"))
            board = desk_roi_plan.helper_advice_log_board(tmp)
            self.assertEqual(board["n"], 2)
            self.assertEqual(board["accept_n"], 1)
            self.assertEqual(board["reject_n"], 1)

    def test_eligible_and_throughput(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_fit(tmp, bot="btc15m", outcome="buy", ticker="T1")
            desk_roi_plan.record_fit(tmp, bot="memecoin", outcome="buy", ticker="M1")
            funnel = desk_roi_plan.eligible_fill_funnel(tmp, bots=[])
            self.assertEqual(funnel["eligible_buys"], 1)
            self.assertEqual(funnel["all_buys"], 2)
            board = desk_roi_plan.throughput_vs_m1_board(tmp, bots=[])
            self.assertEqual(board["primary"], "M1")
            self.assertEqual(board["secondary"], "eligible_fills")

    def test_opp_cost_api_smoke(self):
        self.assertTrue(callable(desk_roi_plan.note_pending_high_edge))
        self.assertTrue(callable(desk_roi_plan.flush_opp_cost_on_buy))
        # Import paths used by BTC/commodity wiring.
        import importlib.util
        for mod, path in (
            ("btc15m_signal", os.path.join(HERE, "btc15m-signal", "btc15m_signal.py")),
            ("commodity_bot", os.path.join(HERE, "commodity-15m-paper", "bot.py")),
        ):
            spec = importlib.util.spec_from_file_location(mod, path)
            self.assertIsNotNone(spec)

    def test_masters_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = (desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            ).get("roi_plan") or {})
            for key in (
                "selective_kill", "tip_funnel", "gate_a_pilot",
                "gate_a_pilot_sports_clv", "gate_a_pilots", "helper_advice_log",
                "eligible_fill_funnel", "throughput_vs_m1",
            ):
                self.assertIn(key, plan)


if __name__ == "__main__":
    unittest.main()
