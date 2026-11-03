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
            self.assertEqual(summary["version"], 2)
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
        sold = commodity.manage_model_flips(
            state, side_now="NO", prob_now=0.40, bid=0.55, fee=0.02, delta=0.06,
            ticker="KXGOLD-T",
        )
        self.assertEqual(len(sold), 1)
        self.assertEqual(len(state["open"]), 0)
        self.assertIn("model-flip", state["closed"][0]["exit"])

    def test_model_flip_adverse_helper_still_locked(self):
        self.assertTrue(desk_profit.model_flip_adverse("YES", 0.85, 0.70, 0.08))


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


if __name__ == "__main__":
    unittest.main()
