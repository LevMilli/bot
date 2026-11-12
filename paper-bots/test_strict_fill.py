"""Paper buys re-check the book and fill at the worse price, sized to the book."""
from __future__ import annotations

import os
import unittest
from unittest import mock

import strict_fill
import test_btc15m_buy as btc_buy
import test_coinbase_sell as cb_sell
import test_commodity_buy as com_buy
import test_memecoin_buy as meme_buy


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


class SpotRecheckTests(unittest.TestCase):
    def _go(self, live, side="buy", **kw):
        return strict_fill.spot_recheck(100.0, lambda: live, side=side, wait=0, force=True, **kw)

    def test_buy_pays_the_higher_price(self):
        self.assertEqual(self._go(101.0)["price"], 101.0)
        self.assertEqual(self._go(99.0)["price"], 100.0)

    def test_sell_gets_the_lower_price_and_is_never_skipped(self):
        self.assertEqual(self._go(99.0, "sell")["price"], 99.0)
        self.assertEqual(self._go(101.0, "sell")["price"], 100.0)
        crash = self._go(50.0, "sell", max_slip=0.01)
        self.assertTrue(crash["ok"])
        self.assertEqual(crash["price"], 50.0)

    def test_buy_that_ran_away_skips(self):
        out = self._go(106.0, max_slip=0.05)
        self.assertFalse(out["ok"])
        self.assertIn("ran away", out["reason"])

    def test_unreadable_price_assumes_one_percent_worse(self):
        self.assertAlmostEqual(self._go(None)["price"], 101.0)
        self.assertAlmostEqual(self._go(None, "sell")["price"], 99.0)
        boom = strict_fill.spot_recheck(100.0, lambda: 1 / 0, wait=0, force=True)
        self.assertAlmostEqual(boom["price"], 101.0)


class MemecoinStrict(unittest.TestCase):
    def setUp(self):
        self.case = meme_buy.MemecoinBuy("test_intent_names_the_flip_and_the_stop_before_cash_moves")
        self.case.setUp()
        self.bot = self.case.bot
        self.env = mock.patch.dict(os.environ, {"PAPER_STRICT_FILL": "1", "PAPER_REQUOTE_SECONDS": "0"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.case.tearDown()

    def test_buy_fills_at_the_worse_price_and_thinner_pool(self):
        state = {"cash_usd": 100.0, "open": []}
        self.bot.pair_now = lambda pair: (1.02, 50000.0)
        pos = self.bot.commit_paper_buy(
            state, mint="M", symbol="X", pair="P", price=1.0, liq=100000,
            ticket=10, conf=0.9, lane="accurate",
        )
        self.assertIsInstance(pos, dict)
        self.assertEqual(pos["entry_market_price"], 1.02)
        self.assertEqual(pos["entry_liq"], 50000.0)
        self.assertEqual(pos["fill_check"]["decided"], 1.0)
        tokens, _fee, _imp, _fill = self.bot.paper_buy(1.02, 50000.0, 10)
        self.assertAlmostEqual(pos["tokens"], tokens)

    def test_buy_that_ran_away_books_nothing(self):
        state = {"cash_usd": 100.0, "open": []}
        self.bot.pair_now = lambda pair: (1.20, 100000.0)
        out = self.bot.commit_paper_buy(
            state, mint="M", symbol="X", pair="P", price=1.0, liq=100000,
            ticket=10, conf=0.9, lane="accurate",
        )
        self.assertIn("ran away", out)
        self.assertEqual(state["open"], [])
        self.assertEqual(state["cash_usd"], 100.0)

    def test_sell_takes_the_lower_price(self):
        rows = []
        self.bot.append_csv = lambda path, cols, row: rows.append(row)
        self.bot.pair_now = lambda pair: (0.90, 100000.0)
        pos = {"mint": "M", "symbol": "X", "pair": "P", "tokens": 10.0, "tokens_left": 10.0,
               "cost_usd": 10.0}
        st = {"cash_usd": 0.0, "realized_pnl_usd": 0.0}
        try:
            self.bot.sell(st, pos, 1, "stop", 1.0, 100000.0, full=True)
        except Exception:
            pass  # desk ledgers after the fill are not under test here
        self.assertEqual(rows[0]["market_price_usd"], 0.90)


class CoinbaseStrict(unittest.TestCase):
    def setUp(self):
        self.bot = cb_sell._bot()
        self.env = mock.patch.dict(os.environ, {"PAPER_STRICT_FILL": "1", "PAPER_REQUOTE_SECONDS": "0"})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_exit_sells_at_the_lower_live_bid(self):
        self.bot.live_quote = lambda product, side="buy": 97.0
        pos = cb_sell._pos(self.bot)
        state = {"cash": 475.0, "open": [pos], "closed": []}
        out = self.bot.failsafe_sale(state, {"ETH-USD": 98.0}, z_by_product={"ETH-USD": -3},
                                     now=cb_sell.NOW)
        self.assertTrue(out["sold"])
        closed = state["closed"][0]
        self.assertEqual(closed["exit_price"], 97.0)
        self.assertEqual(closed["fill_check"]["decided"], 98.0)

    def test_buy_check_pays_the_live_ask(self):
        self.bot.live_quote = lambda product, side="buy": 100.3
        check = self.bot.strict_mark("ETH-USD", 100.0, "buy")
        self.assertAlmostEqual(check["price"], 100.3)
        self.bot.live_quote = lambda product, side="buy": 101.0
        self.assertFalse(self.bot.strict_mark("ETH-USD", 100.0, "buy")["ok"])

    def test_off_switch(self):
        with mock.patch.dict(os.environ, {"PAPER_STRICT_FILL": "0"}):
            self.assertIsNone(self.bot.strict_mark("ETH-USD", 100.0, "buy"))


if __name__ == "__main__":
    unittest.main()
