"""Commodity 2.0R day ends at America/Chicago midnight, not 6:00 PM CT."""
from __future__ import annotations

import datetime as dt
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_commodity():
    path = os.path.join(HERE, "commodity-15m-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("commodity_15m_bot_chicago_day", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _utc(text: str) -> dt.datetime:
    return dt.datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)


class CommodityChicagoDay(unittest.TestCase):
    def test_evening_close_stays_on_the_chicago_day(self):
        cbot = _load_commodity()
        # 00:30 UTC Nov 11 is 6:30 PM CT Nov 10. UTC date has already rolled.
        now = _utc("2026-11-11 00:30:00")
        closed = [
            {"closed": "2026-11-11 00:30:00 UTC", "pnl": 40.0},
            {"closed": "2026-11-10 18:00:00 UTC", "pnl": 4.0},  # noon CT Nov 10
            {"closed": "2026-11-10 04:00:00 UTC", "pnl": 9.0},  # 10:00 PM CT Nov 9
        ]
        self.assertEqual(cbot.chicago_day_label(now), "2026-11-10")
        self.assertEqual(cbot.sum_chicago_today_pnl(closed, now), 44.0)

    def test_day_resets_at_chicago_midnight(self):
        cbot = _load_commodity()
        # 06:00 UTC Nov 11 is midnight CT Nov 11.
        now = _utc("2026-11-11 06:00:00")
        closed = [
            {"closed": "2026-11-11 00:30:00 UTC", "pnl": 40.0},
            {"closed": "2026-11-11 06:15:00 UTC", "pnl": 3.0},
        ]
        self.assertEqual(cbot.chicago_day_label(now), "2026-11-11")
        self.assertEqual(cbot.sum_chicago_today_pnl(closed, now), 3.0)

    def test_budget_and_sizing_untouched(self):
        import desk_profit
        import desk_roi_plan
        cbot = _load_commodity()
        self.assertEqual(float(desk_roi_plan.DAILY_R_BUDGET["commodity-15m"]), 2.0)
        self.assertEqual(float(desk_roi_plan.DAILY_R_USD), 20.0)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_commodity15m"], 0.05)
        self.assertEqual(cbot.CONF_STAKE_LO, 6.0)
        self.assertEqual(cbot.CONF_STAKE_HI, 15.0)
        self.assertEqual(cbot.confidence_target(0.85), 10.5)
        # WTI/Brent "closed today" still uses the UTC tag. This change is the 2.0R day only.
        with open(os.path.join(HERE, "commodity-15m-paper", "bot.py"), encoding="utf-8") as handle:
            src = handle.read()
        hair = src.split("WTI↔Brent series haircut", 1)[1].split("contracts = desk.contracts_for_stake", 1)[0]
        self.assertIn('dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")', hair)


if __name__ == "__main__":
    unittest.main()
