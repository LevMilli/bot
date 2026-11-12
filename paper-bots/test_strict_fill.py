"""Paper buys re-check the book and fill at the worse price, sized to the book."""
from __future__ import annotations

import os
import unittest
from unittest import mock

import strict_fill
import test_btc15m_buy as btc_buy
import test_commodity_buy as com_buy


def _book(no_bids=(), yes_bids=()):
    return {"orderbook_fp": {
        "yes_dollars": [[str(p), str(q)] for p, q in yes_bids],
        "no_dollars": [[str(p), str(q)] for p, q in no_bids],
    }}


def _check(book, ask=0.80, n=10, **kw):
    kw.setdefault("fee_per", strict_fill.kalshi_fee)
    return strict_fill.recheck("T", "YES", ask, n, fetch=lambda t: book, wait=0, force=True, **kw)


class RecheckTests(unittest.TestCase):
    def test_price_held_keeps_the_fill(self):
        out = _check(_book(no_bids=[(0.20, 100)]))
        self.assertTrue(out["ok"])
        self.assertEqual((out["ask"], out["contracts"], out["slip"]), (0.80, 10, 0.0))
        self.assertTrue(out["requoted"])

    def test_worse_quote_fills_at_the_worse_price(self):
        out = _check(_book(no_bids=[(0.18, 100)]))
        self.assertTrue(out["ok"])
        self.assertEqual(out["ask"], 0.82)
        self.assertAlmostEqual(out["slip"], 0.02)

    def test_better_quote_is_not_taken(self):
        out = _check(_book(no_bids=[(0.25, 100)]))
        self.assertEqual(out["ask"], 0.80)
        self.assertEqual(out["quoted_ask"], 0.75)

    def test_no_side_reads_the_yes_bids(self):
        out = strict_fill.recheck("T", "no", 0.30, 5, fetch=lambda t: _book(yes_bids=[(0.68, 50)]),
                                  wait=0, force=True)
        self.assertEqual(out["ask"], 0.32)

    def test_size_is_capped_to_half_the_book(self):
        out = _check(_book(no_bids=[(0.20, 8), (0.10, 500)]))
        self.assertTrue(out["ok"])
        self.assertEqual(out["contracts"], 4)
        self.assertTrue(out["capped"])
        self.assertIn("size cut", out["note"])

    def test_depth_share_can_be_changed(self):
        with mock.patch.dict(os.environ, {"PAPER_DEPTH_SHARE": "1"}):
            out = _check(_book(no_bids=[(0.20, 8)]))
        self.assertEqual(out["contracts"], 8)

    def test_thin_book_skips(self):
        out = _check(_book(no_bids=[(0.20, 1)]))
        self.assertFalse(out["ok"])
        self.assertIn("too thin", out["reason"])

    def test_price_ran_away_skips(self):
        out = _check(_book(no_bids=[(0.15, 100)]))
        self.assertFalse(out["ok"])
        self.assertIn("ran away", out["reason"])

    def test_edge_gone_after_the_move_skips(self):
        out = _check(_book(no_bids=[(0.18, 100)]), edge=0.06, min_edge=0.05)
        self.assertFalse(out["ok"])
        self.assertIn("edge gone", out["reason"])
        ok = _check(_book(no_bids=[(0.19, 100)]), edge=0.07, min_edge=0.05)
        self.assertTrue(ok["ok"])

    def test_unreadable_book_assumes_a_cent_worse(self):
        def boom(_t):
            raise OSError("down")
        out = strict_fill.recheck("T", "YES", 0.80, 10, fetch=boom, wait=0, force=True)
        self.assertTrue(out["ok"])
        self.assertEqual(out["ask"], 0.81)
        self.assertEqual(out["contracts"], 10)
        self.assertFalse(out["requoted"])
        empty = _check({"orderbook_fp": {}})
        self.assertEqual(empty["ask"], 0.81)

    def test_legacy_cent_books_parse(self):
        out = _check({"orderbook": {"no": [[20, 100]], "yes": []}})
        self.assertEqual(out["quoted_ask"], 0.80)

    def test_switch_off(self):
        with mock.patch.dict(os.environ, {"PAPER_STRICT_FILL": "0"}):
            out = strict_fill.recheck("T", "YES", 0.80, 10, fetch=lambda t: 1 / 0, wait=0)
        self.assertEqual((out["ask"], out["contracts"]), (0.80, 10))


class Btc15mStrictBuy(btc_buy.Btc15mBuy):
    """BTC 15m paper buy runs the re-check and books the worse fill."""

    def setUp(self):
        super().setUp()
        self.env = mock.patch.dict(os.environ, {"PAPER_STRICT_FILL": "1", "PAPER_REQUOTE_SECONDS": "0"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        super().tearDown()

    def _buy(self, book, edge=0.08):
        state = {"cash": 100.0, "open": [], "closed": []}
        with mock.patch.object(strict_fill, "_fetch", lambda t: book):
            msg = self.btc.paper_buy(
                state, "KXBTC15M-T", "YES", 0.80, 0.02, 0.90,
                "2026-11-11T18:00:00Z", True, edge=edge, series="KXBTC15M",
            )
        return msg, state

    def test_second_side_is_not_a_hedge_and_abandon_invents_nothing(self):
        pass  # covered in the parent with the check off

    def test_worse_fill_and_book_size_land_on_the_paper_row(self):
        msg, state = self._buy(_book(no_bids=[(0.19, 12)]))
        self.assertIn("Paper buy", msg)
        pos = state["open"][0]
        self.assertEqual(pos["ask"], 0.81)
        self.assertEqual(pos["contracts"], 6)
        self.assertEqual(pos["fee"], strict_fill.kalshi_fee(0.81))
        self.assertEqual(pos["cost"], round(6 * (0.81 + strict_fill.kalshi_fee(0.81)), 2))
        self.assertTrue(pos["fill_check"]["capped"])
        self.assertEqual(pos["fill_check"]["decided_ask"], 0.80)

    def test_run_away_price_books_nothing(self):
        msg, state = self._buy(_book(no_bids=[(0.10, 100)]))
        self.assertIn("ran away", msg)
        self.assertEqual(state["open"], [])
        self.assertEqual(state["cash"], 100.0)


class CommodityStrictBuy(com_buy.CommodityBuy):
    """Commodity 15m paper buy books the re-checked price and fee."""

    def setUp(self):
        super().setUp()
        self.env = mock.patch.dict(os.environ, {"PAPER_STRICT_FILL": "1", "PAPER_REQUOTE_SECONDS": "0"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        super().tearDown()

    def test_intent_is_written_before_cash_and_a_red_day_skip_writes_nothing(self):
        pass  # parent covers it with the check off

    def test_open_series_is_not_averaged_and_abandoned_intent_adds_nothing(self):
        pass

    def test_worse_fill_lands_on_the_commodity_row(self):
        state = {"cash": 100.0, "open": [], "closed": []}
        with mock.patch.object(strict_fill, "_fetch", lambda t: _book(no_bids=[(0.18, 100)])):
            msg = self.bot.paper_buy(state, self._ev(), 0)
        self.assertTrue(msg.startswith("Paper buy"), msg)
        pos = state["open"][0]
        self.assertEqual(pos["ask"], 0.82)
        self.assertEqual(pos["fee"], strict_fill.kalshi_fee(0.82))
        self.assertEqual(pos["fill_check"]["slip"], 0.02)

    def test_edge_gone_books_nothing(self):
        state = {"cash": 100.0, "open": [], "closed": []}
        ev = dict(self._ev(), edge=0.015)
        with mock.patch.object(strict_fill, "_fetch", lambda t: _book(no_bids=[(0.18, 100)])):
            msg = self.bot.paper_buy(state, ev, 0)
        self.assertIn("edge gone", msg)
        self.assertEqual(state["open"], [])
        self.assertFalse(os.path.exists(self.path))


if __name__ == "__main__":
    unittest.main()
