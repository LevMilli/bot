"""Nine paper shadows log a public book and buy nothing. No network."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_profit
import desk_roi_plan
import pimp_desk
import shadow_missing


LOCKED = {
    "kalshi_sports": 0.06,
    "kalshi_btc15m": 0.05,
    "kalshi_commodity15m": 0.05,
    "kalshi_inx": 0.02,
    "solana_dex": 0.02,
    "coinbase_spot": 0.05,
}


def _load(folder):
    path = os.path.join(HERE, folder, "bot.py")
    spec = importlib.util.spec_from_file_location(folder.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _checker():
    path = os.path.join(HERE, "tools", "new_tower.py")
    spec = importlib.util.spec_from_file_location("new_tower_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.check_tower


class ShadowMissingTests(unittest.TestCase):
    def test_floors_stay_locked_and_no_new_key(self):
        for key, floor in LOCKED.items():
            self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE[key], floor)
        self.assertNotIn("mentions", desk_profit.DEFAULT_VENUE_MIN_EDGE)
        self.assertNotIn("polymarket_mentions", desk_profit.DEFAULT_VENUE_MIN_EDGE)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_econ"], 0.05)
        self.assertFalse(desk_roi_plan.LIVE_ORDERS_ENABLED)
        self.assertFalse(pimp_desk.LIVE_SWITCH_BUILT)
        self.assertEqual(len(shadow_missing.TOWERS), 9)

    def test_each_logger_buys_nothing_and_does_not_say_the_repo(self):
        absent = {"commodity-calendar", "btc-options"}
        for spec in shadow_missing.TOWERS:
            with self.subTest(spec["id"]):
                _load(spec["folder"])
                with tempfile.TemporaryDirectory() as tmp:
                    buf = io.StringIO()
                    with redirect_stdout(buf):
                        shadow_missing.run_once(spec["id"], desk_root=tmp, fetch=False)
                    out = buf.getvalue()
                    self.assertIn("SIGNAL: SKIP", out)
                    self.assertNotIn("not in the repo", out)
                    self.assertIn("no trade", out)
                    self.assertNotIn("BUY", out)
                    tower = os.path.join(tmp, spec["folder"])
                    with open(os.path.join(tower, "paper_account.json"), encoding="utf-8") as handle:
                        state = json.load(handle)
                    self.assertEqual(state["cash"], 0.0)
                    self.assertEqual(state["open"], [])
                    self.assertEqual(state["closed"], [])
                    self.assertEqual(state["buys"], 0)
                    self.assertEqual(state["stake_usd"], 0.0)
                    self.assertIsNone(state["fair"])
                    self.assertIsNone(state["fill"])
                    self.assertEqual(state["ticker_missing"], spec["id"] in absent)
                    self.assertTrue(state["shadow_only"])
                    self.assertFalse(state["live_orders"])
                    if spec["id"] in absent:
                        self.assertIn("does not list", out)
                    else:
                        self.assertIn("Listed", out)
                        self.assertIn("No fill", out)
                    with open(os.path.join(tower, "evidence.jsonl"), encoding="utf-8") as handle:
                        evidence = [json.loads(line) for line in handle if line.strip()]
                    self.assertEqual(len(evidence), 1)
                    self.assertFalse(evidence[0]["counts_as_evidence"])
                    self.assertEqual(evidence[0]["buys"], 0)
                    self.assertIsNone(evidence[0]["fair"])
                    self.assertIsNone(evidence[0]["fill"])
                    with redirect_stdout(io.StringIO()):
                        shadow_missing.run_once(spec["id"], desk_root=tmp, fetch=False)
                    with open(os.path.join(tower, "evidence.jsonl"), encoding="utf-8") as handle:
                        again = [line for line in handle if line.strip()]
                    self.assertEqual(len(again), 1)

    def test_known_series_are_not_borrowed(self):
        spread = shadow_missing.evaluate("point-spread")
        self.assertIn("KXNFLGAME", spread["rejected_series"])
        self.assertEqual(spread["series"], list(shadow_missing.SPREAD_SERIES))
        self.assertNotIn("KXNFLGAME", spread["series"])
        self.assertEqual(spread["spread_cap"], 0.05)
        self.assertEqual(spread["floor"], 0.06)
        self.assertIsNone(spread["fair"])
        self.assertIsNone(spread["fill"])
        self.assertEqual(spread["buys"], 0)
        total = shadow_missing.evaluate("game-total")
        self.assertEqual(total["series"], list(shadow_missing.TOTAL_SERIES))
        self.assertNotIn("KXNFLGAME", total["series"])
        props = shadow_missing.evaluate("player-props")
        self.assertEqual(props["series"], list(shadow_missing.PROP_SERIES))
        self.assertNotIn("KXNFLGAME", props["series"])
        period = shadow_missing.evaluate("period-winner")
        self.assertEqual(period["series"], list(shadow_missing.PERIOD_SERIES))
        self.assertFalse(period["ticker_missing"])
        ucl = shadow_missing.evaluate("champions-league")
        self.assertEqual(ucl["series"], ["KXUCLGAME"])
        self.assertFalse(ucl["ticker_missing"])
        self.assertFalse(ucl["buys_favorite"])
        esports = shadow_missing.evaluate("esports-match")
        self.assertEqual(esports["series"], list(shadow_missing.ESPORTS_SERIES))
        self.assertNotIn("KXUFCFIGHT", esports["series"])
        self.assertFalse(esports["ticker_missing"])
        self.assertFalse(esports["buys_favorite"])

    def test_commodity_calendar_does_not_inherit_the_ladder(self):
        row = shadow_missing.evaluate("commodity-calendar")
        self.assertEqual(row["front_symbols"], ["CL=F", "GC=F"])
        self.assertIn("KXGOLD15M", row["rejected_series"])
        self.assertIn("KXWTI15M", row["rejected_series"])
        self.assertTrue(row["ticker_missing"])
        self.assertIsNone(row["commission"])
        self.assertIn("does not list a WTI or gold calendar-spread series", row["reason"])
        self.assertNotIn("not in the repo", row["reason"])
        self.assertNotIn("KXWTI", row["series"])
        self.assertNotIn("KXGOLD15M", row["series"])
        self.assertTrue(row["binary_floor_not_a_fee"])
        self.assertFalse(row["inherits_15m_ladder"])
        self.assertEqual(row["stake_usd"], 0.0)
        self.assertEqual(row["floor"], 0.05)
        self.assertNotEqual(row["stake_usd"], 6.0)
        self.assertNotEqual(row["stake_usd"], 15.0)
        cfg = shadow_missing.locked_cfg(
            shadow_missing.spec_for("commodity-calendar"),
            {"stake_usd": 15, "venue_min_edge": 0.02, "live_orders": True},
        )
        self.assertEqual(cfg["stake_usd"], 0.0)
        self.assertGreaterEqual(cfg["venue_min_edge"], 0.05)
        self.assertFalse(cfg["live_orders"])

    def test_btc_options_refuses_the_fifteen_minute_series(self):
        row = shadow_missing.evaluate("btc-options")
        self.assertEqual(set(row["rejected_series"]), {"KXBTC15M", "KXETH15M", "KXBTCD"})
        self.assertEqual(row["series"], [])
        self.assertTrue(row["ticker_missing"])
        self.assertIn("does not list a BTC options series", row["reason"])
        self.assertNotIn("not in the repo", row["reason"])
        self.assertIsNone(row["commission"])
        self.assertIsNone(row["implied"])
        self.assertIsNone(row["realized"])
        self.assertIsNone(row["gap"])
        self.assertEqual(row["sells"], 0)
        self.assertTrue(row["binary_floor_not_a_fee"])
        forced = shadow_missing.evaluate("btc-options", registry={
            "assignments": {"BTC_OPTIONS_SERIES": ["KXBTC15M"]},
        })
        self.assertEqual(forced["series"], [])
        self.assertTrue(forced["ticker_missing"])
        self.assertEqual(forced["buys"], 0)
        self.assertIsNone(forced["fair"])

    def test_mentions_use_the_repo_taker_and_clear_005(self):
        row = shadow_missing.evaluate("polymarket-mentions")
        self.assertEqual(row["taker_rate"], desk_roi_plan.POLYMARKET_TAKER_RATE["mentions"])
        self.assertEqual(row["taker_rate"], 0.04)
        self.assertEqual(row["floor"], 0.05)
        self.assertNotEqual(row["floor"], desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"])
        self.assertNotEqual(row["floor"], desk_profit.DEFAULT_VENUE_MIN_EDGE["solana_dex"])
        self.assertEqual(row["series"], ["mention-markets"])
        self.assertFalse(row["ticker_missing"])
        self.assertFalse(row["buys_favorite"])
        self.assertIsNone(row["fair"])
        self.assertIn("No fill", row["reason"])
        named = shadow_missing.evaluate("polymarket-mentions", registry={
            "assignments": {"MENTION_MARKETS": ["mention-transcript-1"]},
        })
        self.assertEqual(named["series"], ["mention-transcript-1"])
        self.assertFalse(named["ticker_missing"])
        self.assertEqual(named["buys"], 0)
        self.assertEqual(named["stake_usd"], 0.0)
        self.assertIsNone(named["fair"])
        self.assertIsNone(named["fill"])
        self.assertIn("No fill", named["reason"])
        self.assertNotIn("mention-markets", named["series"])

    def test_a_named_series_still_buys_nothing(self):
        row = shadow_missing.evaluate("point-spread", registry={
            "assignments": {"SPREAD_SERIES": ["KXTESTSPREAD"]},
        })
        self.assertEqual(row["series"], ["KXTESTSPREAD"])
        self.assertFalse(row["ticker_missing"])
        self.assertEqual(row["buys"], 0)
        self.assertIsNone(row["fair"])
        self.assertIsNone(row["fill"])
        self.assertIsNone(row["edge"])
        borrowed = shadow_missing.evaluate("point-spread", registry={
            "assignments": {"SPREAD_SERIES": ["KXNFLGAME"]},
        })
        self.assertEqual(borrowed["series"], [])
        self.assertTrue(borrowed["ticker_missing"])
        self.assertNotIn("KXNFLSPREAD", borrowed["series"])

    def test_a_stub_book_is_logged_and_buys_nothing(self):
        def opener(url):
            if "series_ticker=KXNFLSPREAD" in url:
                return json.dumps({"markets": [{
                    "ticker": "KXNFLSPREAD-26NOV16LACBAL-LAC8",
                    "yes_bid_dollars": "0.1200",
                    "yes_ask_dollars": "0.1400",
                }]}).encode()
            if "/series/" in url:
                name = url.rstrip("/").rsplit("/", 1)[-1]
                return json.dumps({"series": {"ticker": name, "title": "listed"}}).encode()
            return json.dumps({"markets": []}).encode()

        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            with redirect_stdout(buf):
                shadow_missing.run_once("point-spread", desk_root=tmp, opener=opener)
            out = buf.getvalue()
            self.assertIn("KXNFLSPREAD-26NOV16LACBAL-LAC8", out)
            self.assertIn("bid 0.12", out)
            self.assertIn("ask 0.14", out)
            self.assertIn("No fill", out)
            self.assertNotIn("BUY", out)
            self.assertNotIn("not in the repo", out)
            self.assertIn("no trade", out)
            with open(os.path.join(tmp, "point-spread-paper", "paper_account.json"), encoding="utf-8") as handle:
                state = json.load(handle)
            self.assertEqual(state["buys"], 0)
            self.assertEqual(state["stake_usd"], 0.0)
            self.assertEqual(state["cash"], 0.0)
            self.assertIsNone(state["fair"])
            self.assertIsNone(state["fill"])
            self.assertFalse(state["live_orders"])
            self.assertFalse(state["ticker_missing"])
            self.assertGreater(state["book_n"], 0)

    def test_calendar_and_options_searches_do_not_adopt_the_wrong_book(self):
        def calendar(url):
            self.assertNotIn("KXINXU", url)
            return json.dumps({"current_page": [
                {"series_ticker": "KXWTI", "series_title": "WTI oil on day"},
                {"series_ticker": "KXGOLD15M", "series_title": "Gold 15-minute"},
                {"series_ticker": "KXWTI15M", "series_title": "WTI 15-minute"},
                {"series_ticker": "KXGOLDMON", "series_title": "Gold Monthly Price"},
            ]}).encode()

        def options(url):
            return json.dumps({"current_page": [
                {"series_ticker": "KXBTC15M", "series_title": "Bitcoin 15 minute options"},
                {"series_ticker": "KXBTCD", "series_title": "Bitcoin options above/below"},
                {"series_ticker": "KXETH15M", "series_title": "Ethereum 15 minute options"},
                {"series_ticker": "KXPUBLICOPTIONHOUSE", "series_title": "House passage of a public health insurance option"},
                {"series_ticker": "KXBTCMINMON", "series_title": "BTC one touch minimum"},
            ]}).encode()

        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            with redirect_stdout(buf):
                shadow_missing.run_once("commodity-calendar", desk_root=tmp, opener=calendar)
            out = buf.getvalue()
            self.assertIn("does not list a WTI or gold calendar-spread series", out)
            self.assertNotIn("KXWTI", out)
            self.assertNotIn("KXGOLD15M", out)
            self.assertNotIn("BUY", out)
            row = shadow_missing.evaluate(
                "commodity-calendar",
                book=shadow_missing.load_public_book(
                    shadow_missing.spec_for("commodity-calendar"), {}, calendar,
                ),
            )
            self.assertEqual(row["series"], [])
            self.assertTrue(row["ticker_missing"])
            self.assertEqual(row["buys"], 0)

        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            with redirect_stdout(buf):
                shadow_missing.run_once("btc-options", desk_root=tmp, opener=options)
            out = buf.getvalue()
            self.assertIn("does not list a BTC options series", out)
            self.assertNotIn("KXBTC15M", out)
            self.assertNotIn("KXBTCD", out)
            self.assertNotIn("BUY", out)
            self.assertEqual(shadow_missing.evaluate("btc-options")["sells"], 0)

    def test_polymarket_stub_logs_the_mention_slug(self):
        slug = "will-cisco-say-ai-25-during-earnings-call-november-12"

        def opener(url):
            self.assertIn("tag_slug=mention-markets", url)
            self.assertNotIn("kalshi", url)
            return json.dumps([{
                "slug": "what-will-cisco-say",
                "closed": False,
                "markets": [{
                    "slug": slug,
                    "closed": False,
                    "bestBid": 0.966,
                    "bestAsk": 0.98,
                }],
            }]).encode()

        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            with redirect_stdout(buf):
                shadow_missing.run_once("polymarket-mentions", desk_root=tmp, opener=opener)
            out = buf.getvalue()
            self.assertIn(slug, out)
            self.assertIn("No fill", out)
            self.assertNotIn("BUY", out)
            self.assertNotIn("not in the repo", out)
            with open(os.path.join(tmp, "polymarket-mentions-paper", "paper_account.json"), encoding="utf-8") as handle:
                state = json.load(handle)
            self.assertEqual(state["buys"], 0)
            self.assertEqual(state["stake_usd"], 0.0)
            self.assertIsNone(state["fair"])
            self.assertFalse(state["live_orders"])
            self.assertEqual(state["series"], ["mention-markets"])

    def test_desk_rows_are_shadows_without_a_stake(self):
        for spec in shadow_missing.TOWERS:
            with self.subTest(spec["id"]):
                bot_id = spec["id"]
                row = next(item for item in pimp_desk.BOTS if item["id"] == bot_id)
                self.assertTrue(row["shadow_only"])
                self.assertNotIn(bot_id, pimp_desk.DEFAULTS["tower_risk_budgets"])
                plans = pimp_desk.BOT_PLANS[bot_id]
                self.assertTrue(plans["entry_gated"])
                self.assertEqual(plans["exit_quality"], "partial")
                self.assertEqual(plans["stake"], "none")
                self.assertIn("does not buy", " ".join(plans["buy"]).lower())
                self.assertEqual(pimp_desk.TOWER_STARTER_CASH[bot_id], 0.0)
                self.assertEqual(pimp_desk.ACTIONS[bot_id]["run"]["entry"], False)
                self.assertEqual(desk_profit.bot_venue_edge(bot_id), spec["floor"])
                check = _checker()(bot_id)
                self.assertTrue(check["ok"], check)
                self.assertTrue(check["shadow_only"])
                self.assertEqual(check["venue"], spec["venue"])

    def test_existing_buy_rules_are_untouched(self):
        sports = " ".join(pimp_desk.BOT_PLANS["sports-gap"]["buy"])
        self.assertIn("ESPN game matched to a Kalshi series", sports)
        commodity = " ".join(pimp_desk.BOT_PLANS["commodity-15m"]["buy"])
        self.assertIn("kalshi_commodity15m", commodity)
        meme = " ".join(pimp_desk.BOT_PLANS["memecoin"]["buy"])
        self.assertIn("Entries refused until taxed EV", meme)
        btc = " ".join(pimp_desk.BOT_PLANS["btc15m"]["buy"])
        self.assertIn("KXBTC15M", btc)
        exclusive = " ".join(pimp_desk.BOT_PLANS["exclusive-set"]["buy"])
        self.assertIn("mutually exclusive Kalshi set", exclusive)
        self.assertIn("does not buy", exclusive.lower())

    def test_snapshot_is_flat(self):
        snap = pimp_desk.snapshot(HERE)
        desk_ids = [bot["id"] for bot in snap["bots"] if not bot.get("shadow_only")]
        for spec in shadow_missing.TOWERS:
            row = next(bot for bot in snap["bots"] if bot["id"] == spec["id"])
            self.assertTrue(row["shadow_only"])
            self.assertEqual(row["cash"], 0.0)
            self.assertEqual(row["positions"], [])
            self.assertEqual(row["open_count"], 0)
            self.assertEqual(row["sizing_mode"], "none")
            self.assertEqual(row["capital_weight"], 0)
            self.assertNotIn(spec["id"], desk_ids)
            flat = {
                "id": spec["id"], "present": True, "open_count": 0,
                "cash": 0.0, "today": 0.0, "realized": 0.0, "history": [],
            }
            self.assertTrue(pimp_desk.tower_doing_good(flat))
            self.assertFalse(pimp_desk.tower_needs_midnight_reload(flat))


if __name__ == "__main__":
    unittest.main()
