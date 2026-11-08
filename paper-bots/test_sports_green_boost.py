"""Sports green_boost gate + green-or-gone Masters flags."""
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


class SportsGreenBoost(unittest.TestCase):
    def test_default_boost_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = desk_roi_plan.sports_green_boost_status(tmp, bots=[])
            self.assertFalse(st["ready"])
            self.assertTrue(st["evidence_thin"])
            self.assertTrue(st["observe_only"])
            self.assertIn("THIN", st["label"])
            self.assertTrue(st["missing"])
            self.assertEqual(st["green_boost"], 0)
            self.assertFalse(st["auto_promote"])
            self.assertEqual(desk_roi_plan.sports_green_boost(tmp), 0)

    def test_hydrates_sports_m1_from_account_without_bots(self):
        """gap_bot calls green_boost(root) with no bots — must see closed fills."""
        with tempfile.TemporaryDirectory() as tmp:
            sports_dir = os.path.join(tmp, "sports-gap-paper")
            os.makedirs(sports_dir, exist_ok=True)
            closed = [
                {
                    "ticker": f"KX-{i}",
                    "pnl": 0.50,
                    "contracts": 2,
                    "closed": f"2026-11-08 12:0{i % 10}:00 CT",
                }
                for i in range(20)
            ]
            with open(os.path.join(sports_dir, "state.json"), "w", encoding="utf-8") as fh:
                json.dump({"cash": 100, "open": [], "closed": closed, "paper_only": True}, fh)
            st = desk_roi_plan.sports_green_boost_status(tmp)  # bots=None
            self.assertEqual(st["sports_m1_n"], 20)
            self.assertTrue(st["hist_ok"])
            self.assertGreaterEqual(float(st["sports_m1"]), 0.0)
            # Still thin on weeks/CLV — never force-arms.
            self.assertFalse(st["ready"])
            self.assertEqual(st["green_boost"], 0)
            self.assertFalse(st["auto_promote"])

    def test_repair_weekly_sports_m1_from_day_closes(self):
        with tempfile.TemporaryDirectory() as tmp:
            sports_dir = os.path.join(tmp, "sports-gap-paper")
            os.makedirs(sports_dir, exist_ok=True)
            with open(os.path.join(sports_dir, "state.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "cash": 100,
                    "open": [],
                    "closed": [
                        {
                            "ticker": "KX-A",
                            "pnl": 2.0,
                            "contracts": 10,
                            "closed": "2026-11-06 18:00:00 CT",
                        },
                        {
                            "ticker": "KX-B",
                            "pnl": 1.0,
                            "contracts": 5,
                            "closed": "2026-11-07 19:00:00 CT",
                        },
                    ],
                    "paper_only": True,
                }, fh)
            # Seed cards missing sports_m1 (capture without sports history).
            path = os.path.join(tmp, desk_roi_plan.WEEKLY_SCORECARD)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({
                    "paper_only": True,
                    "cards": [
                        {"label": "2026-11-06", "sports_m1": None, "m1": 0.1},
                        {"label": "2026-11-07", "sports_m1": None, "m1": 0.2},
                        {"label": "2026-11-08", "sports_m1": 1.5, "m1": 0.3},
                    ],
                }, fh)
            out = desk_roi_plan.repair_weekly_sports_m1(tmp)
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["repaired"], 2)
            with open(path, encoding="utf-8") as fh:
                cards = json.load(fh)["cards"]
            by = {c["label"]: c for c in cards}
            self.assertIsNotNone(by["2026-11-06"]["sports_m1"])
            self.assertIsNotNone(by["2026-11-07"]["sports_m1"])
            # No closes on 11-08 → leave prior sports_m1 alone.
            self.assertEqual(by["2026-11-08"]["sports_m1"], 1.5)
            st = desk_roi_plan.sports_green_boost_status(tmp)
            self.assertTrue(st["weeks_ok"])
            self.assertEqual(st["weeks_n"], 2)

    def test_repair_weekly_sports_m1_refreshes_stale_day_copy(self):
        """Stale card with prior-day m1/n must refresh once that day's closes exist."""
        with tempfile.TemporaryDirectory() as tmp:
            sports_dir = os.path.join(tmp, "sports-gap-paper")
            os.makedirs(sports_dir, exist_ok=True)
            with open(os.path.join(sports_dir, "state.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "cash": 100,
                    "open": [],
                    "closed": [
                        {
                            "ticker": "KX-DAY8-A",
                            "pnl": -1.44,
                            "contracts": 24,
                            "closed": "2026-11-08 13:15:38 CT",
                        },
                        {
                            "ticker": "KX-DAY8-B",
                            "pnl": -1.95,
                            "contracts": 39,
                            "closed": "2026-11-08 14:48:37 CT",
                        },
                        {
                            "ticker": "KX-DAY8-C",
                            "pnl": 3.45,
                            "contracts": 10,
                            "closed": "2026-11-08 00:30:49 CT",
                        },
                    ],
                    "paper_only": True,
                }, fh)
            path = os.path.join(tmp, desk_roi_plan.WEEKLY_SCORECARD)
            # Poison: 11-08 card copied prior-day m1/n=14 (green weeks_ok false friend).
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({
                    "paper_only": True,
                    "cards": [
                        {
                            "label": "2026-11-07",
                            "sports_m1": 3.1714,
                            "sports_m1_n": 14,
                        },
                        {
                            "label": "2026-11-08",
                            "sports_m1": 3.1714,
                            "sports_m1_n": 14,
                        },
                    ],
                }, fh)
            out = desk_roi_plan.repair_weekly_sports_m1(tmp)
            self.assertTrue(out["ok"], out)
            self.assertGreaterEqual(out["repaired"], 1)
            self.assertFalse(out.get("live"))
            self.assertFalse(out.get("auto_promote"))
            with open(path, encoding="utf-8") as fh:
                by = {c["label"]: c for c in json.load(fh)["cards"]}
            day8 = by["2026-11-08"]
            self.assertEqual(day8["sports_m1_n"], 3)
            # Taxed m1: (-1.44-0.24)+(-1.95-0.39)+(3.45-0.10) / 3
            self.assertAlmostEqual(float(day8["sports_m1"]), -0.2233, places=3)
            self.assertTrue(day8.get("sports_m1_repaired"))
            # Idempotent once honest.
            out2 = desk_roi_plan.repair_weekly_sports_m1(tmp)
            self.assertEqual(out2["repaired"], 0)

    def test_green_missing_names_negative_week_m1_not_weeks_2_of_2(self):
        """Enough week cards with sports_m1<0 must not emit false-friend weeks 2/2."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, desk_roi_plan.WEEKLY_SCORECARD)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({
                    "paper_only": True,
                    "cards": [
                        {"label": "2026-11-07", "sports_m1": 3.1714, "sports_m1_n": 14},
                        {"label": "2026-11-08", "sports_m1": -0.2667, "sports_m1_n": 3},
                    ],
                }, fh)
            st = desk_roi_plan.sports_green_boost_status(tmp, bots=[])
            self.assertFalse(st["weeks_ok"])
            miss = " ".join(st.get("missing") or [])
            self.assertIn("weeks_m1<0", miss)
            self.assertIn("2026-11-08", miss)
            self.assertNotIn("weeks 2/2", miss)

    def test_green_missing_names_underwater_hist_not_n_bar_cleared(self):
        """n≥bar with expectancy_taxed<0 must not emit false-friend sports_m1_n 30/20."""
        with tempfile.TemporaryDirectory() as tmp:
            # Heavy losers → firm_taxed_m1 expectancy < 0 with n≥20.
            hist = [{"pnl": -1.0, "contracts": 1} for _ in range(25)]
            hist += [{"pnl": 0.1, "contracts": 1} for _ in range(5)]
            bots = [{"id": "sports-gap", "history": hist, "gate_a": {"ready": True}}]
            st = desk_roi_plan.sports_green_boost_status(tmp, bots=bots)
            self.assertFalse(st["hist_ok"])
            self.assertGreaterEqual(int(st["sports_m1_n"]), desk_roi_plan.SPORTS_M1_MIN_N)
            self.assertIsNotNone(st["sports_m1"])
            self.assertLess(float(st["sports_m1"]), 0.0)
            miss = " ".join(st.get("missing") or [])
            self.assertIn("sports_m1<0", miss)
            self.assertNotIn(
                f"sports_m1_n {st['sports_m1_n']}/{desk_roi_plan.SPORTS_M1_MIN_N}",
                miss,
            )

    def test_green_missing_names_clv_rate_fail_not_n_bar_cleared(self):
        """CLV n≥bar with beat-close below bar must not emit false-friend clv 25/20."""
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(25):
                desk_more.record_sports_clv(
                    tmp,
                    ticker=f"KX-{i}",
                    side="home",
                    fair_entry=0.60,
                    close_fair=0.50 if i < 10 else 0.70,  # 10/25 = 0.40 beat
                    pnl=0.05,
                )
            st = desk_roi_plan.sports_green_boost_status(tmp, bots=[])
            self.assertFalse(st["clv_ok"])
            self.assertGreaterEqual(int(st["clv_n"]), desk_roi_plan.SPORTS_CLV_MIN_N)
            miss = " ".join(st.get("missing") or [])
            self.assertIn("clv_rate<", miss)
            self.assertNotIn(
                f"clv {st['clv_n']}/{desk_roi_plan.SPORTS_CLV_MIN_N}",
                miss,
            )

    def test_ready_when_weeks_hist_clv(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = [{"pnl": 0.10, "contracts": 1} for _ in range(20)]
            bots = [{"id": "sports-gap", "today": 2.0, "history": hist, "gate_a": {"ready": True}}]
            # Two weekly cards with sports_m1 ≥ 0.
            desk_roi_plan.capture_weekly_scorecard(tmp, bots=bots, label="2026-10-27")
            desk_roi_plan.capture_weekly_scorecard(tmp, bots=bots, label="2026-11-03")
            # CLV beat-close ≥52% with n≥20.
            for i in range(20):
                desk_more.record_sports_clv(
                    tmp,
                    ticker=f"KX-{i}",
                    side="home",
                    fair_entry=0.60,
                    close_fair=0.50 if i < 12 else 0.65,  # 12/20 = 0.60 beat
                    pnl=0.05,
                )
            st = desk_roi_plan.sports_green_boost_status(tmp, bots=bots)
            self.assertTrue(st["hist_ok"])
            self.assertTrue(st["weeks_ok"])
            self.assertTrue(st["clv_ok"])
            self.assertTrue(st["ready"])
            self.assertFalse(st["evidence_thin"])
            self.assertEqual(st["missing"], [])
            self.assertIn("ready", st["label"])
            self.assertEqual(st["green_boost"], 1)

    def test_green_or_gone_flags_red_open(self):
        flags = desk_roi_plan.green_or_gone_status([
            {"id": "memecoin", "today": -5.0, "open_risk": 8.0, "gate_a": {"ready": False}},
            {"id": "btc15m", "today": 2.0, "open_risk": 10.0, "gate_a": {"ready": True}},
        ])
        self.assertFalse(flags["pass"])
        self.assertEqual(flags["flagged_n"], 1)
        self.assertEqual(flags["flags"][0]["bot"], "memecoin")

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "sports-gap", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("sports_green_boost", plan)
            self.assertIn("green_or_gone", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])

    def test_staff_cannot_arm_before_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            denied = desk_roi_plan.staff_set_sports_green_boost(tmp, True)
            self.assertFalse(denied["ok"])
            self.assertEqual(desk_roi_plan.sports_green_boost(tmp), 0)

    def test_staff_force_arm_without_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            armed = desk_roi_plan.staff_set_sports_green_boost(
                tmp, True, note="staff gate lifted", force=True,
            )
            self.assertTrue(armed["ok"])
            self.assertEqual(armed["green_boost"], 1)
            st = desk_roi_plan.sports_green_boost_status(tmp)
            self.assertFalse(st["ready"])
            self.assertTrue(st["staff_armed"])
            self.assertEqual(st["green_boost"], 1)
            self.assertEqual(desk_roi_plan.sports_green_boost(tmp), 1)
            disarmed = desk_roi_plan.staff_set_sports_green_boost(tmp, False)
            self.assertTrue(disarmed["ok"])
            self.assertEqual(desk_roi_plan.sports_green_boost(tmp), 0)


if __name__ == "__main__":
    unittest.main()
