"""Slip-scan spelling: Tesseract reads Bijan Robinson as Brian. Other Brians stay."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import bot


class BijanScanNameTests(unittest.TestCase):
    def test_nfl_brian_robinson_and_rush_line_map_to_bijan(self):
        self.assertEqual(bot.correct_scanned_brian("Brian Robinson", sport="NFL"), "Bijan Robinson")
        self.assertEqual(
            bot.correct_scanned_brian("Brian o72.5 rush yds", sport="NFL"),
            "Bijan Robinson o72.5 rush yds",
        )
        self.assertEqual(
            bot.correct_scanned_brian("Brian Robinson over 72.5 Rush Yards", sport="NFL"),
            "Bijan Robinson over 72.5 Rush Yards",
        )
        slip = {
            "sport": "NFL",
            "legs": ["Brian Robinson", "Brian o72.5 rush yds"],
        }
        bot.apply_scan_bijan_fix(slip)
        self.assertEqual(slip["legs"], ["Bijan Robinson", "Bijan Robinson o72.5 rush yds"])

    def test_atl_or_falcons_context_on_an_nfl_slip(self):
        self.assertEqual(
            bot.correct_scanned_brian("Brian over 18.5 Receiving Yards", sport="NFL", context="ATL"),
            "Bijan Robinson over 18.5 Receiving Yards",
        )
        self.assertEqual(
            bot.correct_scanned_brian("Brian o55.5 rec yds", sport="NFL", context="Falcons"),
            "Bijan Robinson o55.5 rec yds",
        )

    def test_real_brians_are_not_renamed(self):
        for line in (
            "Brian Burns",
            "Brian Burns over 1.5 Sacks",
            "Brian Thomas",
            "Brian Thomas o64.5 rec yds",
            "Brian Thomas Jr over 64.5 Rec Yards",
        ):
            for context in ("", "ATL", "Falcons", "Robinson"):
                fixed = bot.correct_scanned_brian(line, sport="NFL", context=context)
                self.assertEqual(fixed, line)
                self.assertNotIn("Bijan", fixed)

    def test_other_brians_and_other_leagues_stay(self):
        self.assertEqual(
            bot.correct_scanned_brian("Brian Robinson over 18.5 Points", sport="NBA"),
            "Brian Robinson over 18.5 Points",
        )
        self.assertEqual(
            bot.correct_scanned_brian("Brian over 55.5 Receiving Yards", sport="NFL"),
            "Brian over 55.5 Receiving Yards",
        )
        self.assertEqual(bot.correct_scanned_brian("See Brian", sport="NFL"), "See Brian")
        slip = {
            "sport": "NFL",
            "description": "Falcons",
            "legs": [
                "Brian Burns over 1.5 Sacks",
                "Brian Thomas under 64.5 Rec Yards",
                "Bijan Robinson over 72.5 Rush Yards",
            ],
        }
        bot.apply_scan_bijan_fix(slip)
        self.assertEqual(slip["legs"][0], "Brian Burns over 1.5 Sacks")
        self.assertEqual(slip["legs"][1], "Brian Thomas under 64.5 Rec Yards")
        self.assertEqual(slip["legs"][2], "Bijan Robinson over 72.5 Rush Yards")

    def test_free_fix_names_keeps_bijan_when_espn_returns_brian(self):
        slip = {
            "sport": "NFL",
            "legs": [
                "Brian Robinson over 72.5 Rush Yards",
                "Brian o72.5 rush yds",
                "Brian Burns over 1.5 Sacks",
                "Brian Thomas under 64.5 Rec Yards",
            ],
        }

        async def run():
            with patch.object(bot, "get_setting", return_value="{}"), \
                    patch.object(bot, "set_setting") as save, \
                    patch.object(bot, "_get_json", new=AsyncMock(return_value={
                        "items": [{"displayName": "Brian Robinson"}]})):
                await bot.free_fix_names(slip)
            return save

        save = asyncio.run(run())
        self.assertEqual(slip["legs"][0], "Bijan Robinson over 72.5 Rush Yards")
        self.assertEqual(slip["legs"][1], "Bijan Robinson o72.5 rush yds")
        self.assertEqual(slip["legs"][2], "Brian Burns over 1.5 Sacks")
        self.assertEqual(slip["legs"][3], "Brian Thomas under 64.5 Rec Yards")
        saved = [call.args[2] for call in save.call_args_list]
        self.assertTrue(saved)
        self.assertNotIn("Brian Robinson", saved[-1])
        self.assertIn("Bijan Robinson", saved[-1])


if __name__ == "__main__":
    unittest.main()
