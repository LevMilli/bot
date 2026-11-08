#!/usr/bin/env python3
"""BTC + commodity CARD densify: evaluate skips surface on CARD (#396 sibling)."""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
BTC = HERE / "btc15m-signal" / "btc15m_signal.py"
CMD = HERE / "commodity-15m-paper" / "bot.py"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BtcCardSkipDensify(unittest.TestCase):
    def test_card_prefers_evaluate_skip_over_generic_no_buy(self):
        btc = _load(BTC, "btc15m_card_under_test")
        card = btc._card_sentence(
            buys=0,
            markets_n=3,
            eth_markets_n=2,
            last_sentence="Checked all open BTC 15-minute markets. No paper buy.",
            skip_reasons=["z < 1.25 (0.91); edge < 0.05 after fees"],
        )
        self.assertIn("z < 1.25", card)
        self.assertNotIn("No paper buy", card)

    def test_card_generic_only_when_skips_empty(self):
        btc = _load(BTC, "btc15m_card_under_test_empty")
        card = btc._card_sentence(
            buys=0,
            markets_n=3,
            eth_markets_n=0,
            last_sentence="Checked all open BTC 15-minute markets. No paper buy.",
            skip_reasons=[],
        )
        self.assertIn("No paper buy", card)

    def test_card_first_skip_wins(self):
        btc = _load(BTC, "btc15m_card_under_test_first")
        card = btc._card_sentence(
            buys=0,
            markets_n=1,
            eth_markets_n=0,
            last_sentence="Checked all open BTC 15-minute markets. No paper buy.",
            skip_reasons=["edge < 0.05 after fees", "firm queue blocks"],
        )
        self.assertEqual(card, "edge < 0.05 after fees")


class CommodityCardSkipDensify(unittest.TestCase):
    def test_card_prefers_evaluate_skip_over_generic_no_buy(self):
        cmd = _load(CMD, "commodity_card_under_test")
        card = cmd._card_sentence(
            buys=0,
            skip_reasons=["edge < 0.05 after fees; z < 1.0"],
        )
        self.assertIn("edge < 0.05", card)
        self.assertNotIn("No paper buy", card)

    def test_card_generic_only_when_skips_empty(self):
        cmd = _load(CMD, "commodity_card_under_test_empty")
        card = cmd._card_sentence(buys=0, skip_reasons=[])
        self.assertIn("No paper buy", card)

    def test_empty_windows_unchanged(self):
        cmd = _load(CMD, "commodity_card_under_test_empty_win")
        card = cmd._card_sentence(buys=0, open_windows=False)
        self.assertIn("No open windows", card)

    def test_evaluate_skip_densifies_brain_skip_board(self):
        cmd = _load(CMD, "commodity_brain_skip_under_test")
        import desk_brain
        import desk_more

        with tempfile.TemporaryDirectory() as tmp:
            cmd.DESK_ROOT = tmp
            cmd._densify_evaluate_skip(
                reasons=["edge < 0.05 after fees", "z < 1.0"],
                ticker="KXGOLD-TEST",
                side="YES",
                edge=0.02,
                confidence=0.61,
            )
            journal = desk_brain.load_journal(tmp)
            last = (journal.get("decisions") or [])[-1]
            self.assertEqual(last.get("bot"), "commodity-15m")
            self.assertEqual(last.get("action"), "skip")
            self.assertEqual(last.get("ticker"), "KXGOLD-TEST")
            board = desk_more.skip_leaderboard(tmp)
            by_bot = board.get("by_bot") or {}
            self.assertIn("commodity-15m", by_bot)
            bot_codes = by_bot.get("commodity-15m") or {}
            self.assertIsInstance(bot_codes, dict)
            self.assertGreaterEqual(sum(int(v) for v in bot_codes.values()), 1)


if __name__ == "__main__":
    unittest.main()
