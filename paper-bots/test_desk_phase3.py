"""Phase 3 expansion — ladder companion + parlay joint EV. No network."""

import tempfile
import unittest

import desk_phase3


class DeskPhase3Tests(unittest.TestCase):
    def test_self_check(self):
        desk_phase3.self_check()

    def test_depth_beats_thin_at_same_edge(self):
        rows = [
            {"ticker": "thin", "spot": 100, "strike": 99, "ask": 0.80, "fee": 0.01, "depth": 4, "model_p": 0.90},
            {"ticker": "deep", "spot": 100, "strike": 99, "ask": 0.80, "fee": 0.01, "depth": 55, "model_p": 0.90},
        ]
        # depth 4 fails LADDER_MIN_DEPTH=5 → only deep is ok
        pick = desk_phase3.pick_ladder_rung(rows, min_edge=0.05)
        self.assertIsNotNone(pick)
        self.assertEqual(pick["ticker"], "deep")

    def test_shadow_rank_without_model(self):
        # Cheap near-money ask scores above a richer far-strike ask (distance prior).
        rows = [
            {"ticker": "far", "spot": 100, "strike": 90, "ask": 0.55, "fee": 0.02, "depth": 10},
            {"ticker": "near", "spot": 100, "strike": 99.5, "ask": 0.40, "fee": 0.02, "depth": 12},
        ]
        pick = desk_phase3.pick_ladder_rung(rows, min_edge=0.05, require_ok=False)
        self.assertIsNotNone(pick)
        self.assertFalse(pick.get("ok"))
        self.assertEqual(pick["ticker"], "near")

    def test_parlay_corr_haircut_blocks_bad_joint(self):
        with tempfile.TemporaryDirectory() as tmp:
            sim = desk_phase3.simulate_parlay(
                tmp,
                [
                    {"ticker": "a", "fair": 0.60, "ask": 0.78, "fee": 0.02, "side": "YES", "series": "KXBTC15M"},
                    {"ticker": "b", "fair": 0.60, "ask": 0.78, "fee": 0.02, "side": "YES", "series": "KXETH15M"},
                ],
                note="bad joint",
            )
            self.assertTrue(sim["ok"])
            self.assertGreater(sim["corr_haircut"], 0)
            self.assertFalse(desk_phase3.should_open_parlay(sim, min_ev=0.0))
            summary = desk_phase3.phase3_summary(tmp)
            self.assertEqual(summary["parlay_sim_count"], 1)

    def test_parlay_opposite_sides_no_haircut(self):
        sim = desk_phase3.parlay_joint_ev([
            {"fair": 0.90, "ask": 0.82, "fee": 0.01, "side": "YES", "series": "KXBTC15M"},
            {"fair": 0.90, "ask": 0.82, "fee": 0.01, "side": "NO", "series": "KXETH15M"},
        ])
        self.assertEqual(sim["corr_haircut"], 0.0)
        # joint 0.81 vs product cost ~0.83*0.83 → still slightly negative; need more edge.
        rich = desk_phase3.parlay_joint_ev([
            {"fair": 0.92, "ask": 0.78, "fee": 0.01, "side": "YES", "series": "KXBTC15M"},
            {"fair": 0.92, "ask": 0.78, "fee": 0.01, "side": "NO", "series": "KXETH15M"},
        ])
        self.assertEqual(rich["corr_haircut"], 0.0)
        self.assertTrue(desk_phase3.should_open_parlay(rich, min_ev=0.0))
        # Same-direction haircut should erase that edge.
        same = desk_phase3.parlay_joint_ev([
            {"fair": 0.92, "ask": 0.78, "fee": 0.01, "side": "YES", "series": "KXBTC15M"},
            {"fair": 0.92, "ask": 0.78, "fee": 0.01, "side": "YES", "series": "KXETH15M"},
        ])
        self.assertGreater(same["corr_haircut"], 0)
        self.assertFalse(desk_phase3.should_open_parlay(same, min_ev=0.0))


if __name__ == "__main__":
    unittest.main()
