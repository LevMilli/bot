"""Living Trading Upgrade — desk_living + P0 guards. Floors stay locked."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest import mock

import desk_living
import desk_profit


CT = ZoneInfo("America/Chicago")


class DeskLivingTests(unittest.TestCase):
    def test_chicago_today_uses_america_chicago(self):
        # Fixed UTC instant → Chicago date
        now = datetime(2026, 11, 6, 5, 30, tzinfo=ZoneInfo("UTC"))  # 11/5 evening CT
        self.assertEqual(desk_living.chicago_today(now).isoformat(), "2026-11-05")
        now2 = datetime(2026, 11, 6, 6, 30, tzinfo=ZoneInfo("UTC"))  # 11/6 midnight CT
        self.assertEqual(desk_living.chicago_today(now2).isoformat(), "2026-11-06")

    def test_feature_store_and_completions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_living.record_decision_features(
                tmp,
                bot="btc15m",
                action="skip",
                series="KXBTC15M",
                edge=0.04,
                skip_codes=["EDGE"],
            )
            self.assertTrue(out["recorded"])
            cov = desk_living.feature_store_coverage(tmp)
            self.assertEqual(cov["n"], 1)
            self.assertEqual(cov["skips"], 1)
            desk_living.record_completion(
                tmp,
                bot="btc15m",
                ticker="T",
                pnl=1.25,
                contracts=2,
                eligible=True,
            )
            desk_living.record_completion(
                tmp,
                bot="memecoin",
                ticker="M",
                pnl=-1.0,
                eligible=True,  # still not fee-clear → eligible False via bot id
            )
            summary = desk_living.completions_summary(tmp)
            self.assertEqual(summary["eligible_completions_today"], 1)
            self.assertEqual(summary["completions_today"], 2)
            board = desk_living.living_upgrade_board(tmp)
            self.assertTrue(board["fee_floors_locked"])
            self.assertFalse(board["grok_buys"])

    def test_honor_entry_gate_sets_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ.pop("DESK_BLOCK_ENTRIES", None)
            os.environ.pop("DESK_BLOCK_REASON", None)
            with mock.patch("pimp_desk.entry_gate", return_value="Max open risk is reached ($100)."):
                reason = desk_living.honor_desk_entry_gate(tmp)
            self.assertIn("open risk", reason.lower())
            self.assertEqual(os.environ.get("DESK_BLOCK_ENTRIES"), "1")
            os.environ.pop("DESK_BLOCK_ENTRIES", None)
            os.environ.pop("DESK_BLOCK_REASON", None)

    def test_fee_floors_untouched(self):
        floors = desk_profit.DEFAULT_VENUE_MIN_EDGE
        self.assertEqual(floors["kalshi_sports"], 0.06)
        self.assertEqual(floors["kalshi_btc15m"], 0.05)
        self.assertEqual(floors["kalshi_commodity15m"], 0.05)
        self.assertEqual(floors["kalshi_inx"], 0.02)
        parsed, err = desk_profit.parse_venue_min_edge({"kalshi_btc15m": 0.01})
        self.assertIsNotNone(err)


class BtcNewsFailClosed(unittest.TestCase):
    def test_none_news_blocks(self):
        import importlib.util
        path = os.path.join(os.path.dirname(__file__), "btc15m-signal", "btc15m_signal.py")
        # Light check: source contains fail-closed string and news is None path
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("fail-closed", text)
        self.assertIn("USD news calendar unavailable (fail-closed)", text)
        self.assertNotIn(
            "# Soft: calendar never loaded → do not block; known high-impact still blocks.",
            text,
        )


class InsightHelpers(unittest.TestCase):
    def test_tip_radar_and_skip_historian(self):
        from helpers import tip_radar, skip_historian, timer_heartbeat, empty_card_bee
        from helpers import clv_closer, injury_wire
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "helpers"), exist_ok=True)
            d = tip_radar.write_digest(tmp, games=[
                {"league": "NBA", "ticker": "X", "tip_in_min": 4},
            ])
            self.assertEqual(d["games"][0]["priority"], "T-5")
            self.assertFalse(d["may_place_alone"])
            s = skip_historian.write_digest(tmp, ["EDGE", "BUDGET", "EDGE"])
            self.assertEqual(s["top"][0]["code"], "EDGE")
            h = timer_heartbeat.write_digest(tmp, alive=False, detail="test")
            self.assertEqual(h["status"], "dead")
            e = empty_card_bee.write_digest(tmp, events=[
                {"bot": "btc15m", "series": "KXBTC15M", "sec": 4.0},
            ])
            self.assertEqual(e["breaches"], 1)
            c = clv_closer.build_digest({"n": 3, "complete": 2, "pass": False})
            self.assertEqual(c["helper"], "clv_closer")
            self.assertFalse(c["may_place_alone"])
            iw = injury_wire.write_digest(tmp, headlines=[{"league": "NFL", "text": "QB out"}])
            self.assertEqual(iw["n"], 1)

    def test_record_eval_features(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_living.record_eval_features(
                tmp,
                bot="btc15m",
                action="skip",
                series="KXBTC15M",
                ev={"side": "YES", "ask": 0.8, "edge": 0.03, "p": 0.88, "z": 0.7},
                reasons=["z thin"],
            )
            cov = desk_living.feature_store_coverage(tmp)
            self.assertEqual(cov["n"], 1)
            self.assertEqual(cov["skips"], 1)


class MemeChicagoDay(unittest.TestCase):
    def test_today_local_is_chicago(self):
        import importlib.util
        path = os.path.join(os.path.dirname(__file__), "memecoin-paper", "bot.py")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("America/Chicago", text)
        self.assertIn("datetime.now(CT).date()", text)


if __name__ == "__main__":
    unittest.main()
