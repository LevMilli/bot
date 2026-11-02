"""Desk brain helpers — no network."""

import os
import tempfile
import unittest

import desk_brain


class DeskBrainTests(unittest.TestCase):
    def test_rank_and_score(self):
        desk_brain.self_check()
        ranked = desk_brain.rank_candidates([
            {"ticker": "weak", "edge": 0.03, "confidence": 0.9, "depth": 100},
            {"ticker": "strong", "edge": 0.12, "confidence": 0.88, "depth": 10},
        ])
        self.assertEqual(ranked[0]["ticker"], "strong")

    def test_journal_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_brain.record_decision(
                tmp, bot="btc15m", action="skip", ticker="T1",
                reasons=["p 0.70 < safer floor 0.80"], edge=0.01, confidence=0.7,
            )
            desk_brain.record_decision(
                tmp, bot="btc15m", action="buy", ticker="T2",
                edge=0.09, confidence=0.86, depth=12, note="ok",
            )
            summary = desk_brain.brain_summary(tmp)
            self.assertEqual(summary["decision_count"], 2)
            self.assertEqual(summary["by_bot"]["btc15m"]["buys"], 1)
            self.assertEqual(summary["by_bot"]["btc15m"]["skips"], 1)
            self.assertTrue(summary["top_skip_gates"])
            self.assertTrue(os.path.exists(os.path.join(tmp, "desk_brain_journal.json")))
            self.assertIn("rank", summary["loop"])


if __name__ == "__main__":
    unittest.main()
