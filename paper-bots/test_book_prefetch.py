"""Parallel book prefetch + empty-market CARD <3s bar."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_more
import desk_roi_plan


def _load_commodity():
    path = os.path.join(HERE, "commodity-15m-paper", "bot.py")
    spec = importlib.util.spec_from_file_location("commodity_15m_bot", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class BookPrefetch(unittest.TestCase):
    def test_prefetch_map_parallel(self):
        seen = []

        def worker(job):
            seen.append(job)
            time.sleep(0.05)
            return job * 2

        t0 = time.perf_counter()
        ok, err = desk_more.prefetch_map([1, 2, 3, 4], worker, max_workers=4)
        elapsed = time.perf_counter() - t0
        self.assertEqual(err, {})
        self.assertEqual(ok, {1: 2, 2: 4, 3: 6, 4: 8})
        # Parallel should beat serial 4*0.05 ≈ 0.20s.
        self.assertLess(elapsed, 0.18)

    def test_prefetch_map_captures_errors(self):
        def worker(job):
            if job == "bad":
                raise RuntimeError("boom")
            return "ok"

        ok, err = desk_more.prefetch_map(["good", "bad"], worker)
        self.assertEqual(ok, {"good": "ok"})
        self.assertIn("bad", err)

    def test_depth_from_book(self):
        cbot = _load_commodity()
        raw = {
            "orderbook": {
                "yes": [[0.48, 5], [0.47, 10]],
                "no": [[0.50, 3]],
            }
        }
        spread, depth = cbot.depth_from_book(raw, "YES", 0.50)
        self.assertIsNotNone(spread)
        self.assertGreaterEqual(depth, 5)
        self.assertEqual(cbot.depth_from_book(None, "YES", 0.5), (None, 0))

    def test_empty_card_status_bar(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_empty_card(tmp, bot="commodity-15m", seconds=1.2)
            desk_roi_plan.record_empty_card(tmp, bot="btc15m", seconds=2.5)
            st = desk_roi_plan.empty_card_status(tmp)
            self.assertEqual(st["n"], 2)
            self.assertTrue(st["pass"])
            self.assertLessEqual(st["p50_s"], 3.0)
            desk_roi_plan.record_empty_card(tmp, bot="commodity-15m", seconds=9.0)
            desk_roi_plan.record_empty_card(tmp, bot="commodity-15m", seconds=9.5)
            desk_roi_plan.record_empty_card(tmp, bot="commodity-15m", seconds=10.0)
            slow = desk_roi_plan.empty_card_status(tmp, bot="commodity-15m")
            self.assertFalse(slow["pass"])

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_empty_card(tmp, bot="btc15m", seconds=0.8)
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("empty_card", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])


if __name__ == "__main__":
    unittest.main()
