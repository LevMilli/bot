"""Trade-more / win-more: line CLV for green_boost + BTC/commodity cushion when z clears."""

from __future__ import annotations

import datetime as dt
import importlib.util
import os
import tempfile
import unittest
from unittest import mock

import desk_more
import desk_roi_plan

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load_btc():
    path = os.path.join(ROOT, "btc15m-signal", "btc15m_signal.py")
    spec = importlib.util.spec_from_file_location("btc15m_tw", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_commodity():
    path = os.path.join(ROOT, "commodity-15m-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("commodity15m_tw", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TradeWinClvCushionTests(unittest.TestCase):
    def test_binary_settle_clv_excluded_from_boost_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Legacy binary proxies: wins always clv<0, losses always clv>0.
            for i in range(10):
                desk_more.record_sports_clv(
                    tmp,
                    ticker=f"KX-BIN-W{i}",
                    side="home",
                    fair_entry=0.80,
                    close_fair=1.0,
                    pnl=5.0,
                    league="NBA",
                    exit_reason="settled",
                    clv_kind="binary",
                )
            for i in range(10):
                desk_more.record_sports_clv(
                    tmp,
                    ticker=f"KX-BIN-L{i}",
                    side="home",
                    fair_entry=0.80,
                    close_fair=0.0,
                    pnl=-20.0,
                    league="NBA",
                    exit_reason="settled",
                    clv_kind="binary",
                )
            summ = desk_more.clv_summary(tmp)
            self.assertEqual(summ["n"], 0)
            self.assertEqual(summ["binary_excluded_n"], 20)
            self.assertIsNone(summ["beat_close_rate"])

            # Line closes count toward beat rate.
            for i in range(12):
                desk_more.record_sports_clv(
                    tmp,
                    ticker=f"KX-LINE-{i}",
                    side="home",
                    fair_entry=0.80,
                    close_fair=0.70 if i < 8 else 0.85,
                    pnl=1.0,
                    league="NBA",
                    exit_reason="settled",
                    clv_kind="line",
                )
            summ2 = desk_more.clv_summary(tmp)
            self.assertEqual(summ2["n"], 12)
            self.assertAlmostEqual(summ2["beat_close_rate"], 8 / 12, places=4)

    def test_legacy_untagged_01_settle_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_more.record_sports_clv(
                tmp,
                ticker="KX-LEG",
                side="home",
                fair_entry=0.75,
                close_fair=1.0,
                pnl=2.0,
                league="NFL",
                exit_reason="settled",
            )
            # Default kind is line, but exact 0/1 settled still excluded.
            state = desk_more.load_clv(tmp)
            state["rows"][0]["clv_kind"] = "line"
            desk_more.save_clv(state, tmp)
            summ = desk_more.clv_summary(tmp)
            self.assertEqual(summ["n"], 0)
            self.assertEqual(summ["binary_excluded_n"], 1)

    def test_gap_bot_settle_clv_prefers_last_fair_not_wipe(self):
        """Hold-to-settle densify: stash last_fair; refuse Kalshi wipe 0/1 as line."""
        gap_path = os.path.join(ROOT, "sports-gap-paper", "gap_bot.py")
        with open(gap_path, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('p["last_fair"]', src)
        self.assertIn('p["last_mark"]', src)
        self.assertIn("last_fair", src)
        self.assertIn("last_mark", src)
        self.assertIn('clv_kind = "binary"', src)
        self.assertIn("refuse kalshi wipe 0/1 as line", src.lower())
        # last_fair line close counts toward green_boost; wipe binary does not.
        with tempfile.TemporaryDirectory() as tmp:
            desk_more.record_sports_clv(
                tmp,
                ticker="KX-LAST-FAIR",
                side="home",
                fair_entry=0.82,
                close_fair=0.91,
                pnl=3.0,
                league="NCAAF",
                exit_reason="settled",
                clv_kind="line",
            )
            desk_more.record_sports_clv(
                tmp,
                ticker="KX-WIPE",
                side="home",
                fair_entry=0.82,
                close_fair=1.0,
                pnl=3.0,
                league="NCAAF",
                exit_reason="settled",
                clv_kind="binary",
            )
            summ = desk_more.clv_summary(tmp)
            self.assertEqual(summ["n"], 1)
            self.assertEqual(summ["binary_excluded_n"], 1)
            self.assertAlmostEqual(summ["beat_close_rate"], 0.0, places=4)

    def test_gap_bot_post_settle_densifies_line_fair_home(self):
        """Bare post / info=None must densify fair_home so green CLV is not binary."""
        gap_path = os.path.join(ROOT, "sports-gap-paper", "gap_bot.py")
        with open(gap_path, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("def _line_clv_fair_home", src)
        self.assertIn("def _post_settle_fair_home", src)
        # Scoreboard post + open hold densifies fair_home before continue.
        post_idx = src.find('if g["state"] == "post":')
        self.assertGreater(post_idx, 0)
        post_chunk = src[post_idx:post_idx + 900]
        self.assertIn("open_by_game", post_chunk)
        self.assertIn("_post_settle_fair_home", post_chunk)
        self.assertIn('entry["fair_home"]', post_chunk)
        # Next-day info=None lift also densifies fair_home.
        none_idx = src.find("if info is None:")
        self.assertGreater(none_idx, 0)
        none_chunk = src[none_idx:none_idx + 2200]
        self.assertIn("_post_settle_fair_home", none_chunk)
        self.assertIn('info["fair_home"] = fair_home', none_chunk)
        # Idle cache must not skip leagues with open holds.
        idle_idx = src.find("if league_cached_idle(path)")
        self.assertGreater(idle_idx, 0)
        idle_chunk = src[idle_idx:idle_idx + 200]
        self.assertIn("league_has_open", idle_chunk)
        # Runtime: wipe 0/1 refused; line WP accepted.
        spec = importlib.util.spec_from_file_location("gap_bot_clv_post", gap_path)
        gap = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gap)
        self.assertIsNone(gap._line_clv_fair_home(0.0))
        self.assertIsNone(gap._line_clv_fair_home(1.0))
        self.assertIsNone(gap._line_clv_fair_home(None))
        self.assertAlmostEqual(gap._line_clv_fair_home(0.9533), 0.9533, places=4)
        self.assertIn("def _espn_settle_line_wp", src)
        # Wipe-only series → still None (no invent).
        with mock.patch.object(gap, "espn_summary", return_value={
            "winprobability": [{"homeWinPercentage": 1.0}],
        }):
            self.assertIsNone(
                gap._post_settle_fair_home(
                    "football/college-football",
                    {"id": "x", "state": "post", "status": {}},
                    "espn",
                )
            )
        # Pre-wipe last line densifies as before.
        with mock.patch.object(gap, "espn_summary", return_value={
            "winprobability": [{"homeWinPercentage": 0.9533}],
        }):
            fair = gap._post_settle_fair_home(
                "football/college-football",
                {"id": "401856856", "state": "post", "status": {}},
                "espn",
            )
        self.assertAlmostEqual(fair, 0.9533, places=4)
        # True finals: trailing wipe 0/1 must walk back to last line WP.
        with mock.patch.object(gap, "espn_summary", return_value={
            "winprobability": [
                {"homeWinPercentage": 0.8877},
                {"homeWinPercentage": 1.0},
                {"homeWinPercentage": 1.0},
            ],
        }):
            fair = gap._post_settle_fair_home(
                "football/nfl",
                {"id": "401873039", "state": "post", "status": {}},
                "espn",
            )
        self.assertAlmostEqual(fair, 0.8877, places=4)
        self.assertAlmostEqual(
            gap._espn_settle_line_wp({
                "winprobability": [
                    {"homeWinPercentage": 0.001},
                    {"homeWinPercentage": 0.0},
                ],
            }),
            0.001,
            places=4,
        )
        # Mid-open buy fair still uses wipe-last espn_home_wp (unchanged).
        self.assertEqual(
            gap.espn_home_wp({
                "winprobability": [
                    {"homeWinPercentage": 0.8877},
                    {"homeWinPercentage": 1.0},
                ],
            }),
            1.0,
        )

    def test_repair_does_not_invent_binary_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_more.record_sports_clv(
                tmp,
                ticker="KX-MISS",
                side="home",
                fair_entry=0.62,
                close_fair=None,
                pnl=1.0,
                league="NBA",
                exit_reason="settled",
            )
            state = desk_more.load_clv(tmp)
            state["rows"][0].pop("fair_close", None)
            state["rows"][0].pop("close_fair", None)
            state["rows"][0]["clv"] = None
            desk_more.save_clv(state, tmp)
            out = desk_roi_plan.repair_clv_completeness(tmp)
            self.assertEqual(out["repaired"], 0)
            self.assertGreaterEqual(out["skipped"], 1)
            again = desk_more.load_clv(tmp)
            self.assertIsNone(again["rows"][0].get("fair_close") or again["rows"][0].get("close_fair"))

    def test_btc_cushion_skipped_when_z_clears(self):
        btc = _load_btc()
        close = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=12)
        open_t = close - dt.timedelta(minutes=15)
        # σ≈20 → cushion $30 → z=1.5 clears MIN_Z=0.60; absolute $35 must not veto.
        m = {
            "ticker": "KXBTC15M-TEST",
            "series": "KXBTC15M",
            "target": 100000.0,
            "open_time": open_t,
            "close_time": close,
            "yes_ask": 0.82,
            "no_ask": 0.20,
            "yes_bid": 0.80,
            "no_bid": 0.18,
        }
        closes = [100020.0] * 10 + [100030.0]  # price above target → YES
        with mock.patch.object(btc, "_sigma_for", return_value=(20.0, 20.0, None)):
            with mock.patch.object(btc, "usd_high_impact_near", return_value=False):
                with mock.patch.object(
                    desk_roi_plan,
                    "effective_near_miss_relax",
                    return_value={"p_relax": 0.0, "z_relax": 0.0},
                ):
                    ev = btc.evaluate_window(
                        m, 100030.0, closes, None, False, 0.05,
                        book=(0.80, 0.82, 10.0),
                    )
        reasons = " | ".join(ev.get("reasons") or [])
        self.assertNotIn("cushion", reasons)
        self.assertGreaterEqual(float(ev.get("z") or 0), 0.60)

    def test_btc_cushion_still_blocks_when_z_thin(self):
        btc = _load_btc()
        close = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=12)
        open_t = close - dt.timedelta(minutes=15)
        # σ≈100 → cushion $30 → z=0.30 < MIN_Z → cushion veto OK.
        m = {
            "ticker": "KXBTC15M-TEST2",
            "series": "KXBTC15M",
            "target": 100000.0,
            "open_time": open_t,
            "close_time": close,
            "yes_ask": 0.82,
            "no_ask": 0.20,
            "yes_bid": 0.80,
            "no_bid": 0.18,
        }
        closes = [100020.0] * 10 + [100030.0]
        with mock.patch.object(btc, "_sigma_for", return_value=(100.0, 100.0, None)):
            with mock.patch.object(btc, "usd_high_impact_near", return_value=False):
                with mock.patch.object(
                    desk_roi_plan,
                    "effective_near_miss_relax",
                    return_value={"p_relax": 0.0, "z_relax": 0.0},
                ):
                    ev = btc.evaluate_window(
                        m, 100030.0, closes, None, False, 0.05,
                        book=(0.80, 0.82, 10.0),
                    )
        reasons = " | ".join(ev.get("reasons") or [])
        self.assertIn("cushion", reasons)

    def test_btc_toward_skipped_when_p_clears_need(self):
        btc = _load_btc()
        close = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=12)
        open_t = close - dt.timedelta(minutes=15)
        # YES side + falling last 5 candles → toward=True; Φ(z) still fee-clears.
        m = {
            "ticker": "KXBTC15M-TOWARD-OK",
            "series": "KXBTC15M",
            "target": 100000.0,
            "open_time": open_t,
            "close_time": close,
            "yes_ask": 0.82,
            "no_ask": 0.20,
            "yes_bid": 0.80,
            "no_bid": 0.18,
        }
        # 6+ closes ending lower so move < 0 while price still above target.
        closes = [100050.0] * 5 + [100040.0, 100030.0]
        with mock.patch.object(btc, "_sigma_for", return_value=(20.0, 20.0, None)):
            with mock.patch.object(btc, "usd_high_impact_near", return_value=False):
                with mock.patch.object(
                    desk_roi_plan,
                    "effective_near_miss_relax",
                    return_value={"p_relax": 0.0, "z_relax": 0.0},
                ):
                    ev = btc.evaluate_window(
                        m, 100030.0, closes, None, False, 0.05,
                        book=(0.80, 0.82, 10.0),
                    )
        self.assertTrue(ev.get("toward"))
        self.assertGreaterEqual(float(ev.get("p") or 0), float(ev.get("need") or 1))
        reasons = " | ".join(ev.get("reasons") or [])
        self.assertNotIn("candles moving toward", reasons)

    def test_btc_toward_still_blocks_when_p_thin(self):
        btc = _load_btc()
        close = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=12)
        open_t = close - dt.timedelta(minutes=15)
        # Ask high so need_p > p even with solid z; toward must still veto.
        m = {
            "ticker": "KXBTC15M-TOWARD-BLOCK",
            "series": "KXBTC15M",
            "target": 100000.0,
            "open_time": open_t,
            "close_time": close,
            "yes_ask": 0.90,
            "no_ask": 0.12,
            "yes_bid": 0.88,
            "no_bid": 0.10,
        }
        closes = [100050.0] * 5 + [100040.0, 100030.0]
        with mock.patch.object(btc, "_sigma_for", return_value=(20.0, 20.0, None)):
            with mock.patch.object(btc, "usd_high_impact_near", return_value=False):
                with mock.patch.object(
                    desk_roi_plan,
                    "effective_near_miss_relax",
                    return_value={"p_relax": 0.0, "z_relax": 0.0},
                ):
                    ev = btc.evaluate_window(
                        m, 100030.0, closes, None, False, 0.05,
                        book=(0.88, 0.90, 10.0),
                    )
        self.assertTrue(ev.get("toward"))
        self.assertLess(float(ev.get("p") or 1), float(ev.get("need") or 0) + 0.05)
        reasons = " | ".join(ev.get("reasons") or [])
        # Either p < need reason and/or toward candle — toward must fire when p thin.
        self.assertIn("candles moving toward", reasons)

    def test_commodity_cushion_skipped_when_z_clears(self):
        # Silver metal playbook: min_z=0.70, cush_mult=1.10 → frac floor 0.0011*spot.
        # ml=10 → σ≈0.0367; cushion 0.0315 → z≈0.86 clears, frac floor still fails.
        cmd = _load_commodity()
        close = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10)
        spot = 30.0
        cushion = 0.0315
        m = {
            "ticker": "KXSILVER15M-TEST",
            "series": "KXSILVER15M",
            "target": spot - cushion,
            "close_time": close,
            "yes_ask": 0.70,
            "no_ask": 0.32,
            "yes_bid": 0.68,
            "no_bid": 0.30,
        }
        with mock.patch.object(
            desk_roi_plan,
            "effective_near_miss_relax",
            return_value={"p_relax": 0.0, "z_relax": 0.0},
        ):
            ev = cmd.evaluate(m, spot, 0.05, book=(0.02, 10))
        reasons = " | ".join(ev.get("reasons") or [])
        self.assertNotIn("cushion", reasons)
        self.assertGreaterEqual(float(ev.get("z") or 0), 0.70)
        self.assertFalse(ev.get("reasons"))

    def test_commodity_cushion_still_blocks_when_z_thin(self):
        cmd = _load_commodity()
        close = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10)
        spot = 30.0
        cushion = 0.020  # z≈0.54 < metal min_z 0.70 → frac cushion still vetoes
        m = {
            "ticker": "KXSILVER15M-TEST2",
            "series": "KXSILVER15M",
            "target": spot - cushion,
            "close_time": close,
            "yes_ask": 0.70,
            "no_ask": 0.32,
            "yes_bid": 0.68,
            "no_bid": 0.30,
        }
        with mock.patch.object(
            desk_roi_plan,
            "effective_near_miss_relax",
            return_value={"p_relax": 0.0, "z_relax": 0.0},
        ):
            ev = cmd.evaluate(m, spot, 0.05, book=(0.02, 10))
        reasons = " | ".join(ev.get("reasons") or [])
        self.assertIn("cushion", reasons)
        self.assertLess(float(ev.get("z") or 1), 0.70)


if __name__ == "__main__":
    unittest.main()
