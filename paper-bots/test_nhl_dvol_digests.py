"""NHL Poisson audit + DVOL regime insight digests (observe-only)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest

import desk_living
from helpers import dvol_regime, nhl_poisson_audit


class NhlDvolDigests(unittest.TestCase):
    def test_nhl_audit_gap_and_wipe(self):
        def fake_model(summary, game):
            del summary, game
            return 0.0  # wipe

        summary = {
            "header": {"id": "ev1"},
            "pickcenter": [{
                "homeTeamOdds": {"moneyLine": -150},
                "awayTeamOdds": {"moneyLine": 130},
            }],
            "competitions": [{
                "status": {"period": 3, "clock": 0},
                "competitors": [
                    {"homeAway": "home", "score": "4", "team": {"name": "A"}},
                    {"homeAway": "away", "score": "1", "team": {"name": "B"}},
                ],
            }],
        }
        row = nhl_poisson_audit.audit_summary(summary, nhl_model=fake_model)
        self.assertIsNotNone(row)
        self.assertTrue(row["wipe_01"])
        self.assertGreaterEqual(row["abs_gap"], 0.0)
        incomplete = nhl_poisson_audit.audit_summary({"competitions": []}, nhl_model=fake_model)
        self.assertIsNone(incomplete)
        digest = nhl_poisson_audit.build_digest([row])
        self.assertEqual(digest["helper"], "nhl_poisson_audit")
        self.assertFalse(digest["may_place_alone"])
        self.assertEqual(digest["wipe_01_n"], 1)

    def test_nhl_write_chip(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = os.path.join(tmp, "sports-gap-paper")
            os.makedirs(cache_dir)
            body = {
                "header": {
                    "id": "401",
                    "competitions": [{
                        "status": {"period": 1, "clock": 1200},
                        "competitors": [
                            {"homeAway": "home", "score": "0", "team": {"name": "H"}},
                            {"homeAway": "away", "score": "0", "team": {"name": "A"}},
                        ],
                    }],
                },
                "pickcenter": [{
                    "homeTeamOdds": {"moneyLine": -110},
                    "awayTeamOdds": {"moneyLine": -110},
                }],
            }
            with open(os.path.join(cache_dir, "quote_cache.json"), "w", encoding="utf-8") as handle:
                json.dump({
                    "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary?event=401": {
                        "at": 1, "body": body,
                    },
                }, handle)
            out = nhl_poisson_audit.write_digest_from_desk(tmp)
            self.assertGreaterEqual(out["n"], 0)
            chip = desk_living.nhl_poisson_audit_chip(tmp)
            self.assertIn("nhl poisson", chip["label"])

    def test_dvol_regime_classify_and_no_invent(self):
        self.assertEqual(dvol_regime.classify_regime(35), "low")
        self.assertEqual(dvol_regime.classify_regime(50), "mid")
        self.assertEqual(dvol_regime.classify_regime(70), "high")
        self.assertIsNone(dvol_regime.classify_regime(None))
        waiting = dvol_regime.build_digest(None, source="")
        self.assertTrue(waiting["waiting"])
        self.assertIsNone(waiting["dvol"])
        self.assertFalse(waiting["may_place_alone"])

    def test_dvol_write_from_cache_and_opener(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "desk_btc_vol_binary.json"), "w", encoding="utf-8") as handle:
                json.dump({"rows": [{"dvol": 48.5, "ask": 0.5}]}, handle)

            def boom(_url):
                raise TimeoutError("net down")

            out = dvol_regime.write_digest_from_desk(tmp, opener=boom)
            self.assertEqual(out["dvol"], 48.5)
            self.assertEqual(out["source"], "cache")
            self.assertEqual(out["regime"], "mid")
            chip = desk_living.dvol_regime_chip(tmp)
            self.assertIn("dvol regime", chip["label"])

            def opener(_url):
                return json.dumps({"result": {"data": [[0, 1, 1, 1, 55.2]]}}).encode()

            live = dvol_regime.write_digest_from_desk(tmp, opener=opener)
            self.assertEqual(live["dvol"], 55.2)
            self.assertEqual(live["source"], "deribit")

    def test_inventory_lists_helpers(self):
        self.assertIn("nhl_poisson_audit_digest.json", desk_living.INSIGHT_HELPER_DIGESTS)
        self.assertIn("dvol_regime_digest.json", desk_living.INSIGHT_HELPER_DIGESTS)


if __name__ == "__main__":
    unittest.main()
