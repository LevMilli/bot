#!/usr/bin/env python3
"""Sports-gap evaluate densify: skips surface on CARD; book-unchanged still logs."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
GAP = HERE / "sports-gap-paper" / "gap_bot.py"


def _load_gap():
    spec = importlib.util.spec_from_file_location("gap_bot_under_test", GAP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SportsGapSkipDensify(unittest.TestCase):
    def test_card_prefers_evaluate_skip_over_lanes_clear(self):
        gap = _load_gap()
        card = gap._card_line({
            "trades": [],
            "skips": ["gap < 6 (accurate) - no trade"],
            "live_games": 8,
            "matched": 13,
        })
        self.assertIn("gap < 6", card)
        self.assertNotIn("lanes clear", card)

    def test_card_lanes_clear_only_when_skips_empty(self):
        gap = _load_gap()
        card = gap._card_line({
            "trades": [],
            "skips": [],
            "live_games": 8,
            "matched": 13,
        })
        self.assertIn("lanes clear", card)


if __name__ == "__main__":
    unittest.main()
