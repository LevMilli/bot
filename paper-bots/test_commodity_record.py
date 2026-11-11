"""Commodity records the close, the bid, the fee, and the reason. P/L is not retyped."""
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest

import desk_brain
import desk_profit

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load():
    path = os.path.join(ROOT, "commodity-15m-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("commodity_record", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CommodityRecord(unittest.TestCase):
    def test_sale_records_the_bid_fee_and_model_flip(self):
        bot = _load()
        pos = {
            "ticker": "KXBRENT15M-T",
            "series": "KXBRENT15M",
            "side": "YES",
            "fill_id": "KXBRENT15M-T|1",
            "fee": 0.07,
            "cost": 3.24,
            "pnl": -1.5,
            "exit": "model-flip side YES→NO",
        }
        with tempfile.TemporaryDirectory() as tmp:
            row = bot.record_close(
                pos, cash=80.5, reason=pos["exit"], bid=0.35, fee=0.02, root=tmp,
            )
            again = bot.record_close(
                pos, cash=80.5, reason=pos["exit"], bid=0.35, fee=0.02, root=tmp,
            )
            saved = desk_brain.load_journal(tmp)
        self.assertEqual(pos["pnl"], -1.5)
        self.assertNotIn("ytd", pos)
        self.assertNotIn("year_to_date", pos)
        self.assertEqual(pos["exit_name"], "model-flip")
        self.assertEqual(pos["exit_fee"], 0.02)
        self.assertEqual(pos["cash_after"], 80.5)
        self.assertEqual(row["fill_id"], "KXBRENT15M-T|1")
        self.assertEqual(row["bid"], 0.35)
        self.assertEqual(row["fee"], 0.02)
        self.assertEqual(row["exit_name"], "model-flip")
        self.assertEqual(row["action"], "sell")
        self.assertEqual(row["cash"], 80.5)
        self.assertEqual(again["fill_id"], row["fill_id"])
        self.assertEqual(again["exit_name"], row["exit_name"])
        self.assertEqual(len(saved["decisions"]), 1)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_commodity15m"], 0.05)

    def test_settle_does_not_invent_a_bid(self):
        bot = _load()
        pos = {
            "ticker": "KXGOLD15M-T",
            "series": "KXGOLD15M",
            "side": "YES",
            "fill_id": "KXGOLD15M-T|2",
            "fee": 0.04,
            "cost": 6.0,
            "pnl": 2.25,
            "exit": "settled",
        }
        with tempfile.TemporaryDirectory() as tmp:
            row = bot.record_close(
                pos, cash=88.25, reason="settled", bid=None, fee=pos["fee"], root=tmp,
            )
        self.assertEqual(pos["pnl"], 2.25)
        self.assertNotIn("bid", row)
        self.assertNotIn("exit_price", pos)
        self.assertEqual(row["exit_name"], "settled")
        self.assertEqual(row["action"], "settle")
        self.assertEqual(row["fee"], 0.04)
        self.assertIn("record_close", bot.paper_sell.__code__.co_names)
        self.assertIn("record_close", bot.settle_account.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
