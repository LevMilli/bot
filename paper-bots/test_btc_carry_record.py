"""BTC carry record uses the printed premium. The reserved exit fee stays reserved."""
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest

import desk_brain
import desk_profit

HERE = os.path.dirname(os.path.abspath(__file__))


def _bot():
    path = os.path.join(HERE, "btc-carry-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("btc_carry_record", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _book():
    return {
        "cash": 499.25,
        "open": [{
            "ticker": "BTCUSDT",
            "notional": 500.0,
            "leverage": 1,
            "premium": 0.0005,
            "failsafe_premium": 0.0005,
            "exit_fee_reserved": 0.75,
            "failsafe": "hold, not a sell",
        }],
        "closed": [{
            "ticker": "BTCUSDT",
            "exit": "month-mark",
            "month": "2026-02",
            "pnl": -0.1,
            "cost": 500.0,
            "note": "mark only; the hold stays open",
        }],
    }


class BtcCarryRecord(unittest.TestCase):
    def test_the_month_mark_uses_the_printed_premium_and_does_not_spend_the_fee(self):
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp:
            state = _book()
            saved = bot.record_month(state, claimed=97000.0, root=tmp)
            self.assertTrue(saved["recorded"])
            self.assertFalse(saved["sold"])
            self.assertFalse(saved["fee_spent"])
            self.assertEqual(saved["open"], 1)
            self.assertEqual(len(state["open"]), 1)
            self.assertEqual(state["open"][0]["exit_fee_reserved"], 0.75)
            self.assertEqual(state["cash"], 499.25)
            self.assertEqual(state["closed"][0]["premium"], 0.0005)
            self.assertNotIn("hit", state["closed"][0])
            journal = desk_brain.load_journal(tmp)
            rows = [
                row for row in journal["decisions"]
                if row.get("bot") == "btc-carry" and row.get("action") == "month-mark"
            ]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["premium"], 0.0005)
            self.assertNotEqual(row["premium"], 97000.0)
            self.assertEqual(row["fill_id"], "BTCUSDT|2026-02")
            self.assertEqual(row["exit_name"], "month-mark")
            self.assertEqual(row["exit_fee"], "reserved")
            self.assertFalse(row["fee_spent"])
            self.assertNotIn("fee", row)
            self.assertNotIn("hit", row)
            self.assertNotEqual(row["action"], "sell")

            again = bot.record_month(state, claimed=0.01, root=tmp)
            self.assertEqual(again["rows"][0]["premium"], 0.0005)
            self.assertEqual(
                len([
                    item for item in desk_brain.load_journal(tmp)["decisions"]
                    if item.get("fill_id") == "BTCUSDT|2026-02"
                ]),
                1,
            )
            self.assertEqual(state["open"][0]["exit_fee_reserved"], 0.75)

        with tempfile.TemporaryDirectory() as tmp:
            missing = _book()
            missing["open"][0]["premium"] = 97000.0
            missing["open"][0]["failsafe_premium"] = None
            missing["open"][0].pop("last_mark", None)
            empty = bot.record_month(missing, claimed=0.0009, root=tmp)
            self.assertTrue(empty["recorded"])
            row = desk_brain.load_journal(tmp)["decisions"][0]
            self.assertNotIn("premium", row)
            self.assertFalse(row["fee_spent"])
            self.assertEqual(row["exit_fee"], "reserved")
            self.assertEqual(missing["open"][0]["exit_fee_reserved"], 0.75)
            self.assertEqual(len(missing["open"]), 1)

        with tempfile.TemporaryDirectory() as tmp:
            quiet = {"cash": 500.0, "open": [], "closed": []}
            none = bot.record_month(quiet, claimed=12.0, root=tmp)
            self.assertFalse(none["recorded"])
            self.assertFalse(none["sold"])
            self.assertFalse(none["fee_spent"])
            self.assertEqual(desk_brain.load_journal(tmp)["decisions"], [])
            self.assertEqual(quiet["cash"], 500.0)
            self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["binance_btc_carry"], 0.02)
            self.assertIn("record_month", bot.run_once.__code__.co_names)
            self.assertNotIn("place_open", bot.record_month.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
