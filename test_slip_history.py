"""The past-slip page renders with nothing stored, and with one stored slip."""

import unittest

from slip_history import clock_text, render_slip_history_page


SAMPLE = {
    "id": 42,
    "platform": "PrizePicks",
    "description": "Cade over 22.5 points",
    "bettor_name": "Ada",
    "status": "win",
    "cost": 10,
    "payout": 30,
    "returned": None,
    "created_at": "2026-10-01T18:00:00+00:00",
    "settled_at": "2026-10-01T22:30:00+00:00",
    "legs": [{"idx": 1, "text": "Cade over 22.5 points", "status": "hit"}],
}


class SlipHistoryPageTests(unittest.TestCase):
    def test_empty_state(self):
        page = render_slip_history_page([])
        self.assertIn("No slips in this list.", page)
        self.assertIn("<table", page)
        self.assertIn("Past slips", page)
        self.assertIn(">All<", page)
        self.assertIn(">Hits<", page)
        self.assertIn(">Misses<", page)
        self.assertIn(">Open<", page)
        self.assertIn("Page 1 of 1", page)
        self.assertNotIn("data-slip=", page)
        self.assertNotIn("PrizePicks", page)

    def test_one_sample_row(self):
        page = render_slip_history_page([SAMPLE], slip_id=42)
        self.assertIn('data-slip="42"', page)
        self.assertIn("PrizePicks", page)
        self.assertIn("Cade over 22.5 points", page)
        self.assertIn(">Hit<", page)
        self.assertIn("Ada", page)
        self.assertIn("$10.00", page)
        self.assertIn("$30.00", page)
        self.assertIn('class="unk">unknown', page)
        self.assertIn("4h 30m", page)
        self.assertIn("Oct 1, 2026, 1:00 PM CT", page)
        self.assertIn("Oct 1, 2026, 5:30 PM CT", page)
        self.assertIn(">hit<", page)
        self.assertNotIn("-$10.00", page)
        self.assertNotIn("<script>", page)
        self.assertIn(clock_text(SAMPLE["created_at"]), page)
        self.assertEqual(clock_text(SAMPLE["created_at"]), "Oct 1, 2026, 1:00 PM CT")

    def test_missing_return_is_not_a_loss_of_the_stake(self):
        page = render_slip_history_page([{
            "id": 3,
            "status": "open",
            "platform": "Kalshi",
            "description": "Still open",
            "cost": 5,
            "payout": 12,
            "created_at": "2026-10-01T18:00:00+00:00",
        }], slip_id=3)
        self.assertIn(">Open<", page)
        self.assertIn("Still open", page)
        self.assertIn("$5.00", page)
        self.assertIn('class="unk">unknown', page)
        self.assertNotIn("-$5.00", page)
        self.assertNotIn(">0m<", page)

    def test_slippage_uses_only_stored_pairs(self):
        full = render_slip_history_page([{
            "id": 9,
            "status": "loss",
            "description": "Cade over 22.5 points",
            "cost": 10,
            "payout": 20,
            "returned": 0,
            "settled_price": 18,
            "created_at": "2026-10-01T18:00:00+00:00",
            "settled_at": "2026-10-01T20:00:00+00:00",
            "legs": [
                {"text": "Cade over 22.5 points", "status": "miss"},
                {"text": "Other over 10.5 rebounds", "status": "hit"},
            ],
        }], slip_id=9)
        self.assertIn("-$10.00", full)
        self.assertIn("-$20.00 vs payout", full)
        self.assertNotIn("vs line", full)
        one_line = render_slip_history_page([{
            "id": 10,
            "status": "win",
            "description": "Cade over 22.5 points",
            "cost": 10,
            "payout": 20,
            "returned": 20,
            "settled_price": 26,
            "created_at": "2026-10-01T18:00:00+00:00",
            "settled_at": "2026-10-01T20:00:00+00:00",
            "legs": [{"text": "Cade over 22.5 points", "status": "hit"}],
        }], slip_id=10)
        self.assertIn("+$10.00", one_line)
        self.assertIn("+$0.00 vs payout", one_line)
        self.assertIn("+3.5 vs line", one_line)

    def test_filters_and_pages(self):
        picks = [
            {"id": 1, "status": "win", "description": "Winner", "cost": 1, "returned": 2, "payout": 2,
             "created_at": "2026-10-01T00:00:00+00:00", "settled_at": "2026-10-01T01:00:00+00:00"},
            {"id": 2, "status": "loss", "description": "Loser", "cost": 1, "returned": 0, "payout": 2,
             "created_at": "2026-10-01T00:00:00+00:00", "settled_at": "2026-10-01T02:00:00+00:00"},
            {"id": 3, "status": "open", "description": "Waiting", "cost": 1, "payout": 2,
             "created_at": "2026-10-01T03:00:00+00:00"},
        ]
        hits = render_slip_history_page(picks, filt="hits")
        self.assertIn("Winner", hits)
        self.assertNotIn("Loser", hits)
        self.assertNotIn("Waiting", hits)
        misses = render_slip_history_page(picks, filt="misses")
        self.assertIn("Loser", misses)
        self.assertNotIn("Winner", misses)
        opened = render_slip_history_page(picks, filt="open")
        self.assertIn("Waiting", opened)
        self.assertIn("No hits in this list.", render_slip_history_page(
            [picks[2]], filt="hits"))
        page = render_slip_history_page(picks, page=2, page_size=1)
        self.assertIn("Page 2 of 3", page)
        self.assertIn("Loser", page)
        self.assertNotIn("Winner", page)
        self.assertNotIn("Waiting", page)
        self.assertIn("filter=all&amp;page=3", page)
        self.assertIn("filter=all&amp;page=1", page)

    def test_description_is_escaped(self):
        page = render_slip_history_page([{
            "id": 1,
            "status": "open",
            "description": "<script>alert(1)</script>",
            "cost": 1,
        }])
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_dashboard_points_at_the_history_page(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent
        source = (root / "bot.py").read_text(encoding="utf-8")
        self.assertIn('web.get("/history", dash_slip_history)', source)
        self.assertIn('href="/history"', source)
        self.assertNotIn("pimp_desk", (root / "slip_history.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
