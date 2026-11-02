"""Phase 0/1 desk_more — trade-more helpers (no network)."""

import os
import tempfile
import time
import unittest

import desk_brain
import desk_more


class DeskMoreTests(unittest.TestCase):
    def test_self_check(self):
        desk_more.self_check()

    def test_skip_leaderboard_weekend(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_more.record_skip_codes(
                tmp, bot="kalshi-sp", reasons=["WEEKEND equity closed"], weekday=6, day="2026-11-01",
            )
            desk_more.record_skip_codes(
                tmp, bot="btc15m", reasons=["cushion $20 < $40"], weekday=0, day="2026-11-01",
            )
            board = desk_more.skip_leaderboard(tmp, day="2026-11-01")
            self.assertEqual(board["weekend_n"], 1)
            self.assertEqual(board["weekday_n"], 1)
            codes = {r["code"] for r in board["top"]}
            self.assertIn("WEEKEND", codes)
            self.assertIn("cushion", codes)

    def test_depth_rank_prefers_thick_book(self):
        thin = desk_more.opportunity_score_v2(0.10, 0.90, depth=2, need=10)
        thick = desk_more.opportunity_score_v2(0.10, 0.90, depth=20, need=10)
        self.assertGreater(thick, thin)
        ranked = desk_brain.rank_candidates([
            {"ticker": "thin", "edge": 0.10, "confidence": 0.90, "depth": 2},
            {"ticker": "thick", "edge": 0.10, "confidence": 0.90, "depth": 20},
        ])
        self.assertEqual(ranked[0]["ticker"], "thick")

    def test_tower_budgets_block_meme_hog(self):
        cfg = {"max_open_risk": 100.0, "tower_risk_budgets": desk_more.DEFAULT_TOWER_BUDGET_SHARE}
        # memecoin share = 5 → $5 cap
        msg = desk_more.tower_budget_blocks("memecoin", 4.5, 2.0, cfg)
        self.assertIn("tower risk budget", msg)
        ok = desk_more.tower_budget_blocks("btc15m", 10.0, 5.0, cfg)
        self.assertEqual(ok, "")

    def test_near_miss_shadow_only(self):
        nm = desk_more.is_near_miss(z=0.60, p=0.88, reasons=["z 0.60 < floor 0.65"])
        self.assertTrue(nm["near_miss"])
        self.assertTrue(nm["shadow_only"])
        self.assertEqual(nm["stake"], desk_more.NEAR_MISS_STAKE)
        hard = desk_more.is_near_miss(z=0.60, reasons=["news blackout FOMC"])
        self.assertFalse(hard["near_miss"])

    def test_sticky_and_clv_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            bots = [{
                "id": "btc15m",
                "positions": [{
                    "ticker": "OLD",
                    "side": "yes",
                    "opened": "2026-10-01T12:00:00Z",
                    "risk": 20,
                }],
            }]
            sticky = desk_more.sticky_positions(bots, now_epoch=time.time())
            self.assertTrue(sticky)
            self.assertEqual(sticky[0]["ticker"], "OLD")
            desk_more.remember_sticky(tmp, sticky)
            row = desk_more.record_sports_clv(
                tmp,
                ticker="KXNHLGAME",
                side="home",
                fair_entry=0.82,
                close_fair=0.70,
                pnl=5.0,
                league="nhl",
                exit_reason="settled",
            )
            self.assertAlmostEqual(row["clv"], 0.12)
            summary = desk_more.clv_summary(tmp)
            self.assertEqual(summary["n"], 1)
            self.assertGreater(summary["avg_clv"], 0)
            more = desk_more.more_summary(tmp, bots=bots, cfg={"max_open_risk": 100})
            self.assertIn("skip_leaderboard", more)
            self.assertIn("tower_budgets", more)
            self.assertTrue(os.path.exists(os.path.join(tmp, "desk_more_state.json")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "desk_sports_clv.json")))

    def test_series_prior_and_decay(self):
        nat = desk_more.series_vol_prior("KXNATGAS15M-XYZ")
        gold = desk_more.series_vol_prior("KXGOLD15M")
        self.assertGreater(nat, gold)
        vol = {"score": 0.40, "regime": "elevated", "reasons": []}
        bumped = desk_more.apply_series_vol_prior(vol, "KXNATGAS15M")
        self.assertGreater(bumped["score"], 0.40)
        dhr = desk_more.decayed_hit_rate(
            [
                {"pnl": 5, "closed": "2026-10-01T12:00:00Z"},
                {"pnl": 5, "closed": "2026-11-01T12:00:00Z"},
            ],
            now_ts=time.mktime(time.strptime("2026-11-02", "%Y-%m-%d")),
        )
        self.assertEqual(dhr["n"], 2)
        self.assertIsNotNone(dhr["hit_rate_decayed"])

    def test_brain_records_skip_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_brain.record_decision(
                tmp, bot="btc15m", action="skip",
                reasons=["cushion too thin"], edge=0.02, confidence=0.7,
            )
            board = desk_more.skip_leaderboard(tmp)
            self.assertGreaterEqual(board["total"], 1)
            summary = desk_brain.brain_summary(tmp)
            self.assertIn("skip_leaderboard", summary)


if __name__ == "__main__":
    unittest.main()
