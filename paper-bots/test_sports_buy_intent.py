"""Sports gap writes a crash intent before cash moves. It does not invent a fill."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GAP_DIR = os.path.join(HERE, "sports-gap-paper")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if GAP_DIR not in sys.path:
    sys.path.insert(0, GAP_DIR)

import desk_brain
import gap_bot


class SportsBuyIntent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "buy_intent.json")
        self._old = gap_bot.BUY_INTENT
        gap_bot.BUY_INTENT = self.path

    def tearDown(self):
        gap_bot.BUY_INTENT = self._old
        self.tmp.cleanup()

    def test_intent_uses_the_real_ask_and_does_not_buy(self):
        payload = gap_bot.write_buy_intent(
            fill_id="TICK|2026-11-11 10:00:00 CT",
            ticker="TICK",
            side="home",
            contracts=2,
            stake=12.5,
            ask=0.62,
        )
        self.assertEqual(payload["tower"], "sports-gap")
        self.assertEqual(payload["exit_rule"], "sports-gap live exit")
        self.assertTrue(payload["paper_only"])
        self.assertEqual(payload["status"], "intent")
        self.assertEqual(payload["ask"], 0.62)
        state = {"cash": 100.0, "open": [], "closed": [], "paper_only": True}
        self.assertEqual(gap_bot.reconcile_buy_intent(state), "abandoned")
        self.assertEqual(state["open"], [])
        self.assertEqual(state["cash"], 100.0)
        with open(self.path, encoding="utf-8") as handle:
            saved = json.loads(handle.read())
        self.assertEqual(saved["status"], "abandoned")
        self.assertNotIn("entry_price", saved)

    def test_saved_fill_is_resumed_not_duplicated(self):
        gap_bot.write_buy_intent(
            fill_id="TICK|1",
            ticker="TICK",
            side="away",
            contracts=1,
            stake=8.0,
            ask=0.55,
        )
        state = {
            "cash": 92.0,
            "open": [{"fill_id": "TICK|1", "ticker": "TICK", "ask": 0.55}],
            "closed": [],
        }
        self.assertEqual(gap_bot.reconcile_buy_intent(state), "open")
        self.assertEqual(len(state["open"]), 1)
        self.assertEqual(state["cash"], 92.0)

    def test_missing_ask_is_not_invented(self):
        with self.assertRaises(ValueError):
            gap_bot.write_buy_intent(
                fill_id="TICK|1",
                ticker="TICK",
                side="home",
                contracts=1,
                stake=8.0,
                ask=None,
            )
        self.assertFalse(os.path.exists(self.path))

    def test_fee_floor_unchanged(self):
        self.assertEqual(gap_bot.MIN_GAP, 0.06)

    def test_exit_this_check_blocks_a_replacement(self):
        self.assertEqual(
            gap_bot.replacement_block("g1", {}, {"g1"}),
            "no replacement after an exit this check",
        )
        self.assertEqual(
            gap_bot.replacement_block("g1", {"g1": {}}, set()),
            "already holding this game",
        )
        self.assertEqual(gap_bot.replacement_block("g2", {}, set()), "")

    def test_close_journals_cash_fee_and_exit_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = {
                "fill_id": "g|1",
                "ticker": "KXNBAGAME-TEST",
                "side": "home",
                "cost": 6.0,
                "fee": 0.02,
                "pnl": 1.5,
            }
            first = gap_bot.record_close(
                row, cash=101.5, exit_name="gap-decay", bid=0.55,
                stake=6.0, exit_fee=gap_bot.fee(0.55), root=tmp,
            )
            second = gap_bot.record_close(
                row, cash=101.5, exit_name="gap-decay", bid=0.55,
                stake=6.0, exit_fee=gap_bot.fee(0.55), root=tmp,
            )
            self.assertEqual(row["cash_after"], 101.5)
            self.assertEqual(row["exit_fee"], gap_bot.fee(0.55))
            self.assertEqual(row["pnl"], 1.5)
            self.assertEqual(first["bot"], "sports-gap")
            self.assertEqual(first["fill_id"], "g|1")
            self.assertEqual(first["bid"], 0.55)
            self.assertEqual(first["stake"], 6.0)
            self.assertEqual(first["exit_name"], "gap-decay")
            self.assertEqual(first["cash"], 101.5)
            self.assertEqual(first["fee"], gap_bot.fee(0.55))
            journal = desk_brain.load_journal(tmp)
            matches = [
                d for d in journal["decisions"]
                if d.get("fill_id") == "g|1" and d.get("exit_name") == "gap-decay"
            ]
            self.assertEqual(len(matches), 1)
            self.assertEqual(second["fill_id"], first["fill_id"])

    def test_settle_does_not_invent_a_bid(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = {"fill_id": "g|2", "ticker": "T", "side": "away", "cost": 4.0, "pnl": -4.0}
            written = gap_bot.record_close(
                row, cash=96.0, exit_name="settled", bid=None, stake=4.0, root=tmp,
            )
            self.assertNotIn("bid", written)
            self.assertNotIn("exit_fee", row)
            self.assertEqual(written["exit_name"], "settled")
            self.assertEqual(written["action"], "settle")
            self.assertEqual(row["pnl"], -4.0)


if __name__ == "__main__":
    unittest.main()
