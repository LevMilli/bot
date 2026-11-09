"""BTC carry tower: held unlevered spot/perp, fee lock, flat card. No network."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_profit
import pimp_desk


def _bot():
    path = os.path.join(HERE, "btc-carry-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("btc_carry_bot", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _marks(funding, premium):
    return {"funding": funding, "premium": premium, "error": ""}


def _capture(bot, tmp, marks, now, env=None):
    buf = io.StringIO()
    previous = {key: os.environ.get(key) for key in bot.KEY_ENV}
    previous["DESK_BLOCK_ENTRIES"] = os.environ.get("DESK_BLOCK_ENTRIES")
    if env:
        for key, value in env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    try:
        with redirect_stdout(buf):
            bot.run_once(desk_root=tmp, cfg=bot.locked_cfg({}), fetch=lambda: marks, now=now)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return buf.getvalue()


class BtcCarryRules(unittest.TestCase):
    def test_fees_stay_on_the_binance_schedule(self):
        bot = _bot()
        cfg = bot.locked_cfg({
            "spot_taker": 0.009,
            "perp_taker": 0.0001,
            "leverage": 5,
            "notional_usd": 5000,
        })
        self.assertEqual(cfg["spot_taker"], 0.001)
        self.assertEqual(cfg["perp_taker"], 0.0005)
        self.assertAlmostEqual(cfg["round_trip"], 0.003, places=6)
        self.assertEqual(cfg["leverage"], 1)
        self.assertEqual(cfg["notional_usd"], 500.0)
        self.assertNotEqual(cfg["spot_taker"], 0.009)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"], 0.05)
        parsed, err = desk_profit.parse_venue_min_edge({"binance_btc_carry": 0.01})
        self.assertIsNone(parsed)
        self.assertIn("cannot lower", err or "")
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["binance_btc_carry"], 0.02)
        self.assertEqual(desk_profit.bot_venue_edge("btc-carry"), 0.02)

    def test_2026_hold_passes_and_the_monthly_flip_is_a_reject(self):
        bot = _bot()
        scored = bot.score_months(bot.BTC_2026_GROSS)
        self.assertEqual(scored["n"], 10)
        self.assertAlmostEqual(scored["held_median"], 0.003, places=6)
        self.assertAlmostEqual(scored["flip_mean"], -0.00034, places=6)
        self.assertTrue(scored["pass"])
        self.assertTrue(scored["flip_reject"])
        card = bot.research_card()
        self.assertTrue(card["paper_only"])
        self.assertFalse(card["live_orders"])
        self.assertTrue(card["shadow_only"])
        self.assertFalse(card["auto_promote"])
        self.assertAlmostEqual(card["round_trip"], 0.003, places=6)
        self.assertIn("median stays positive", card["pass_bar"])
        self.assertIn("reject", card["pass_bar"])
        self.assertEqual(card["flat_card"], bot.FLAT_CARD)

    def test_flat_card_when_there_is_no_mark(self):
        bot = _bot()
        now = bot._parse_time("2026-03-01T00:00:00+00:00")
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "btc-carry-paper"))
            out = _capture(bot, tmp, {"funding": [], "premium": [], "error": "no archive rows"}, now)
            self.assertIn("CARD: " + bot.FLAT_CARD, out)
            self.assertIn("no trade", out)
            self.assertEqual(pimp_desk.card_copy(out), bot.FLAT_CARD)
            state = json.load(open(os.path.join(tmp, "btc-carry-paper", "paper_account.json"), encoding="utf-8"))
            self.assertEqual(state["open"], [])
            self.assertTrue(state["shadow_only"])
            self.assertFalse(state["live_orders"])
            funding_only = _marks(
                [{"time": "2026-03-01T00:00:00+00:00", "rate": 0.0001}],
                [],
            )
            out = _capture(bot, tmp, funding_only, now)
            self.assertIn("CARD: " + bot.FLAT_CARD, out)
            state = json.load(open(os.path.join(tmp, "btc-carry-paper", "paper_account.json"), encoding="utf-8"))
            self.assertEqual(state["open"], [])

    def test_opens_once_and_sits_through_a_red_month(self):
        bot = _bot()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "btc-carry-paper"))
            first = _marks(
                [{"time": "2026-02-01T00:00:00+00:00", "rate": 0.0001}],
                [{"time": "2026-02-01T00:00:00+00:00", "close": 0.0004}],
            )
            opened = bot._parse_time("2026-02-01T00:00:00+00:00")
            out = _capture(bot, tmp, first, opened)
            self.assertIn("CARD: " + bot.HOLD_CARD, out)
            self.assertNotIn("no trade", out)
            state = json.load(open(os.path.join(tmp, "btc-carry-paper", "paper_account.json"), encoding="utf-8"))
            self.assertEqual(len(state["open"]), 1)
            self.assertEqual(state["entry_fees"], 1)
            self.assertEqual(state["open"][0]["leverage"], 1)
            self.assertEqual(state["open"][0]["notional"], 500.0)
            self.assertAlmostEqual(state["cash"], 499.25, places=2)
            red = _marks(
                [
                    {"time": "2026-02-01T00:00:00+00:00", "rate": 0.0001},
                    {"time": "2026-02-01T08:00:00+00:00", "rate": -0.0002},
                ],
                [
                    {"time": "2026-02-01T00:00:00+00:00", "close": 0.0004},
                    {"time": "2026-02-01T08:00:00+00:00", "close": 0.0005},
                ],
            )
            later = bot._parse_time("2026-02-01T08:00:00+00:00")
            out = _capture(bot, tmp, red, later)
            self.assertIn("CARD: " + bot.HOLD_CARD, out)
            state = json.load(open(os.path.join(tmp, "btc-carry-paper", "paper_account.json"), encoding="utf-8"))
            self.assertEqual(len(state["open"]), 1)
            self.assertEqual(state["entry_fees"], 1)
            self.assertEqual(state["open"][0]["notional"], 500.0)
            # Short pays 0.0002 funding and pays 1 bp more premium: 500 * (0.0002 + 0.0001).
            self.assertAlmostEqual(state["cash"], 499.1, places=2)
            self.assertEqual(state["closed"], [])
            march = _marks(
                red["funding"] + [{"time": "2026-03-01T00:00:00+00:00", "rate": 0.0001}],
                red["premium"] + [{"time": "2026-03-01T00:00:00+00:00", "close": 0.0005}],
            )
            out = _capture(bot, tmp, march, bot._parse_time("2026-03-01T00:00:00+00:00"))
            self.assertIn("CARD: " + bot.HOLD_CARD, out)
            state = json.load(open(os.path.join(tmp, "btc-carry-paper", "paper_account.json"), encoding="utf-8"))
            self.assertEqual(len(state["open"]), 1)
            self.assertEqual(state["entry_fees"], 1)
            self.assertEqual(state["closed"][-1]["exit"], "month-mark")
            self.assertEqual(state["closed"][-1]["month"], "2026-02")
            self.assertLess(state["closed"][-1]["pnl"], 0)
            self.assertTrue(state["pass_bar"]["flip_reject"])
            self.assertTrue(os.path.isfile(os.path.join(tmp, "desk_incubation.json")))
            again = _capture(bot, tmp, march, bot._parse_time("2026-03-01T08:00:00+00:00"))
            self.assertIn(bot.HOLD_CARD, again)
            state2 = json.load(open(os.path.join(tmp, "btc-carry-paper", "paper_account.json"), encoding="utf-8"))
            self.assertEqual(state2["entry_fees"], 1)
            self.assertEqual(len(state2["open"]), 1)
            self.assertEqual(
                [row["month"] for row in state2["closed"] if row["exit"] == "month-mark"],
                ["2026-02"],
            )

    def test_desk_gate_and_a_key_keep_the_book_flat(self):
        bot = _bot()
        now = bot._parse_time("2026-05-01T00:00:00+00:00")
        marks = _marks(
            [{"time": "2026-05-01T00:00:00+00:00", "rate": 0.0002}],
            [{"time": "2026-05-01T00:00:00+00:00", "close": 0.0002}],
        )
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "btc-carry-paper"))
            out = _capture(bot, tmp, marks, now, env={"DESK_BLOCK_ENTRIES": "1"})
            self.assertIn("CARD: " + bot.FLAT_CARD, out)
            self.assertIn("no trade", out)
            state = json.load(open(os.path.join(tmp, "btc-carry-paper", "paper_account.json"), encoding="utf-8"))
            self.assertEqual(state["open"], [])
            out = _capture(bot, tmp, marks, now, env={"BINANCE_API_KEY": "not-a-real-key"})
            self.assertIn("key is set", out.lower())
            self.assertIn("CARD: " + bot.FLAT_CARD, out)
            self.assertNotIn("not-a-real-key", out)

    def test_archive_parser_and_host(self):
        bot = _bot()
        now = bot._parse_time("2026-10-15T00:00:00+00:00")
        urls = [url for _kind, url in bot.archive_urls(now)]
        self.assertTrue(urls)
        self.assertTrue(all("data.binance.vision" in url for url in urls))
        self.assertFalse(any("fapi.binance.com" in url for url in urls))
        blob = io.BytesIO()
        with zipfile.ZipFile(blob, "w") as archive:
            archive.writestr(
                "BTCUSDT-fundingRate-2026-10.csv",
                "calc_time,funding_interval_hours,last_funding_rate\n"
                "1760000000000,8,0.0001\n",
            )
        rows = bot.parse_funding_csv(bot._csv_from_zip(blob.getvalue()))
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["rate"], 0.0001)
        premium = io.BytesIO()
        with zipfile.ZipFile(premium, "w") as archive:
            archive.writestr(
                "BTCUSDT-8h-2026-10.csv",
                "1760000000000,0.0001,0.0002,0.00005,0.00015,0\n",
            )
        parsed = bot.parse_premium_csv(bot._csv_from_zip(premium.getvalue()))
        self.assertAlmostEqual(parsed[0]["close"], 0.00015)
        seen = []

        def opener(url):
            seen.append(url)
            if "fundingRate" in url and url.endswith("2026-10.zip"):
                return blob.getvalue()
            if "premiumIndexKlines" in url and url.endswith("2026-10.zip"):
                return premium.getvalue()
            return None

        marks = bot.fetch_marks(now, opener=opener)
        self.assertEqual(len(marks["funding"]), 1)
        self.assertEqual(len(marks["premium"]), 1)
        self.assertTrue(all("data.binance.vision" in url for url in seen))
        self.assertFalse(any("fapi" in url for url in seen))

    def test_desk_registers_the_shadow_book(self):
        spec = next(row for row in pimp_desk.BOTS if row["id"] == "btc-carry")
        self.assertTrue(spec["shadow_only"])
        self.assertEqual(spec["folder"], "btc-carry-paper")
        self.assertNotIn("btc-carry", pimp_desk.DEFAULTS["tower_risk_budgets"])
        self.assertEqual(pimp_desk.BOT_PLANS["btc-carry"]["exit_quality"], "partial")
        self.assertTrue(pimp_desk.BOT_PLANS["btc-carry"]["entry_gated"])
        self.assertIn("binance_btc_carry", pimp_desk.DEFAULTS["venue_min_edge"])
        self.assertEqual(pimp_desk.DEFAULTS["venue_min_edge"]["kalshi_btc15m"], 0.05)
        slot = next(row for row in pimp_desk.AUTO if row["id"] == "btc-carry")
        self.assertEqual(slot["every_sec"], 300)
        plan = __import__("desk_roi_plan").default_exit_plan("btc-carry")
        self.assertTrue(plan["fee_floors_locked"])
        self.assertFalse(plan["auto_promote"])
        self.assertFalse(plan["monthly_flip"])
        self.assertTrue(plan["unlevered"])
        sys.path.insert(0, os.path.join(HERE, "tools"))
        import new_tower
        self.assertTrue(new_tower.check_tower("btc-carry")["ok"])
        text = open(os.path.join(HERE, "btc-carry-paper", "README.md"), encoding="utf-8").read()
        self.assertIn("after-fee monthly median stays positive", text.lower())
        self.assertIn("flipping every month is a reject", text.lower())


if __name__ == "__main__":
    unittest.main()
