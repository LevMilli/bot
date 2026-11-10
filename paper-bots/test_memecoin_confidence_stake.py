"""Memecoin buy-in scales with confidence on this tower's $10–$25 band.

Paper only. Does not copy another tower's dollars, and does not open a buy
when the residual refuse still skips the name.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_bot():
    meme = os.path.join(HERE, "memecoin-paper")
    sys.path.insert(0, meme)
    # bot.py opens a requests session at import. The stake math does not use it.
    if "requests" not in sys.modules:
        import types
        stub = types.ModuleType("requests")

        class _Session:
            headers: dict = {}

        stub.Session = _Session
        sys.modules["requests"] = stub
    path = os.path.join(meme, "bot.py")
    spec = importlib.util.spec_from_file_location("meme_bot_conf_stake", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class MemecoinConfidenceStake(unittest.TestCase):
    def test_eighty_is_ten_and_ninety_is_twenty_five(self):
        bot = _load_bot()
        cash = {"cash_usd": 100.0}
        low = bot.ticket_for(cash, 0.80, "accurate")
        high = bot.ticket_for(cash, 0.90, "accurate")
        self.assertEqual(low, 10.0)
        self.assertEqual(high, 25.0)
        self.assertGreater(high, low)

    def test_eighty_five_is_linear(self):
        bot = _load_bot()
        stake = bot.confidence_buy_in(0.85, "accurate")
        self.assertEqual(stake, 17.5)

    def test_above_ninety_stays_at_the_cap(self):
        bot = _load_bot()
        self.assertEqual(bot.confidence_buy_in(0.96, "accurate"), 25.0)

    def test_speed_lane_stays_on_the_low_ticket(self):
        bot = _load_bot()
        self.assertEqual(bot.confidence_buy_in(0.74, "speed"), 10.0)
        # A high print on the speed lane still must not outgrow the 80% ticket.
        self.assertEqual(bot.confidence_buy_in(0.93, "speed"), 10.0)
        sized = bot.apply_entry_cuts(25.0, {"cash_usd": 100.0}, "speed", 0.0)
        self.assertEqual(sized, 10.0)

    def test_red_day_ceiling_and_cash_still_cut(self):
        bot = _load_bot()
        red = bot.apply_entry_cuts(
            bot.ticket_for({"cash_usd": 100.0}, 0.90, "accurate"),
            {"cash_usd": 100.0},
            "accurate",
            -1.0,
        )
        self.assertEqual(red, 10.0)
        thin = bot.ticket_for({"cash_usd": 12.0}, 0.90, "accurate")
        self.assertEqual(thin, 12.0)
        broke = bot.ticket_for({"cash_usd": 8.0}, 0.90, "accurate")
        self.assertEqual(broke, 0.0)

    def test_locks_and_fee_floor_unchanged(self):
        bot = _load_bot()
        import desk_profit
        self.assertEqual(bot.C.EXIT["stop_pct"], -12)
        self.assertEqual(bot.C.RED_DAY_ENTRY_LOCK_USD, 5)
        self.assertEqual(bot.C.RED_DAY_TICKET_USD, 10)
        self.assertEqual(bot.C.MIN_TICKET_USD, 10)
        self.assertEqual(bot.C.TICKET_USD, 25)
        self.assertTrue(bot.C.PAPER)
        self.assertFalse(hasattr(bot.C, "expand_volume") and bool(getattr(bot.C, "expand_volume")))
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["solana_dex"], 0.02)
        with open(os.path.join(HERE, "memecoin-paper", "bot.py"), encoding="utf-8") as handle:
            src = handle.read()
        self.assertIn("def refuse_conf_residual_as_edge(", src)
        self.assertNotIn("TICKET_USD * 0.7", src)


if __name__ == "__main__":
    unittest.main()
