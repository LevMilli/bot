"""Trade-more / win-more: line CLV for green_boost + BTC cushion when z clears."""

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


if __name__ == "__main__":
    unittest.main()
