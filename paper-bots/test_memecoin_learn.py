"""Memecoin learning is one row per mint. A cold mint does not lower 0.02."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
import unittest

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
    spec = importlib.util.spec_from_file_location("memecoin_learn", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pos(mint="MINT1", fill="MINT1|1"):
    return {
        "mint": mint,
        "fill_id": fill,
        "confidence": 0.86,
        "cost_usd": 10.0,
        "lane": "accurate",
        "exit_name": "model-flip −6%",
    }


class MemecoinLearn(unittest.TestCase):
    def test_one_row_for_this_mint_and_a_cold_mint_does_not_lower_the_floor(self):
        bot = _load()
        row = bot.memecoin_learning_row(_pos(), -1.0, "model-flip −6%")
        self.assertEqual(row["market"], "MINT1")
        self.assertEqual(row["reason"], "model-flip −6%")
        self.assertNotIn("result", row)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                bot.tell_memecoin_learning(_pos(), -1.0, "model-flip −6%", root=tmp),
                "recorded",
            )
            self.assertEqual(
                bot.tell_memecoin_learning(_pos(), -1.0, "model-flip −6%", root=tmp),
                "duplicate",
            )
            saved = bot._desk().load_learning(tmp)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["market"], "MINT1")
        self.assertEqual(saved[0]["bucket"], "0.8-0.9")
        self.assertNotIn("result", saved[0])

        cold = [
            {
                "market": "MINT1",
                "bucket": "0.8-0.9",
                "result": "miss",
                "side": "ACCURATE",
                "hour_ct": 13,
            }
            for _ in range(8)
        ]
        self.assertIn("MINT1", bot.mint_learning_skip(cold, "MINT1", 0.86, "accurate", 13))
        self.assertEqual(bot.mint_learning_skip(cold, "MINT2", 0.86, "accurate", 13), "")
        self.assertEqual(bot.floor_for_next_mint(0.01, cold), 0.02)
        self.assertEqual(bot.floor_for_next_mint(0.05, cold), 0.05)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["solana_dex"], 0.02)
        self.assertIn("tell_memecoin_learning", bot.sell.__code__.co_names)
        self.assertIn("memecoin_learning_row", bot.tell_memecoin_learning.__code__.co_names)
        self.assertFalse(
            hasattr(bot.C, "expand_volume") and bool(getattr(bot.C, "expand_volume"))
        )


if __name__ == "__main__":
    unittest.main()
