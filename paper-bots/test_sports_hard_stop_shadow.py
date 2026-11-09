"""Sports hard-stop shadow + latency/fit wiring (positive-ROI next slice)."""
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


class SportsHardStopShadow(unittest.TestCase):
    def test_hit_threshold(self):
        hit = desk_roi_plan.sports_hard_stop_hit(0.80, 0.68, drop=0.12)
        self.assertTrue(hit["hit"])
        self.assertEqual(hit["threshold"], 0.68)
        miss = desk_roi_plan.sports_hard_stop_hit(0.80, 0.69, drop=0.12)
        self.assertFalse(miss["hit"])

    def test_hit_allows_finalized_loser_bid_zero(self):
        # Settle-retro densify: Kalshi finalized losers quote yes_bid=0.
        # bid=0 must count (strongest adverse) — never treat as missing quote.
        hit = desk_roi_plan.sports_hard_stop_hit(0.72, 0.0, drop=0.12)
        self.assertTrue(hit["hit"])
        self.assertEqual(hit["bid"], 0.0)
        self.assertEqual(hit["threshold"], 0.60)
        with tempfile.TemporaryDirectory() as tmp:
            rec = desk_roi_plan.record_sports_hard_stop_shadow(
                tmp,
                ticker="KX-LOSER-0",
                entry_price=0.72,
                bid=0.0,
                contracts=10,
                cost=7.2,
            )
            self.assertTrue(rec["recorded"])
            row = rec["row"]
            self.assertTrue(row["priced_at_threshold"])
            self.assertEqual(row["exit_bid"], 0.60)
            # Exit at threshold — not full wipe — so EV is stop-fill, not -cost.
            self.assertGreater(row["shadow_pnl"], -7.2)
            self.assertEqual(desk_roi_plan.sports_hard_stop_shadow_summary(tmp)["n"], 1)

    def test_shadow_never_live_by_default(self):
        self.assertFalse(desk_roi_plan.SPORTS_HARD_STOP_LIVE)
        with tempfile.TemporaryDirectory() as tmp:
            rec = desk_roi_plan.record_sports_hard_stop_shadow(
                tmp,
                ticker="KXNBA-T",
                side="home",
                league="NBA",
                entry_price=0.78,
                bid=0.60,
                contracts=20,
                cost=16.0,
            )
            self.assertTrue(rec["recorded"])
            self.assertTrue(rec["shadow_only"])
            summ = desk_roi_plan.sports_hard_stop_shadow_summary(tmp)
            self.assertEqual(summ["n"], 1)
            self.assertFalse(summ["live"])
            self.assertFalse(summ["auto_promote"])
            self.assertEqual(summ["decision"], "reject")  # n < 30
            self.assertTrue(summ["evidence_thin"])
            self.assertGreater(summ["n_to_promote"], 0)
            self.assertIn("THIN", summ.get("label") or "")

    def test_promote_stays_review_not_auto(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(30):
                desk_roi_plan.record_sports_hard_stop_shadow(
                    tmp,
                    ticker=f"T{i}",
                    entry_price=0.80,
                    bid=0.60,
                    contracts=10,
                    cost=5.0,  # shadow pnl positive-ish at bid 0.60
                )
            summ = desk_roi_plan.sports_hard_stop_shadow_summary(tmp)
            self.assertGreaterEqual(summ["n_with_pnl"], 30)
            # Even when EV looks ok, never auto-promote.
            self.assertFalse(summ["auto_promote"])
            self.assertFalse(summ["code_default_live"])
            self.assertFalse(desk_roi_plan.SPORTS_HARD_STOP_LIVE)
            self.assertIn(summ["decision"], ("review", "reject"))
            self.assertTrue(summ["promote_ready"])
            self.assertFalse(summ["evidence_thin"])
            self.assertEqual(summ["n_to_promote"], 0)
            # Staff arm via file; code constant stays False.
            armed = desk_roi_plan.staff_set_sports_hard_stop_live(
                tmp, True, note="n≥30 shadow EV ok",
            )
            self.assertTrue(armed["ok"])
            self.assertTrue(desk_roi_plan.sports_hard_stop_is_live(tmp))
            self.assertFalse(desk_roi_plan.SPORTS_HARD_STOP_LIVE)
            disarmed = desk_roi_plan.staff_set_sports_hard_stop_live(tmp, False)
            self.assertTrue(disarmed["ok"])
            self.assertFalse(desk_roi_plan.sports_hard_stop_is_live(tmp))

    def test_staff_cannot_arm_before_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_sports_hard_stop_shadow(
                tmp, ticker="T0", entry_price=0.80, bid=0.60, contracts=10, cost=5.0,
            )
            denied = desk_roi_plan.staff_set_sports_hard_stop_live(tmp, True)
            self.assertFalse(denied["ok"])
            self.assertFalse(desk_roi_plan.sports_hard_stop_is_live(tmp))

    def test_staff_force_arm_before_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_sports_hard_stop_shadow(
                tmp, ticker="T0", entry_price=0.80, bid=0.60, contracts=10, cost=5.0,
            )
            armed = desk_roi_plan.staff_set_sports_hard_stop_live(
                tmp, True, note="staff gate lifted", force=True,
            )
            self.assertTrue(armed["ok"])
            self.assertTrue(desk_roi_plan.sports_hard_stop_is_live(tmp))
            self.assertFalse(desk_roi_plan.SPORTS_HARD_STOP_LIVE)


class StaffBatchArmPromotes(unittest.TestCase):
    def test_batch_force_arms_all_three(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.staff_batch_arm_promotes(
                tmp,
                force=True,
                note="staff gate lifted batch",
                inx_band_id="80_90",
            )
            self.assertTrue(out["ok"])
            self.assertFalse(out["auto_promote"])
            self.assertTrue(out["fee_floors_locked"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertTrue(desk_roi_plan.sports_hard_stop_is_live(tmp))
            self.assertEqual(desk_roi_plan.sports_green_boost(tmp), 1)
            live = desk_roi_plan.inx_live_band(tmp)
            self.assertEqual(live["id"], "80_90")
            self.assertTrue(live["staff_approved"])
            self.assertFalse(live["live_changed"])

    def test_batch_denied_without_force_when_thin(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.staff_batch_arm_promotes(tmp, force=False)
            self.assertFalse(out["ok"])
            self.assertFalse(desk_roi_plan.sports_hard_stop_is_live(tmp))
            self.assertEqual(desk_roi_plan.sports_green_boost(tmp), 0)


class SportsLatencyFit(unittest.TestCase):
    def test_sports_m4_bar_is_45s(self):
        with tempfile.TemporaryDirectory() as tmp:
            for _ in range(5):
                desk_roi_plan.record_latency(tmp, bot="sports-gap", seconds=30.0)
            lat = desk_roi_plan.latency_p50(tmp, "sports-gap")
            self.assertEqual(lat["bar_s"], 45.0)
            self.assertTrue(lat["pass"])
            row = desk_master.tower_master_row(
                {"id": "sports-gap", "open_risk": 0, "history": [], "gate_a": {}},
                cfg={"max_open_risk": 100, "tower_risk_budgets": {"sports-gap": 0.35}},
                root=tmp,
            )
            self.assertEqual(row["M4_bar_s"], 45.0)
            self.assertTrue(row["passing"]["M4"])

    def test_master_exposes_hard_stop_shadow(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_sports_hard_stop_shadow(
                tmp, ticker="T", entry_price=0.8, bid=0.5, contracts=1, cost=1,
            )
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "sports-gap", "today": 1, "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100, "tower_risk_budgets": {"sports-gap": 0.35}},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("sports_hard_stop_shadow", plan)
            self.assertFalse(plan["sports_hard_stop_shadow"]["live"])


class FeeFloorsStillLocked(unittest.TestCase):
    def test_floors(self):
        import desk_profit
        parsed, err = desk_profit.parse_venue_min_edge({"kalshi_sports": 0.03})
        self.assertIsNone(parsed)
        self.assertIn("cannot lower", err or "")


class HardStopShadowCsvExport(unittest.TestCase):
    def test_export_csv_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(3):
                desk_roi_plan.record_sports_hard_stop_shadow(
                    tmp,
                    ticker=f"T{i}",
                    entry_price=0.80,
                    bid=0.60,
                    contracts=10,
                    cost=5.0,
                )
            out = desk_roi_plan.export_sports_hard_stop_shadow_csv(tmp)
            self.assertTrue(out["ok"])
            self.assertEqual(out["n"], 3)
            self.assertTrue(out["fee_floors_locked"])
            self.assertFalse(out["auto_promote"])
            self.assertIn("shadow_pnl", out["csv"])
            self.assertTrue(out["path"] and out["path"].endswith(".csv"))


class OrphanHardStopDensify(unittest.TestCase):
    """Prefer-1: info=None opens must ticker-fetch + HS densify (no live sell)."""

    def test_gap_bot_wires_orphan_info_none_hs(self):
        gap_path = os.path.join(HERE, "sports-gap-paper", "gap_bot.py")
        with open(gap_path, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("orphan shadow hard-stop — no live sell", src)
        self.assertIn("ORPHAN STOP", src)
        self.assertIn("if info is None and bid is not None:", src)
        # Fetch must not require live_info (starved shadow n while losers rode).
        self.assertNotIn("if info and bid is None:", src)
        self.assertIn("if bid is None:", src)
        self.assertFalse(desk_roi_plan.SPORTS_HARD_STOP_LIVE)

    def test_orphan_note_records_shadow_not_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec = desk_roi_plan.record_sports_hard_stop_shadow(
                tmp,
                ticker="KX-ORPHAN-1",
                side="home",
                league="NBA",
                entry_price=0.80,
                bid=0.60,
                fair=None,
                contracts=10,
                cost=8.0,
                note="orphan shadow hard-stop — no live sell",
            )
            self.assertTrue(rec["recorded"])
            self.assertTrue(rec["shadow_only"])
            summ = desk_roi_plan.sports_hard_stop_shadow_summary(tmp)
            self.assertEqual(summ["n"], 1)
            self.assertFalse(summ["live"])
            self.assertFalse(desk_roi_plan.sports_hard_stop_is_live(tmp))


if __name__ == "__main__":
    unittest.main()
