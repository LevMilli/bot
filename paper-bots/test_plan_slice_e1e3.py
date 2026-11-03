"""APEX plan slice E1/E3: meme pulse, red budgets, NFL floors, commodity calm, helper scanner."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

import desk_more
import desk_top25
import pimp_desk
from helpers import calendar_scanner

ROOT = os.path.dirname(os.path.abspath(__file__))


class PlanSliceE1E3Tests(unittest.TestCase):
    def test_meme_manage_pulse_when_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "memecoin-paper")
            os.makedirs(folder)
            with open(os.path.join(folder, "positions.json"), "w", encoding="utf-8") as handle:
                json.dump({"open": [{"mint": "x", "cost_usd": 5}], "cash_usd": 90}, handle)
            self.assertEqual(pimp_desk._meme_open_count(tmp), 1)
            self.assertEqual(pimp_desk._meme_auto_gap_sec(tmp, 180), float(pimp_desk.MEME_MANAGE_OPEN_SEC))
            with open(os.path.join(folder, "positions.json"), "w", encoding="utf-8") as handle:
                json.dump({"open": [], "cash_usd": 100}, handle)
            self.assertEqual(pimp_desk._meme_auto_gap_sec(tmp, 180), 180.0)

    def test_commodity_calm_cadence(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "commodity-15m-paper")
            os.makedirs(folder)
            with open(os.path.join(folder, "paper_account.json"), "w", encoding="utf-8") as handle:
                json.dump({"open": [{"series": "KXWTI15M"}, {"series": "KXGOLD15M"}]}, handle)
            self.assertEqual(pimp_desk._commodity_open_count(tmp), 2)
            self.assertEqual(
                pimp_desk._commodity_auto_gap_sec(tmp, 90),
                float(pimp_desk.COMMODITY_CALM_OPEN_SEC),
            )
            with open(os.path.join(folder, "paper_account.json"), "w", encoding="utf-8") as handle:
                json.dump({"open": [{"series": "KXWTI15M"}]}, handle)
            self.assertEqual(pimp_desk._commodity_auto_gap_sec(tmp, 90), 90.0)

    def test_meme_red_day_starves_budget(self):
        shares = desk_more.effective_tower_shares(meme_today=-22)
        self.assertAlmostEqual(shares["memecoin"], desk_more.MEME_RED_SHARE)
        base = desk_more.DEFAULT_TOWER_BUDGET_SHARE
        self.assertGreater(shares["btc15m"], base["btc15m"])
        self.assertGreater(shares["commodity-15m"], base["commodity-15m"])
        budgets = desk_more.tower_budgets({"max_open_risk": 100}, meme_today=-22)
        self.assertAlmostEqual(budgets["memecoin"], 3.0)
        ok = desk_more.effective_tower_shares(meme_today=-5)
        self.assertAlmostEqual(ok["memecoin"], base["memecoin"])

    def test_nfl_fair_floors_locked(self):
        self.assertEqual(desk_top25.league_fair_floor("NFL"), 0.82)
        self.assertEqual(desk_top25.league_fair_floor("nhl"), 0.80)
        self.assertGreaterEqual(desk_top25.league_fair_floor("nfl"), desk_top25.league_fair_floor("nhl"))
        self.assertEqual(desk_top25.league_speed_floor("nfl"), 0.74)
        self.assertEqual(desk_top25.league_speed_floor("nhl"), 0.72)
        self.assertGreaterEqual(desk_top25.league_speed_floor("nfl"), desk_top25.league_speed_floor("default"))

    def test_calendar_scanner_never_places(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "helpers"))
            from helpers import calendar_cache
            import time
            calendar_cache.save_raw(
                {
                    "paper_only": True,
                    "fetched_at": time.time(),
                    "source": calendar_cache.FF_URL,
                    "events": [
                        {
                            "country": "USD",
                            "impact": "High",
                            "title": "FOMC",
                            "date": datetime.now(timezone.utc).isoformat(),
                        }
                    ],
                    "last_error": None,
                },
                tmp,
            )
            digest = calendar_scanner.scan(tmp)
            self.assertFalse(digest["places_orders"])
            self.assertTrue(digest["helper_only"])
            self.assertGreaterEqual(digest["n_high"], 1)
            self.assertTrue(os.path.isfile(calendar_scanner.digest_path(tmp)))
            calendar_scanner.self_check()

    def test_timer_mentions_manage_pulse(self):
        text = pimp_desk.timer_text().lower()
        self.assertIn("2 minutes", text)
        self.assertIn("60 seconds", text)


if __name__ == "__main__":
    unittest.main()
