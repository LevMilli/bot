"""Wall Street is one floor of 120 traders. It does not trade."""

import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _bot():
    path = os.path.join(HERE, "wall-street-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("wall_street_bot", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WallStreetTests(unittest.TestCase):
    def test_floor_houses_over_one_hundred_and_skips(self):
        bot = _bot()
        self.assertGreaterEqual(bot.HEADCOUNT, 100)
        self.assertEqual(bot.HEADCOUNT, 120)
        row = bot.evaluate()
        self.assertEqual(row["action"], "skip")
        self.assertEqual(row["traders"], 120)
        self.assertIn("120 traders", row["reason"])
        self.assertIn("six desks", row["reason"])
        self.assertIn("does not trade", row["reason"])
        desks = row["departments"]
        self.assertEqual([d["id"] for d in desks], ["quote", "research", "risk", "ledger", "control", "book"])
        self.assertEqual(sum(d["seats"] for d in desks), 120)
        for desk in desks:
            self.assertTrue(str(desk["job"]).strip())
            self.assertNotIn("strategy", desk["job"].lower())

    def test_desk_row_is_shadow_and_flat(self):
        import pimp_desk

        spec = next(row for row in pimp_desk.BOTS if row["id"] == "wall-street")
        self.assertEqual(spec["name"], "Wall Street")
        self.assertTrue(spec["shadow_only"])
        self.assertEqual(spec["traders"], 120)
        self.assertNotIn("wall-street", pimp_desk.DEFAULTS["tower_risk_budgets"])
        self.assertFalse(any(slot.get("id") == "wall-street" for slot in pimp_desk.AUTO))
        plans = pimp_desk.BOT_PLANS["wall-street"]
        self.assertTrue(plans["entry_gated"])
        self.assertEqual(plans["exit_quality"], "partial")
        self.assertIn("does not buy", " ".join(plans["buy"]).lower())
        snap = pimp_desk.snapshot(HERE)
        row = next(b for b in snap["bots"] if b["id"] == "wall-street")
        self.assertTrue(row["present"])
        self.assertTrue(row["shadow_only"])
        self.assertEqual(row["traders"], 120)
        self.assertEqual(row["cash"], 0.0)
        self.assertEqual(row["positions"], [])
        self.assertEqual(row["open_count"], 0)
        self.assertIsNone(row["venue_min_edge"])
        self.assertEqual(row["sizing_mode"], "none")
        self.assertEqual(row["capital_weight"], 0)
        desks = row["departments"]
        self.assertEqual(sum(d["seats"] for d in desks), 120)
        self.assertEqual(
            [(d["id"], d["seats"], d["job"]) for d in desks],
            [(d["id"], d["seats"], d["job"]) for d in spec["departments"]],
        )
        self.assertIn("six desks", row["why"])
        desk_ids = [b["id"] for b in snap["bots"] if not b.get("shadow_only")]
        self.assertNotIn("wall-street", desk_ids)
