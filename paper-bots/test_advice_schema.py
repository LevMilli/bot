"""Helper advice schema validator."""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import helpers
from helpers.advice_schema import validate_helper_advice


class AdviceSchema(unittest.TestCase):
    def test_requires_floors_and_ttl(self):
        ok, reason = validate_helper_advice({"ttl": 60})
        self.assertFalse(ok)
        self.assertIn("floors_locked", reason)
        ok, reason = validate_helper_advice({"floors_locked": True, "ttl": 0})
        self.assertFalse(ok)
        self.assertIn("ttl", reason)
        ok, reason = validate_helper_advice({"fee_floors_locked": True, "ttl": 30})
        self.assertTrue(ok)
        self.assertEqual(helpers.validate_helper_advice({"floors_locked": True, "ttl": 10})[0], True)

    def test_rejects_soften_below_floor(self):
        ok, reason = validate_helper_advice({
            "floors_locked": True,
            "ttl": 60,
            "venue_min_edge": {"kalshi_sports": 0.04},
        })
        self.assertFalse(ok)
        self.assertIn("soften", reason)
        ok, _ = validate_helper_advice({
            "floors_locked": True,
            "ttl": 60,
            "venue_min_edge": {"kalshi_btc15m": 0.05},
        })
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
