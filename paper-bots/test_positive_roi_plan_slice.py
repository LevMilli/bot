"""Positive-ROI plan slice: M3/M4, bleed, TP, commodity flip, CLV, INX research."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_more
import desk_profit
import desk_roi_plan


class FitLatencyMasters(unittest.TestCase):
    def test_m3_m4_no_longer_stubs(self):
        with tempfile.TemporaryDirectory() as tmp:
            for _ in range(10):
                desk_roi_plan.record_fit(tmp, bot="btc15m", outcome="buy", ticker="T")
            for i in range(5):
                desk_roi_plan.record_latency(tmp, bot="btc15m", seconds=10.0 + i)
            row = desk_master.tower_master_row(
                {"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}},
                cfg={"max_open_risk": 100, "tower_risk_budgets": {"btc15m": 0.3}},
                root=tmp,
            )
            self.assertIsNotNone(row["M3_fit_buy"])
            self.assertEqual(row["M3_fit_buy"], 1.0)
            self.assertTrue(row["passing"]["M3"])
            self.assertIsNotNone(row["M4_latency_s"])
            self.assertTrue(row["passing"]["M4"])
            self.assertNotIn("stub", (row.get("note") or "").lower())


class FirmBleedCapital(unittest.TestCase):
    def test_bleed_and_misplaced(self):
        bleed = desk_roi_plan.firm_bleed_ratio([
            {"id": "memecoin", "today": -10},
            {"id": "sports-gap", "today": 40},
        ])
        self.assertEqual(bleed["ratio"], 0.25)
        self.assertTrue(bleed["pass"])
        mis = desk_roi_plan.capital_misplaced(
            [
                {"id": "memecoin", "today": -8, "open_risk": 20},
                {"id": "btc15m", "today": 2, "open_risk": 15},
            ],
            {"max_open_risk": 100},
        )
        self.assertEqual(mis["misplaced_usd"], 20.0)

    def test_master_summary_includes_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[
                    {"id": "memecoin", "today": -10, "open_risk": 5, "history": [], "gate_a": {}},
                    {"id": "sports-gap", "today": 5, "open_risk": 10, "history": [], "gate_a": {}},
                ],
                cfg={"max_open_risk": 100, "tower_risk_budgets": {"memecoin": 0.05, "sports-gap": 0.35}},
            )
            self.assertEqual(summary["version"], 3)
            self.assertIsInstance(summary.get("bleed"), dict)
            self.assertIsInstance(summary.get("capital_misplaced"), dict)
            self.assertIsInstance(summary.get("roi_plan"), dict)
            self.assertTrue(summary["roi_plan"]["fee_floors_locked"])
            self.assertIsNotNone(summary["roi_plan"].get("baseline"))


class ClvCompleteness(unittest.TestCase):
    def test_record_sports_clv_completeness(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = desk_more.record_sports_clv(
                tmp,
                ticker="KXTEST",
                side="YES",
                fair_entry=0.82,
                close_fair=0.78,
                pnl=1.5,
                league="NBA",
                exit_reason="settled",
            )
            self.assertTrue(desk_roi_plan.clv_row_complete(row))
            self.assertIsNotNone(row.get("clv"))
            self.assertEqual(row["fair_entry"], 0.82)
            comp = desk_roi_plan.clv_completeness(tmp)
            self.assertTrue(comp["pass"])
            self.assertEqual(comp["settled_complete"], 1)

    def test_incomplete_without_entry_fair(self):
        self.assertFalse(desk_roi_plan.clv_row_complete({"clv": 0.02}))
        self.assertTrue(desk_roi_plan.clv_row_complete({"fair_entry": 0.8}))

    def test_settled_missing_close_fair_fails_closed(self):
        self.assertFalse(desk_roi_plan.clv_row_complete({
            "fair_entry": 0.82, "exit": "settled",
        }))
        self.assertFalse(desk_roi_plan.clv_row_complete({
            "fair_entry": 0.82, "clv": 0.04,
        }))
        self.assertTrue(desk_roi_plan.clv_row_complete({
            "fair_entry": 0.82, "close_fair": 0.78, "clv": 0.04, "exit": "settled",
        }))


class InxBandResearch(unittest.TestCase):
    def test_research_does_not_change_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            rep = desk_roi_plan.run_inx_band_research(
                tmp,
                history=[
                    {"ask": 0.85, "pnl": 3.0, "contracts": 1},
                    {"ask": 0.85, "pnl": -1.0, "contracts": 1},
                    {"ask": 0.72, "pnl": -2.0, "contracts": 1},
                ],
            )
            self.assertFalse(rep["live_changed"])
            self.assertEqual(rep["live_band"], "80_90")
            self.assertTrue(rep["fee_floors_locked"])


class BtcTakeProfit(unittest.TestCase):
    def test_manage_take_profits_executes(self):
        sys.path.insert(0, os.path.join(HERE, "btc15m-signal"))
        import btc15m_signal as btc

        state = {
            "cash": 100.0,
            "open": [{
                "ticker": "KXBTC-T",
                "side": "YES",
                "contracts": 10,
                "ask": 0.70,
                "cost": 7.5,
                "take_profit": 0.85,
            }],
            "closed": [],
        }
        sold = btc.manage_take_profits(state, bid=0.86, fee=0.02, ticker="KXBTC-T")
        self.assertEqual(len(sold), 1)
        self.assertEqual(len(state["open"]), 0)
        self.assertEqual(len(state["closed"]), 1)
        self.assertIn("take-profit", state["closed"][0]["exit"])

    def test_manage_take_profits_holds_below(self):
        sys.path.insert(0, os.path.join(HERE, "btc15m-signal"))
        import btc15m_signal as btc

        state = {
            "cash": 100.0,
            "open": [{
                "ticker": "KXBTC-T",
                "side": "YES",
                "contracts": 10,
                "ask": 0.70,
                "cost": 7.5,
                "take_profit": 0.85,
            }],
            "closed": [],
        }
        sold = btc.manage_take_profits(state, bid=0.80, fee=0.02, ticker="KXBTC-T")
        self.assertEqual(sold, [])
        self.assertEqual(len(state["open"]), 1)


class CommodityModelFlip(unittest.TestCase):
    def test_manage_model_flips_side_change(self):
        sys.path.insert(0, os.path.join(HERE, "commodity-15m-paper"))
        import bot as commodity

        state = {
            "cash": 100.0,
            "open": [{
                "ticker": "KXGOLD-T",
                "side": "YES",
                "contracts": 5,
                "cost": 4.0,
                "fair_at_entry": 0.85,
            }],
            "closed": [],
        }
        market = {
            "ticker": "KXGOLD-T",
            "yes_bid": 0.40,
            "yes_ask": 0.45,
            "no_bid": 0.55,
            "no_ask": 0.60,
        }
        sold = commodity.manage_model_flips(
            state, side_now="NO", prob_now=0.40, bid=0.55, fee=0.02, delta=0.06,
            ticker="KXGOLD-T",
            market=market,
        )
        self.assertEqual(len(sold), 1)
        self.assertEqual(len(state["open"]), 0)
        self.assertIn("model-flip", state["closed"][0]["exit"])
        # Held YES marks yes_bid — never complementary NO model bid.
        self.assertAlmostEqual(float(state["closed"][0]["exit_price"]), 0.40)

    def test_model_flip_adverse_helper_still_locked(self):
        self.assertTrue(desk_profit.model_flip_adverse("YES", 0.85, 0.70, 0.08))
        # Held-side fair for NO/away — drop flips; rise does not.
        self.assertTrue(desk_profit.model_flip_adverse("NO", 0.85, 0.70, 0.08))
        self.assertFalse(desk_profit.model_flip_adverse("away", 0.82, 0.91, 0.06))


class FeeFloorsUntouched(unittest.TestCase):
    def test_floors_locked(self):
        floors = desk_profit.DEFAULT_VENUE_MIN_EDGE
        self.assertEqual(floors["kalshi_sports"], 0.06)
        self.assertEqual(floors["kalshi_btc15m"], 0.05)
        self.assertEqual(floors["kalshi_commodity15m"], 0.05)
        parsed, err = desk_profit.parse_venue_min_edge({"kalshi_btc15m": 0.01})
        self.assertIsNone(parsed)
        self.assertIn("cannot lower", err or "")


class NearMissWeekly(unittest.TestCase):
    def test_weekly_card_rejects_thin_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            card = desk_roi_plan.near_miss_weekly_card(tmp)
            self.assertEqual(card["decision"], "reject")
            self.assertFalse(card["auto_promote"])
            self.assertTrue(card["fee_floors_locked"])


class ExitPlanCoverage(unittest.TestCase):
    def test_default_exit_plans_fee_clear(self):
        sports = desk_roi_plan.default_exit_plan("sports-gap")
        self.assertIn("hard_stop_shadow", sports)
        self.assertTrue(sports.get("fee_floors_locked"))
        self.assertFalse(sports.get("hard_stop_live"))
        btc = desk_roi_plan.default_exit_plan("btc15m")
        self.assertEqual(btc.get("kind"), "take_profit+model_flip+settle")
        commodity = desk_roi_plan.default_exit_plan("commodity-15m")
        self.assertIn("model_flip", commodity)
        self.assertFalse(sports.get("board_chip", False))
        inx = desk_roi_plan.default_exit_plan("kalshi-sp")
        self.assertEqual(inx.get("kind"), "model_flip+settle")
        sized = desk_roi_plan.default_exit_plan("kalshi-sized")
        self.assertEqual(sized.get("ask_band"), "84-92")
        meme = desk_roi_plan.default_exit_plan("memecoin")
        self.assertEqual(meme.get("stop_pct"), -0.12)

    def test_coverage_pass_when_plans_present(self):
        bots = [
            {
                "id": "sports-gap",
                "open": [{"ticker": "A", "exit_plan": desk_roi_plan.default_exit_plan("sports-gap")}],
            },
            {
                "id": "btc15m",
                "open": [{"ticker": "B", "exit_plan": desk_roi_plan.default_exit_plan("btc15m")}],
            },
            {
                "id": "commodity-15m",
                "open": [{"ticker": "C", "exit_plan": desk_roi_plan.default_exit_plan("commodity-15m")}],
            },
        ]
        cov = desk_roi_plan.exit_plan_coverage(bots=bots)
        self.assertTrue(cov.get("pass"))
        self.assertEqual(cov.get("n_open"), 3)
        self.assertEqual(cov.get("n_with_plan"), 3)
        self.assertFalse(cov.get("board_chip"))
        self.assertTrue(cov.get("fee_floors_locked"))

    def test_coverage_fails_without_plan(self):
        bots = [{"id": "sports-gap", "open": [{"ticker": "A"}]}]
        cov = desk_roi_plan.exit_plan_coverage(bots=bots)
        self.assertFalse(cov.get("pass"))
        self.assertIn("sports-gap", cov.get("missing_bots") or [])

    def test_master_summary_includes_exit_plans(self):
        import desk_master
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}, "open": []}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("exit_plans", plan)
            self.assertTrue((plan.get("exit_plans") or {}).get("fee_floors_locked"))


class BleedWeekObserve(unittest.TestCase):
    def test_capture_bleed_week_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots = [
                {"id": "btc15m", "today": 10.0, "open_risk": 0, "gate_a": {"ready": True}},
                {"id": "memecoin", "today": -3.0, "open_risk": 5.0, "gate_a": {"ready": False}},
            ]
            card = desk_roi_plan.capture_bleed_week(tmp, bots=bots, label="2026-11-06")
            self.assertEqual(card.get("label"), "2026-11-06")
            self.assertEqual(card.get("target_lt"), 0.5)
            self.assertFalse(card.get("board_chip"))
            self.assertTrue(card.get("fee_floors_locked"))
            self.assertAlmostEqual(float(card.get("ratio") or 0), 0.3, places=4)
            self.assertTrue(card.get("pass"))
            latest = desk_roi_plan.latest_bleed_week(tmp)
            self.assertEqual((latest or {}).get("label"), "2026-11-06")

    def test_master_summary_includes_bleed_week(self):
        import desk_master
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[
                    {"id": "btc15m", "today": 8.0, "open_risk": 0, "history": [], "gate_a": {}, "open": []},
                    {"id": "sports-gap", "today": -1.0, "open_risk": 2.0, "history": [], "gate_a": {}, "open": []},
                ],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("bleed_week", plan)
            self.assertTrue((plan.get("bleed_week") or {}).get("fee_floors_locked"))


if __name__ == "__main__":
    unittest.main()
