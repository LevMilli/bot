"""Commodity Phase 3 time-stop shadow — ≤3m left + underwater mark."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_roi_plan


def _close_in(minutes: float) -> str:
    when = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


class CommodityTimeStop(unittest.TestCase):
    def test_hit_near_close_underwater(self):
        hit = desk_roi_plan.commodity_time_stop_hit(
            _close_in(2.0),
            bid=0.40,
            entry_price=0.55,
            cost=5.5,
            contracts=10,
        )
        self.assertTrue(hit["hit"])
        self.assertTrue(hit["near_close"])
        self.assertTrue(hit["underwater"])
        self.assertTrue(hit["shadow_only"])

    def test_no_hit_when_far_from_close(self):
        hit = desk_roi_plan.commodity_time_stop_hit(
            _close_in(10.0),
            bid=0.40,
            entry_price=0.55,
            cost=5.5,
            contracts=10,
        )
        self.assertFalse(hit["hit"])
        self.assertFalse(hit["near_close"])

    def test_no_hit_when_in_profit(self):
        hit = desk_roi_plan.commodity_time_stop_hit(
            _close_in(2.0),
            bid=0.70,
            entry_price=0.40,
            cost=4.0,
            contracts=10,
        )
        self.assertFalse(hit["hit"])
        self.assertFalse(hit["underwater"])

    def test_shadow_summary_and_no_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = desk_roi_plan.commodity_time_stop_shadow_summary(tmp)
            self.assertTrue(st["evidence_thin"])
            self.assertFalse(st["promote_ready"])
            self.assertIn("THIN", st["label"])
            denied = desk_roi_plan.staff_set_commodity_time_stop_live(tmp, True)
            self.assertFalse(denied["ok"])
            for i in range(30):
                desk_roi_plan.record_commodity_time_stop_shadow(
                    tmp,
                    ticker=f"KX-{i}",
                    side="YES",
                    series="KXWTI15M",
                    close_time=_close_in(1.5),
                    entry_price=0.60,
                    bid=0.40,
                    contracts=10,
                    cost=6.0,
                )
            st2 = desk_roi_plan.commodity_time_stop_shadow_summary(tmp)
            # mark_pnl negative → not promote_ready (EV < 0)
            self.assertGreaterEqual(st2["n_with_pnl"], 30)
            self.assertFalse(st2["promote_ready"])
            armed = desk_roi_plan.staff_set_commodity_time_stop_live(
                tmp, True, force=True, note="test",
            )
            self.assertTrue(armed["ok"])
            self.assertTrue(desk_roi_plan.commodity_time_stop_is_live(tmp))

    def test_default_exit_plan_includes_tstop(self):
        plan = desk_roi_plan.default_exit_plan("commodity-15m")
        self.assertIn("time_stop", plan["kind"])
        self.assertTrue(plan["time_stop_shadow"])
        self.assertFalse(plan["time_stop_live"])

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "commodity-15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("commodity_time_stop", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertAlmostEqual(floors["venues"]["kalshi_commodity15m"]["floor"], 0.05)

    def test_bot_all_opens_densify_path(self):
        bot_src = os.path.join(HERE, "commodity-15m-paper", "bot.py")
        with open(bot_src, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("all-opens densify", text)
        self.assertIn("record_commodity_time_stop_shadow", text)

    def test_settle_retro_time_stop_records_shadow(self):
        """Settle underwater open → settle-retro records time-stop shadow once."""
        bot_src = os.path.join(HERE, "commodity-15m-paper", "bot.py")
        with open(bot_src, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("settle-retro shadow time-stop", text)
        self.assertIn("time_stop_shadowed", text)
        with tempfile.TemporaryDirectory() as tmp:
            close_iso = (
                datetime.now(timezone.utc) - timedelta(minutes=1)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            # now must match parsed close_time (no subsecond drift) → minutes_left≈0.
            close_dt = datetime.fromisoformat(close_iso.replace("Z", "+00:00"))
            rec = desk_roi_plan.record_commodity_time_stop_shadow(
                tmp,
                ticker="KXWTI15M-SETTLE-1",
                side="YES",
                series="KXWTI15M",
                close_time=close_iso,
                entry_price=0.60,
                bid=0.35,
                contracts=10,
                cost=6.0,
                note="settle-retro shadow time-stop — no live sell",
                now=close_dt,
            )
            self.assertTrue(rec["recorded"], rec)
            self.assertTrue(rec.get("shadow_only", True))
            summ = desk_roi_plan.commodity_time_stop_shadow_summary(tmp)
            self.assertEqual(summ["n"], 1)
            self.assertFalse(summ["auto_promote"])
            self.assertFalse(desk_roi_plan.COMMODITY_TIME_STOP_LIVE)
            # Closed flag contract: settle path sets time_stop_shadowed on pos.
            closed = {
                "ticker": "KXWTI15M-SETTLE-1",
                "side": "YES",
                "close_time": close_iso,
                "entry": 0.60,
                "cost": 6.0,
                "contracts": 10,
                "time_stop_shadowed": True,
                "exit": "settled",
                "pnl": -6.0,
            }
            self.assertTrue(closed["time_stop_shadowed"])
            self.assertEqual(closed["exit"], "settled")


if __name__ == "__main__":
    unittest.main()
