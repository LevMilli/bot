"""APEX plan slice next: tip-force AUTO, meme stop-bleed measure, bank walk bounds."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import desk_master
import pimp_desk

ROOT = os.path.dirname(os.path.abspath(__file__))
CT = ZoneInfo("America/Chicago")


class PlanSliceNextTests(unittest.TestCase):
    def test_sports_tip_force_from_cache(self):
        now = datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc)
        tip_soon = (now + timedelta(minutes=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
        tip_far = (now + timedelta(minutes=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
        cache = {
            "https://example/scoreboard": {
                "at": now.isoformat(),
                "body": {
                    "events": [
                        {
                            "name": "Soon Tip Game",
                            "date": tip_soon,
                            "competitions": [
                                {
                                    "date": tip_soon,
                                    "status": {"type": {"state": "pre"}},
                                }
                            ],
                        },
                        {
                            "name": "Far Tip Game",
                            "date": tip_far,
                            "competitions": [
                                {
                                    "date": tip_far,
                                    "status": {"type": {"state": "pre"}},
                                }
                            ],
                        },
                    ]
                },
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "sports-gap-paper")
            os.makedirs(folder)
            with open(os.path.join(folder, "quote_cache.json"), "w", encoding="utf-8") as handle:
                json.dump(cache, handle)
            tip = pimp_desk.sports_tip_alarm_from_cache(tmp, now=now)
            self.assertTrue(tip["active"])
            self.assertEqual(tip["band"], 15)
            self.assertEqual(tip["n_tip"], 1)
            self.assertIn("Soon", tip["sample"])
            gap = pimp_desk._sports_auto_gap_sec(tmp, 180, now=now)
            self.assertEqual(gap, float(pimp_desk.SPORTS_TIP_FORCE_SEC))

            quiet = pimp_desk.sports_tip_alarm_from_cache(
                tmp, now=now + timedelta(hours=3),
            )
            self.assertFalse(quiet["active"])
            self.assertIsNone(quiet["band"])

    def test_sports_tip_band_five(self):
        now = datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc)
        tip = (now + timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        cache = {
            "u": {
                "body": {
                    "events": [
                        {
                            "name": "Imminent",
                            "competitions": [
                                {"date": tip, "status": {"type": {"state": "pre"}}}
                            ],
                        }
                    ]
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "sports-gap-paper")
            os.makedirs(folder)
            with open(os.path.join(folder, "quote_cache.json"), "w", encoding="utf-8") as handle:
                json.dump(cache, handle)
            row = pimp_desk.sports_tip_alarm_from_cache(tmp, now=now)
            self.assertEqual(row["band"], 5)

    def test_meme_stopbleed_measure(self):
        bleed = desk_master.meme_stopbleed_measure(
            {
                "id": "memecoin",
                "today": -5,
                "history": [
                    {"side": "SELL", "exit_reason": "stop -20% <= -18%", "pnl": -3},
                    {"side": "SELL", "exit_reason": "model-flip momentum -9%", "pnl": -1},
                    {"side": "SELL", "exit_reason": "trail 12% off peak", "pnl": 2},
                    {"side": "BUY", "reason": "entry", "pnl": None},
                ],
            }
        )
        self.assertEqual(bleed["stop_exits"], 1)
        self.assertEqual(bleed["model_flip_exits"], 1)
        self.assertEqual(bleed["trail_exits"], 1)
        self.assertFalse(bleed["red_day_locked"])
        self.assertFalse(bleed["expand_volume"])
        summary = desk_master.master_summary(
            bots=[{"id": "memecoin", "open_risk": 1, "history": [], "gate_a": {}}],
            cfg={"max_open_risk": 100, "tower_risk_budgets": {"memecoin": 0.05}},
        )
        self.assertIn("stopbleed", summary)

    def test_timer_mentions_tip_force(self):
        text = pimp_desk.timer_text().lower()
        self.assertIn("45 seconds", text)
        self.assertIn("cached tip", text)

    def test_bank_walk_clamp_contract(self):
        # Mirror bankWalk.ts numbers — keep Python smoke in sync with aisle clear.
        aisle_half, lane_half = 3.25, 0.7
        max_x = max(0.35, aisle_half - lane_half - 0.45)
        z_back, z_front = -8.45, 5.75
        min_z, max_z = z_back + 1.35, z_front - 0.9

        def clamp(x, z):
            return (
                min(max_x, max(-max_x, x)),
                min(max_z, max(min_z, z)),
            )

        x, z = clamp(9.0, -20.0)
        self.assertLessEqual(abs(x), max_x + 1e-9)
        self.assertGreaterEqual(z, min_z - 1e-9)
        x2, z2 = clamp(0.0, 0.0)
        self.assertEqual((x2, z2), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
