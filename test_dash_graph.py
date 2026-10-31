"""The picks dashboard profit graph omits the display name Lelouch."""

import os
import tempfile
import unittest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.gettempdir(), "pimp-dash-graph-test.db"))

import bot


class DashGraphTests(unittest.TestCase):
    def test_lelouch_is_omitted_case_insensitively(self):
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
