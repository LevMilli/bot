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
