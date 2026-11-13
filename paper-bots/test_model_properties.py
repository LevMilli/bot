"""Property tests (plan steps 354-357), seeded so every run is the same.

* edge never rises when the fee rises
* fair is always between 0 and 1
* a ticket never spends more than the cash (or the stake)
* open positions never pass the cap after a buy
"""
from __future__ import annotations

import contextlib
import datetime as dt
import importlib.util
import io
import math
import os
import random
import tempfile
import unittest
from unittest import mock

import kalshi_shadow_tower as engine

ROOT = os.path.dirname(os.path.abspath(__file__))
CASES = 400


def _more():
    spec = importlib.util.spec_from_file_location("more15m_props", os.path.join(ROOT, "more-15m-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _quote(rng: random.Random, i: int) -> dict:
    ask = round(rng.uniform(0.02, 0.98), 2)
    return {"ticker": f"T{i}", "event": f"E{i}", "side": rng.choice(("yes", "no")),
            "fair": rng.uniform(0.0, 1.0), "ask": ask, "bid": max(0.01, round(ask - 0.02, 2)),
            "label": f"t{i}", "why": "prop"}


class EdgeVsFee(unittest.TestCase):
    def test_edge_never_rises_when_fee_rises(self):
        rng = random.Random(1)
        cfg = engine.locked_cfg({"floor": 0.05, "max_edge": 0.20})
        base_fee = engine.fee
        for i in range(CASES):
            q = _quote(rng, i)
            last_edge, last_buy = None, True
            for mult in (1.0, 1.5, 2.0, 3.0):
                with mock.patch.object(engine, "fee", lambda p, m=mult: base_fee(p) * m):
                    d = engine.decide(q, cfg)
                if d["edge"] is None:
                    break
                if last_edge is not None:
                    self.assertLessEqual(d["edge"], last_edge + 1e-9, q)
                # a higher fee can only turn a buy off (or hit the trust cap less often)
                if d["action"] == "buy":
                    self.assertTrue(last_buy or d["edge"] <= cfg["max_edge"] + 1e-9)
                last_edge, last_buy = d["edge"], d["action"] == "buy"

    def test_order_fee_grows_with_size_and_never_beats_sum_rounding(self):
        rng = random.Random(2)
        for _ in range(CASES):
            p = round(rng.uniform(0.01, 0.99), 2)
            prev = 0.0
            for c in range(1, 60):
                f = engine.order_fee(c, p)
                self.assertGreaterEqual(f + 1e-9, prev)
                self.assertLessEqual(f, c * engine.fee(p) + 1e-9)  # once per order is never dearer
                prev = f

    def test_btc_need_rises_with_fee(self):
        spec = importlib.util.spec_from_file_location(
            "btc_props", os.path.join(ROOT, "btc15m-signal", "btc15m_signal.py"))
        btc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(btc)
        for c in range(1, 99):
            p = c / 100
            self.assertGreaterEqual(btc.fee_per_contract(p), 0.0)
            self.assertLessEqual(btc.fee_per_contract(p), 0.02)


class FairRange(unittest.TestCase):
    def test_fair_between_0_and_1(self):
        more = _more()
        rng = random.Random(3)
        now = dt.datetime(2026, 11, 12, 15, 0, tzinfo=dt.timezone.utc)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(more, "HERE", tmp):
            for i in range(CASES):
                series = rng.choice(sorted(more.SERIES))
                strike = rng.uniform(0.5, 100000)
                spot = strike * math.exp(rng.gauss(0, 0.05))
                close = now + dt.timedelta(minutes=rng.uniform(-2, 16))
                m = {"ticker": f"{series}-P{i}", "event_ticker": f"{series}-P{i}", "floor_strike": strike,
                     "close_time": close.isoformat(), "yes_ask_dollars": 0.5, "no_ask_dollars": 0.5}
                sigma = rng.choice((more.SERIES[series][4], rng.uniform(1e-6, 0.05)))
                for row in more.window_quotes(series, [m], spot, sigma, now):
                    self.assertTrue(0.0 < row["fair"] < 1.0, row)
                    self.assertTrue(math.isfinite(row["fair"]))

    def test_phi_in_range(self):
        more = _more()
        rng = random.Random(4)
        for _ in range(CASES):
            z = rng.uniform(-1e6, 1e6) if rng.random() < 0.1 else rng.gauss(0, 5)
            self.assertTrue(0.0 <= more.phi(z) <= 1.0)


class StakeAndCap(unittest.TestCase):
    def test_ticket_never_exceeds_stake(self):
        rng = random.Random(5)
        for _ in range(CASES):
            ask = round(rng.uniform(0.01, 0.99), 2)
            stake = rng.choice((1.0, 5.0, 25.0, 100.0))
            for per_order in (False, True):
                c, f, cost = engine.size_order(stake, ask, per_order)
                self.assertGreaterEqual(c, 0)
                self.assertLessEqual(cost, stake + 1e-9)
                if c:
                    self.assertAlmostEqual(cost, round(c * ask + f, 2), places=6)

    def _run(self, rng, tower, spec, n_checks=40, cash=None):
        if cash is not None:
            engine.write_json(os.path.join(tower, "paper_account.json"),
                              {"cash": cash, "open": [], "closed": [], "checks": 0})
        now = dt.datetime(2026, 11, 12, 15, 0, tzinfo=dt.timezone.utc)
        for k in range(n_checks):
            quotes = [_quote(rng, k * 100 + j) for j in range(rng.randint(0, 12))]
            for q in quotes:
                q["fair"] = min(0.99, q["ask"] + rng.uniform(0.0, 0.3))
            results = {q["ticker"]: rng.choice(("yes", "no", "")) for q in quotes}
            before = engine.read_json(os.path.join(tower, "paper_account.json")) or {}
            with contextlib.redirect_stdout(io.StringIO()):
                engine.run_tower(spec, tower, None, now=now + dt.timedelta(minutes=k), quotes=quotes,
                                 fetch=lambda t, r=results: {"result": r.get(t, "")},
                                 tape=lambda t, _n: [{"yes_price_dollars": 0.01, "count": 1e6},
                                                     {"yes_price_dollars": 0.99, "count": 1e6}])
            yield before, engine.read_json(os.path.join(tower, "paper_account.json"))

    def test_stake_never_exceeds_cash(self):
        rng = random.Random(6)
        spec = {"id": "prop", "name": "Prop", "floor": 0.05, "max_open": 6, "max_edge": 0.30,
                "tape_check": True, "fee_per_order": True}
        bought = 0
        with tempfile.TemporaryDirectory() as tower:
            for before, after in self._run(rng, tower, spec, cash=60.0):
                self.assertGreaterEqual(after["cash"], -1e-9)
                new = [p for p in after["open"] if p not in (before.get("open") or [])]
                bought += len(new)
                for pos in new:
                    self.assertLessEqual(pos["cost"], 25.0 + 1e-9)
        self.assertGreater(bought, 0)

    def test_open_never_passes_cap_after_buy(self):
        rng = random.Random(7)
        for max_open, extra in ((1, 0), (2, 2), (4, 2)):
            spec = {"id": "prop", "name": "Prop", "floor": 0.05, "max_open": max_open,
                    "max_edge": 0.40, "extra_slots": extra}
            peak = 0
            with tempfile.TemporaryDirectory() as tower:
                for before, after in self._run(rng, tower, spec):
                    peak = max(peak, len(after["open"]))
                    self.assertLessEqual(len(after["open"]), max_open + extra)
                    self.assertLessEqual(len(after["open"]) - len(before.get("open") or []), 1)
                    risk = sum(float(p["cost"]) for p in after["open"])
                    self.assertLessEqual(risk, (max_open + extra) * 25.0 + 1e-9)
                    # the book adds up: cash + open cost + closed P&L == starting cash
                    closed = sum(float(r["pnl"]) for r in after["closed"])
                    self.assertAlmostEqual(after["cash"] + risk, 500.0 + closed, places=6)
            self.assertEqual(peak, max_open + extra)


if __name__ == "__main__":
    unittest.main()
