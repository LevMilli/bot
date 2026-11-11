"""Commodity buy writes the model-flip intent before cash. It does not average an open series."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import tempfile
import unittest

import desk_more
import desk_profit
import desk_roi_plan

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load():
    path = os.path.join(ROOT, "commodity-15m-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("commodity_buy", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Desk:
    def load_settings(self, root):
        return {}

    def correlation_blocks(self, *args, **kwargs):
        return ""

    def stake_dollars_for(self, *args, **kwargs):
        return 15.0, {"notes": []}

    def contracts_for_stake(self, per, stake):
        return 4


class CommodityBuy(unittest.TestCase):
    def setUp(self):
        self.bot = _load()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "buy_intent.json")
        self._old_intent = self.bot.BUY_INTENT
        self.bot.BUY_INTENT = self.path
        self.bot.save_account = lambda state: None
        self.bot.commodity_learning_block = lambda *args, **kwargs: ""
        self.bot._desk = lambda: _Desk()
        self._cool = desk_roi_plan.adverse_cool_blocks
        self._stale = desk_roi_plan.stale_world_blocks
        self._revenge = desk_roi_plan.anti_revenge_blocks
        self._budget = desk_more.tower_budget_remaining
        desk_roi_plan.adverse_cool_blocks = lambda *args, **kwargs: ""
        desk_roi_plan.stale_world_blocks = lambda *args, **kwargs: ""
        desk_roi_plan.anti_revenge_blocks = lambda *args, **kwargs: ""
        desk_more.tower_budget_remaining = lambda *args, **kwargs: {"left": 100.0}

    def tearDown(self):
        self.bot.BUY_INTENT = self._old_intent
        desk_roi_plan.adverse_cool_blocks = self._cool
        desk_roi_plan.stale_world_blocks = self._stale
        desk_roi_plan.anti_revenge_blocks = self._revenge
        desk_more.tower_budget_remaining = self._budget
        self.tmp.cleanup()

    def _ev(self, series="KXGOLD15M", ticker="KXGOLD15M-TEST"):
        return {
            "ticker": ticker,
            "series": series,
            "side": "YES",
            "ask": 0.80,
            "fee": 0.01,
            "p": 0.90,
            "edge": 0.08,
            "close_time": dt.datetime(2026, 11, 11, 18, 15, tzinfo=dt.timezone.utc),
        }

    def test_intent_names_the_exit_and_the_series(self):
        written = self.bot.write_buy_intent(
            fill_id="KXGOLD15M-T|1",
            ticker="KXGOLD15M-T",
            series="KXGOLD15M",
            side="YES",
            contracts=4,
            stake=3.24,
            ask=0.80,
        )
        self.assertEqual(written["exit_rule"], "commodity model-flip KXGOLD15M")
        self.assertEqual(written["series"], "KXGOLD15M")
        self.assertTrue(written["paper_only"])
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_commodity15m"], 0.05)
        with self.assertRaises(ValueError):
            self.bot.write_buy_intent(
                fill_id="x", ticker="x", series="KXGOLD15M",
                side="YES", contracts=1, stake=1, ask=0,
            )
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["fill_id"], "KXGOLD15M-T|1")

    def test_intent_is_written_before_cash_and_a_red_day_skip_writes_nothing(self):
        state = {"cash": 100.0, "open": [], "closed": []}
        seen = {}
        real = self.bot.write_buy_intent

        def _wrapped(**kwargs):
            seen["cash"] = state["cash"]
            return real(**kwargs)

        self.bot.write_buy_intent = _wrapped
        msg = self.bot.paper_buy(state, self._ev(), 0)
        self.assertTrue(msg.startswith("Paper buy"))
        self.assertEqual(seen["cash"], 100.0)
        self.assertLess(state["cash"], 100.0)
        with open(self.path, encoding="utf-8") as handle:
            saved = json.load(handle)
        self.assertEqual(saved["exit_rule"], "commodity model-flip KXGOLD15M")
        self.assertEqual(state["open"][0]["exit_rule"], saved["exit_rule"])
        self.assertEqual(state["open"][0]["contracts"], 4)

        os.remove(self.path)
        red = {
            "cash": 100.0,
            "open": [],
            "closed": [{
                "series": "KXGOLD15M",
                "side": "YES",
                "fair_at_entry": 0.84,
                "pnl": -10.0,
                "closed": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            }],
        }
        skip = self.bot.paper_buy(red, self._ev("KXSILVER15M", "KXSILVER15M-TEST"), 1)
        self.assertEqual(skip, "one new buy on a red day")
        self.assertEqual(red["cash"], 100.0)
        self.assertFalse(os.path.exists(self.path))

    def test_open_series_is_not_averaged_and_abandoned_intent_adds_nothing(self):
        state = {
            "cash": 100.0,
            "open": [{
                "series": "KXBRENT15M",
                "ticker": "KXBRENT15M-OLD",
                "contracts": 5,
                "fill_id": "old",
            }],
            "closed": [],
        }
        msg = self.bot.paper_buy(state, self._ev("KXBRENT15M", "KXBRENT15M-NEW"), 0)
        self.assertEqual(msg, "do not add a contract to average an open series")
        self.assertEqual(state["open"][0]["contracts"], 5)
        self.assertEqual(state["cash"], 100.0)
        self.assertFalse(os.path.exists(self.path))

        self.bot.write_buy_intent(
            fill_id="missing",
            ticker="KXGOLD15M-T",
            series="KXGOLD15M",
            side="YES",
            contracts=1,
            stake=1,
            ask=0.8,
        )
        book = {"cash": 100.0, "open": [], "closed": []}
        self.assertEqual(self.bot.reconcile_buy_intent(book), "abandoned")
        self.assertEqual(book["open"], [])
        self.assertEqual(book["closed"], [])


if __name__ == "__main__":
    unittest.main()
