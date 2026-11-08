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

    def test_early_eval_skip_densifies_brain_and_features(self):
        gap = _load_gap()
        with tempfile.TemporaryDirectory() as tmp:
            gap.DESK_ROOT = tmp
            gap._densify_early_eval_skip(
                reason="gap < 6 (accurate) - no trade",
                ticker="KXNHL-TEST",
                side="home",
                series="KXNHLGAME",
                league="NHL",
                fair=0.62,
                gap=0.04,
                ask=0.55,
                bid=0.52,
                lane="accurate",
            )
            import desk_brain
            journal = desk_brain.load_journal(tmp)
            decisions = journal.get("decisions") or []
            self.assertTrue(decisions)
            last = decisions[-1]
            self.assertEqual(last.get("action"), "skip")
            self.assertEqual(last.get("bot"), "sports-gap")
            self.assertEqual(last.get("ticker"), "KXNHL-TEST")
            self.assertIn("gap < 6", str((last.get("reasons") or [""])[0]))
            self.assertEqual(
                int((journal.get("by_bot") or {}).get("sports-gap", {}).get("skips") or 0),
                1,
            )
            feat_path = os.path.join(tmp, "desk_feature_store.jsonl")
            self.assertTrue(os.path.isfile(feat_path))
            with open(feat_path, encoding="utf-8") as fh:
                lines = [ln for ln in fh.read().splitlines() if ln.strip()]
            self.assertTrue(lines)
            row = json.loads(lines[-1])
            self.assertEqual(row.get("bot"), "sports-gap")
            self.assertEqual(row.get("action"), "skip")
            self.assertIn("gap < 6", str(row.get("skip_codes") or row.get("note") or ""))

    def test_match_miss_path_calls_early_densify(self):
        """Match-miss CARD densify must also hit brain (honest empty ticker)."""
        src = GAP.read_text(encoding="utf-8")
        miss_idx = src.find('miss = "no Kalshi match - skip"')
        self.assertGreater(miss_idx, 0)
        chunk = src[miss_idx:miss_idx + 700]
        self.assertIn("_densify_early_eval_skip", chunk)
        self.assertIn("ticker=\"\"", chunk)
        gap = _load_gap()
        with tempfile.TemporaryDirectory() as tmp:
            gap.DESK_ROOT = tmp
            gap._densify_early_eval_skip(
                reason="no Kalshi match - skip",
                ticker="",
                series="KXNHLGAME",
                league="NHL",
            )
            import desk_brain
            import desk_more
            last = (desk_brain.load_journal(tmp).get("decisions") or [])[-1]
            self.assertEqual(last.get("bot"), "sports-gap")
            self.assertEqual(last.get("action"), "skip")
            self.assertEqual(last.get("ticker"), "")
            self.assertIn("no Kalshi match", str((last.get("reasons") or [""])[0]))
            board = desk_more.skip_leaderboard(tmp)
            self.assertIn("sports-gap", board.get("by_bot") or {})


if __name__ == "__main__":
    unittest.main()
