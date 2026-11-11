"""BTC carry writes the hold intent before cash. One unlevered pair."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import tempfile
import unittest

import desk_profit

HERE = os.path.dirname(os.path.abspath(__file__))
NOW = dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc)


def _bot():
    path = os.path.join(HERE, "btc-carry-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("btc_carry_buy", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _marks():
    return {
        "symbol": "BTCUSDT",
        "funding": [{"time": "2026-02-01T00:00:00+00:00", "rate": 0.0001}],
        "premium": [{"time": "2026-02-01T00:00:00+00:00", "close": 0.0004}],
    }


class BtcCarryBuy(unittest.TestCase):
    def test_the_intent_is_written_before_cash_and_a_restart_does_not_open_again(self):
        bot = _bot()
        decision = {"action": "open", "floor": 0.02, "leverage": 5}
        with tempfile.TemporaryDirectory() as tmp:
            intent = os.path.join(tmp, "buy_intent.json")
            flat = {"cash": 500.0, "open": [], "closed": [], "entry_fees": 0}
            refused = bot.place_open(
                flat, {"action": "flat", "floor": 0.02}, _marks(), intent_path=intent, now=NOW,
            )
            self.assertFalse(refused["bought"])
            self.assertFalse(os.path.exists(intent))
            self.assertEqual(flat["open"], [])
            self.assertEqual(flat["cash"], 500.0)

            spot = {"funding": [], "premium": [{"time": "2026-02-01T00:00:00+00:00", "close": 97000.0}]}
            missed = bot.place_open(flat, decision, spot, intent_path=intent, now=NOW)
            self.assertFalse(missed["bought"])
            self.assertEqual(flat["cash"], 500.0)
            self.assertFalse(os.path.exists(intent))

            cheap = bot.place_open(
                flat, {"action": "open", "floor": 0.01}, _marks(), intent_path=intent, now=NOW,
            )
            self.assertEqual(cheap["reason"], "floor stays 0.02")
            self.assertEqual(flat["open"], [])

            blocked = os.path.join(tmp, "blocked")
            os.makedirs(blocked)
            stuck = {"cash": 500.0, "open": [], "closed": [], "entry_fees": 0}
            failed = bot.place_open(stuck, decision, _marks(), intent_path=blocked, now=NOW)
            self.assertFalse(failed["bought"])
            self.assertEqual(stuck["open"], [])
            self.assertEqual(stuck["cash"], 500.0)

            bought = bot.place_open(flat, decision, _marks(), intent_path=intent, now=NOW)
            self.assertTrue(bought["bought"])
            self.assertEqual(bought["exit_name"], "hold — red month is a mark")
            self.assertEqual(bought["notional"], 500.0)
            self.assertEqual(bought["leverage"], 1)
            self.assertEqual(bought["exit_fee_reserved"], 0.75)
            self.assertFalse(bought["sold"])
            self.assertAlmostEqual(flat["cash"], 499.25, places=2)
            self.assertEqual(len(flat["open"]), 1)
            pos = flat["open"][0]
            self.assertEqual(pos["leverage"], 1)
            self.assertEqual(pos["notional"], 500.0)
            self.assertEqual(pos["exit_name"], "hold — red month is a mark")
            self.assertEqual(pos["exit_fee_reserved"], 0.75)
            self.assertEqual(pos["premium"], 0.0004)
            self.assertEqual(flat["entry_fees"], 1)
            with open(intent, encoding="utf-8") as handle:
                wrote = json.load(handle)
            self.assertEqual(wrote["status"], "intent")
            self.assertEqual(wrote["notional"], 500.0)
            self.assertEqual(wrote["leverage"], 1)
            self.assertEqual(wrote["exit_fee_reserved"], 0.75)
            self.assertEqual(wrote["exit_name"], "hold — red month is a mark")
            self.assertEqual(wrote["premium"], 0.0004)
            self.assertTrue(wrote["paper_only"])

            again = bot.place_open(flat, decision, _marks(), intent_path=intent, now=NOW)
            self.assertEqual(again["reason"], "one pair")
            self.assertFalse(again["bought"])
            self.assertEqual(len(flat["open"]), 1)
            self.assertAlmostEqual(flat["cash"], 499.25, places=2)
            self.assertEqual(flat["entry_fees"], 1)

            orphan = {"cash": 500.0, "open": [], "closed": []}
            with open(intent, "w", encoding="utf-8") as handle:
                json.dump({"fill_id": "btc-carry|missing", "premium": 97000.0, "leverage": 5}, handle)
            status = bot.reconcile_open_intent(orphan, intent)
            self.assertEqual(status, "abandoned")
            self.assertEqual(orphan["open"], [])
            self.assertEqual(orphan["cash"], 500.0)
            with open(intent, encoding="utf-8") as handle:
                left = json.load(handle)
            self.assertEqual(left["status"], "abandoned")
            self.assertEqual(left["exit_name"], "hold — red month is a mark")
            self.assertEqual(left["leverage"], 1)
            self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["binance_btc_carry"], 0.02)
            self.assertIn("place_open", bot.hold_step.__code__.co_names)
            self.assertIn("write_open_intent", bot.place_open.__code__.co_names)
            self.assertIn("hold_step", bot.run_once.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
