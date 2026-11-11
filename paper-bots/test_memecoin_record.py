"""Memecoin records the mark, the fee, and the exit. The −$5 lock is not a fill."""
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
    meme = os.path.join(ROOT, "memecoin-paper")
    if meme not in sys.path:
        sys.path.insert(0, meme)
    if "requests" not in sys.modules:
        stub = types.ModuleType("requests")
        stub.Session = lambda: types.SimpleNamespace(headers={})
        sys.modules["requests"] = stub
    path = os.path.join(meme, "bot.py")
    spec = importlib.util.spec_from_file_location("memecoin_record", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MemecoinRecord(unittest.TestCase):
    def test_a_sale_records_the_mark_the_fee_and_the_exit(self):
        bot = _load()
        pos = {
            "mint": "MINT1",
            "symbol": "DOGE",
            "lane": "accurate",
            "fill_id": "MINT1|1",
            "cost_usd": 10.0,
            "realized_usd": -1.25,
            "exit_name": "model-flip −6%",
        }
        with tempfile.TemporaryDirectory() as tmp:
            row = bot.record_close(
                pos, cash=88.75, reason="model-flip −6%", mark=0.94, fee=0.1, root=tmp,
            )
            again = bot.record_close(
                pos, cash=88.75, reason="model-flip −6%", mark=0.94, fee=0.1, root=tmp,
            )
            saved = desk_brain.load_journal(tmp)
        self.assertEqual(pos["realized_usd"], -1.25)
        self.assertNotIn("ytd", pos)
        self.assertEqual(pos["exit_name"], "model-flip −6%")
        self.assertEqual(pos["exit_mark"], 0.94)
        self.assertEqual(pos["exit_fee"], 0.1)
        self.assertEqual(pos["cash_after"], 88.75)
        self.assertEqual(row["fill_id"], "MINT1|1")
        self.assertEqual(row["bid"], 0.94)
        self.assertEqual(row["fee"], 0.1)
        self.assertEqual(row["exit_name"], "model-flip −6%")
        self.assertEqual(row["cash"], 88.75)
        self.assertEqual(again["fill_id"], row["fill_id"])
        self.assertEqual(len(saved["decisions"]), 1)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["solana_dex"], 0.02)
        self.assertIn("record_close", bot.sell.__code__.co_names)

    def test_the_red_day_lock_is_an_entry_fact_not_a_fill(self):
        bot = _load()
        fact = bot.record_close(
            None, cash=100.0, reason=bot.decide_skip(-5), mark=None, fee=None,
        )
        self.assertEqual(fact["action"], "skip")
        self.assertFalse(fact["fill"])
        self.assertIn("−$5", fact["entry_fact"])
        self.assertNotIn("bid", fact)
        self.assertNotIn("fill_id", fact)
        missing = {
            "mint": "MINT1",
            "fill_id": "MINT1|2",
            "cost_usd": 10.0,
            "realized_usd": 0.5,
        }
        with tempfile.TemporaryDirectory() as tmp:
            row = bot.record_close(
                missing, cash=90.0, reason="stop −12%", mark=None, fee=0.1, root=tmp,
            )
        self.assertEqual(missing["realized_usd"], 0.5)
        self.assertNotIn("exit_mark", missing)
        self.assertNotIn("bid", row)
        self.assertEqual(row["exit_name"], "stop −12%")
        self.assertFalse(
            hasattr(bot.C, "expand_volume") and bool(getattr(bot.C, "expand_volume"))
        )


if __name__ == "__main__":
    unittest.main()
