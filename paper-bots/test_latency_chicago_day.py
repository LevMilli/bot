"""Latency rows are stamped in UTC; the boards count them on the Chicago day."""
import tempfile
import unittest
from unittest import mock

import desk_roi_plan


class LatencyChicagoDay(unittest.TestCase):
    def test_utc_stamp_maps_to_the_chicago_day(self):
        # 9 PM CT on Nov 11 is already Nov 12 in UTC.
        self.assertEqual(desk_roi_plan._stamp_chicago_day("2026-11-12T03:00:00Z"), "2026-11-11")
        self.assertEqual(desk_roi_plan._stamp_chicago_day("2026-11-11T18:00:00Z"), "2026-11-11")
        self.assertEqual(desk_roi_plan._stamp_chicago_day("2026-11-11 21:00:00 CT"), "2026-11-11")
        self.assertEqual(desk_roi_plan._stamp_chicago_day(""), "")

    def test_evening_breach_counts_today(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {"rows": [
                {"at": "2026-11-12T03:00:00Z", "bot": "btc15m", "seconds": 55.0, "stage": "exit"},
            ]}
            desk_roi_plan.save_latency(state, tmp)
            with mock.patch.object(desk_roi_plan, "_chicago_day", return_value="2026-11-11"):
                board = desk_roi_plan.m4_latency_board(tmp)
            self.assertTrue(board["towers"]["btc15m"]["day_breach"])


if __name__ == "__main__":
    unittest.main()
