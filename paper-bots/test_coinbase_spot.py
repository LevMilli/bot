"""Coinbase spot tower: fee floor, skip base, exits, scaffold check. No network."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_profit
import pimp_desk


def _bot():
    path = os.path.join(HERE, "coinbase-spot-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("coinbase_spot_bot", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _chop(n=400):
    """Alternating noise. The typical closed trade loses the round trip."""
    px = 100.0
    closes = []
    for i in range(n):
        px *= 1.01 if i % 2 == 0 else 0.99
        closes.append(px)
    return closes


def _winner(n_trades=22, look=10, hold=6):
    """Repeated crosses that stay above the average until the time stop, then a fresh cross."""
    closes = [100.0] * look
    for _ in range(n_trades):
        closes.append(90.0)
        closes.append(130.0)
        closes.extend([150.0] * hold)
        closes.extend([80.0] * look)
    closes.append(70.0)
    closes.append(120.0)
    return closes


def _fast_cfg(bot, **extra):
    cfg = bot.locked_cfg({})
    cfg.update({"trend_look": 10, "hold_bars": 6, "stop_pct": 0.15})
    cfg.update(extra)
    return bot.locked_cfg(cfg)


class CoinbaseSpotRules(unittest.TestCase):
    def test_floor_cannot_be_softened(self):
        bot = _bot()
        cfg = bot.locked_cfg({"venue_min_edge": 0.01, "capture_haircut": 0.9, "taker_fee": 0.001, "slippage": 0})
        self.assertGreaterEqual(cfg["venue_min_edge"], 0.05)
        self.assertLessEqual(cfg["capture_haircut"], 0.25)
        self.assertGreaterEqual(cfg["taker_fee"], 0.009)
        self.assertGreaterEqual(cfg["slippage"], 0.001)
        parsed, err = desk_profit.parse_venue_min_edge({"coinbase_spot": 0.01})
        self.assertIsNone(parsed)
        self.assertIn("cannot lower", err or "")
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["coinbase_spot"], 0.05)
        self.assertEqual(desk_profit.bot_venue_edge("coinbase-spot"), 0.05)
        tightened = bot.locked_cfg({"min_sample": 3, "hit_floor": 0.1, "hold_bars": 10, "time_stop_hours": 1})
        self.assertGreaterEqual(tightened["min_sample"], 20)
        self.assertGreaterEqual(tightened["hit_floor"], 0.40)
        self.assertGreaterEqual(tightened["time_stop_hours"], 240)

    def test_losing_sample_stays_flat_and_winning_sample_buys(self):
        bot = _bot()
        cfg = _fast_cfg(bot)
        chop = bot.evaluate_closes(_chop(), cfg, product="ETH-USD")
        self.assertEqual(chop["action"], "skip")
        self.assertIn("typical trade loses", chop["reason"])
        self.assertNotIn("long-only", chop["reason"])
        self.assertLess(chop["median"], 0)
        short = bot.evaluate_closes(_chop(30), cfg, product="ETH-USD")
        self.assertEqual(short["action"], "skip")
        self.assertIn("needs 20", short["reason"])
        won = bot.evaluate_closes(_winner(), cfg, product="ETH-USD")
        self.assertEqual(won["action"], "buy")
        self.assertGreaterEqual(won["edge"], 0.05)
        self.assertGreater(won["median"], 0)
        self.assertGreaterEqual(won["sample_n"], 20)

    def test_research_card_states_the_hurdle(self):
        bot = _bot()
        card = bot.research_card()
        self.assertTrue(card["paper_only"])
        self.assertFalse(card["live_orders"])
        self.assertTrue(card["shadow_only"])
        self.assertAlmostEqual(card["round_trip"], 0.02, places=4)
        self.assertGreaterEqual(card["min_sample"], 20)
        self.assertGreaterEqual(card["hit_floor"], 0.40)
        self.assertEqual(card["trend_look"], 50)
        self.assertIn("ETH-USD", card["products_trade"])
        self.assertIn("BTC-USD", card["products_research_only"])
        self.assertIn("median", card["base"])

    def test_run_skips_chop_buys_winner_and_refuses_btc(self):
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "coinbase-spot-paper"))
            cfg = _fast_cfg(bot)
            books = {
                "ETH-USD": _chop(),
                "SOL-USD": _chop(),
                "BTC-USD": _winner(),
            }
            out = _capture(bot, tmp, cfg, books)
            self.assertIn("no trade", out)
            self.assertIn("typical trade loses", out)
            self.assertIn("SKIP BTC-USD", out)
            self.assertIn("research only", out)
            self.assertNotIn("long-only", out)
            state = json.load(open(os.path.join(tmp, "coinbase-spot-paper", "paper_account.json"), encoding="utf-8"))
            self.assertEqual(state["open"], [])
            self.assertTrue(state["shadow_only"])
            books["ETH-USD"] = _winner()
            out = _capture(bot, tmp, cfg, books)
            self.assertIn("paper buy ETH-USD", out)
            self.assertNotIn("no trade", out)
            state = json.load(open(os.path.join(tmp, "coinbase-spot-paper", "paper_account.json"), encoding="utf-8"))
            self.assertEqual(len(state["open"]), 1)
            self.assertEqual(state["open"][0]["ticker"], "ETH-USD")
            self.assertAlmostEqual(state["cash"], 475.0, places=2)

    def test_btc_yes_blocks_and_exits_fire(self):
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "coinbase-spot-paper"))
            os.makedirs(os.path.join(tmp, "btc15m-signal"))
            with open(os.path.join(tmp, "btc15m-signal", "paper_account.json"), "w", encoding="utf-8") as handle:
                json.dump({"open": [{"side": "YES", "ticker": "KXBTC15M"}]}, handle)
            cfg = _fast_cfg(bot)
            winner = _winner()
            out = _capture(bot, tmp, cfg, {"ETH-USD": winner, "SOL-USD": _chop(), "BTC-USD": _chop()})
            self.assertIn("btc15m YES open", out)
            self.assertIn("no trade", out)
            os.remove(os.path.join(tmp, "btc15m-signal", "paper_account.json"))
            _capture(bot, tmp, cfg, {"ETH-USD": winner, "SOL-USD": _chop(), "BTC-USD": _chop()})
            state = json.load(open(os.path.join(tmp, "coinbase-spot-paper", "paper_account.json"), encoding="utf-8"))
            entry = state["open"][0]["entry_price"]
            # A new bar, so the crash is an exit and not a fresh cross that buys again.
            crashed = list(winner) + [entry * 0.80]
            out = _capture(bot, tmp, cfg, {"ETH-USD": crashed, "SOL-USD": _chop(), "BTC-USD": _chop()})
            self.assertIn("paper sell ETH-USD stop", out)
            state = json.load(open(os.path.join(tmp, "coinbase-spot-paper", "paper_account.json"), encoding="utf-8"))
            self.assertEqual(state["open"], [])
            self.assertEqual(state["closed"][-1]["exit"], "stop")
            self.assertTrue(os.path.isfile(os.path.join(tmp, "desk_incubation.json")))

    def test_key_in_env_refuses(self):
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "coinbase-spot-paper"))
            os.environ["COINBASE_API_KEY"] = "not-a-real-key"
            try:
                import io
                from contextlib import redirect_stdout
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = bot.run_once(desk_root=tmp, cfg=bot.locked_cfg({}))
                self.assertEqual(code, 0)
                self.assertIn("refusing", buf.getvalue())
                self.assertNotIn("not-a-real-key", buf.getvalue())
            finally:
                os.environ.pop("COINBASE_API_KEY", None)

    def test_desk_registers_shadow_tower(self):
        spec = next(row for row in pimp_desk.BOTS if row["id"] == "coinbase-spot")
        self.assertTrue(spec["shadow_only"])
        self.assertNotIn("coinbase-spot", pimp_desk.DEFAULTS["tower_risk_budgets"])
        self.assertEqual(pimp_desk.BOT_PLANS["coinbase-spot"]["exit_quality"], "partial")
        self.assertTrue(pimp_desk.BOT_PLANS["coinbase-spot"]["entry_gated"])
        self.assertIn("coinbase_spot", pimp_desk.DEFAULTS["venue_min_edge"])
        slot = next(row for row in pimp_desk.AUTO if row["id"] == "coinbase-spot")
        self.assertEqual(slot["every_sec"], 300)
        plan = __import__("desk_roi_plan").default_exit_plan("coinbase-spot")
        self.assertTrue(plan["fee_floors_locked"])
        self.assertFalse(plan["auto_promote"])

    def test_scaffold_and_check(self):
        sys.path.insert(0, os.path.join(HERE, "tools"))
        import new_tower
        self.assertTrue(new_tower.check_tower("coinbase-spot")["ok"])
        with tempfile.TemporaryDirectory() as tmp:
            bad = new_tower.scaffold(tmp, "weather-kalshi", "Weather", 0.01)
            self.assertFalse(bad["ok"])
            good = new_tower.scaffold(tmp, "weather-kalshi", "Weather Kalshi", 0.06)
            self.assertTrue(good["ok"])
            self.assertTrue(os.path.isfile(os.path.join(tmp, "weather-kalshi-paper", "bot.py")))
            again = new_tower.scaffold(tmp, "weather-kalshi", "Weather Kalshi", 0.06)
            self.assertFalse(again["ok"])
            text = open(os.path.join(tmp, "weather-kalshi-paper", "config.json"), encoding="utf-8").read()
            self.assertIn("true", text.lower())
            self.assertNotIn('"live_orders": true', text)


def _capture(bot, tmp, cfg, books) -> str:
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        bot.run_once(desk_root=tmp, cfg=cfg, fetch=lambda product: books[product])
    return buf.getvalue()


if __name__ == "__main__":
    unittest.main()
