"""BTC 15-minute records the fill, the bid, the fee, and which exit fired."""
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest

import desk_brain
import desk_profit

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load_btc():
    path = os.path.join(ROOT, "btc15m-signal", "btc15m_signal.py")
    spec = importlib.util.spec_from_file_location("btc15m_record", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Btc15mRecord(unittest.TestCase):
    def test_sale_records_the_bid_fee_and_exit(self):
        btc = _load_btc()
        pos = {
            "ticker": "KXBTC15M-T",
            "side": "YES",
            "fill_id": "KXBTC15M-T|1",
            "fee": 0.07,
            "cost": 7.2,
            "pnl": -1.5,
            "exit": "take-profit +15¢ cap 99¢ bid 0.90 ≥ 0.85",
        }
        with tempfile.TemporaryDirectory() as tmp:
            row = btc.record_close(
                pos, cash=95.16, reason=pos["exit"], bid=0.90, fee=0.02, root=tmp,
            )
            again = btc.record_close(
                pos, cash=95.16, reason=pos["exit"], bid=0.90, fee=0.02, root=tmp,
            )
            saved = desk_brain.load_journal(tmp)
        self.assertEqual(pos["pnl"], -1.5)
        self.assertEqual(pos["exit_name"], "take-profit +15¢ cap 99¢")
        self.assertEqual(pos["exit_fee"], 0.02)
        self.assertEqual(pos["cash_after"], 95.16)
        self.assertEqual(row["fill_id"], "KXBTC15M-T|1")
        self.assertEqual(row["bid"], 0.90)
        self.assertEqual(row["fee"], 0.02)
        self.assertEqual(row["exit_name"], "take-profit +15¢ cap 99¢")
        self.assertEqual(row["action"], "sell")
        self.assertEqual(again["fill_id"], row["fill_id"])
        self.assertEqual(again["exit_name"], row["exit_name"])
        self.assertEqual(len(saved["decisions"]), 1)
        self.assertEqual(btc.exit_that_fired("model-flip side YES→NO"), "model-flip")
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"], 0.05)

    def test_settle_does_not_invent_a_bid(self):
        btc = _load_btc()
        pos = {
            "ticker": "KXBTC15M-T",
            "side": "YES",
            "fill_id": "KXBTC15M-T|2",
            "fee": 0.07,
            "cost": 7.2,
            "pnl": 2.8,
            "exit": "settled",
        }
        with tempfile.TemporaryDirectory() as tmp:
            row = btc.record_close(
                pos, cash=102.8, reason="settled", bid=None, fee=pos["fee"], root=tmp,
            )
        self.assertEqual(pos["pnl"], 2.8)
        self.assertNotIn("exit_price", pos)
        self.assertNotIn("bid", row)
        self.assertEqual(row["exit_name"], "settled")
        self.assertEqual(row["action"], "settle")
        self.assertEqual(row["fee"], 0.07)
        self.assertEqual(row["fill_id"], "KXBTC15M-T|2")
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"], 0.05)


if __name__ == "__main__":
    unittest.main()
