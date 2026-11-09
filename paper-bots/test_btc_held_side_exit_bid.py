"""BTC/ETH exits must mark held-side bid — never complementary model bid."""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BTC_PATH = os.path.join(HERE, "btc15m-signal", "btc15m_signal.py")


def _load_btc():
    spec = importlib.util.spec_from_file_location("btc15m_signal", BTC_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["btc15m_signal"] = mod
    spec.loader.exec_module(mod)
    return mod


class HeldSideExitBid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.btc = _load_btc()

    def _yes_open(self, **extra):
        pos = {
            "ticker": "KXBTC15M-T",
            "side": "YES",
            "ask": 0.70,
            "take_profit": 0.85,
            "contracts": 10,
            "cost": 7.20,
            "fair_at_entry": 0.88,
            "fill_id": "t1",
        }
        pos.update(extra)
        return pos

    def test_false_tp_refused_on_complement_bid(self):
        """Model flipped to NO with high NO bid must not TP a YES hold."""
        state = {"cash": 100.0, "open": [self._yes_open()], "closed": [], "paper_only": True}
        market = {
            "ticker": "KXBTC15M-T",
            "yes_bid": 0.18,
            "yes_ask": 0.22,
            "no_bid": 0.80,
            "no_ask": 0.84,
        }
        # Old bug: manage_take_profits(bid=0.80) with TP=0.85 narrowly misses,
        # but TP=0.80 would false-fire. Use TP=0.80 to prove refusal.
        state["open"][0]["take_profit"] = 0.80
        sold = self.btc.manage_take_profits(
            state,
            bid=0.80,  # NO / model side
            fee=0.02,
            ticker="KXBTC15M-T",
            market=market,
            model_side="NO",
        )
        self.assertEqual(sold, [])
        self.assertEqual(len(state["open"]), 1)
        self.assertEqual(state["open"][0]["side"], "YES")

    def test_flip_sells_at_held_listing_bid(self):
        state = {"cash": 100.0, "open": [self._yes_open()], "closed": [], "paper_only": True}
        market = {
            "ticker": "KXBTC15M-T",
            "yes_bid": 0.18,
            "yes_ask": 0.22,
            "no_bid": 0.80,
            "no_ask": 0.84,
        }
        sold = self.btc.manage_model_flips(
            state,
            side_now="NO",
            prob_now=0.82,
            bid=0.80,  # complementary — must not be the mark
            fee=0.02,
            delta=0.08,
            ticker="KXBTC15M-T",
            market=market,
        )
        self.assertEqual(len(sold), 1)
        self.assertEqual(len(state["open"]), 0)
        closed = state["closed"][0]
        self.assertAlmostEqual(float(closed["exit_price"]), 0.18)
        self.assertIn("model-flip side YES→NO", closed["exit"])
        # Proceeds at 0.18 − fee, not invent at 0.80.
        self.assertLess(float(closed["pnl"]), 0.0)

    def test_same_side_tp_still_fires(self):
        state = {"cash": 100.0, "open": [self._yes_open()], "closed": [], "paper_only": True}
        market = {
            "ticker": "KXBTC15M-T",
            "yes_bid": 0.86,
            "yes_ask": 0.88,
            "no_bid": 0.12,
            "no_ask": 0.14,
        }
        sold = self.btc.manage_take_profits(
            state,
            bid=0.86,
            fee=0.02,
            ticker="KXBTC15M-T",
            market=market,
            model_side="YES",
        )
        self.assertEqual(len(sold), 1)
        self.assertAlmostEqual(float(state["closed"][0]["exit_price"]), 0.86)

    def test_mark_helper_refuses_complement_without_listing(self):
        pos = self._yes_open()
        # No listing + book hard-fail — must not fall back to complementary NO bid.
        orig = self.btc.book_for_side
        self.btc.book_for_side = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no book"))
        try:
            mark = self.btc.mark_bid_for_held(
                pos, model_side="NO", model_bid=0.90, market=None,
            )
        finally:
            self.btc.book_for_side = orig
        self.assertIsNone(mark)

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertAlmostEqual(floors["venues"]["kalshi_btc15m"]["floor"], 0.05)


if __name__ == "__main__":
    unittest.main()
