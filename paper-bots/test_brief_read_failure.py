"""A Kalshi read failure in the morning brief is a skipped card, not a traceback."""
from __future__ import annotations

import datetime as dt
import importlib.util
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(folder, name):
    path = os.path.join(HERE, folder)
    for p in (HERE, os.path.join(HERE, "kalshi-sp500-paper"), path):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(name, os.path.join(path, "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BriefReadFailure(unittest.TestCase):
    def _check(self, folder, name):
        bot = _load(folder, name)
        boom = RuntimeError("Kalshi API read failed after 5 tries (HTTPError)")
        with mock.patch.object(bot.risk_manager, "news_skip_reason", return_value=None), \
             mock.patch.object(bot.risk_manager, "check_can_trade", return_value=(True, "")), \
             mock.patch.object(bot.paper_sim, "trades_on", return_value=[]), \
             mock.patch.object(bot.paper_sim, "realised_pnl_on", return_value=0.0), \
             mock.patch.object(bot.feed, "find_event_for", side_effect=boom), \
             mock.patch("builtins.print"):
            text = bot.step_brief(None, {"bankroll": 100.0}, dt.date(2026, 11, 12))
        self.assertTrue(text.startswith("CARD: Brief skipped."))
        self.assertIn("read failed", text)
        self.assertNotIn("Traceback", text)

    def test_kalshi_sp_brief(self):
        self._check("kalshi-sp500-paper", "sp_brief_fail")

    def test_kalshi_sized_brief(self):
        self._check("kalshi-sized-paper", "sized_brief_fail")
