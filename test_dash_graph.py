"""PIMP-BOT dashboards omit the display name Lelouch everywhere."""

import os
import tempfile
import unittest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.gettempdir(), "pimp-dash-graph-test.db"))

import bot


class DashGraphTests(unittest.TestCase):
    def test_hidden_name_is_exact_case_insensitive(self):
        self.assertTrue(bot.dashboard_hidden_name("Lelouch"))
        self.assertTrue(bot.dashboard_hidden_name("LELOUCH"))
        self.assertTrue(bot.dashboard_hidden_name(" lelouch "))
        self.assertFalse(bot.dashboard_hidden_name("Levi"))
        self.assertFalse(bot.dashboard_hidden_name("Not Lelouch"))
        self.assertFalse(bot.dashboard_hidden_name(""))
        self.assertFalse(bot.dashboard_hidden_name(None))

    def test_lelouch_is_omitted_from_profit_series(self):
        series = {
            "Lelouch": [(1, 2.0)],
            "LELOUCH": [(1, 3.0)],
            " lelouch ": [(1, 4.0)],
            "Levi": [(1, 5.0)],
            "Not Lelouch": [(1, 6.0)],
        }
        kept = bot.dashboard_profit_series(series)
        self.assertEqual(list(kept), ["Levi", "Not Lelouch"])
        self.assertEqual(kept["Levi"], [(1, 5.0)])
        self.assertEqual(kept["Not Lelouch"], [(1, 6.0)])

    def test_other_names_and_an_empty_graph_stay(self):
        self.assertEqual(bot.dashboard_profit_series({}), {})
        kept = bot.dashboard_profit_series({"Pimp": [(1, 1.0)], "": [(1, 0.0)]})
        self.assertEqual(list(kept), ["Pimp", ""])

    def test_hidden_pick_and_line(self):
        self.assertTrue(bot.dashboard_hidden_pick({"bettor_name": "Lelouch"}))
        self.assertTrue(bot.dashboard_hidden_pick({"who": "LELOUCH"}))
        self.assertFalse(bot.dashboard_hidden_pick({"bettor_name": "Levi"}))
        self.assertTrue(bot.dashboard_hidden_line(
            "🚀 Biggest hit: +$10 · Lelouch · Over 20.5"))
        self.assertTrue(bot.dashboard_hidden_line(
            "📈 Best month: +$5 · Lelouch (January 2026)"))
        self.assertFalse(bot.dashboard_hidden_line(
            "🚀 Biggest hit: +$10 · Not Lelouch · Over 20.5"))
        self.assertFalse(bot.dashboard_hidden_line("📕 Closed week: this week"))

    def test_group_stats_filter_matches_hidden_helper(self):
        rows = [{"name": "Lelouch"}, {"name": "LELOUCH"}, {"name": "Levi"}, {"name": "Not Lelouch"}]
        kept = [s["name"] for s in rows if not bot.dashboard_hidden_name(s.get("name"))]
        self.assertEqual(kept, ["Levi", "Not Lelouch"])


if __name__ == "__main__":
    unittest.main()
