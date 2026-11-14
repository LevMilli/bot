"""The city side and the vault read one cash book. Paper only. No invented balances."""
import os
import shutil
import tempfile
import unittest

import pimp_desk
import teller_memory

ROOT = os.path.dirname(os.path.abspath(__file__))


class RecordedCashTests(unittest.TestCase):
    def test_each_kind_reads_only_its_own_key(self):
        self.assertEqual(pimp_desk.recorded_cash({"cash": 12.5, "cash_usd": 99}, "macro"), 12.5)
        self.assertEqual(pimp_desk.recorded_cash({"cash": 12.5, "bankroll": 400}, "sports"), 12.5)
        self.assertEqual(pimp_desk.recorded_cash({"bankroll": 444.37, "cash": 1}, "kalshi"), 444.37)
        self.assertEqual(pimp_desk.recorded_cash({"cash_usd": 5.09, "cash": 80}, "meme"), 5.09)
        self.assertEqual(pimp_desk.recorded_cash({"cash": 0.0}, "floor"), 0.0)
        self.assertEqual(pimp_desk.recorded_cash({"cash": 0.0}, "log"), 0.0)

    def test_missing_cash_stays_blank(self):
        self.assertIsNone(pimp_desk.recorded_cash({"paper_only": True}, "macro"))
        self.assertIsNone(pimp_desk.recorded_cash({"paper_only": True}, "sports"))
        self.assertIsNone(pimp_desk.recorded_cash({"cash_usd": 100}, "fed-watch"))
        self.assertIsNone(pimp_desk.recorded_cash({"open": []}, "floor"))
        self.assertIsNone(pimp_desk.recorded_cash(None, "btc"))
        self.assertIsNone(pimp_desk.recorded_cash({"cash": "nope"}, "spot"))

    def test_book_does_not_borrow_another_tower(self):
        bots = [
            {"id": "sports-gap", "cash": 100.0, "shadow_only": False},
            {"id": "fed-watch", "cash": None, "shadow_only": True},
            {"id": "coinbase-spot", "cash": 480.25, "shadow_only": True},
        ]
        book = teller_memory.cash_book(bots)
        self.assertEqual(book["cash"], 580.25)
        by_id = {row["id"]: row["cash"] for row in book["rows"]}
        self.assertEqual(by_id["sports-gap"], 100.0)
        self.assertIsNone(by_id["fed-watch"])
        self.assertEqual(by_id["coinbase-spot"], 480.25)
        self.assertEqual(teller_memory.tower_cash_line(bots[1]), "")
        self.assertEqual(teller_memory.tower_cash_line(bots[2]), "coinbase-spot cash $480.25")

    def test_checkout_book_matches_every_tower_and_not_the_desk_subset(self):
        previous = os.environ.get("PAPER_KEEP_SETTLEMENTS")
        os.environ["PAPER_KEEP_SETTLEMENTS"] = "0"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                dest = os.path.join(tmp, "paper-bots")
                shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(
                    "__pycache__", ".pytest_cache", "fixtures", "*.jsonl", "*.jsonl.1", "recordings",
                ))
                snap = pimp_desk.snapshot(dest)
        finally:
            if previous is None:
                os.environ.pop("PAPER_KEEP_SETTLEMENTS", None)
            else:
                os.environ["PAPER_KEEP_SETTLEMENTS"] = previous
        bots = snap["bots"]
        book = snap["desk"]["cash_book"]
        self.assertEqual([row["id"] for row in book["rows"]], [bot["id"] for bot in bots])
        for bot, row in zip(bots, book["rows"]):
            self.assertEqual(row["cash"], bot["cash"], bot["id"])
        recorded = [bot["cash"] for bot in bots if bot["cash"] is not None]
        self.assertEqual(book["cash"], round(sum(recorded), 2))
        # Desk cash stays the towers that spend it. The shared book is wider.
        self.assertNotEqual(snap["desk"]["cash"], book["cash"])
        self.assertIsNone(next(bot["cash"] for bot in bots if bot["id"] == "fed-watch"))
        self.assertIsNone(next(bot["cash"] for bot in bots if bot["id"] == "sports-sharp-lag"))
        fed = next(bot for bot in bots if bot["id"] == "fed-watch")
        self.assertNotIn("cash_line", fed)

    def test_shadow_sleeve_without_a_file_is_not_given_cash(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "btc15m-signal"))
            cfg = {"shadow": {"enabled": True, "btc15m": [{"id": "edge08", "params": {"venue_edge": 0.08}}]}}
            rows = pimp_desk.shadow_snapshot_rows(tmp, cfg)
            self.assertEqual(len(rows), 1)
            self.assertIsNone(rows[0]["cash"])
            pimp_desk.save_shadow_account(tmp, "btc15m", "edge08", {
                "cash": 999.0, "open": [], "closed": [], "paper_only": True,
            })
            again = pimp_desk.shadow_snapshot_rows(tmp, cfg)
            self.assertEqual(again[0]["cash"], 999.0)


if __name__ == "__main__":
    unittest.main()
