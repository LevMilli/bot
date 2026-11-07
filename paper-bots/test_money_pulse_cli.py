"""Money-path pulse CLI surfaces — firm queue / completions / feature store."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_living
import desk_roi_plan


class MoneyPulseSurfaces(unittest.TestCase):
    def test_firm_queue_status_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = desk_roi_plan.firm_queue_status(tmp)
            self.assertTrue(st.get("fee_floors_locked") or st.get("paper_only"))
            self.assertIn("towers", st)

    def test_completions_summary_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = desk_living.completions_summary(tmp)
            self.assertTrue(st["fee_floors_locked"])
            self.assertEqual(st["eligible_completions_today"], 0)

    def test_feature_store_coverage_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            cov = desk_living.feature_store_coverage(tmp)
            self.assertIn("n", cov)
            quiet = desk_living.feature_store_quiet_alert(tmp)
            self.assertIsInstance(quiet, dict)

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertAlmostEqual(floors["venues"]["kalshi_sports"]["floor"], 0.06)


if __name__ == "__main__":
    unittest.main()
