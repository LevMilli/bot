"""Opportunity-cost clock + 90d idea review cadence."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_roi_plan


class OppCostIdeas(unittest.TestCase):
    def test_record_requires_wait_and_higher_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            short = desk_roi_plan.record_opp_cost(
                tmp, bot="sports-gap", blocked_ticker="A", blocked_edge=0.1,
                taken_ticker="B", taken_edge=0.05, wait_sec=30,
            )
            self.assertFalse(short["recorded"])
            worse = desk_roi_plan.record_opp_cost(
                tmp, bot="sports-gap", blocked_ticker="A", blocked_edge=0.04,
                taken_ticker="B", taken_edge=0.08, wait_sec=120,
            )
            self.assertFalse(worse["recorded"])
            ok = desk_roi_plan.record_opp_cost(
                tmp, bot="sports-gap", blocked_ticker="A", blocked_edge=0.12,
                taken_ticker="B", taken_edge=0.05, wait_sec=120,
            )
            self.assertTrue(ok["recorded"])
            self.assertEqual(desk_roi_plan.opp_cost_summary(tmp)["n"], 1)

    def test_pending_flush(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.note_pending_high_edge(
                tmp, bot="sports-gap", ticker="KXHI", edge=0.15, reason="max buys",
            )
            store = desk_roi_plan._opp_store(tmp)
            for row in (store.get("pending") or {}).values():
                row["first_at"] = "2026-10-01T00:00:00+00:00"
            desk_roi_plan._save(desk_roi_plan._path(desk_roi_plan.OPP_COST_NAME, tmp), store)
            out = desk_roi_plan.flush_opp_cost_on_buy(
                tmp, bot="sports-gap", ticker="KXLO", edge=0.05,
            )
            self.assertGreaterEqual(out["emitted"], 1)

    def test_idea_register_and_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = desk_roi_plan.staff_register_idea(
                tmp, idea="raise BTC cushion", lever="min_cushion_btc", who="alice",
            )
            self.assertTrue(reg["ok"])
            idea_id = reg["idea"]["id"]
            st = desk_roi_plan.idea_review_status(tmp)
            self.assertEqual(st["open_n"], 1)
            self.assertEqual(st["stale_n"], 0)
            closed = desk_roi_plan.staff_close_idea(
                tmp, idea_id, decision="kill", note="no lift", who="bob",
            )
            self.assertTrue(closed["ok"])
            self.assertEqual(desk_roi_plan.idea_review_status(tmp)["open_n"], 0)

    def test_stale_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = desk_roi_plan.staff_register_idea(tmp, idea="old idea", who="ops")
            path = desk_roi_plan._path(desk_roi_plan.IDEA_REVIEW_NAME, tmp)
            store = desk_roi_plan._load(path, {"ideas": []})
            for row in store.get("ideas") or []:
                row["opened_at"] = "2026-01-01T00:00:00+00:00"
            desk_roi_plan._save(path, store)
            st = desk_roi_plan.idea_review_status(tmp)
            self.assertEqual(st["stale_n"], 1)
            self.assertTrue(st["stale"][0]["stale"])

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "sports-gap", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("opp_cost", plan)
            self.assertIn("idea_review", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])


if __name__ == "__main__":
    unittest.main()
