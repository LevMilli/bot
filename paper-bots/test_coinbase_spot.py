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


def _quiet(n=40):
    """Alternating noise plus a small last up-bar. Edge stays under the floor."""
    px = 100.0
    closes = [px]
    for i in range(n - 2):
        step = 0.002 if i % 2 == 0 else -0.0015
        px *= 1.0 + step
        closes.append(px)
    closes.append(px * 1.001)
    return closes


def _moon():
    closes = _quiet()
    closes[-1] = closes[-2] * 1.30
    return closes


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

    def test_ordinary_bar_skips_and_moon_bar_clears(self):
        bot = _bot()
        cfg = bot.locked_cfg({})
        quiet = bot.evaluate_returns(bot.closes_to_returns(_quiet()), cfg, product="ETH-USD")
        self.assertEqual(quiet["action"], "skip")
        self.assertLess(quiet["edge"], 0.05)
        moon = bot.evaluate_returns(bot.closes_to_returns(_moon()), cfg, product="ETH-USD")
        self.assertEqual(moon["action"], "buy")
        self.assertGreaterEqual(moon["edge"], 0.05)
        self.assertGreaterEqual(moon["z"], 2.0)
        down = _quiet()
        down.append(down[-1] * 0.70)
        short = bot.evaluate_returns(bot.closes_to_returns(down), cfg, product="ETH-USD")
        self.assertEqual(short["action"], "skip")
        self.assertIn("long-only", short["reason"])

    def test_research_card_states_the_hurdle(self):
        bot = _bot()
        card = bot.research_card()
        self.assertTrue(card["paper_only"])
        self.assertFalse(card["live_orders"])
        self.assertTrue(card["shadow_only"])
        self.assertAlmostEqual(card["round_trip"], 0.02, places=4)
        self.assertGreater(card["bar_return_to_clear"], 0.25)
        self.assertIn("ETH-USD", card["products_trade"])
        self.assertIn("BTC-USD", card["products_research_only"])

    def test_run_skips_quiet_buys_moon_and_refuses_btc(self):
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "coinbase-spot-paper"))
            with open(os.path.join(HERE, "coinbase-spot-paper", "config.json"), encoding="utf-8") as handle:
                cfg = json.load(handle)
            books = {
                "ETH-USD": _quiet(),
                "SOL-USD": _quiet(),
                "BTC-USD": _moon(),
            }
            out = _capture(bot, tmp, cfg, books)
            self.assertIn("no trade", out)
            self.assertIn("SKIP BTC-USD", out)
            self.assertIn("research only", out)
            state = json.load(open(os.path.join(tmp, "coinbase-spot-paper", "paper_account.json"), encoding="utf-8"))
            self.assertEqual(state["open"], [])
            self.assertTrue(state["shadow_only"])
            books["ETH-USD"] = _moon()
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
            cfg = bot.locked_cfg({})
            out = _capture(bot, tmp, cfg, {"ETH-USD": _moon(), "SOL-USD": _quiet(), "BTC-USD": _quiet()})
            self.assertIn("btc15m YES open", out)
            self.assertIn("no trade", out)
            os.remove(os.path.join(tmp, "btc15m-signal", "paper_account.json"))
            _capture(bot, tmp, cfg, {"ETH-USD": _moon(), "SOL-USD": _quiet(), "BTC-USD": _quiet()})
            state = json.load(open(os.path.join(tmp, "coinbase-spot-paper", "paper_account.json"), encoding="utf-8"))
            entry = state["open"][0]["entry_price"]
            crashed = [entry * 0.97] * 5
            # Need a real series for evaluate; exit uses the last close.
            quiet = _quiet()
            quiet[-1] = entry * 0.97
            out = _capture(bot, tmp, cfg, {"ETH-USD": quiet, "SOL-USD": _quiet(), "BTC-USD": _quiet()})
            self.assertIn("paper sell ETH-USD stop", out)
            state = json.load(open(os.path.join(tmp, "coinbase-spot-paper", "paper_account.json"), encoding="utf-8"))
            self.assertEqual(state["open"], [])
            self.assertEqual(state["closed"][-1]["exit"], "stop")
            self.assertTrue(os.path.isfile(os.path.join(tmp, "desk_incubation.json")))
            _ = crashed

    def test_card_prefers_feed_down_over_first_z_skip(self):
        """ETH quiet + SOL TimeoutError must densify CARD as data fail (#457)."""
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "coinbase-spot-paper"))
            with open(os.path.join(HERE, "coinbase-spot-paper", "config.json"), encoding="utf-8") as handle:
                cfg = json.load(handle)

            def fetch(product: str):
                if product == "SOL-USD":
                    raise TimeoutError("candle fetch timed out")
                if product == "ETH-USD":
                    return _quiet()
                return _quiet()

            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                bot.run_once(desk_root=tmp, cfg=cfg, fetch=fetch)
            out = buf.getvalue()
            self.assertIn("SKIP SOL-USD data TimeoutError", out)
            self.assertIn("CARD: data TimeoutError", out)
            self.assertNotRegex(out, r"CARD: z .* < ")

    def test_card_densifies_fee_bar_on_z_skip(self):
        """Quiet bars must show the locked ~28% fee-bar need, not a bare z miss."""
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "coinbase-spot-paper"))
            with open(os.path.join(HERE, "coinbase-spot-paper", "config.json"), encoding="utf-8") as handle:
                cfg = json.load(handle)

            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                bot.run_once(
                    desk_root=tmp,
                    cfg=cfg,
                    fetch=lambda product: _quiet(),
                )
            out = buf.getvalue()
            self.assertRegex(out, r"CARD: z .* < 2")
            self.assertIn("15m needs ~28% bar", out)
            self.assertIn("ordinary bars skip", out)
            self.assertIn("no trade", out)

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
