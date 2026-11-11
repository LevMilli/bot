"""BTC 15-minute failsafe sells at the held-side bid. A sell before settle is not a hit."""
from __future__ import annotations

import importlib.util
import os
import unittest

import desk_profit

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load_btc():
    path = os.path.join(ROOT, "btc15m-signal", "btc15m_signal.py")
    spec = importlib.util.spec_from_file_location("btc15m_sell", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Btc15mSell(unittest.TestCase):
    def test_take_profit_uses_the_book_bid_and_is_not_a_hit(self):
        btc = _load_btc()
        btc.IS_SHADOW = True
        pos = {
            "ticker": "KXBTC15M-T",
            "side": "YES",
            "ask": 0.70,
            "take_profit": 0.85,
            "contracts": 10,
            "cost": 7.2,
            "fill_id": "KXBTC15M-T|1",
            "fair_at_entry": 0.88,
            "series": "KXBTC15M",
        }
        state = {"cash": 100.0, "open": [dict(pos)], "closed": []}
        market = {"yes_bid": 0.90, "no_bid": 0.08, "yes_ask": 0.91, "no_ask": 0.10}
        sold = btc.manage_take_profits(
            state, 0.90, btc.fee_per_contract(0.90),
            ticker="KXBTC15M-T", market=market, model_side="YES",
        )
        self.assertEqual(len(sold), 1)
        self.assertEqual(state["open"], [])
        closed = state["closed"][0]
        fee = btc.fee_per_contract(0.90)
        self.assertAlmostEqual(closed["payout"], round(10 * (0.90 - fee), 2))
        self.assertLess(closed["payout"], 9.0)
        self.assertIn("take-profit +15¢ cap 99¢", closed["exit"])
        self.assertFalse(closed["opens_new_ticket"])
        row = btc.sell_learning_row(pos, closed["exit"])
        self.assertNotIn("result", row)
        self.assertEqual(row["market"], "KXBTC15M")
        self.assertIn("take-profit", row["reason"])

        held = {"cash": 100.0, "open": [dict(pos)], "closed": []}
        quiet = btc.manage_take_profits(
            held, 0.50, 0.02, ticker="KXBTC15M-T",
            market={"yes_bid": 0.50, "no_bid": 0.48}, model_side="YES",
        )
        self.assertEqual(quiet, [])
        self.assertEqual(len(held["open"]), 1)
        for bad in (None, 0, 1, 1.2):
            stuck = {"cash": 100.0, "open": [dict(pos)], "closed": []}
            btc.manage_take_profits(
                stuck, bad, 0.02, ticker="KXBTC15M-T",
                market={"yes_bid": bad, "no_bid": 0.10}, model_side="YES",
            )
            self.assertEqual(len(stuck["open"]), 1)
        self.assertEqual(btc.last_minute_block(0.4), "no new buy in the last minute")
        self.assertEqual(btc.last_minute_block(3.0), "")
        cash = {"cash": 100.0, "open": [], "closed": []}
        msg = btc.paper_buy(
            cash, "KXBTC15M-T", "YES", 0.80, 0.02, 0.88,
            "2026-11-11T18:00:00Z", True, edge=0.06,
            vol_kwargs={"minutes_left": 0.4},
        )
        self.assertEqual(msg, "no new buy in the last minute")
        self.assertEqual(cash["cash"], 100.0)
        self.assertEqual(cash["open"], [])
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"], 0.05)


if __name__ == "__main__":
    unittest.main()
