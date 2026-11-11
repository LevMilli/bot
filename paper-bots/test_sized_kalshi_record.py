"""Sized Kalshi records the close that happened. A header is not a sample fill."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
import unittest

import desk_brain
import desk_profit

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load():
    if "requests" not in sys.modules:
        stub = types.ModuleType("requests")
        stub.Session = lambda: types.SimpleNamespace(headers={})
        sys.modules["requests"] = stub
    sibling = os.path.join(ROOT, "kalshi-sp500-paper")
    sized = os.path.join(ROOT, "kalshi-sized-paper")
    for path in (sibling, sized):
        if path in sys.path:
            sys.path.remove(path)
        sys.path.insert(0, path)
    bot_path = os.path.join(sized, "bot.py")
    spec = importlib.util.spec_from_file_location("sized_kalshi_record", bot_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SizedKalshiRecord(unittest.TestCase):
    def test_sale_keeps_the_bid_and_a_header_is_not_a_fill(self):
        bot = _load()
        sim = bot.paper_sim
        with tempfile.TemporaryDirectory() as tmp:
            pos = {
                "fill_id": "KXINXU-SIZED|1",
                "ticker": "KXINXU-SIZED",
                "side": "yes",
                "tower": "kalshi-sized",
                "cost": 8.5,
                "fee": 0.11,
                "risk": 8.61,
                "exit_price": 0.40,
                "exit_fee": 0.17,
                "pnl": -4.84,
            }
            first = sim.record_close(
                pos, bankroll=495.16, reason="model-flip bid under 50c",
                bid=0.40, root=tmp,
            )
            second = sim.record_close(
                pos, bankroll=495.16, reason="model-flip bid under 50c",
                bid=0.40, root=tmp,
            )
            self.assertEqual(pos["bankroll_after"], 495.16)
            self.assertEqual(pos["pnl"], -4.84)
            self.assertEqual(pos["exit_price"], 0.40)
            self.assertEqual(first["bot"], "kalshi-sized")
            self.assertEqual(first["fill_id"], "KXINXU-SIZED|1")
            self.assertEqual(first["bid"], 0.40)
            self.assertEqual(first["fee"], 0.17)
            self.assertEqual(first["exit_name"], "model-flip bid under 50c")
            self.assertEqual(first["cash"], 495.16)
            self.assertEqual(first["action"], "sell")
            journal = desk_brain.load_journal(tmp)
            matches = [
                row for row in journal["decisions"]
                if row.get("fill_id") == "KXINXU-SIZED|1"
            ]
            self.assertEqual(len(matches), 1)
            self.assertEqual(second["fill_id"], first["fill_id"])

            sibling = {
                "fill_id": "KXINXU-SP|1",
                "ticker": "KXINXU-SP",
                "tower": "kalshi-sp",
                "pnl": -1.0,
            }
            self.assertIsNone(sim.record_close(
                sibling, bankroll=400, reason="model-flip bid under 50c",
                bid=0.33, root=tmp,
            ))
            self.assertNotIn("exit_price", sibling)
            self.assertEqual(sibling["pnl"], -1.0)
            self.assertFalse(any(
                row.get("fill_id") == "KXINXU-SP|1" for row in desk_brain.load_journal(tmp)["decisions"]
            ))

            settled = {
                "fill_id": "KXINXU-SIZED|2",
                "ticker": "KXINXU-SIZED",
                "side": "no",
                "tower": "kalshi-sized",
                "fee": 0.11,
                "pnl": -8.61,
            }
            written = sim.record_close(
                settled, bankroll=491.39, reason="settled", bid=None, root=tmp,
            )
            self.assertNotIn("bid", written)
            self.assertNotIn("exit_price", settled)
            self.assertEqual(written["exit_name"], "settled")
            self.assertEqual(written["action"], "settle")
            self.assertEqual(settled["pnl"], -8.61)
            for raw in (0, 1, ""):
                sim.record_close(
                    settled, bankroll=491.39, reason="settled", bid=raw, root=tmp,
                )
            self.assertNotIn("exit_price", settled)
            again = desk_brain.load_journal(tmp)
            settle_rows = [
                row for row in again["decisions"] if row.get("fill_id") == "KXINXU-SIZED|2"
            ]
            self.assertEqual(len(settle_rows), 1)
            self.assertNotIn("bid", settle_rows[0])

            blank = {}
            fact = sim.record_close(
                blank, bankroll=500, reason="# Learning.md - Sized Kalshi notes\n",
                bid=0.40, root=tmp,
            )
            self.assertFalse(fact["fill"])
            self.assertEqual(fact["fact"], "header-only learning file")
            self.assertEqual(blank, {})
            self.assertFalse(any(
                row.get("note", "").startswith("#") for row in desk_brain.load_journal(tmp)["decisions"]
            ))
            self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"], 0.02)
            self.assertIn("record_close", bot.step_settle.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
