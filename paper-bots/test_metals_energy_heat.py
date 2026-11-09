"""Metals + energy heat insight digests (observe-only)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest

import desk_living
from helpers import energy_heat, metals_heat


class MetalsEnergyHeat(unittest.TestCase):
    def test_metals_heat_ranks_by_prior_and_z(self):
        rows = metals_heat.score_series({
            "KXGOLD15M": [1.0, 1.2],
            "KXNATGAS15M": [50.0],  # ignored — not a metal
            "KXPALLADIUM15M": [8.0, 9.0, 10.0, 11.0, 12.0],
        })
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(r["family"] == "metal" for r in rows))
        # Palladium has higher prior + higher |z| → should beat gold.
        by = {r["series"]: r for r in rows}
        self.assertGreater(by["KXPALLADIUM15M"]["heat"], by["KXGOLD15M"]["heat"])
        digest = metals_heat.build_digest(rows)
        self.assertEqual(digest["helper"], "metals_heat")
        self.assertFalse(digest["may_place_alone"])
        self.assertTrue(digest["floors_locked"])

    def test_metals_write_chip(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "desk_feature_store.jsonl"), "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"series": "KXGOLD15M", "z": 2.0}) + "\n")
                handle.write(json.dumps({"series": "KXSILVER15M", "z": 6.0}) + "\n")
            out = metals_heat.write_digest_from_desk(tmp)
            self.assertEqual(out["n"], 5)
            self.assertIn(out["hottest"], ("KXSILVER15M", "KXGOLD15M", "KXPALLADIUM15M", "KXCOPPER15M", "KXPLATINUM15M"))
            chip = desk_living.metals_heat_chip(tmp)
            self.assertIn("metals heat", chip["label"])

    def test_energy_heat_joins_eia(self):
        rows = energy_heat.score_series(
            {"KXNATGAS15M": [20.0] * 5, "KXWTI15M": [2.0] * 5},
            regimes={
                "KXNATGAS15M": {"eia_regime": "draw", "roll_yield": -0.01},
                "KXWTI15M": {"eia_regime": "neutral", "roll_yield": 0.001},
            },
        )
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["series"], "KXNATGAS15M")
        self.assertEqual(rows[0]["eia_regime"], "draw")
        digest = energy_heat.build_digest(rows)
        self.assertEqual(digest["hottest"], "KXNATGAS15M")
        self.assertFalse(digest["may_place_alone"])

    def test_energy_write_chip(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "desk_feature_store.jsonl"), "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"series": "KXWTI15M", "z": 3.0}) + "\n")
            with open(os.path.join(tmp, "desk_commodity_curve.json"), "w", encoding="utf-8") as handle:
                json.dump({
                    "rows": [{"series": "KXWTI15M", "eia_regime": "build", "roll_yield": 0.002}],
                }, handle)
            out = energy_heat.write_digest_from_desk(tmp)
            self.assertEqual(out["n"], 3)
            wti = next(r for r in out["series"] if r["series"] == "KXWTI15M")
            self.assertEqual(wti["eia_regime"], "build")
            chip = desk_living.energy_heat_chip(tmp)
            self.assertIn("energy heat", chip["label"])

    def test_inventory_lists_helpers(self):
        self.assertIn("metals_heat_digest.json", desk_living.INSIGHT_HELPER_DIGESTS)
        self.assertIn("energy_heat_digest.json", desk_living.INSIGHT_HELPER_DIGESTS)


if __name__ == "__main__":
    unittest.main()
