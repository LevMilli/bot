"""Fed Watch compares Polymarket Fed decision odds with the Kalshi ask."""
from __future__ import annotations

import datetime as dt
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

ROOT = os.path.dirname(os.path.abspath(__file__))
TOWER = os.path.join(ROOT, "fed-watch-paper")
if TOWER not in sys.path:
    sys.path.insert(0, TOWER)
import fed_feed  # noqa: E402

NOW = dt.datetime(2026, 11, 12, 18, 0, tzinfo=dt.timezone.utc)


def _bot():
    spec = importlib.util.spec_from_file_location("fed_watch_live", os.path.join(TOWER, "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pm(title, bid, ask, month="December", year=2026):
    return {
        "groupItemTitle": title, "bestBid": bid, "bestAsk": ask, "active": True, "closed": False,
        "question": f"Will ... after the {month} {year} meeting?",
    }


EVENTS = [{
    "slug": "fed-decision-in-december-2026", "title": "Fed Decision in December?",
    "endDate": "2026-12-10T04:59:00Z",
    "markets": [
        _pm("No change", 0.035, 0.038),
        _pm("25 bps increase", 0.86, 0.87),
        _pm("50+ bps increase", 0.09, 0.10),
        _pm("25 bps decrease", 0.002, 0.30),  # too wide, skipped
    ],
}, {"slug": "how-many-fed-rate-cuts-in-2026", "markets": [_pm("No change", 0.4, 0.41)]}]

KALSHI = [
    {"ticker": "KXFEDDECISION-26DEC-H25", "event_ticker": "KXFEDDECISION-26DEC",
     "yes_ask_dollars": "0.7500", "no_ask_dollars": "0.2600"},
    {"ticker": "KXFEDDECISION-26DEC-H0", "event_ticker": "KXFEDDECISION-26DEC",
     "yes_ask_dollars": "0.0500", "no_ask_dollars": "0.9600"},
    {"ticker": "KXFEDDECISION-26DEC-C25", "event_ticker": "KXFEDDECISION-26DEC",
     "yes_ask_dollars": "0.0100", "no_ask_dollars": "1.0000"},
    {"ticker": "KXFEDDECISION-27JUN-H0", "event_ticker": "KXFEDDECISION-27JUN",
     "yes_ask_dollars": "0.5000", "no_ask_dollars": "0.5100"},
]


class ParseTests(unittest.TestCase):
    def test_outcome_and_meeting_names(self):
        self.assertEqual(fed_feed.pm_outcome("No change"), "hold")
        self.assertEqual(fed_feed.pm_outcome("25 bps decrease"), "cut25")
        self.assertEqual(fed_feed.pm_outcome("50+ bps increase"), "hike50")
        self.assertIsNone(fed_feed.pm_outcome("Emergency cut"))
        self.assertEqual(fed_feed.kalshi_meeting("KXFEDDECISION-27MAR"), (2027, 3))
        self.assertEqual(fed_feed.pm_meeting(EVENTS[0], EVENTS[0]["markets"][0]), (2026, 12))
        jan_end = {"title": "Fed Decision in December?", "endDate": "2027-01-01T04:59:00Z"}
        self.assertEqual(fed_feed.pm_meeting(jan_end), (2026, 12))

    def test_pairs_same_meeting_and_outcome_both_sides(self):
        quotes, unmatched = fed_feed.pair_quotes(KALSHI, EVENTS)
        by = {(q["ticker"], q["side"]): q for q in quotes}
        hike = by[("KXFEDDECISION-26DEC-H25", "yes")]
        self.assertAlmostEqual(hike["fair"], 0.865)
        self.assertEqual(hike["ask"], 0.75)
        self.assertAlmostEqual(by[("KXFEDDECISION-26DEC-H25", "no")]["fair"], 0.135)
        # Wide Polymarket cut market and the June meeting with no Polymarket twin are skipped.
        self.assertNotIn(("KXFEDDECISION-26DEC-C25", "yes"), by)
        self.assertEqual(unmatched, 2)
        # The "how many cuts" event is not a meeting decision market.
        self.assertTrue(all(q["pm_slug"].startswith("fed-decision-in-") for q in quotes))


class RunTests(unittest.TestCase):
    def test_live_run_buys_biggest_gap_then_settles(self):
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(fed_feed, "kalshi_open", lambda: KALSHI), \
                mock.patch.object(fed_feed, "polymarket_events", lambda: EVENTS):
            buf = io.StringIO()
            with redirect_stdout(buf):
                bot.run_once(desk_root=tmp, now=NOW)
            self.assertIn("BUY 2026-12 Hike 25 YES", buf.getvalue())
            with open(os.path.join(tmp, "fed-watch-paper", "paper_account.json")) as fh:
                state = json.load(fh)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "fed-watch-paper", "fedwatch_quotes.json")))
        pos = state["open"][0]
        self.assertEqual((pos["kalshi_ticker"], pos["side"]), ("KXFEDDECISION-26DEC-H25", "yes"))
        self.assertEqual(pos["contracts"], 32)  # 25 // (0.75 + 0.02)
        closed = bot.settle_open(state, NOW, fetch=lambda t: {"result": "no"})
        self.assertEqual(closed[0]["payout"], 0.0)
        self.assertAlmostEqual(closed[0]["pnl"], -pos["cost"])
        self.assertEqual(state["open"], [])

    def test_no_side_wins_when_result_is_no(self):
        bot = _bot()
        state = {"cash": 100.0, "open": [{"kalshi_ticker": "X", "side": "no", "contracts": 10, "cost": 9.0}]}
        closed = bot.settle_open(state, NOW, fetch=lambda t: {"result": "no"})
        self.assertEqual(closed[0]["pnl"], 1.0)
        self.assertEqual(state["cash"], 110.0)

    def test_unsettled_rows_stay_open(self):
        bot = _bot()
        state = {"cash": 100.0, "open": [{"kalshi_ticker": "X", "side": "yes", "contracts": 1, "cost": 0.5}]}
        self.assertEqual(bot.settle_open(state, NOW, fetch=lambda t: {"result": ""}), [])
        self.assertEqual(len(state["open"]), 1)

    def test_read_failure_waits(self):
        bot = _bot()

        def boom():
            raise OSError("down")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(fed_feed, "kalshi_open", boom):
            buf = io.StringIO()
            with redirect_stdout(buf):
                bot.run_once(desk_root=tmp, now=NOW)
        self.assertIn("read failed", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
