"""Bulk post-E3E7 boards: SERIES order, vol-prior depth need, latency stage,
speed KPIs, INX warm, M5 annotation, firm M1 gap, distance stance, floors locked."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_more
import desk_profit
import desk_roi_plan
import desk_roi_post_e3e7 as post


def _load_commodity_bot():
    path = os.path.join(HERE, "commodity-15m-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("commodity_15m_bot_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class FeeFloorsLocked(unittest.TestCase):
    def test_floors_locked(self):
        floors = desk_profit.DEFAULT_VENUE_MIN_EDGE
        self.assertEqual(floors["kalshi_sports"], 0.06)
        self.assertEqual(floors["kalshi_btc15m"], 0.05)
        self.assertEqual(floors["kalshi_commodity15m"], 0.05)
        self.assertEqual(floors["kalshi_inx"], 0.02)
        self.assertEqual(floors["solana_dex"], 0.02)
        check = post.fee_floors_locked_check()
        self.assertTrue(check["ok"])
        self.assertTrue(check["fee_floors_locked"])
        soft, err = desk_profit.parse_venue_min_edge({"kalshi_sports": 0.03})
        self.assertIsNone(soft)
        self.assertIsNotNone(err)


class CommoditySeriesPriority560(unittest.TestCase):
    def test_liquid_first_thin_last(self):
        bot = _load_commodity_bot()
        series = list(bot.SERIES)
        self.assertEqual(series[0], "KXGOLD15M")
        self.assertEqual(series[1], "KXWTI15M")
        self.assertIn("KXPALLADIUM15M", series[-2:])
        self.assertEqual(series[-1], "KXNATGAS15M")
        # Gold and WTI before thin books.
        self.assertLess(series.index("KXGOLD15M"), series.index("KXPALLADIUM15M"))
        self.assertLess(series.index("KXWTI15M"), series.index("KXNATGAS15M"))
        self.assertEqual(len(series), 8)
        self.assertEqual(len(set(series)), 8)


class DepthNeedVolPrior471(unittest.TestCase):
    def test_natgas_need_above_gold(self):
        base = desk_more.DEFAULT_DEPTH_NEED
        nat = desk_more.effective_depth_need("KXNATGAS15M", base)
        gold = desk_more.effective_depth_need("KXGOLD15M", base)
        self.assertGreater(nat, gold)
        self.assertGreaterEqual(nat, base)
        self.assertGreaterEqual(gold, base)

    def test_depth_board_uses_series_need(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = desk_roi_plan.depth_adjusted_edge_board(
                tmp,
                candidates=[
                    {
                        "bot": "commodity-15m",
                        "ticker": "NG-1",
                        "series": "KXNATGAS15M",
                        "edge": 0.10,
                        "depth": 8,
                    },
                    {
                        "bot": "commodity-15m",
                        "ticker": "AU-1",
                        "series": "KXGOLD15M",
                        "edge": 0.10,
                        "depth": 8,
                    },
                ],
                need=10.0,
            )
            self.assertTrue(board["vol_prior_raises_need"])
            by_ticker = {r["ticker"]: r for r in board["candidates"]}
            self.assertGreater(
                by_ticker["NG-1"]["depth_need"], by_ticker["AU-1"]["depth_need"],
            )
            # Higher need → lower depth-adjusted edge at same depth.
            self.assertLess(
                by_ticker["NG-1"]["depth_adjusted_edge"],
                by_ticker["AU-1"]["depth_adjusted_edge"],
            )


class LatencyStageBoard502(unittest.TestCase):
    def test_weekly_book_and_evaluate_ms(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_latency(
                tmp, bot="btc15m", seconds=0.12, stage="book", note="book",
            )
            desk_roi_plan.record_latency(
                tmp, bot="btc15m", seconds=0.45, stage="evaluate", note="eval",
            )
            desk_roi_plan.record_latency(
                tmp, bot="sports-gap", seconds=0.20, stage="espn", note="espn",
            )
            desk_roi_plan.record_latency(
                tmp, bot="sports-gap", seconds=0.30, stage="kalshi", note="kalshi",
            )
            desk_roi_plan.record_latency(
                tmp, bot="commodity-15m", seconds=0.08, stage="spot", note="spot",
            )
            board = desk_roi_plan.latency_stage_board(tmp)
            self.assertTrue(board["fee_floors_locked"])
            self.assertTrue(board["observe_only"])
            btc = board["by_bot"]["btc15m"]
            self.assertEqual(btc["book_fetch_ms"], 120.0)
            self.assertEqual(btc["evaluate_ms"], 450.0)
            sports = board["by_bot"]["sports-gap"]
            self.assertEqual(sports["book_fetch_ms"], 300.0)  # kalshi
            self.assertEqual(sports["spot_espn_ms"], 200.0)


class InxPreNoonWarm515(unittest.TestCase):
    def test_mocked_clock_window(self):
        ct = ZoneInfo("America/Chicago")
        at = datetime(2026, 11, 7, 11, 50, tzinfo=ct)
        self.assertTrue(desk_more.in_inx_pre_noon_warm_window(at))
        self.assertFalse(
            desk_more.in_inx_pre_noon_warm_window(
                datetime(2026, 11, 7, 12, 30, tzinfo=ct),
            )
        )

    def test_warm_writes_cache_no_orders(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []

            def fake_fetch(url):
                calls.append(url)
                return {"markets": [{"ticker": "KXINXU-TEST"}]}

            at = datetime(2026, 11, 7, 11, 50, tzinfo=ZoneInfo("America/Chicago"))
            out = desk_more.warm_inx_books_pre_noon(
                tmp,
                now_ct=at,
                fetch=fake_fetch,
                bots=("kalshi-sp",),
                series=("KXINXU",),
            )
            self.assertTrue(out["warmed"])
            self.assertTrue(out["in_window"])
            self.assertFalse(out["orders_placed"])
            self.assertTrue(out["buys_still_1_per_day"])
            self.assertEqual(out["max_trades_per_day"], 1)
            self.assertEqual(out["warmed_n"], 1)
            self.assertEqual(len(calls), 1)
            cache = desk_more.inx_quote_cache_path(tmp, bot="kalshi-sp")
            self.assertTrue(os.path.exists(cache))

            outside = desk_more.warm_inx_books_pre_noon(
                tmp,
                now_ct=datetime(2026, 11, 7, 10, 0, tzinfo=ZoneInfo("America/Chicago")),
                fetch=fake_fetch,
            )
            self.assertFalse(outside["warmed"])
            self.assertFalse(outside["in_window"])


class SpeedKpis498(unittest.TestCase):
    def test_tip_to_decision_and_exit_freed(self):
        with tempfile.TemporaryDirectory() as tmp:
            t0 = 1_000_000.0
            post.record_tip_alarm(tmp, tip_at_ms=t0, league="NFL")
            post.record_fee_clear_decision(
                tmp, bot="sports-gap", decision_at_ms=t0 + 850.0, fee_clear=True,
            )
            tip = desk_roi_plan.tip_to_decision_ms(tmp)
            self.assertEqual(tip["n"], 1)
            self.assertEqual(tip["p50_ms"], 850.0)
            self.assertTrue(tip["observe_only"])

            post.record_exit_signal(
                tmp, bot="btc15m", ticker="T1", exit_at_ms=t0,
            )
            post.record_risk_freed(
                tmp, bot="btc15m", ticker="T1", freed_at_ms=t0 + 120.0,
            )
            freed = desk_roi_plan.exit_to_risk_freed_ms(tmp)
            self.assertEqual(freed["n"], 1)
            self.assertEqual(freed["p50_ms"], 120.0)

    def test_fill_capacity_observe(self):
        with tempfile.TemporaryDirectory() as tmp:
            post.record_prefetch_hit(
                tmp, bot="sports-gap", tip_books=4, hit=True, free_risk=40.0,
            )
            post.record_prefetch_hit(
                tmp, bot="sports-gap", tip_books=2, hit=False, free_risk=40.0,
            )
            board = desk_roi_plan.fill_capacity_observe(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 10}],
                cfg={"max_open_risk": 100},
            )
            self.assertEqual(board["tip_books"], 6)
            self.assertEqual(board["prefetch_hit_rate"], 0.5)
            self.assertEqual(board["free_risk"], 90.0)
            # 6 * 0.5 * 90 = 270
            self.assertEqual(board["fill_capacity"], 270.0)
            self.assertTrue(board["fee_floors_locked"])


class M5IdleVsBudget663(unittest.TestCase):
    def test_idle_pass_vs_budget_starvation(self):
        with tempfile.TemporaryDirectory() as tmp:
            # No skips → pure idle_pass
            idle = desk_roi_plan.m5_idle_vs_budget_annotation(
                "btc15m", util=None, open_risk=0.0, root=tmp,
            )
            self.assertEqual(idle["m5_annotation"], "idle_pass")
            self.assertTrue(idle["m5_pass"])

            desk_more.record_skip_codes(
                tmp,
                bot="btc15m",
                reasons=[
                    "max open risk is reached",
                    "tower budget full",
                    "max open positions",
                ],
            )
            starved = desk_roi_plan.m5_idle_vs_budget_annotation(
                "btc15m", util=None, open_risk=0.0, root=tmp,
            )
            self.assertEqual(starved["m5_annotation"], "BUDGET_starvation")
            self.assertIn("BUDGET", starved["tooltip"])
            self.assertTrue(starved["m5_pass"])

            row = desk_master.tower_master_row(
                {"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}},
                cfg={"max_open_risk": 100, "tower_risk_budgets": {"btc15m": 0.35}},
                root=tmp,
            )
            self.assertEqual(row["M5_annotation"], "BUDGET_starvation")
            self.assertTrue(row["passing"]["M5"])


class FirmTowerM1Gap778(unittest.TestCase):
    def test_gap_alert_when_sum_diverges(self):
        bots = [
            {
                "id": "btc15m",
                "history": [
                    {"pnl": 2.0, "contracts": 1},
                    {"pnl": 2.0, "contracts": 1},
                ],
            },
            {
                "id": "sports-gap",
                "history": [
                    {"pnl": -1.0, "contracts": 1},
                ],
            },
        ]
        board = desk_roi_plan.firm_tower_m1_gap_alert(bots)
        self.assertTrue(board["fee_floors_locked"])
        self.assertIn("firm_m1", board)
        self.assertIn("sum_tower_m1", board)
        self.assertIn("m1_gap", board)
        # Sum of tower means vs firm mean can diverge → may alert.
        self.assertIsInstance(board["alert"], bool)
        # Integrity reconciliation of totals should be ~0.
        self.assertAlmostEqual(board["reconciliation_gap"], 0.0, places=6)

    def test_alert_threshold(self):
        # Two towers with different n → sum of means ≠ firm mean by >$1 often.
        bots = [
            {"id": "btc15m", "history": [{"pnl": 5.0, "contracts": 1}] * 2},
            {"id": "memecoin", "history": [{"pnl": -3.0, "contracts": 1}] * 10},
        ]
        board = desk_roi_plan.firm_tower_m1_gap_alert(bots, threshold=1.0)
        # firm mean ≈ (2*4 + 10*-4)/12 = (8-40)/12 = -2.666...
        # sum means ≈ 4 + (-4) = 0 → |gap| > 1
        self.assertTrue(board["alert"])


class DistanceStance733(unittest.TestCase):
    def test_stance_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.capture_baseline(
                tmp,
                bots=[{"id": "btc15m", "today": -100}, {"id": "memecoin", "today": -125}],
                label="W0",
            )
            bleed = desk_roi_plan.distance_to_zero_board(
                tmp,
                bots=[
                    {"id": "btc15m", "today": 0.1},
                    {"id": "memecoin", "today": -8.0},
                ],
            )
            self.assertEqual(bleed["recommended_stance"], "bleed_stop")
            self.assertFalse(bleed["force_buys"])

            earn = desk_roi_plan.distance_to_zero_board(
                tmp,
                bots=[
                    {"id": "btc15m", "today": 2.0},
                    {"id": "sports-gap", "today": 1.0},
                    {"id": "memecoin", "today": 0.0},
                ],
            )
            self.assertEqual(earn["recommended_stance"], "fee_clear_earn")

            idle = desk_roi_plan.distance_to_zero_board(
                tmp,
                bots=[
                    {"id": "btc15m", "today": 0.0},
                    {"id": "memecoin", "today": 0.0},
                ],
            )
            self.assertEqual(idle["recommended_stance"], "idle")


class MastersWirePostE3E7(unittest.TestCase):
    def test_master_summary_exposes_boards(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_latency(
                tmp, bot="btc15m", seconds=0.1, stage="book",
            )
            post.record_tip_alarm(tmp, tip_at_ms=1000.0)
            post.record_fee_clear_decision(
                tmp, bot="sports-gap", decision_at_ms=1500.0,
            )
            summary = desk_master.master_summary(
                tmp,
                bots=[
                    {"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}, "today": 0},
                    {"id": "sports-gap", "open_risk": 5, "history": [], "gate_a": {}, "today": 1},
                ],
                cfg={"max_open_risk": 100, "tower_risk_budgets": {"btc15m": 0.35, "sports-gap": 0.4}},
            )
            plan = summary.get("roi_plan") or {}
            for key in (
                "latency_stage",
                "tip_to_decision_ms",
                "exit_to_risk_freed_ms",
                "fill_capacity_observe",
                "firm_tower_m1_gap",
                "distance_to_zero",
            ):
                self.assertIn(key, plan, key)
                self.assertIsInstance(plan[key], dict, key)
                self.assertTrue(plan[key].get("fee_floors_locked") or plan[key].get("paper_only"))
            self.assertIn(
                plan["distance_to_zero"].get("recommended_stance"),
                ("bleed_stop", "fee_clear_earn", "idle"),
            )


if __name__ == "__main__":
    unittest.main()
