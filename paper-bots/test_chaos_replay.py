"""Chaos tests for the shared tower engine (plan steps 358-363).

A source returns garbage, a source times out, Kalshi returns 429 for a
minute, the disk is full, the clock jumps, and two passes overlap. In every
case the tower must fail closed (no invented buy) and the paper book must
still add up. Run them on their own with ``make replay-chaos``.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import errno
import importlib.util
import io
import json
import os
import tempfile
import threading
import unittest
import urllib.error
from unittest import mock

import kalshi_shadow_tower as engine

ROOT = os.path.dirname(os.path.abspath(__file__))
SPEC = {"id": "chaos", "name": "Chaos", "floor": 0.05, "max_open": 4, "max_edge": 0.20,
        "tape_check": True, "fee_per_order": True}
T0 = dt.datetime(2026, 11, 12, 15, 0, tzinfo=dt.timezone.utc)
GOOD = {"ticker": "KXSOL15M-A", "event": "KXSOL15M-A", "side": "yes", "fair": 0.62, "ask": 0.50,
        "bid": 0.48, "label": "SOL up", "why": "chaos"}


def _tape_ok(_ticker, _now):
    return [{"yes_price_dollars": 0.50, "count": 1000}]


def _run(tower, *, now=T0, quotes=None, model=None, fetch=None, tape=_tape_ok):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = engine.run_tower(SPEC, tower, model, now=now, quotes=quotes, fetch=fetch or (lambda t: {}), tape=tape)
    return rc, buf.getvalue(), engine.read_json(os.path.join(tower, "paper_account.json"))


def _balanced(test, state, start=500.0):
    risk = sum(float(p["cost"]) for p in state["open"])
    pnl = sum(float(r["pnl"]) for r in state["closed"])
    test.assertAlmostEqual(state["cash"] + risk, start + pnl, places=6)


def _http(code):
    return urllib.error.HTTPError("https://api.elections.kalshi.com", code, "Too Many Requests", {}, None)


class Garbage(unittest.TestCase):
    def test_garbage_quotes_never_buy(self):
        junk = [
            {"ticker": "G1", "fair": "abc", "ask": 0.5},
            {"ticker": "G2", "fair": float("nan"), "ask": 0.5},
            {"ticker": "G3", "fair": 0.9, "ask": float("inf")},
            {"ticker": "G4", "fair": 1.7, "ask": 0.5},
            {"ticker": "G5", "fair": -0.2, "ask": 0.1},
            {"ticker": "G6", "fair": 0.9, "ask": 5},
            {"ticker": "G7", "fair": 0.9, "ask": -0.3},
            {"ticker": "G8"},
            {},
        ]
        with tempfile.TemporaryDirectory() as tower:
            rc, out, state = _run(tower, quotes=junk)
        self.assertEqual(rc, 0)
        self.assertEqual(state["open"], [])
        self.assertEqual(state["cash"], 500.0)
        self.assertIn("no trade", out)

    def test_garbage_market_rows_skip_that_series(self):
        spec = importlib.util.spec_from_file_location("more_chaos", os.path.join(ROOT, "more-15m-paper", "bot.py"))
        more = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(more)
        with mock.patch.object(more, "hl_oracles", return_value={"xyz:SP500": "oops"}), \
                mock.patch.object(more.engine, "kalshi_open_markets", return_value=["not a market", 7]), \
                mock.patch.object(more, "coin_spot", return_value=100.0), \
                mock.patch.object(more, "sigma_per_min", return_value=0.001), \
                mock.patch.object(more.time, "sleep"):
            quotes, note = more.model({}, T0)
        self.assertEqual(quotes, [])
        self.assertIn("skipped", note)

    def test_garbage_tape_rows_count_nothing(self):
        rows = [{"yes_price_dollars": "x"}, {"count": 9}, {"yes_price": None, "count": 5}, "junk"[:0] or {}]
        self.assertEqual(engine.tape_volume(rows, "yes", 0.5), 0.0)
        with tempfile.TemporaryDirectory() as tower:
            _rc, out, state = _run(tower, quotes=[GOOD], tape=lambda t, n: rows)
        self.assertEqual(state["open"], [])
        self.assertIn("Kalshi tape", out)

    def test_garbage_settle_result_keeps_position(self):
        with tempfile.TemporaryDirectory() as tower:
            _run(tower, quotes=[GOOD])
            _rc, _out, state = _run(tower, now=T0 + dt.timedelta(minutes=1), quotes=[],
                                    fetch=lambda t: {"result": "maybe"})
        self.assertEqual(len(state["open"]), 1)
        _balanced(self, state)


class Timeouts(unittest.TestCase):
    def test_model_timeout_is_a_skip(self):
        def slow(_cfg, _now):
            raise TimeoutError("read timed out")
        with tempfile.TemporaryDirectory() as tower:
            rc, out, state = _run(tower, model=slow)
        self.assertEqual(rc, 0)
        self.assertIn("read failed (TimeoutError)", out)
        self.assertEqual(state["open"], [])

    def test_tape_timeout_means_no_buy(self):
        def tape(_t, _n):
            raise TimeoutError
        with tempfile.TemporaryDirectory() as tower:
            _rc, out, state = _run(tower, quotes=[GOOD], tape=tape)
        self.assertEqual(state["open"], [])
        self.assertIn("tape read failed (TimeoutError); no buy", out)

    def test_settle_timeout_keeps_position(self):
        def fetch(_t):
            raise TimeoutError
        with tempfile.TemporaryDirectory() as tower:
            _run(tower, quotes=[GOOD])
            _rc, _out, state = _run(tower, now=T0 + dt.timedelta(minutes=20), quotes=[], fetch=fetch)
        self.assertEqual(len(state["open"]), 1)


class RateLimit(unittest.TestCase):
    def test_kalshi_429_for_a_minute(self):
        """Every Kalshi read fails with 429 for 60 seconds, then recovers."""
        def limited(now):
            return T0 + dt.timedelta(minutes=1) <= now < T0 + dt.timedelta(minutes=2)

        with tempfile.TemporaryDirectory() as tower:
            _run(tower, quotes=[GOOD])  # one position before the storm
            for sec in range(60, 120, 10):
                now = T0 + dt.timedelta(seconds=sec)

                def model(_cfg, _now):
                    raise _http(429)

                def fetch(_t, _now=now):
                    if limited(_now):
                        raise _http(429)
                    return {"result": "yes"}

                def tape(_t, _n):
                    raise _http(429)

                _rc, out, state = _run(tower, now=now, model=model, fetch=fetch, tape=tape)
                self.assertEqual(len(state["open"]), 1)  # kept, not guessed
                self.assertIn("read failed (HTTPError)", out)
            # recovered: the result is read and the book settles
            _rc, _out, state = _run(tower, now=T0 + dt.timedelta(minutes=3), quotes=[],
                                    fetch=lambda t: {"result": "yes"})
            self.assertEqual(state["open"], [])
            self.assertEqual(state["closed"][0]["exit"], "settled")
            _balanced(self, state)


class DiskFull(unittest.TestCase):
    def test_disk_full_never_books_a_phantom_trade(self):
        with tempfile.TemporaryDirectory() as tower:
            _run(tower, quotes=[])
            acct = os.path.join(tower, "paper_account.json")
            with open(acct, encoding="utf-8") as fh:
                before = fh.read()

            def full(*_a, **_k):
                raise OSError(errno.ENOSPC, "No space left on device")

            with mock.patch.object(engine, "write_json", side_effect=full):
                with self.assertRaises(OSError):
                    _run(tower, now=T0 + dt.timedelta(minutes=1), quotes=[GOOD])
            with open(acct, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), before)  # the old book is whole
            self.assertFalse([f for f in os.listdir(tower) if f.endswith(".tmp")])
            # space back: the next pass works normally
            _rc, _out, state = _run(tower, now=T0 + dt.timedelta(minutes=2), quotes=[GOOD])
            self.assertEqual(len(state["open"]), 1)

    def test_research_log_full_is_not_fatal(self):
        real_open = open

        def picky(path, *a, **k):
            if str(path).endswith("research.jsonl"):
                raise OSError(errno.ENOSPC, "No space left on device")
            return real_open(path, *a, **k)

        with tempfile.TemporaryDirectory() as tower:
            with mock.patch("builtins.open", side_effect=picky):
                rc, _out, _state = _run(tower, quotes=[GOOD])
            state = engine.read_json(os.path.join(tower, "paper_account.json"))
        self.assertEqual(rc, 0)
        self.assertEqual(len(state["open"]), 1)

    def test_atomic_write_keeps_old_file_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.json")
            engine.write_json(path, {"cash": 1})
            with mock.patch("json.dump", side_effect=OSError(errno.ENOSPC, "full")):
                with self.assertRaises(OSError):
                    engine.write_json(path, {"cash": 2})
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh), {"cash": 1})


class ClockJumps(unittest.TestCase):
    def test_clock_back_and_forward(self):
        with tempfile.TemporaryDirectory() as tower:
            _run(tower, quotes=[GOOD])
            # clock jumps back an hour: still holding, no second buy of the same market
            _rc, _out, state = _run(tower, now=T0 - dt.timedelta(hours=1), quotes=[GOOD])
            self.assertEqual(len(state["open"]), 1)
            # clock jumps forward a day: the result settles once
            _rc, _out, state = _run(tower, now=T0 + dt.timedelta(days=1), quotes=[],
                                    fetch=lambda t: {"result": "no"})
            self.assertEqual(state["open"], [])
            self.assertEqual(len(state["closed"]), 1)
            self.assertLess(state["closed"][0]["pnl"], 0)  # the loss counts
            _rc, _out, state = _run(tower, now=T0 + dt.timedelta(days=1, minutes=1), quotes=[],
                                    fetch=lambda t: {"result": "no"})
            self.assertEqual(len(state["closed"]), 1)
            self.assertEqual(state["checks"], 4)
            _balanced(self, state)


class Overlap(unittest.TestCase):
    def test_back_to_back_passes_do_not_double_buy(self):
        with tempfile.TemporaryDirectory() as tower:
            _run(tower, quotes=[GOOD])
            _rc, out, state = _run(tower, quotes=[GOOD])
        self.assertEqual(len(state["open"]), 1)
        self.assertIn("already holding this market", out)

    def test_overlapping_passes_keep_the_book_whole(self):
        """Pass A reads the book, then pass B runs start to finish, then A finishes.

        The engine has no file lock, so the later save wins. That can drop one
        pass's buy, but cash and positions move together, so the book still adds
        up and nothing is double counted.
        """
        with tempfile.TemporaryDirectory() as tower:
            _run(tower, quotes=[])
            b_done = threading.Event()
            other = dict(GOOD, ticker="KXXRP15M-B", event="KXXRP15M-B", label="XRP up")

            def slow_model(_cfg, _now):
                b_done.wait(5)
                return [GOOD], ""

            errors = []

            def pass_a():
                try:
                    _run(tower, now=T0 + dt.timedelta(minutes=1), model=slow_model)
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            t = threading.Thread(target=pass_a)
            t.start()
            try:
                _run(tower, now=T0 + dt.timedelta(minutes=1), quotes=[other])
            finally:
                b_done.set()
                t.join(10)
            self.assertFalse(errors)
            state = engine.read_json(os.path.join(tower, "paper_account.json"))
        self.assertLessEqual(len(state["open"]), 2)
        self.assertEqual(len({p["ticker"] for p in state["open"]}), len(state["open"]))
        _balanced(self, state)


if __name__ == "__main__":
    unittest.main()
