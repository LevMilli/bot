"""Wire profit_lock_size_mult into stake_dollars_for Kelly path."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_roi_plan
import pimp_desk


class ProfitLockKelly(unittest.TestCase):
    def test_stake_halves_when_locked(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.capture_profit_lock(
                tmp,
                bots=[{"id": "sports-gap", "today": 45.0}],
                label="2026-11-03",
                target_usd=40.0,
            )
            self.assertEqual(desk_roi_plan.profit_lock_size_mult(tmp), 0.5)
            cfg = dict(pimp_desk.DEFAULTS)
            # Avoid tower-budget / history side effects by stubbing view path.
            with mock.patch.object(pimp_desk, "_load_runs", return_value={}):
                with mock.patch.object(
                    pimp_desk,
                    "_bot_view",
                    return_value={"id": "btc15m", "history": [], "open_risk": 0},
                ):
                    open_stake, plan = pimp_desk.stake_dollars_for(
                        "btc15m",
                        0.90,
                        edge=0.10,
                        cfg=cfg,
                        open_risk_used=0,
                        ask=0.70,
                        root=tmp,
                        return_plan=True,
                    )
            self.assertLessEqual(plan.get("profit_lock_mult") or 1.0, 0.5 + 1e-9)
            self.assertTrue(
                any("profit-lock" in str(n) for n in (plan.get("notes") or []))
            )
            # Unlocked root should size larger or equal.
            with tempfile.TemporaryDirectory() as tmp2:
                with mock.patch.object(pimp_desk, "_load_runs", return_value={}):
                    with mock.patch.object(
                        pimp_desk,
                        "_bot_view",
                        return_value={"id": "btc15m", "history": [], "open_risk": 0},
                    ):
                        free_stake, free_plan = pimp_desk.stake_dollars_for(
                            "btc15m",
                            0.90,
                            edge=0.10,
                            cfg=cfg,
                            open_risk_used=0,
                            ask=0.70,
                            root=tmp2,
                            return_plan=True,
                        )
            self.assertNotIn("profit_lock_mult", free_plan)
            if free_stake > 0 and open_stake > 0:
                self.assertLess(open_stake + 1e-9, free_stake)
                self.assertAlmostEqual(open_stake, free_stake * 0.5, places=2)

    def test_floors_still_locked(self):
        floors = __import__("desk_profit").venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])
        self.assertGreaterEqual(floors["venues"]["kalshi_sports"]["floor"], 0.06)


if __name__ == "__main__":
    unittest.main()