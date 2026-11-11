"""Exclusive-set shadow logs Kalshi baskets and buys nothing. No network."""
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


def _bot():
    path = os.path.join(HERE, "exclusive-set-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("exclusive_set_bot", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _market(event, ticker, ask, series, source="public"):
    return {
        "event_ticker": event,
        "ticker": ticker,
        "series_ticker": series,
        "yes_ask_dollars": ask,
        "source": source,
    }


class ExclusiveSetTests(unittest.TestCase):
    def test_floors_are_sports_and_other_not_inx(self):
        bot = _bot()
        self.assertEqual(bot.sports_floor(), 0.06)
        self.assertEqual(bot.other_floor(), 0.05)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_sports"], 0.06)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"], 0.02)
        self.assertNotEqual(bot.other_floor(), desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"])
        self.assertEqual(desk_profit.bot_venue_edge("exclusive-set"), 0.06)
        cfg = bot.locked_cfg({"sports_floor": 0.02, "other_floor": 0.02, "stake_usd": 25})
        self.assertGreaterEqual(cfg["sports_floor"], 0.06)
        self.assertGreaterEqual(cfg["other_floor"], 0.05)
        self.assertEqual(cfg["stake_usd"], 0.0)
        self.assertFalse(cfg["live_orders"])
        self.assertTrue(cfg["shadow_only"])
        for price in (0.40, 0.44, 0.46, 0.47, 0.50, 0.90):
            self.assertEqual(bot.kalshi_fee(price), desk_roi_plan.estimate_kalshi_fee(price, 1.0))

    def test_sports_series_match_the_game_book(self):
        bot = _bot()
        path = os.path.join(HERE, "sports-gap-paper", "gap_bot.py")
        spec = importlib.util.spec_from_file_location("gap_bot_series", path)
        gap = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gap)
        self.assertEqual(set(bot.SPORTS_SERIES), {row[1] for row in gap.SPORTS.values()})

    def test_sports_clear_other_clear_and_inx_sized_edge_does_not(self):
        bot = _bot()
        sports = bot.score_basket("KXNFLGAME-1", [
            _market("KXNFLGAME-1", "KXNFLGAME-1-H", 0.40, "KXNFLGAME"),
            _market("KXNFLGAME-1", "KXNFLGAME-1-A", 0.40, "KXNFLGAME"),
        ])
        self.assertEqual(sports["set"], "sports")
        self.assertEqual(sports["floor"], 0.06)
        self.assertTrue(sports["interesting"])
        self.assertTrue(sports["counts_as_evidence"])
        self.assertEqual(sports["action"], "log")
        self.assertEqual(sports["buys"], 0)
        self.assertGreaterEqual(sports["edge"], 0.06)

        # Edge 0.05 clears the other-set floor and misses the sports floor.
        other = bot.score_basket("KXFEDDECISION-1", [
            _market("KXFEDDECISION-1", "KXFEDDECISION-1-H", 0.45, "KXFEDDECISION"),
            _market("KXFEDDECISION-1", "KXFEDDECISION-1-C", 0.46, "KXFEDDECISION"),
        ])
        self.assertEqual(other["set"], "other")
        self.assertEqual(other["floor"], 0.05)
        self.assertAlmostEqual(other["edge"], 0.05, places=4)
        self.assertTrue(other["counts_as_evidence"])
        same = bot.score_basket("KXNFLGAME-2", [
            _market("KXNFLGAME-2", "KXNFLGAME-2-H", 0.45, "KXNFLGAME"),
            _market("KXNFLGAME-2", "KXNFLGAME-2-A", 0.46, "KXNFLGAME"),
        ])
        self.assertFalse(same["interesting"])
        self.assertEqual(same["floor"], 0.06)

        # 0.04 would clear the INX 0.02 floor. This tower does not.
        thin = bot.score_basket("KXWTI15M-1", [
            _market("KXWTI15M-1", "KXWTI15M-1-A", 0.46, "KXWTI15M"),
            _market("KXWTI15M-1", "KXWTI15M-1-B", 0.46, "KXWTI15M"),
        ])
        self.assertAlmostEqual(thin["edge"], 0.04, places=4)
        self.assertEqual(thin["floor"], 0.05)
        self.assertFalse(thin["interesting"])
        self.assertFalse(thin["counts_as_evidence"])
        inx = desk_roi_plan.dutch_book_probe(
            [{"side": "a", "ask": 0.46}, {"side": "b", "ask": 0.46}],
            venue="kalshi_inx",
        )
        self.assertTrue(inx["clear"])
        self.assertEqual(inx["floor"], 0.02)

    def test_kxinxu_and_one_sided_books_are_skipped(self):
        bot = _bot()
        refused = bot.score_basket("KXINXU-26NOV10", [
            _market("KXINXU-26NOV10", "KXINXU-1", 0.20, "KXINXU"),
            _market("KXINXU-26NOV10", "KXINXU-2", 0.20, "KXINXU"),
        ])
        self.assertTrue(refused["refused"])
        self.assertFalse(refused["interesting"])
        self.assertFalse(refused["counts_as_evidence"])
        self.assertIn("KXINXU", refused["reason"])
        self.assertEqual(bot.fetch_series("KXINXU", opener=lambda url: b'{"markets":[]}'), [])

        one = bot.score_basket("KXNFLGAME-3", [
            _market("KXNFLGAME-3", "KXNFLGAME-3-H", 0.40, "KXNFLGAME"),
            {"event_ticker": "KXNFLGAME-3", "ticker": "KXNFLGAME-3-A", "series_ticker": "KXNFLGAME"},
        ])
        self.assertFalse(one["interesting"])
        self.assertIn("one-sided", one["reason"])

    def test_observe_examples_are_not_evidence(self):
        bot = _bot()
        board = desk_roi_plan.dutch_book_observe(".")
        labels = [row["label"] for row in board["baskets"]]
        self.assertEqual(labels, ["underround_sports", "overround_sports", "thin_underround"])
        rejected = bot.reject_observe_board(board)
        self.assertEqual(rejected["accepted"], 0)
        self.assertEqual(rejected["rejected"], 3)
        self.assertFalse(rejected["counts_as_evidence"])
        with open(os.path.join(HERE, "exclusive-set-paper", "bot.py"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("dutch_book_observe(", source)
        rows = bot.score_markets([
            {"yes_ask_dollars": 0.44, "ticker": "HOME", "source": "dutch_book_observe", "label": "underround_sports"},
            {"yes_ask_dollars": 0.44, "ticker": "AWAY", "source": "dutch_book_observe", "label": "underround_sports"},
        ])
        self.assertTrue(rows)
        self.assertFalse(any(row.get("counts_as_evidence") for row in rows))

    def test_run_logs_and_buys_nothing(self):
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "exclusive-set-paper"))
            markets = [
                _market("KXNFLGAME-9", "KXNFLGAME-9-H", 0.40, "KXNFLGAME"),
                _market("KXNFLGAME-9", "KXNFLGAME-9-A", 0.40, "KXNFLGAME"),
            ]
            buf = io.StringIO()
            with redirect_stdout(buf):
                bot.run_once(desk_root=tmp, markets=markets, fetch=False)
            out = buf.getvalue()
            self.assertIn("SIGNAL: LOG", out)
            self.assertIn("no trade", out)
            self.assertNotIn("BUY", out)
            with open(os.path.join(tmp, "exclusive-set-paper", "paper_account.json"), encoding="utf-8") as handle:
                state = json.load(handle)
            self.assertEqual(state["cash"], 0.0)
            self.assertEqual(state["open"], [])
            self.assertEqual(state["closed"], [])
            self.assertEqual(state["buys"], 0)
            self.assertEqual(state["stake_usd"], 0.0)
            self.assertTrue(state["shadow_only"])
            self.assertFalse(state["live_orders"])
            self.assertEqual(state["evidence_n"], 1)
            with open(os.path.join(tmp, "exclusive-set-paper", "evidence.jsonl"), encoding="utf-8") as handle:
                evidence = [json.loads(line) for line in handle if line.strip()]
            self.assertEqual(len(evidence), 1)
            self.assertEqual(evidence[0]["event"], "KXNFLGAME-9")
            self.assertNotIn("underround_sports", [row.get("label") for row in evidence])
            buf = io.StringIO()
            with redirect_stdout(buf):
                bot.run_once(desk_root=tmp, markets=markets, fetch=False)
            self.assertEqual(bot._evidence_count(os.path.join(tmp, "exclusive-set-paper")), 1)
            buf = io.StringIO()
            with redirect_stdout(buf):
                bot.run_once(desk_root=tmp, markets=[], fetch=False)
            self.assertIn("waiting on a public exclusive set", buf.getvalue())
            self.assertIn("no trade", buf.getvalue())

    def test_fetch_scans_sports_and_never_requests_kxinxu(self):
        bot = _bot()
        seen = []

        def opener(url):
            seen.append(url)
            self.assertNotIn("KXINXU", url)
            if "KXNFLGAME" in url:
                body = {
                    "markets": [
                        _market("KXNFLGAME-4", "KXNFLGAME-4-H", "0.40", "KXNFLGAME"),
                        _market("KXNFLGAME-4", "KXNFLGAME-4-A", "0.40", "KXNFLGAME"),
                        _market("KXINXU-1", "KXINXU-1-A", "0.10", "KXINXU"),
                    ]
                }
                return json.dumps(body).encode()
            return b'{"markets":[]}'

        with tempfile.TemporaryDirectory() as tmp:
            tower = os.path.join(tmp, "exclusive-set-paper")
            os.makedirs(tower)
            bot._write_json(os.path.join(tower, "exclusive_book.json"), {
                "source": "public",
                "series": ["KXFEDDECISION", "KXINXU"],
                "markets": [
                    _market("KXFEDDECISION-9", "KXFEDDECISION-9-A", 0.45, "KXFEDDECISION"),
                    _market("KXFEDDECISION-9", "KXFEDDECISION-9-B", 0.46, "KXFEDDECISION"),
                ],
            })
            buf = io.StringIO()
            with redirect_stdout(buf):
                bot.run_once(desk_root=tmp, opener=opener)
            self.assertTrue(seen)
            self.assertTrue(any("KXNFLGAME" in url for url in seen))
            self.assertTrue(any("KXFEDDECISION" in url for url in seen))
            self.assertFalse(any("KXINXU" in url for url in seen))
            events = bot._evidence_events(os.path.join(tower, "evidence.jsonl"))
            self.assertIn("KXNFLGAME-4", events)
            self.assertIn("KXFEDDECISION-9", events)
            self.assertFalse(any(event.startswith("KXINXU") for event in events))
            self.assertIn("no trade", buf.getvalue())

    def test_desk_row_is_shadow_without_a_stake(self):
        spec = next(row for row in pimp_desk.BOTS if row["id"] == "exclusive-set")
        self.assertTrue(spec["shadow_only"])
        self.assertNotIn("exclusive-set", pimp_desk.DEFAULTS["tower_risk_budgets"])
        plans = pimp_desk.BOT_PLANS["exclusive-set"]
        self.assertTrue(plans["entry_gated"])
        self.assertEqual(plans["exit_quality"], "partial")
        self.assertEqual(plans["stake"], "none")
        self.assertIn("does not buy", " ".join(plans["buy"]).lower())
        self.assertEqual(pimp_desk.TOWER_STARTER_CASH["exclusive-set"], 0.0)
        self.assertEqual(pimp_desk.ACTIONS["exclusive-set"]["run"]["entry"], False)
        self.assertFalse(desk_roi_plan.LIVE_ORDERS_ENABLED)
        snap = pimp_desk.snapshot(HERE)
        row = next(bot for bot in snap["bots"] if bot["id"] == "exclusive-set")
        self.assertTrue(row["shadow_only"])
        self.assertEqual(row["cash"], 0.0)
        self.assertEqual(row["positions"], [])
        self.assertEqual(row["open_count"], 0)
        self.assertEqual(row["sizing_mode"], "none")
        self.assertEqual(row["capital_weight"], 0)
        self.assertEqual(row["venue_min_edge"], 0.06)
        flat = {
            "id": "exclusive-set", "present": True, "open_count": 0,
            "cash": 0.0, "today": 0.0, "realized": 0.0, "history": [],
        }
        self.assertTrue(pimp_desk.tower_doing_good(flat))
        self.assertFalse(pimp_desk.tower_needs_midnight_reload(flat))
        desk_ids = [bot["id"] for bot in snap["bots"] if not bot.get("shadow_only")]
        self.assertNotIn("exclusive-set", desk_ids)


if __name__ == "__main__":
    unittest.main()
