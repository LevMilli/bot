"""BTC carry on Coinbase: wallet, margin, hourly funding, daily results. No network."""
from __future__ import annotations

import datetime as dt
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_profit
import desk_safety


def _bot():
    path = os.path.join(HERE, "btc-carry-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("btc_carry_cb_bot", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


B = _bot()
T0 = dt.datetime(2026, 11, 14, 6, 30, tzinfo=dt.timezone.utc)
CLEAN_ENV = {k: "" for k in B.KEY_ENV}


def _q(price=67280.0, rate=0.000004, ftime=None, spread=10.0, perp_gap=10.0,
       overnight=0.256625, intraday=0.0999811):
    ftime = ftime or T0.replace(minute=0)
    return {
        "at": T0.isoformat(), "error": "",
        "spot_bid": price - spread / 2, "spot_ask": price + spread / 2,
        "perp_bid": price - perp_gap / 2 + 0.0, "perp_ask": price + perp_gap / 2,
        "funding_rate": rate, "funding_time": ftime.isoformat(timespec="seconds"),
        "short_margin_overnight": overnight, "short_margin_intraday": intraday,
        "contract_size": 0.01, "index": price,
    }


def _cfg():
    return B.locked_cfg(B.load_config())


def _seed_funding(state, rate, hours, end):
    for i in range(hours, 0, -1):
        t = end - dt.timedelta(hours=i)
        state["funding_seen"].append({"time": t.replace(minute=0, second=0, microsecond=0)
                                      .isoformat(timespec="seconds"), "rate": rate, "est": False})


def _opened(rate=0.00004):
    st = B.empty_state()
    _seed_funding(st, rate, 30, T0)
    cfg = _cfg()
    out = B.place_open(st, _q(rate=rate), cfg, T0)
    assert out["bought"], out
    return st, cfg


class LockTests(unittest.TestCase):
    def test_fees_only_go_up(self):
        cfg = B.locked_cfg({"spot_taker": 0.0001, "perp_taker": 0, "perp_fee_min": 0,
                            "liq_fee_rate": 0, "venue_min_edge": 0.001, "contracts": 9})
        self.assertEqual(cfg["spot_taker"], 0.009)
        self.assertEqual(cfg["perp_taker"], 0.0005)
        self.assertEqual(cfg["perp_fee_min"], 0.20)
        self.assertEqual(cfg["liq_fee_rate"], 0.008)
        self.assertEqual(cfg["contracts"], 1)
        self.assertEqual(cfg["venue_min_edge"], 0.02)
        self.assertFalse(cfg["live_orders"])

    def test_locked_floor_tables(self):
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["coinbase_btc_carry"], 0.02)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["binance_btc_carry"], 0.02)
        self.assertEqual(desk_safety.LOCKED_FLOORS["coinbase_btc_carry"], 0.02)
        self.assertEqual(desk_profit.BOT_VENUE["btc-carry"], "coinbase_btc_carry")

    def test_perp_fee_minimum(self):
        cfg = _cfg()
        self.assertAlmostEqual(B.perp_fee(cfg, 67000.0), 0.335, places=4)
        self.assertAlmostEqual(B.perp_fee(cfg, 1000.0), 0.20, places=4)

    def test_round_trip_is_about_two_percent(self):
        rt = B.round_trip_rate(_cfg(), _q())
        self.assertGreater(rt, 0.018)
        self.assertLess(rt, 0.021)

    def test_no_order_endpoints_or_keys_in_source(self):
        src = open(os.path.join(HERE, "btc-carry-paper", "bot.py"), encoding="utf-8").read()
        for bad in ("/orders", "CB-ACCESS", "api_secret", "create_order", "fapi.binance"):
            self.assertNotIn(bad, src)
        self.assertTrue(re.search(r"api\.coinbase\.com/api/v3/brokerage/market", src))


class QuoteTests(unittest.TestCase):
    def test_parse_coinbase_json(self):
        spot = {"pricebook": {"bids": [{"price": "67270"}], "asks": [{"price": "67286"}]}}
        book = {"pricebook": {"bids": [{"price": "67275"}], "asks": [{"price": "67305"}]}}
        perp = {"future_product_details": {
            "funding_rate": "0.000004", "funding_time": "2026-11-14T06:00:00Z",
            "contract_size": "0.01", "index_price": "67271",
            "intraday_margin_rate": {"short_margin_rate": "0.0999811"},
            "overnight_margin_rate": {"short_margin_rate": "0.256625"},
            "perpetual_details": {"funding_rate": ""},
        }}
        q = B.parse_quotes(spot, book, perp, at="x")
        self.assertEqual(q["error"], "")
        self.assertEqual(q["perp_bid"], 67275.0)
        self.assertAlmostEqual(q["funding_rate"], 0.000004)
        self.assertTrue(q["funding_time"].startswith("2026-11-14T06:00:00"))
        self.assertAlmostEqual(q["short_margin_intraday"], 0.0999811)

    def test_bad_quotes_flagged(self):
        self.assertIn("missing", B.quote_problem({**_q(), "perp_bid": None}))
        self.assertEqual(B.quote_problem({**_q(), "contract_size": 0.1}), "contract size changed")
        self.assertEqual(B.quote_problem({**_q(), "funding_rate": 0.5}), "funding rate out of range")


class FundingTests(unittest.TestCase):
    def test_positive_rate_pays_the_short(self):
        st, cfg = _opened()
        before = B.equity(st, _q())
        q = _q(rate=0.0001, ftime=T0.replace(minute=0) + dt.timedelta(hours=1))
        out = B.record_funding(st, q, T0 + dt.timedelta(hours=1))
        self.assertGreater(out["credited"], 0)
        self.assertAlmostEqual(out["credited"], 0.0001 * 67280.0 * 0.01, places=4)
        self.assertGreater(B.equity(st, q), before)

    def test_negative_rate_costs_the_short(self):
        st, _ = _opened()
        q = _q(rate=-0.0001, ftime=T0.replace(minute=0) + dt.timedelta(hours=1))
        self.assertLess(B.record_funding(st, q, T0 + dt.timedelta(hours=1))["credited"], 0)

    def test_missed_hours_estimated_once(self):
        st, _ = _opened(rate=0.00002)
        q = _q(rate=0.00003, ftime=T0.replace(minute=0) + dt.timedelta(hours=4))
        out = B.record_funding(st, q, T0 + dt.timedelta(hours=4))
        # Seeds end at 05:00; 06-09 are estimated, 10:00 is real.
        self.assertEqual(out["new_hours"], 5)
        self.assertEqual(out["estimated"], 4)
        # Only hours after the 06:30 open are credited: 07, 08, 09.
        self.assertEqual(st["est_hours"], 3)
        again = B.record_funding(st, q, T0 + dt.timedelta(hours=4, minutes=5))
        self.assertEqual(again["new_hours"], 0)

    def test_flat_book_earns_nothing(self):
        st = B.empty_state()
        out = B.record_funding(st, _q(), T0)
        self.assertEqual(out["credited"], 0.0)
        self.assertEqual(out["new_hours"], 1)


class EntryTests(unittest.TestCase):
    def test_waits_for_24_hours(self):
        st = B.empty_state()
        _seed_funding(st, 0.0001, 10, T0)
        e = B.entry_edge(st, _q(), _cfg(), T0)
        self.assertFalse(e["ok"])
        self.assertIn("waiting on funding history", e["reason"])

    def test_low_funding_stays_flat(self):
        st = B.empty_state()
        _seed_funding(st, 0.000004, 30, T0)  # about 3.5%/yr
        e = B.entry_edge(st, _q(), _cfg(), T0)
        self.assertFalse(e["ok"])
        self.assertIn("below floor", e["reason"])

    def test_high_funding_opens(self):
        st = B.empty_state()
        _seed_funding(st, 0.00001, 30, T0)  # about 8.8%/yr
        e = B.entry_edge(st, _q(), _cfg(), T0)
        self.assertTrue(e["ok"], e["reason"])

    def test_open_lays_out_wallet(self):
        st, _ = _opened()
        w = st["wallet"]
        self.assertAlmostEqual(w["spot_btc"], 0.01)
        self.assertEqual(w["short_contracts"], 1)
        self.assertGreater(w["futures_usd"], 300)
        self.assertLess(w["spot_usd"], 1500 - 672)
        self.assertGreater(st["fees_paid"], 6)
        # Equity drops only by fees, not by the BTC bought.
        self.assertAlmostEqual(B.equity(st, _q()), 1500 - st["fees_paid"] - 0.05, delta=0.2)

    def test_wallet_too_small(self):
        st = B.empty_state()
        st["wallet"]["spot_usd"] = 500.0
        out = B.place_open(st, _q(), _cfg(), T0)
        self.assertFalse(out["bought"])
        self.assertIn("below", out["reason"])


class MarginAndSettleTests(unittest.TestCase):
    def test_daily_settle_sums_to_equity_change(self):
        st, cfg = _opened()
        t = T0
        price = 67280.0
        for day in range(1, 6):
            t = T0 + dt.timedelta(days=day)
            price += 500 if day % 2 else -900
            q = _q(price=price, rate=0.00004, ftime=t.replace(minute=0))
            B.record_funding(st, q, t)
            B.margin_check(st, q, cfg, t)
            B.daily_settle(st, q, cfg, t)
        rows = B.results(st)
        self.assertGreaterEqual(len(rows), 4)
        self.assertTrue(all(r["exit"] == "day-mark" for r in rows))
        self.assertAlmostEqual(sum(r["pnl"] for r in rows),
                               st["equity_at_settle"] - 1500.0, places=2)

    def test_top_up_from_spot_usd(self):
        st, cfg = _opened()
        q = _q(price=67280.0 * 1.15)
        out = B.margin_check(st, q, cfg, T0 + dt.timedelta(hours=2))
        self.assertEqual(out["action"], "topped_up")
        self.assertEqual(out["btc_sold"], 0.0)
        self.assertTrue(any(s["why"] == "margin top-up" for s in st["sweeps"]))

    def test_top_up_sells_btc_when_usd_is_gone(self):
        st, cfg = _opened()
        st["wallet"]["spot_usd"] = 0.0
        q = _q(price=67280.0 * 1.15)
        out = B.margin_check(st, q, cfg, T0 + dt.timedelta(hours=2))
        self.assertGreater(out["btc_sold"], 0)
        self.assertLess(st["wallet"]["spot_btc"], 0.01)
        self.assertTrue(any(e["kind"] == "hedge-drift" for e in st["events"]))

    def test_liquidation_below_intraday(self):
        st, cfg = _opened()
        st["wallet"]["futures_usd"] = 20.0
        out = B.margin_check(st, _q(price=67280.0 * 1.05), cfg, T0 + dt.timedelta(hours=2))
        self.assertEqual(out["action"], "liquidated")
        self.assertEqual(st["open"], [])
        self.assertEqual(B.results(st)[-1]["exit"], "liquidation")
        self.assertAlmostEqual(st["wallet"]["futures_usd"], 0.0, places=6)
        self.assertTrue(any(s["why"] == "cover futures deficit" for s in st["sweeps"]))

    def test_sweep_back_at_settle(self):
        st, cfg = _opened()
        t = T0 + dt.timedelta(days=1)
        q = _q(price=67280.0 * 0.85, ftime=t.replace(minute=0))
        B.daily_settle(st, q, cfg, t)
        self.assertTrue(any(s["why"] == "extra margin back to spot" for s in st["sweeps"]))
        need = B.margin_need(st, q)
        self.assertAlmostEqual(st["wallet"]["futures_usd"], 2 * need, places=2)


class ExitTests(unittest.TestCase):
    def test_no_exit_inside_30_days(self):
        st, cfg = _opened()
        _seed_funding(st, -0.0001, 30, T0 + dt.timedelta(days=10))
        self.assertFalse(B.exit_check(st, _q(), cfg, T0 + dt.timedelta(days=10))["exit"])

    def test_exit_on_negative_week_after_30_days(self):
        st, cfg = _opened()
        later = T0 + dt.timedelta(days=31)
        _seed_funding(st, -0.00001, 168, later)
        out = B.exit_check(st, _q(), cfg, later)
        self.assertTrue(out["exit"])
        self.assertEqual(B.results(st)[-1]["exit"], "close")
        self.assertAlmostEqual(st["wallet"]["spot_usd"], st["equity_at_settle"], places=4)


class RunTests(unittest.TestCase):
    def _root(self, tmp, state=None):
        tower = os.path.join(tmp, "btc-carry-paper")
        os.makedirs(tower)
        with open(os.path.join(HERE, "btc-carry-paper", "config.json"), encoding="utf-8") as f:
            cfg = f.read()
        with open(os.path.join(tower, "config.json"), "w", encoding="utf-8") as f:
            f.write(cfg)
        if state is not None:
            with open(os.path.join(tower, "paper_account.json"), "w", encoding="utf-8") as f:
                json.dump(state, f)
        return tower

    def test_key_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._root(tmp)
            buf = io.StringIO()
            with mock.patch.dict(os.environ, {**CLEAN_ENV, B.KEY_ENV[0]: "x"}), redirect_stdout(buf):
                B.run_once(tmp, fetch=lambda: self.fail("no fetch with a key"), now=T0)
            self.assertIn("SKIP key", buf.getvalue())

    def test_migration_archives_binance_book(self):
        old = {"cash": 499.25, "open": [{"ticker": "BTCUSDT"}], "closed": [{"pnl": 1.5}]}
        with tempfile.TemporaryDirectory() as tmp:
            tower = self._root(tmp, old)
            with mock.patch.dict(os.environ, CLEAN_ENV), redirect_stdout(io.StringIO()):
                B.run_once(tmp, fetch=lambda: _q(), now=T0)
            arch = json.load(open(os.path.join(tower, "paper_account.binance-retired.json")))
            self.assertEqual(arch["cash"], 499.25)
            st = json.load(open(os.path.join(tower, "paper_account.json")))
            self.assertEqual(st["venue"], "coinbase_btc_carry")
            self.assertEqual(st["closed"], [])
            self.assertEqual(st["wallet"]["spot_usd"], 1500.0)
            self.assertTrue(any(e["kind"] == "moved" for e in st["events"]))

    def test_run_flat_then_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            tower = self._root(tmp)
            buf = io.StringIO()
            with mock.patch.dict(os.environ, {**CLEAN_ENV, "DESK_BLOCK_ENTRIES": ""}), redirect_stdout(buf):
                B.run_once(tmp, fetch=lambda: _q(), now=T0)
            self.assertIn("waiting on funding history", buf.getvalue())
            st = json.load(open(os.path.join(tower, "paper_account.json")))
            _seed_funding(st, 0.00002, 30, T0 + dt.timedelta(hours=1))
            json.dump(st, open(os.path.join(tower, "paper_account.json"), "w"))
            buf = io.StringIO()
            t = T0 + dt.timedelta(hours=1)
            with mock.patch.dict(os.environ, {**CLEAN_ENV, "DESK_BLOCK_ENTRIES": ""}), redirect_stdout(buf):
                B.run_once(tmp, fetch=lambda: _q(rate=0.00002, ftime=t.replace(minute=0)), now=t)
            self.assertIn("SIGNAL: OPEN", buf.getvalue())
            st = json.load(open(os.path.join(tower, "paper_account.json")))
            self.assertEqual(len(st["open"]), 1)
            self.assertTrue(st["paper_only"])

    def test_entry_gate_blocks_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = B.empty_state()
            _seed_funding(st, 0.00002, 30, T0)
            tower = self._root(tmp, st)
            buf = io.StringIO()
            with mock.patch.dict(os.environ, {**CLEAN_ENV, "DESK_BLOCK_ENTRIES": "1"}), redirect_stdout(buf):
                B.run_once(tmp, fetch=lambda: _q(rate=0.00002), now=T0)
            self.assertIn("desk entry gate", buf.getvalue())
            self.assertEqual(json.load(open(os.path.join(tower, "paper_account.json")))["open"], [])

    def test_bad_data_is_a_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._root(tmp)
            buf = io.StringIO()
            with mock.patch.dict(os.environ, CLEAN_ENV), redirect_stdout(buf):
                B.run_once(tmp, fetch=lambda: {"error": "URLError"}, now=T0)
            self.assertIn("SKIP data", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
