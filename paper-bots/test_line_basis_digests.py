"""Line shopper + BTC basis scout insight digests (observe-only)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest

import desk_living
from helpers import btc_basis_scout, line_shopper


class LineBasisDigests(unittest.TestCase):
    def test_line_shopper_scores_clear_and_thin(self):
        rows = line_shopper.score_quotes([
            {"game": "thin", "league": "NFL", "sharp_fair": 0.55, "ask": 0.52},
            {"game": "fat", "league": "NFL", "sharp_fair": 0.70, "ask": 0.50},
            {"game": "incomplete", "league": "NBA", "ask": 0.48},
        ])
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["clear"])
        self.assertEqual(rows[0]["game"], "fat")
        self.assertFalse(rows[1]["clear"])
        digest = line_shopper.build_digest(
            [
                {"game": "fat", "league": "NFL", "sharp_fair": 0.70, "ask": 0.50},
            ],
            clv_leagues={"pass_n": 0, "thin_n": 5, "leagues": []},
        )
        self.assertEqual(digest["helper"], "line_shopper")
        self.assertFalse(digest["may_place_alone"])
        self.assertTrue(digest["floors_locked"])
        self.assertEqual(digest["clear_n"], 1)
        self.assertEqual(digest["clv_pass_n"], 0)

    def test_line_shopper_write_and_chip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tower = os.path.join(tmp, "sports-sharp-lag-paper")
            os.makedirs(tower)
            with open(os.path.join(tower, "sharp_quotes.json"), "w", encoding="utf-8") as handle:
                json.dump({
                    "quotes": [
                        {"game": "X HOME", "league": "NFL", "sharp_fair": 0.70, "ask": 0.50},
                    ],
                }, handle)
            out = line_shopper.write_digest_from_desk(tmp)
            self.assertEqual(out["clear_n"], 1)
            self.assertTrue(os.path.isfile(line_shopper.digest_path(tmp)))
            chip = desk_living.line_shopper_chip(tmp)
            self.assertIn("line shopper", chip["label"])
            self.assertFalse(chip["may_place_alone"])

    def test_btc_basis_scout_observe_only(self):
        digest = btc_basis_scout.build_digest(
            {"open": [{"funding_pnl": 0.01, "basis_pnl": -0.002}]},
            twins={
                "eth": {"role": "observe_twin_same_factor", "pass": True},
                "sol": {"role": "reject_mean_red", "pass": False},
            },
        )
        self.assertEqual(digest["helper"], "btc_basis_scout")
        self.assertFalse(digest["may_place_alone"])
        self.assertFalse(digest["opens_desk_cash"])
        self.assertEqual(digest["btc_open_n"], 1)
        self.assertIn("observe", digest["eth_stance"])
        self.assertIn("reject", digest["sol_stance"])
        self.assertTrue(digest["sol_reject"])

    def test_btc_basis_scout_write_and_chip(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "btc-carry-paper"))
            with open(
                os.path.join(tmp, "btc-carry-paper", "paper_account.json"),
                "w",
                encoding="utf-8",
            ) as handle:
                json.dump({"open": [{"funding_pnl": 0.0, "basis_pnl": 0.0}]}, handle)
            out = btc_basis_scout.write_digest_from_desk(tmp)
            self.assertEqual(out["helper"], "btc_basis_scout")
            chip = desk_living.btc_basis_scout_chip(tmp)
            self.assertIn("basis scout", chip["label"])
            self.assertFalse(chip["opens_desk_cash"])

    def test_insight_digest_inventory_lists_new_helpers(self):
        self.assertIn("line_shopper_digest.json", desk_living.INSIGHT_HELPER_DIGESTS)
        self.assertIn("btc_basis_scout_digest.json", desk_living.INSIGHT_HELPER_DIGESTS)


if __name__ == "__main__":
    unittest.main()
