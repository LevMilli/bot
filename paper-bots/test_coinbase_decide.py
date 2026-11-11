"""Coinbase decide stays flat until the replay bar and the 0.05 floor both pass."""
from __future__ import annotations

import importlib.util
import os
import unittest

import desk_profit

HERE = os.path.dirname(os.path.abspath(__file__))


def _bot():
    path = os.path.join(HERE, "coinbase-spot-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("coinbase_decide", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _wins(n, ret=0.06):
    return [{"pnl": 25.0 * ret, "cost": 25.0, "ticker": "ETH-USD"} for _ in range(n)]


class CoinbaseDecide(unittest.TestCase):
    def test_replay_and_floor_keep_the_decision_flat(self):
        bot = _bot()
        cfg = bot.locked_cfg({"taker_fee": 0.001, "slippage": 0, "venue_min_edge": 0.01})
        self.assertGreaterEqual(cfg["taker_fee"], 0.009)
        self.assertGreaterEqual(cfg["slippage"], 0.001)
        self.assertGreaterEqual(bot.fee_need(cfg), 0.07)
        self.assertEqual(bot.decide_stake(25, 80), 25)
        self.assertEqual(bot.decide_stake(25, 10), 10)
        self.assertEqual(bot.decide_stake(25, None), 25)

        buy = {"product": "ETH-USD", "action": "buy", "edge": 0.08, "reason": "fee-clear long"}
        flat = bot.decide(buy, [], cfg)
        self.assertTrue(flat["flat"])
        self.assertEqual(flat["action"], "flat")
        self.assertEqual(flat["stake"], 0.0)
        self.assertEqual(flat["reason"], "replay bar not met")

        cold_tail = _wins(10, 0.20) + _wins(20, -0.01)
        self.assertEqual(bot.replay_bar(cold_tail), "replay bar not met")
        self.assertEqual(bot.decide(buy, cold_tail, cfg)["action"], "flat")

        cleared = bot.decide(buy, _wins(20), cfg, adapted=80)
        self.assertFalse(cleared["flat"])
        self.assertEqual(cleared["action"], "buy")
        self.assertEqual(cleared["stake"], 25)
        thin = dict(buy, edge=0.04)
        self.assertEqual(bot.decide(thin, _wins(20), cfg)["reason"], "floor on top of the round trip")

        logged = bot.decide(
            {"product": "BTC-USD", "action": "log", "reason": "research only — logged, not scored as a buy"},
            _wins(20),
            cfg,
        )
        self.assertEqual(logged["action"], "log")
        self.assertEqual(logged["stake"], 0.0)
        self.assertFalse(logged["scored_as_buy"])

        failed = bot.decide(
            {"product": "SOL-USD", "action": "skip", "reason": "data TimeoutError", "data_skip": True},
            _wins(20),
            cfg,
        )
        self.assertEqual(failed["reason"], "data TimeoutError")
        self.assertEqual(failed["stake"], 0.0)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["coinbase_spot"], 0.05)
        self.assertIn("decide", bot.run_once.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
