"""Sports Sharp Lag reads Pinnacle via The Odds API and pairs it with Kalshi."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.abspath(__file__))
TOWER = os.path.join(ROOT, "sports-sharp-lag-paper")
if TOWER not in sys.path:
    sys.path.insert(0, TOWER)
import odds_feed  # noqa: E402

NOW = dt.datetime(2026, 11, 16, 18, 0, tzinfo=dt.timezone.utc)


def _bot():
    spec = importlib.util.spec_from_file_location("sharp_lag_live", os.path.join(TOWER, "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _odds_event(home="Minnesota Timberwolves", away="Portland Trail Blazers", hp=1.50, ap=2.80,
                start="2026-11-17T01:00:00Z"):
    return {
        "commence_time": start, "home_team": home, "away_team": away,
        "bookmakers": [{"key": "pinnacle", "markets": [{"key": "h2h", "last_update": "x", "outcomes": [
            {"name": home, "price": hp}, {"name": away, "price": ap}]}]}],
    }


def _kalshi(home_ask="0.55", away_ask="0.40"):
    ev = "KXNBAGAME-26NOV16PORMIN"
    exp = "2026-11-17T04:00:00Z"
    return [
        {"event_ticker": ev, "ticker": ev + "-MIN", "yes_sub_title": "Minnesota",
         "yes_ask_dollars": home_ask, "expected_expiration_time": exp},
        {"event_ticker": ev, "ticker": ev + "-POR", "yes_sub_title": "Portland",
         "yes_ask_dollars": away_ask, "expected_expiration_time": exp},
    ]


class NameAndPriceTests(unittest.TestCase):
    def test_team_names_fit_on_word_boundaries(self):
        self.assertTrue(odds_feed.team_fits("Golden State", "Golden State Warriors"))
        self.assertTrue(odds_feed.team_fits("Kent St.", "Kent State Golden Flashes"))
        self.assertTrue(odds_feed.team_fits("Los Angeles L", "Los Angeles Lakers"))
        self.assertFalse(odds_feed.team_fits("Los Angeles C", "Los Angeles Lakers"))
        self.assertFalse(odds_feed.team_fits("Texas", "Texas Tech Red Raiders"))
        self.assertFalse(odds_feed.team_fits("Michigan", "Michigan State Spartans"))
        self.assertFalse(odds_feed.team_fits("Texas", "Texas A&M Aggies"))
        self.assertFalse(odds_feed.team_fits("Kent", "Kentucky Wildcats"))

    def test_devig_removes_the_cut(self):
        a, b = odds_feed.devig(1.50, 2.80)
        self.assertAlmostEqual(a + b, 1.0)
        self.assertAlmostEqual(a, (1 / 1.5) / (1 / 1.5 + 1 / 2.8))

    def test_three_way_lines_are_skipped(self):
        ev = _odds_event()
        ev["bookmakers"][0]["markets"][0]["outcomes"].append({"name": "Draw", "price": 4.0})
        self.assertIsNone(odds_feed.book_fairs(ev))

    def test_pairs_each_side_with_its_kalshi_ask(self):
        quotes, unmatched = odds_feed.pair_quotes("NBA", [_odds_event()], _kalshi(), NOW)
        self.assertEqual(unmatched, 0)
        by = {q["side"]: q for q in quotes}
        self.assertEqual(by["home"]["ticker"], "KXNBAGAME-26NOV16PORMIN-MIN")
        self.assertEqual(by["home"]["ask"], 0.55)
        self.assertAlmostEqual(by["home"]["sharp_fair"] + by["away"]["sharp_fair"], 1.0, places=3)

    def test_started_games_and_other_days_are_not_used(self):
        live = _odds_event(start="2026-11-16T17:00:00Z")
        self.assertEqual(odds_feed.pair_quotes("NBA", [live], _kalshi(), NOW)[0], [])
        other_day = _odds_event(start="2026-11-18T01:00:00Z")
        quotes, unmatched = odds_feed.pair_quotes("NBA", [other_day], _kalshi(), NOW)
        self.assertEqual((quotes, unmatched), ([], 1))

    def test_refresh_slows_down_to_make_credits_last(self):
        with mock.patch.dict(os.environ, {"ODDS_REFRESH_MINUTES": "30", "ODDS_API_MIN_LEFT": "25"}):
            self.assertEqual(odds_feed.refresh_minutes(100000, 4, NOW), 30)
            slow = odds_feed.refresh_minutes(500, 4, NOW)
        # ~14.25 days left, 4 leagues, 475 usable credits -> about every 2.9 hours.
        self.assertGreater(slow, 150)
        self.assertLess(slow, 200)


class LiveQuoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def _kalshi(self, series):
        return _kalshi() if series == "KXNBAGAME" else []

    def _odds(self, sport, key, book):
        self.calls.append(sport)
        return [_odds_event()], 480.0

    def test_no_key_means_no_calls(self):
        with mock.patch.dict(os.environ, {"ODDS_API_KEY": ""}):
            quotes, status = odds_feed.live_quotes(self.tmp.name, NOW, kalshi=self._kalshi, odds=self._odds)
        self.assertEqual((quotes, status["state"]), ([], "no_key"))
        self.assertEqual(self.calls, [])

    def test_only_leagues_with_games_soon_spend_a_credit_and_cache_holds(self):
        with mock.patch.dict(os.environ, {"ODDS_API_KEY": "k"}):
            quotes, status = odds_feed.live_quotes(self.tmp.name, NOW, kalshi=self._kalshi, odds=self._odds)
            self.assertEqual(self.calls, ["basketball_nba"])
            self.assertEqual(len(quotes), 2)
            self.assertEqual(status["remaining"], 480.0)
            later = NOW + dt.timedelta(minutes=10)
            again, _ = odds_feed.live_quotes(self.tmp.name, later, kalshi=self._kalshi, odds=self._odds)
        self.assertEqual(self.calls, ["basketball_nba"])  # cached, no second credit
        self.assertEqual(len(again), 2)

    def test_low_credits_stop_calling(self):
        with open(os.path.join(self.tmp.name, odds_feed.CACHE), "w") as fh:
            json.dump({"remaining": 10, "leagues": {}}, fh)
        with mock.patch.dict(os.environ, {"ODDS_API_KEY": "k"}):
            _q, status = odds_feed.live_quotes(self.tmp.name, NOW, kalshi=self._kalshi, odds=self._odds)
        self.assertEqual(self.calls, [])
        self.assertEqual(status["state"], "low_credits")


class SharpLagRunTests(unittest.TestCase):
    def test_buy_then_settle_on_the_kalshi_result(self):
        bot = _bot()
        state = {"cash": 500.0, "open": [], "closed": []}
        with tempfile.TemporaryDirectory() as tmp:
            quotes = [{"game": "POR @ MIN HOME", "ticker": "KXNBAGAME-26NOV16PORMIN-MIN",
                       "sharp_fair": 0.66, "ask": 0.55, "league": "NBA", "source": "pinnacle"}]
            bot.run_once(desk_root=tmp, quotes=quotes, now=NOW)
            with open(os.path.join(tmp, "sports-sharp-lag-paper", "paper_account.json")) as fh:
                state = json.load(fh)
        pos = state["open"][0]
        self.assertEqual(pos["kalshi_ticker"], "KXNBAGAME-26NOV16PORMIN-MIN")
        closed = bot.settle_open(state, NOW, fetch=lambda t: {"result": "yes"})
        self.assertEqual(closed[0]["payout"], float(pos["contracts"]))
        self.assertEqual(state["open"], [])
        self.assertAlmostEqual(state["cash"], 500.0 - pos["cost"] + pos["contracts"], places=2)

    def test_waiting_card_names_the_missing_key(self):
        bot = _bot()
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"ODDS_API_KEY": ""}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                bot.run_once(desk_root=tmp, now=NOW)
        self.assertIn("ODDS_API_KEY", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
