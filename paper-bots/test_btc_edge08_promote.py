"""BTC edge08 shadow promote — raise-only venue_edge 0.08; floors locked."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_roi_plan
import pimp_desk


def _seed_ready(tmp: str, n: int = 30, pnl: float = 1.0) -> None:
    now = datetime.now(timezone.utc)
    closed = []
    for i in range(n):
        closed.append({
            "pnl": pnl,
            "at": (now - timedelta(days=i % 10)).isoformat(),
            "fill_id": f"e{i}",
        })
    pimp_desk.save_shadow_account(tmp, "btc15m", "edge08", {
        "cash": 100.0, "open": [], "closed": closed, "paper_only": True,
    })


class BtcEdge08Promote(unittest.TestCase):
    def test_not_ready_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = desk_roi_plan.btc_edge08_shadow_status(tmp)
            self.assertFalse(st["promote_ready"])
            self.assertFalse(st["auto_promote"])
            denied = desk_roi_plan.staff_promote_btc_edge08(tmp)
            self.assertFalse(denied["ok"])

    def test_promote_when_ready_raises_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            _seed_ready(tmp, 30, pnl=1.0)
            st = desk_roi_plan.btc_edge08_shadow_status(tmp)
            self.assertTrue(st["promote_ready"])
            self.assertGreaterEqual(st["n"], 30)
            armed = desk_roi_plan.staff_promote_btc_edge08(
                tmp, who="ops", note="edge08 ready",
            )
            self.assertTrue(armed["ok"])
            self.assertEqual(armed["venue_edge"], 0.08)
            self.assertTrue(armed["fee_floors_locked"])
            overlay = pimp_desk._read_json(os.path.join(tmp, "pimp-bot-params.json")) or {}
            self.assertEqual(float(overlay["btc15m"]["venue_edge"]), 0.08)
            self.assertEqual(overlay["btc15m"]["promoted_from_shadow"], "edge08")

    def test_force_before_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            pimp_desk.save_shadow_account(tmp, "btc15m", "edge08", {
                "cash": 100.0, "open": [], "closed": [], "paper_only": True,
            })
            armed = desk_roi_plan.staff_promote_btc_edge08(tmp, force=True, who="ops")
            self.assertTrue(armed["ok"])
            self.assertEqual(armed["venue_edge"], 0.08)

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("btc_edge08_shadow", plan)

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertAlmostEqual(floors["venues"]["kalshi_btc15m"]["floor"], 0.05)


if __name__ == "__main__":
    unittest.main()
