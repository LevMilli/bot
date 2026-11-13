"""Model unit tests and edge cases: plan steps 343-353.

Fair price math, zero time / zero volatility / missing price, the normal
helper at extreme values, sigma floors, basis learning, the trust cap at
exactly 0.20, the 70/92 cent ask band, spread and depth at exactly the limit,
the 30-minute news window and candles moving toward the target.
Read only: nothing here changes a tower rule.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import math
import os
import tempfile
import unittest
from unittest import mock

import desk_profit
import kalshi_shadow_tower as engine

ROOT = os.path.dirname(os.path.abspath(__file__))
NOW = dt.datetime(2026, 11, 12, 15, 5, tzinfo=dt.timezone.utc)


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _more():
    return _load(os.path.join("more-15m-paper", "bot.py"), "more15m_edges")


def _btc():
    return _load(os.path.join("btc15m-signal", "btc15m_signal.py"), "btc15m_edges")


def _market(close: dt.datetime, strike: float, ticker: str = "KXSOL15M-26NOV121515-15", yes_ask=0.50,
            yes_bid=0.48, no_ask=0.52, no_bid=0.50):
    return {"ticker": ticker, "event_ticker": ticker.rsplit("-", 1)[0], "floor_strike": strike,
            "close_time": close.isoformat().replace("+00:00", "Z"), "yes_ask_dollars": yes_ask,
            "yes_bid_dollars": yes_bid, "no_ask_dollars": no_ask, "no_bid_dollars": no_bid}


class FairMath(unittest.TestCase):
    """Step 343."""

    def test_more15m_fair_formula_coin(self):
        more = _more()
        close = NOW + dt.timedelta(minutes=8)
        rows = more.window_quotes("KXSOL15M", [_market(close, 100.0)], 100.2, 0.001, NOW)
        yes = next(r for r in rows if r["side"] == "yes")
        no = next(r for r in rows if r["side"] == "no")
        t_eff = 8.0 - 0.67  # the coin settles on a 60-second average
        want = more.phi(math.log(100.2 / 100.0) / (0.001 * math.sqrt(t_eff)))
        self.assertAlmostEqual(yes["fair"], want, places=9)
        self.assertAlmostEqual(yes["fair"] + no["fair"], 1.0, places=9)
        self.assertNotIn("log_only", yes)

    def test_more15m_fair_formula_oracle_no_average_cut(self):
        more = _more()
        close = NOW + dt.timedelta(minutes=8)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(more, "HERE", tmp):
            engine.write_json(os.path.join(tmp, more.BASIS_FILE), {"KXINX15M": {"frac": 0.0, "n": 3, "last": "x"}})
            rows = more.window_quotes("KXINX15M", [_market(close, 6000.0, "KXINX15M-26NOV121515-15")],
                                      6003.0, 0.0002, NOW)
        yes = next(r for r in rows if r["side"] == "yes")
        self.assertAlmostEqual(yes["fair"], more.phi(math.log(6003 / 6000) / (0.0002 * math.sqrt(8.0))), places=9)

    def test_btc_fair_is_phi_of_cushion_over_sigma(self):
        btc = _btc()
        ev = _btc_eval(btc, price=100050.0, sigma=50.0)
        self.assertAlmostEqual(ev["p"], btc.phi(1.0), places=12)
        self.assertEqual(ev["side"], "YES")
        self.assertAlmostEqual(ev["edge"], ev["p"] - ev["ask"] - ev["fee"], places=12)

    def test_engine_fee_and_edge(self):
        self.assertEqual(engine.fee(0.50), 0.02)
        self.assertEqual(engine.fee(0.05), 0.01)
        self.assertEqual(engine.order_fee(50, 0.50), 0.88)
        cfg = engine.locked_cfg({"floor": 0.05, "max_edge": 0.20})
        d = engine.decide({"fair": 0.60, "ask": 0.50, "ticker": "T", "side": "yes"}, cfg)
        self.assertAlmostEqual(d["edge"], 0.08)
        self.assertEqual(d["action"], "buy")


def _btc_eval(btc, *, price=100050.0, sigma=50.0, ask=0.80, bid=0.78, depth=10.0, minutes=12.0,
              closes=None, news=(), side_ask=None):
    close = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)
    m = {"ticker": "KXBTC15M-EDGE", "series": "KXBTC15M", "target": 100000.0,
         "open_time": close - dt.timedelta(minutes=15), "close_time": close,
         "yes_ask": ask, "no_ask": round(1 - bid, 2), "yes_bid": bid,
         "no_bid": None if ask is None else round(1 - ask, 2)}
    closes = list(closes) if closes is not None else [price] * 8
    with mock.patch.object(btc, "_sigma_for", return_value=(sigma, sigma, None)), \
            mock.patch.object(btc, "usd_high_impact_near", return_value=None if news is None else list(news)), \
            mock.patch("desk_roi_plan.effective_near_miss_relax", return_value={}):
        return btc.evaluate_window(m, price, closes, None, False, 0.05, book=(bid, ask, depth))


class EdgeCases(unittest.TestCase):
    """Step 344."""

    def test_zero_time_left_is_never_priced(self):
        more = _more()
        rows = more.window_quotes("KXSOL15M", [_market(NOW, 100.0)], 101.0, 0.001, NOW)
        self.assertEqual(rows, [])
        btc = _btc()
        ev = _btc_eval(btc, minutes=0.0)
        self.assertIn("under 1 minute", ev["reasons"])

    def test_zero_volatility_uses_the_floor(self):
        more = _more()
        flat = [{"c": "100.0"}] * 70
        with mock.patch.object(more, "hl_post", return_value=flat):
            for series, row in more.SERIES.items():
                self.assertEqual(more.sigma_per_min(row[3], row[4], NOW), row[4], series)

    def test_missing_price_skips_never_guesses(self):
        more = _more()
        with mock.patch.object(more, "hl_oracles", side_effect=TimeoutError("slow")), \
                mock.patch.object(more.engine, "kalshi_open_markets",
                                  return_value=[_market(NOW + dt.timedelta(minutes=8), 100.0)]), \
                mock.patch.object(more, "coin_spot", side_effect=ValueError("no spot")), \
                mock.patch.object(more.time, "sleep"):
            quotes, note = more.model({}, NOW)
        self.assertEqual(quotes, [])
        self.assertIn("skipped", note)
        cfg = engine.locked_cfg({"floor": 0.05})
        self.assertEqual(engine.decide({"fair": None, "ask": 0.4}, cfg)["reason"], "need fair + ask")
        self.assertEqual(engine.decide({"fair": 0.6, "ask": None}, cfg)["action"], "skip")
        btc = _btc()
        close = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=12)
        m = {"ticker": "X", "series": "KXBTC15M", "target": 100000.0, "open_time": None, "close_time": close,
             "yes_ask": 0.8, "no_ask": 0.2, "yes_bid": 0.78, "no_bid": 0.2}
        with mock.patch.object(btc, "_sigma_for", return_value=(None, None, None)):
            ev = btc.evaluate_window(m, 100050.0, [], None, False, 0.05, book=(0.78, 0.8, 10))
        self.assertIn("could not compute sigma", ev["reasons"])
        self.assertIsNone(ev["p"])
        ev = _btc_eval(btc, ask=None)
        self.assertIn("missing bid/ask", ev["reasons"])

    def test_btc_sigma_none_without_any_inputs(self):
        btc = _btc()
        self.assertEqual(btc._sigma_for(100000.0, 10.0, [], None), (None, None, None))


class NormalHelper(unittest.TestCase):
    """Step 345."""

    def test_phi_extremes(self):
        for mod in (_more(), _btc()):
            self.assertEqual(mod.phi(0.0), 0.5)
            self.assertEqual(mod.phi(40.0), 1.0)
            self.assertEqual(mod.phi(-40.0), 0.0)
            self.assertEqual(mod.phi(float("inf")), 1.0)
            self.assertEqual(mod.phi(float("-inf")), 0.0)
            self.assertAlmostEqual(mod.phi(1.96), 0.9750021, places=6)
            self.assertAlmostEqual(mod.phi(-1.96) + mod.phi(1.96), 1.0, places=12)
            prev = -1.0
            for i in range(-80, 81):
                v = mod.phi(i / 10.0)
                self.assertGreaterEqual(v, prev)
                self.assertTrue(0.0 <= v <= 1.0)
                prev = v

    def test_more15m_clamps_fair(self):
        more = _more()
        close = NOW + dt.timedelta(minutes=8)
        rows = more.window_quotes("KXSOL15M", [_market(close, 100.0)], 150.0, 0.0004, NOW)
        yes = next(r for r in rows if r["side"] == "yes")
        self.assertEqual(yes["fair"], 0.99)
        rows = more.window_quotes("KXSOL15M", [_market(close, 100.0)], 50.0, 0.0004, NOW)
        self.assertEqual(next(r for r in rows if r["side"] == "yes")["fair"], 0.01)


class SigmaFloors(unittest.TestCase):
    """Step 346."""

    def test_floor_per_asset(self):
        more = _more()
        want = {"KXSOL15M": 0.0004, "KXXRP15M": 0.0004, "KXDOGE15M": 0.0005, "KXBNB15M": 0.0003,
                "KXHYPE15M": 0.0006, "KXINX15M": 0.00008, "KXEURUSD15M": 0.00004, "KXUSDJPY15M": 0.00004}
        self.assertEqual({k: v[4] for k, v in more.SERIES.items()}, want)

    def test_real_moves_above_floor_pass_through(self):
        more = _more()
        closes = [{"c": str(100 * (1.01 if i % 2 else 1.0))} for i in range(70)]
        with mock.patch.object(more, "hl_post", return_value=closes):
            got = more.sigma_per_min("SOL", 0.0004, NOW)
        self.assertGreater(got, 0.004)
        with mock.patch.object(more, "hl_post", return_value=closes):
            self.assertAlmostEqual(more.sigma_per_min("JPY", 0.00004, NOW, 1.3), 1.3 * got, places=12)

    def test_short_history_raises(self):
        more = _more()
        with mock.patch.object(more, "hl_post", return_value=[{"c": "1"}] * 10):
            with self.assertRaises(ValueError):
                more.sigma_per_min("SOL", 0.0004, NOW)


class BasisLearning(unittest.TestCase):
    """Step 347: three window opens before buying an oracle market."""

    def test_three_opens_before_ready(self):
        more = _more()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(more, "HERE", tmp):
            readies = []
            for i in range(4):
                open_at = NOW + dt.timedelta(minutes=15 * i)
                close = open_at + dt.timedelta(minutes=15)
                now = open_at + dt.timedelta(seconds=30)
                m = _market(close, 6010.0, f"KXINX15M-W{i}-15")
                _level, ready = more.anchor("KXINX15M", 6000.0, m, close, now)
                readies.append(ready)
                # a second check in the same window does not count again
                more.anchor("KXINX15M", 6000.0, m, close, now + dt.timedelta(seconds=20))
            self.assertEqual(readies, [False, False, True, True])
            state = engine.read_json(os.path.join(tmp, more.BASIS_FILE))
            self.assertEqual(state["KXINX15M"]["n"], 4)
            self.assertAlmostEqual(state["KXINX15M"]["frac"], 10 / 6000, places=6)

    def test_late_in_window_does_not_learn(self):
        more = _more()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(more, "HERE", tmp):
            close = NOW + dt.timedelta(minutes=10)  # 5 minutes old
            _lvl, ready = more.anchor("KXINX15M", 6000.0, _market(close, 6010.0), close, NOW)
            self.assertFalse(ready)
            self.assertIsNone(engine.read_json(os.path.join(tmp, more.BASIS_FILE)))

    def test_unready_rows_are_log_only(self):
        more = _more()
        close = NOW + dt.timedelta(minutes=8)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(more, "HERE", tmp):
            rows = more.window_quotes("KXEURUSD15M", [_market(close, 1.1, "KXEURUSD15M-X-15")], 1.1, 0.0001, NOW)
        self.assertTrue(all(r.get("log_only") for r in rows))
        self.assertIn("open offset", rows[0]["log_reason"])

    def test_coins_need_no_basis(self):
        more = _more()
        self.assertEqual(more.anchor("KXSOL15M", 100.0, {}, NOW, NOW), (100.0, True))


class Limits(unittest.TestCase):
    """Steps 348-353: rules at exactly their limits."""

    def test_trust_cap_exactly_020(self):
        cfg = engine.locked_cfg({"floor": 0.05, "max_edge": 0.20})
        at_cap = engine.decide({"fair": 0.72, "ask": 0.50, "ticker": "T", "side": "yes"}, cfg)
        self.assertAlmostEqual(at_cap["edge"], 0.20)
        self.assertEqual(at_cap["action"], "buy")
        over = engine.decide({"fair": 0.721, "ask": 0.50, "ticker": "T", "side": "yes"}, cfg)
        self.assertEqual(over["action"], "skip")
        self.assertIn("trust cap", over["reason"])
        self.assertEqual(_more().SPEC["max_edge"], 0.20)

    def test_floor_exactly(self):
        cfg = engine.locked_cfg({"floor": 0.05}, {"venue_min_edge": 0.01})
        self.assertEqual(cfg["venue_min_edge"], 0.05)  # config can never lower the floor
        d = engine.decide({"fair": 0.57, "ask": 0.50, "ticker": "T", "side": "yes"}, cfg)
        self.assertAlmostEqual(d["edge"], 0.05)
        self.assertEqual(d["action"], "buy")
        self.assertEqual(engine.decide({"fair": 0.569, "ask": 0.50}, cfg)["action"], "skip")

    def test_ask_band_edges_70_and_92(self):
        btc = _btc()
        self.assertEqual((btc.ASK_MIN, btc.ASK_MAX), (0.70, 0.92))
        for ask, inside in ((0.70, True), (0.92, True), (0.69, False), (0.93, False)):
            ev = _btc_eval(btc, ask=ask, bid=round(ask - 0.02, 2), price=100200.0, sigma=50.0)
            hit = [r for r in ev["reasons"] if "outside" in r]
            self.assertEqual(not hit, inside, (ask, ev["reasons"]))
            self.assertEqual(btc.scan_drop_reasons(5.0, ask, 100.0) == [], inside)

    def test_spread_exactly_at_limit(self):
        btc = _btc()
        ok = _btc_eval(btc, ask=0.84, bid=0.80, price=100200.0)
        self.assertFalse([r for r in ok["reasons"] if r.startswith("spread")], ok["reasons"])
        wide = _btc_eval(btc, ask=0.85, bid=0.80, price=100200.0)
        self.assertTrue([r for r in wide["reasons"] if r.startswith("spread")])

    def test_depth_exactly_at_limit(self):
        btc = _btc()
        self.assertEqual(btc.MIN_DEPTH, 3)
        ok = _btc_eval(btc, depth=3.0, price=100200.0)
        self.assertFalse([r for r in ok["reasons"] if "contracts at/below ask" in r])
        thin = _btc_eval(btc, depth=2.0, price=100200.0)
        self.assertTrue([r for r in thin["reasons"] if "contracts at/below ask" in r])

    def test_news_window_exactly_30_minutes(self):
        btc = _btc()
        self.assertEqual(btc.NEWS_WINDOW_MIN, 30)
        start = dt.datetime(2026, 11, 12, 15, 0, tzinfo=dt.timezone.utc)
        end = start + dt.timedelta(minutes=15)

        def cal(minutes_after_end):
            t = end + dt.timedelta(minutes=minutes_after_end)
            return [{"country": "USD", "impact": "High", "title": "CPI", "date": t.isoformat()}]

        import helpers.calendar_cache as cc
        with mock.patch.object(cc, "load_ff_calendar", return_value=cal(30)):
            self.assertEqual(len(btc.usd_high_impact_near(start, end)), 1)
        with mock.patch.object(cc, "load_ff_calendar", return_value=cal(30.02)):
            self.assertEqual(btc.usd_high_impact_near(start, end), [])
        before = [{"country": "USD", "impact": "High", "title": "NFP",
                   "date": (start - dt.timedelta(minutes=30)).isoformat()}]
        with mock.patch.object(cc, "load_ff_calendar", return_value=before):
            self.assertEqual(len(btc.usd_high_impact_near(start, end)), 1)
        low = [{"country": "USD", "impact": "Low", "title": "x", "date": end.isoformat()}]
        with mock.patch.object(cc, "load_ff_calendar", return_value=low):
            self.assertEqual(btc.usd_high_impact_near(start, end), [])
        # calendar never loaded -> fail closed
        ev = _btc_eval(btc, news=None, price=100200.0)
        self.assertIn("USD news calendar unavailable (fail-closed)", ev["reasons"])
        ev = _btc_eval(btc, news=["CPI at 15:30 UTC"], price=100200.0)
        self.assertIn("USD high-impact news near this block", ev["reasons"])

    def test_candles_toward_target(self):
        btc = _btc()
        toward = [100300.0 - 20 * i for i in range(8)]  # YES side, price falling toward the target
        weak = _btc_eval(btc, price=toward[-1], sigma=80.0, closes=toward, ask=0.92, bid=0.90)
        self.assertTrue(weak["toward"])
        self.assertIn("last 5 candles moving toward target", weak["reasons"])
        strong = _btc_eval(btc, price=100400.0, sigma=50.0, closes=[100600.0 - 25 * i for i in range(8)])
        self.assertTrue(strong["toward"])
        self.assertNotIn("last 5 candles moving toward target", strong["reasons"])
        away = _btc_eval(btc, price=100200.0, closes=[100000.0 + 25 * i for i in range(8)])
        self.assertFalse(away["toward"])

    def test_locked_floors_unchanged(self):
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"], 0.05)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_commodity15m"], 0.05)


if __name__ == "__main__":
    unittest.main()
