"""Sports extra size waits for 85% accuracy, not the desk's 80% play-big."""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GAP_DIR = os.path.join(HERE, "sports-gap-paper")
if GAP_DIR not in sys.path:
    sys.path.insert(0, GAP_DIR)

import gap_bot


def _perf(*, hit, n, ci, ev):
    return {"hit_rate": hit, "n": n, "hit_ci_low": ci, "expectancy": ev}


class SportsAccuracySize(unittest.TestCase):
    def test_current_book_does_not_size_up(self):
        # 39 wins / 76 decided on the Nov 10 export. Average is still red.
        self.assertFalse(gap_bot.sports_accuracy_ready(
            _perf(hit=0.5132, n=77, ci=0.40, ev=-0.11)
        ))
        stake = gap_bot.apply_sports_accuracy_size(20.0, {"play_big": False, "perf": _perf(
            hit=0.5132, n=77, ci=0.40, ev=-0.11
        )})
        self.assertEqual(stake, 20.0)

    def test_desk_80_percent_size_up_is_removed(self):
        plan = {
            "play_big": True,
            "play_safe": False,
            "perf": _perf(hit=0.82, n=40, ci=0.71, ev=0.20),
        }
        # Desk had already multiplied by 1.75. Sports gives that back.
        self.assertEqual(gap_bot.apply_sports_accuracy_size(35.0, plan), 20.0)

    def test_85_percent_with_green_average_adds_half(self):
        plan = {
            "play_big": True,
            "play_safe": False,
            "perf": _perf(hit=0.867, n=30, ci=0.703, ev=0.15),
        }
        self.assertTrue(gap_bot.sports_accuracy_ready(plan["perf"]))
        # 30 was the desk's 1.75× stake. Back to base 17.14, then ×1.50.
        self.assertEqual(gap_bot.apply_sports_accuracy_size(30.0, plan), 25.71)

    def test_short_85_percent_streak_stays_base_size(self):
        # 17/20 is 85% on the point and only ~64% on the Wilson floor.
        self.assertFalse(gap_bot.sports_accuracy_ready(
            _perf(hit=0.85, n=20, ci=0.64, ev=0.10)
        ))

    def test_high_vol_blocks_the_extra_even_at_85(self):
        plan = {
            "play_big": False,
            "play_safe": True,
            "perf": _perf(hit=0.90, n=40, ci=0.75, ev=0.20),
        }
        self.assertEqual(gap_bot.apply_sports_accuracy_size(12.0, plan), 12.0)

    def test_fee_floor_unchanged(self):
        self.assertEqual(gap_bot.MIN_GAP, 0.06)
        self.assertEqual(gap_bot.MIN_GAP_MODEL, 0.08)


if __name__ == "__main__":
    unittest.main()
