"""APEX plan slice E1/E6: ETH early singles, EIA blackout, teller_memory."""

import importlib.util
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

import teller_memory
from helpers import eia_blackout

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load_btc_signal():
    path = os.path.join(ROOT, "btc15m-signal", "btc15m_signal.py")
    spec = importlib.util.spec_from_file_location("btc15m_signal_e1e6", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class PlanSliceE1E6Tests(unittest.TestCase):
    def test_eth_early_same_gates_not_parlay_only(self):
        btc = _load_btc_signal()
        self.assertTrue(btc.eth_early_should_buy("confident_early", []))
        self.assertTrue(btc.eth_early_should_buy("confident_early", None))
        self.assertFalse(btc.eth_early_should_buy("confident_early", ["edge low"]))
        self.assertFalse(btc.eth_early_should_buy("parlay_window", []))
        self.assertFalse(btc.eth_early_should_buy("volatile_hold", []))
        self.assertFalse(btc.eth_early_should_buy("confident_early", [], delay_eth=True))

    def test_late_single_keeps_fee_floor_and_one_contract_bar(self):
        btc = _load_btc_signal()
        self.assertEqual(btc.EDGE_BUFFER, 0.05)
        self.assertEqual(btc.MIN_MODEL_ACCURATE, 0.80)
        self.assertEqual((btc.ASK_MIN, btc.ASK_MAX), (0.70, 0.92))
        self.assertEqual(btc.MIN_CUSHION_USD, 35)
        self.assertEqual(btc.MIN_CUSHION_ETH, 1.5)
        self.assertEqual(btc.PARLAY_MIN_MIN, 1.0)
        self.assertEqual(btc.PARLAY_MAX_MIN, 5.0)

        def row(**overrides):
            base = {
                "reasons": [],
                "min_left": 3.0,
                "p": 0.86,
                "lane": "accurate",
                "cushion": 40.0,
                "ask": 0.78,
                "edge": 0.06,
                "spread": 0.02,
                "depth": 5,
                "calendar_loaded": True,
                "news": None,
            }
            base.update(overrides)
            return base

        self.assertTrue(btc.late_single_ready(row(), min_cushion=35, edge_floor=0.05))
        self.assertTrue(btc.late_single_ready(row(cushion=1.5), min_cushion=1.5, edge_floor=0.05))
        self.assertFalse(btc.late_single_ready(row(min_left=0.4), min_cushion=35, edge_floor=0.05))
        self.assertFalse(btc.late_single_ready(row(min_left=8), min_cushion=35, edge_floor=0.05))
        self.assertFalse(btc.late_single_ready(row(p=0.79), min_cushion=35, edge_floor=0.05))
        self.assertFalse(btc.late_single_ready(row(lane="speed", p=0.80), min_cushion=35, edge_floor=0.05))
        self.assertFalse(btc.late_single_ready(row(cushion=34), min_cushion=35, edge_floor=0.05))
        self.assertFalse(btc.late_single_ready(row(ask=0.93), min_cushion=35, edge_floor=0.05))
        self.assertFalse(btc.late_single_ready(row(edge=0.04), min_cushion=35, edge_floor=0.05))
        # A caller cannot lower the locked 0.05 floor.
        self.assertFalse(btc.late_single_ready(row(edge=0.03), min_cushion=35, edge_floor=0.01))
        self.assertFalse(btc.late_single_ready(row(reasons=["news"]), min_cushion=35, edge_floor=0.05))
        self.assertFalse(btc.late_single_ready(row(calendar_loaded=False), min_cushion=35, edge_floor=0.05))
        with open(os.path.join(ROOT, "btc15m-signal", "btc15m_signal.py"), encoding="utf-8") as handle:
            src = handle.read()
        self.assertEqual(src.count("late_single_ready("), 3)
        self.assertIn("late_singles < 1", src)
        self.assertNotIn("LIVE_ORDERS = True", src)

    def test_eia_inventory_blackout_energy_only(self):
        eia_blackout.self_check()
        now = datetime(2026, 11, 5, 15, 30, tzinfo=timezone.utc)
        events = [
            {
                "country": "USD",
                "impact": "High",
                "title": "Natural Gas Storage",
                "date": "2026-11-05T15:30:00+00:00",
            }
        ]
        blocked = eia_blackout.energy_blackout("KXNATGAS15M", events, now=now)
        self.assertTrue(blocked["blocked"])
        self.assertIn("EIA/inventory", blocked["reason"])
        metal = eia_blackout.energy_blackout("KXGOLD15M", events, now=now)
        self.assertFalse(metal["blocked"])
        clear = eia_blackout.energy_blackout(
            "KXWTI15M",
            events,
            now=datetime(2026, 11, 5, 22, 0, tzinfo=timezone.utc),
        )
        self.assertFalse(clear["blocked"])

    def test_teller_memory_shared_facts(self):
        teller_memory.self_check()
        with tempfile.TemporaryDirectory() as tmp:
            teller_memory.remember(
                tmp, "facts", "Fee floors stay; helpers never place alone.", bot_id="desk"
            )
            summary = teller_memory.memory_summary(tmp)
            self.assertGreaterEqual(summary["n_facts"], 1)
            self.assertTrue(summary["paper_only"])
            line = teller_memory.dialogue_line(tmp, "desk")
            self.assertIn("Fee floors", line)

    def test_commodity_failsafes_mention_eia(self):
        import pimp_desk

        plans = pimp_desk.BOT_PLANS["commodity-15m"]
        text = " ".join(plans.get("failsafes") or []).lower()
        self.assertIn("eia", text)
        buy = " ".join(plans.get("buy") or []).lower()
        self.assertIn("eia", buy)

    def test_btc_plans_mention_eth_early_singles(self):
        import pimp_desk

        buy = " ".join(pimp_desk.BOT_PLANS["btc15m"].get("buy") or []).lower()
        self.assertIn("eth", buy)
        self.assertIn("same", buy)


if __name__ == "__main__":
    unittest.main()
