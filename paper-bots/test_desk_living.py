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
        from helpers import clv_closer, injury_wire, eia_scout
        from helpers import calib_nag, hard_stop_clerk, near_miss_clerk, bleed_clerk
        from helpers import distance_clerk, bookkeeper_clerk, reporter_clerk, quant_clerk
        from helpers import skip_twin_clerk
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
            from datetime import datetime, timedelta, timezone
            eia = eia_scout.write_digest(tmp, events=[{
                "country": "USD",
                "impact": "High",
                "title": "Crude Oil Inventories",
                "date": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            }])
            self.assertEqual(eia["n"], 1)
            self.assertFalse(eia["may_place_alone"])
            cn = calib_nag.write_digest(tmp, btc={
                "n": 20, "hi_n": 20, "hi_hit_rate": 0.5,
                "miscalibrated": True, "action": "raise_phi",
            })
            self.assertEqual(cn["tickets_n"], 1)
            self.assertFalse(cn["auto_write_phi"])
            hs = hard_stop_clerk.write_digest(tmp, summary={
                "n": 12, "promote_ready": False, "decision": "reject", "live": False,
            })
            self.assertFalse(hs["live"])
            self.assertFalse(hs["auto_promote"])
            nm = near_miss_clerk.write_digest(tmp, status={
                "n": 5, "labeled_n": 5, "promote_ready": False, "decision": "reject",
            })
            self.assertFalse(nm["promote_ready"])
            bl = bleed_clerk.write_digest(tmp, bleed={"ratio": 0.1, "pass": True},
                                         misplaced={"misplaced_usd": 0, "rows": []})
            self.assertEqual(bl["helper"], "bleed_clerk")
            dist = distance_clerk.write_digest(
                tmp, empty_card={"pass": True, "last_sec": 1.1}, firm_queue={"offers_n": 2},
            )
            self.assertEqual(dist["firm_offers_n"], 2)
            bk = bookkeeper_clerk.write_digest(
                tmp, completions={"eligible_completions_today": 1, "completions_today": 2},
            )
            self.assertEqual(bk["eligible_completions_today"], 1)
            rp = reporter_clerk.write_digest(tmp, scorecard={"label": "2026-W45", "m1": -1.0})
            self.assertTrue(rp["present"])
            self.assertFalse(rp["auto_publish"])
            qt = quant_clerk.write_digest(
                tmp, fit={"rate": 0.5, "n_fit": 12, "pass": True}, latency={"p50": 0.9, "pass": True},
            )
            self.assertFalse(qt["auto_write"])
            st = skip_twin_clerk.write_digest(tmp, status={
                "n": 8, "labeled_n": 4, "shadow_ev": 0.01, "decision": "reject",
            })
            self.assertEqual(st["helper"], "skip_twin_clerk")
            self.assertFalse(st["auto_promote"])
            board = desk_living.living_upgrade_board(tmp)
            swarm = board.get("insight_swarm") or {}
            self.assertIn("ratio", swarm)
            self.assertEqual(swarm.get("min_ratio"), 3.0)
            self.assertTrue(board["insight_helper_digests"].get("skip_twin_clerk"))
            self.assertTrue(board["insight_helper_digests"].get("eia_scout"))
            self.assertTrue(board["insight_helper_digests"].get("calib_nag"))
            self.assertTrue(board["insight_helper_digests"].get("hard_stop_clerk"))
            self.assertTrue(board["insight_helper_digests"].get("near_miss_clerk"))
            self.assertTrue(board["insight_helper_digests"].get("bleed_clerk"))
            self.assertTrue(board["insight_helper_digests"].get("distance_clerk"))
            self.assertTrue(board["insight_helper_digests"].get("bookkeeper_clerk"))
            self.assertTrue(board["insight_helper_digests"].get("reporter_clerk"))
            self.assertTrue(board["insight_helper_digests"].get("quant_clerk"))

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

    def test_skip_twin_and_clerk_pulse(self):
        from helpers import clerk_pulse
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "helpers"), exist_ok=True)
            out = desk_living.record_skip_twin_features(
                tmp, bot="btc15m", ticker="T1", would_pnl=0.12, soft="z",
            )
            self.assertTrue(out["recorded"])
            self.assertEqual(out["row"]["action"], "skip_twin")
            digest = clerk_pulse.run_if_due(tmp)
            self.assertIsNotNone(digest)
            self.assertGreaterEqual(digest["refreshed_n"], 1)
            self.assertFalse(digest["may_place_alone"])
            self.assertTrue(os.path.isfile(os.path.join(tmp, "helpers", "clerk_pulse_digest.json")))
            # Due marker: second call within cadence returns None
            again = clerk_pulse.run_if_due(tmp)
            self.assertIsNone(again)


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
