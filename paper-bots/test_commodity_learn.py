"""Commodity learning keeps one series row per fill. A failsafe is not a hit."""
from __future__ import annotations

import datetime as dt
import importlib.util
import os
import tempfile
import unittest

import desk_profit

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load():
    path = os.path.join(ROOT, "commodity-15m-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("commodity_learn", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NOW = dt.datetime(2026, 11, 11, 18, 0, tzinfo=dt.timezone.utc)
STAMP = "2026-11-11 18:00:00 UTC"


class CommodityLearn(unittest.TestCase):
    def test_one_row_per_fill_and_the_failsafe_is_not_a_hit(self):
        bot = _load()
        pos = {
            "series": "KXBRENT15M",
            "fill_id": "KXBRENT15M|1",
            "fair_at_entry": 0.86,
            "cost": 6.0,
            "side": "YES",
            "exit": "model-flip side YES→NO",
        }
        row = bot.commodity_learning_row(pos, 2.0, STAMP)
        self.assertEqual(row["market"], "KXBRENT15M")
        self.assertEqual(row["reason"], "model-flip")
        self.assertNotIn("result", row)
        settled = bot.commodity_learning_row(
            dict(pos, fill_id="KXBRENT15M|2", exit="settled"), 2.0, STAMP,
        )
        self.assertEqual(settled["result"], "hit")
        self.assertEqual(settled["reason"], "settled")
        self.assertEqual(settled["market"], "KXBRENT15M")
        with tempfile.TemporaryDirectory() as tmp:
            bot.DESK_ROOT = tmp
            self.assertEqual(bot.tell_commodity_learning(pos, 2.0, STAMP), "recorded")
            self.assertEqual(bot.tell_commodity_learning(pos, 2.0, STAMP), "duplicate")
            rows = bot._desk().load_learning(tmp)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["market"], "KXBRENT15M")
        self.assertEqual(rows[0]["reason"], "model-flip")
        self.assertNotIn("result", rows[0])
        lost = [{
            "series": "KXBRENT15M",
            "side": "YES",
            "fair_at_entry": 0.86,
            "pnl": -4.0,
            "closed": STAMP,
            "exit": "model-flip side YES→NO",
        }]
        skip = bot.commodity_same_day_skip(lost, "KXBRENT15M", 0.86, "YES", NOW)
        self.assertIn("KXBRENT15M", skip)
        self.assertEqual(
            bot.commodity_same_day_skip(lost, "KXGOLD15M", 0.86, "YES", NOW),
            "",
        )
        self.assertEqual(bot.decide_floor(0.01), 0.05)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_commodity15m"], 0.05)


if __name__ == "__main__":
    unittest.main()
