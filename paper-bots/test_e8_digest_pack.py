"""E8 remaining insight digest pack (observe-only, #829–880 leftovers)."""
from __future__ import annotations

import tempfile
import unittest

import desk_living
from helpers import e8_digest_pack as pack


class E8DigestPack(unittest.TestCase):
    def test_registry_complete(self):
        self.assertEqual(len(pack.HELPER_NAMES), 19)
        for name in pack.HELPER_NAMES:
            digest_name = f"{name}_digest.json"
            self.assertIn(digest_name, desk_living.INSIGHT_HELPER_DIGESTS)
            self.assertIn(name, pack.BUILDERS)

    def test_builders_floors_locked(self):
        for name, builder in pack.BUILDERS.items():
            dig = builder({})
            self.assertEqual(dig["helper"], name)
            self.assertFalse(dig["may_place_alone"])
            self.assertTrue(dig["floors_locked"])
            self.assertTrue(dig["paper_only"])

    def test_write_all_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in pack.HELPER_NAMES:
                out = pack.write_digest_from_desk(name, tmp, bots=[])
                self.assertEqual(out["helper"], name)
                self.assertFalse(out["may_place_alone"])
            chips = desk_living.e8_pack_chips(tmp, bots=[])
            self.assertEqual(len(chips), 19)
            self.assertIn("opp_cost_clock", chips)
            self.assertIn("inx_dual_ev_lab", chips)

    def test_inx_dual_ev_lab_scores_band(self):
        dig = pack.build_inx_dual_ev_lab({
            "fair_best": {"ticker": "A", "fair_edge": 0.02},
            "residual_best": {"ticker": "A", "residual_edge": 0.1},
            "agree": True,
            "n_candidates": 4,
            "thin": False,
        })
        self.assertTrue(dig["agree"])
        self.assertEqual(dig["n_candidates"], 4)

    def test_chip_label(self):
        chip = pack.chip_from_digest("masters_canary", {
            "helper": "masters_canary",
            "label": "canary m1=0.1",
            "m1_holds": True,
        })
        self.assertIn("canary", chip["label"])
        self.assertFalse(chip["may_place_alone"])


if __name__ == "__main__":
    unittest.main()
