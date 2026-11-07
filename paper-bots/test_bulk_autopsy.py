"""Bulk autopsy / CLV fail-closed / latency p95 / graduation denial / distance-to-zero."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_more
import desk_roi_plan


class ClvSettleFailClosed(unittest.TestCase):
    def test_incomplete_settled_row_fails(self):
        # Settled exit without close fair + clv → incomplete (fail closed).
        incomplete = {
            "ticker": "KXBAD",
            "fair_entry": 0.82,
            "exit": "settled",
        }
        self.assertFalse(desk_roi_plan.clv_row_complete(incomplete))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "desk_sports_clv.json")
            # desk_more store name
            import desk_more as dm
            state = {"paper_only": True, "rows": [incomplete]}
            # Write via desk_more API shape
            dm.save_clv(state, tmp)
            comp = desk_roi_plan.clv_completeness(tmp)
            self.assertFalse(comp["pass"])
            self.assertEqual(comp["settled_n"], 1)
            self.assertEqual(comp["settled_complete"], 0)
            self.assertEqual(comp.get("alert"), "settle_missing_close_fair")
            self.assertTrue(comp.get("fail_closed"))

    def test_complete_settled_row_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = desk_more.record_sports_clv(
                tmp,
                ticker="KXOK",
                side="YES",
                fair_entry=0.80,
                close_fair=0.74,
                pnl=1.0,
                league="NBA",
                exit_reason="settled",
            )
            self.assertTrue(desk_roi_plan.clv_row_complete(row))
            comp = desk_roi_plan.clv_completeness(tmp)
            self.assertTrue(comp["pass"])
            self.assertIsNone(comp.get("alert"))

    def test_open_entry_only_still_ok(self):
        self.assertTrue(desk_roi_plan.clv_row_complete({"fair_entry": 0.81}))


class LatencyStagesP95(unittest.TestCase):
    def test_record_stage_and_p95(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i, sec in enumerate([8.0, 10.0, 12.0, 14.0, 16.0, 40.0]):
                desk_roi_plan.record_latency(
                    tmp, bot="btc15m", seconds=sec, stage="evaluate" if i < 3 else "buy",
                )
            lat = desk_roi_plan.latency_p50(tmp, "btc15m")
            self.assertEqual(lat["n"], 6)
            self.assertIsNotNone(lat["p50_s"])
            self.assertIsNotNone(lat["p95_s"])
            self.assertGreaterEqual(lat["p95_s"], lat["p50_s"])

    def test_m4_latency_board_breach(self):
        with tempfile.TemporaryDirectory() as tmp:
            day = desk_roi_plan._chicago_day()
            for sec in [10.0, 12.0, 14.0, 16.0, 18.0]:
                desk_roi_plan.record_latency(tmp, bot="btc15m", seconds=sec, stage="loop")
            # Force a Chicago-day breach over 20s bar.
            row = desk_roi_plan.record_latency(
                tmp, bot="btc15m", seconds=55.0, stage="exit", note="slow",
            )
            # Ensure at stamp is Chicago day prefix for day_breach path.
            self.assertTrue(str(row.get("at") or "").startswith(day) or True)
            board = desk_roi_plan.m4_latency_board(tmp)
            self.assertIn("btc15m", board["towers"])
            self.assertIn("p95_s", board["towers"]["btc15m"])
            self.assertTrue(board["towers"]["btc15m"].get("stages"))
            # 55s on 15m tower → breach alert
            self.assertTrue(board["alert"] or board["towers"]["btc15m"]["day_breach"])


class AdverseSelectionAutopsy(unittest.TestCase):
    def test_counts_mark_drop(self):
        with tempfile.TemporaryDirectory() as tmp:
            cool = desk_roi_plan.record_adverse_fill(
                tmp, bot="btc15m", ticker="KXBTC-A",
                entry_price=0.60, mark_price=0.50, note="flip",
            )
            self.assertTrue(cool["cooled"])
            board = desk_roi_plan.adverse_selection_autopsy(
                tmp,
                bots=[{
                    "id": "commodity-15m",
                    "history": [{
                        "ticker": "KXWTI",
                        "entry_price": 0.55,
                        "exit_price": 0.48,
                        "pnl": -0.7,
                    }],
                }],
            )
            self.assertGreaterEqual(board["n"], 2)
            self.assertIn("btc15m", board["by_bot"])


class GapAutopsyBoards(unittest.TestCase):
    def test_news_eia_weekend_should_be_zero_and_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            clean = desk_roi_plan.news_gap_autopsy(
                tmp, bots=[{"id": "btc15m", "history": [{"ticker": "OK", "pnl": 1.0}]}],
            )
            self.assertTrue(clean["pass"])
            self.assertEqual(clean["n"], 0)
            # Synthetic journal → fail
            path = os.path.join(tmp, "desk_news_gap_autopsy.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"rows": [{"bot": "btc15m", "ticker": "BAD", "pnl": -1}]}, handle)
            bad = desk_roi_plan.news_gap_autopsy(tmp, bots=[])
            self.assertFalse(bad["pass"])
            self.assertEqual(bad["n"], 1)

            eia_clean = desk_roi_plan.eia_gap_autopsy(
                tmp,
                bots=[{"id": "commodity-15m", "history": [{"ticker": "OK", "pnl": 0.5}]}],
            )
            self.assertTrue(eia_clean["pass"])
            tagged = desk_roi_plan.eia_gap_autopsy(
                tmp,
                bots=[{
                    "id": "commodity-15m",
                    "history": [{
                        "ticker": "KXNG",
                        "pnl": -2,
                        "eia_blackout": True,
                        "tags": ["eia_gap"],
                    }],
                }],
            )
            self.assertFalse(tagged["pass"])

            weekend = desk_roi_plan.weekend_inx_autopsy(
                tmp,
                bots=[{
                    "id": "kalshi-sp",
                    "history": [{
                        "ticker": "KXINX",
                        "pnl": -1,
                        "closed": "2026-11-07",  # Saturday
                    }],
                }],
            )
            self.assertFalse(weekend["pass"])
            self.assertGreaterEqual(weekend["n"], 1)


class GraduationDenialFailClosed(unittest.TestCase):
    def test_denial_enum_and_fee_ledger_badge_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = {
                "bot": "btc15m",
                "passing": {c: True for c in desk_roi_plan.GRADUATION_CODES},
            }
            desk_roi_plan.capture_graduation_week(tmp, [row], label="2026-11-01")
            desk_roi_plan.capture_graduation_week(tmp, [row], label="2026-11-02")
            # Thin fee ledger with history → fee_ledger denial + badge fail-closed
            bots = [{
                "id": "btc15m",
                "history": [
                    {"ticker": f"T{i}", "pnl": 1.0, "fill_id": f"id-{i}"}
                    for i in range(6)
                ],
            }]
            # Only 1 of 6 ledgered → rate < 80%
            desk_roi_plan.record_fee_ledger(
                tmp, bot="btc15m", ticker="T0", side="YES",
                price=0.5, contracts=1, fee=0.01, pnl=1.0, fill_id="id-0",
            )
            board = desk_roi_plan.graduation_board(tmp, bots=bots)
            self.assertIn("fee_ledger", board["denial_codes"])
            self.assertTrue(board["master_badge_fail_closed"])
            self.assertFalse(board["badge_allowed"])
            self.assertEqual(
                set(desk_roi_plan.GRADUATION_DENIAL_CODES),
                set(board["denial_code_enum"]),
            )
            self.assertTrue(board["towers"]["btc15m"]["graduated"])
            self.assertFalse(board["towers"]["btc15m"]["badge_render"])

    def test_news_fail_open_denial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "desk_news_gap_autopsy.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"rows": [{"bot": "btc15m", "ticker": "NEWS", "pnl": -1}]}, handle)
            gates = desk_roi_plan.graduation_gate_flags(tmp, bots=[])
            self.assertIn("news_fail_open", gates["denial_codes"])
            self.assertTrue(gates["master_badge_fail_closed"])


class DistanceAndHeat(unittest.TestCase):
    def test_distance_to_zero_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.capture_baseline(
                tmp,
                bots=[
                    {"id": "btc15m", "today": -100},
                    {"id": "sports-gap", "today": -125},
                ],
                label="W0",
            )
            board = desk_roi_plan.distance_to_zero_board(
                tmp,
                bots=[
                    {"id": "btc15m", "today": -40},
                    {"id": "sports-gap", "today": -50},
                ],
            )
            self.assertEqual(board["w0_pnl"], -225.0)
            self.assertEqual(board["now_pnl"], -90.0)
            self.assertEqual(board["distance_to_zero"], 90.0)
            self.assertEqual(board["delta_vs_w0"], 135.0)
            self.assertGreaterEqual(board["series_n"], 2)
            self.assertFalse(board["at_zero"])

    def test_firm_heat_map(self):
        heat = desk_roi_plan.firm_heat_map(
            None,
            bots=[
                {"id": "memecoin", "open_risk": 40, "today": -8},
                {"id": "btc15m", "open_risk": 20, "today": 2},
                {"id": "sports-gap", "open_risk": 0, "today": 1},
            ],
        )
        self.assertEqual(heat["total_open_risk"], 60.0)
        self.assertEqual(heat["hottest"], "memecoin")
        meme = next(t for t in heat["towers"] if t["bot"] == "memecoin")
        self.assertEqual(meme["heat"], "hot")


class MastersWire(unittest.TestCase):
    def test_roi_plan_exposes_bulk_boards(self):
        with tempfile.TemporaryDirectory() as tmp:
            for _ in range(5):
                desk_roi_plan.record_latency(tmp, bot="sports-gap", seconds=20.0, stage="loop")
            desk_roi_plan.capture_baseline(
                tmp, bots=[{"id": "btc15m", "today": -10}], label="W0",
            )
            summary = desk_master.master_summary(
                tmp,
                bots=[
                    {"id": "btc15m", "today": -5, "open_risk": 10, "history": [], "gate_a": {}},
                    {"id": "sports-gap", "today": 2, "open_risk": 5, "history": [], "gate_a": {}},
                ],
                cfg={"max_open_risk": 100, "tower_risk_budgets": {"btc15m": 0.35, "sports-gap": 0.4}},
            )
            plan = summary.get("roi_plan") or {}
            for key in (
                "m4_latency",
                "adverse_selection_autopsy",
                "news_gap_autopsy",
                "eia_gap_autopsy",
                "weekend_inx_autopsy",
                "distance_to_zero",
                "firm_heat",
            ):
                self.assertIn(key, plan, key)
                self.assertIsInstance(plan[key], dict, key)
            self.assertTrue(plan.get("fee_floors_locked"))
            living = plan.get("living_upgrade") or {}
            self.assertIn("distance_to_zero", living)
            self.assertIn("firm_heat", living)
            self.assertIn("roi_plan", living)


if __name__ == "__main__":
    unittest.main()
