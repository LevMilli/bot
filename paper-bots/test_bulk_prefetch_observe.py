"""Sports pre-tip warm + empty CARD series densify + depth-adjusted edge board."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_more
import desk_roi_plan


class WarmTipBooks(unittest.TestCase):
    def test_warm_tip_books_t15_t5_mocked(self):
        calls: list[str] = []
        cached: dict[str, object] = {}

        def fetch(url: str):
            calls.append(url)
            return {"markets": [{"ticker": "KXNBAGAME-DEMO", "yes_ask": 0.55}]}

        def put(url: str, body):
            cached[url] = body

        with tempfile.TemporaryDirectory() as tmp:
            games = [
                {"league": "NBA", "series": "KXNBAGAME", "tip_in_min": 12},
                {"league": "NFL", "series": "KXNFLGAME", "tip_in_min": 4},
                {"league": "NHL", "series": "KXNHLGAME", "tip_in_min": 40},
            ]
            warm15 = desk_more.warm_tip_books(
                tmp, 15, games=games, fetch=fetch, put_cache=put,
            )
            self.assertTrue(warm15["fee_floors_locked"])
            self.assertFalse(warm15["orders_placed"])
            self.assertEqual(warm15["tip_band"], 15)
            self.assertEqual(warm15["games_n"], 2)
            self.assertEqual(warm15["warmed_n"], 2)
            self.assertEqual(len(cached), 2)
            self.assertTrue(all("series_ticker=" in u for u in cached))

            calls.clear()
            cached.clear()
            warm5 = desk_more.warm_tip_books(
                tmp, 5, games=games, fetch=fetch, put_cache=put,
            )
            self.assertEqual(warm5["tip_band"], 5)
            self.assertEqual(warm5["games_n"], 1)
            self.assertEqual(warm5["warmed_n"], 1)
            self.assertEqual(len(calls), 1)
            self.assertIn("KXNFLGAME", calls[0])

    def test_warm_writes_quote_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            sports = os.path.join(tmp, "sports-gap-paper")
            os.makedirs(sports)

            def fetch(url: str):
                return {"markets": []}

            out = desk_more.warm_tip_books(
                tmp,
                15,
                games=[{"league": "NBA", "series": "KXNBAGAME", "tip_in_min": 10}],
                fetch=fetch,
            )
            self.assertEqual(out["warmed_n"], 1)
            cache_path = desk_more.sports_quote_cache_path(tmp)
            self.assertTrue(os.path.isfile(cache_path))


class EmptyCardSeriesBoard(unittest.TestCase):
    def test_series_board_alerts_over_3s(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_empty_card(
                tmp, bot="btc15m", seconds=1.0, series="KXBTC15M",
            )
            desk_roi_plan.record_empty_card(
                tmp, bot="btc15m", seconds=1.2, series="KXETH15M",
            )
            desk_roi_plan.record_empty_card(
                tmp, bot="commodity-15m", seconds=4.5, series="KXGOLD15M",
            )
            desk_roi_plan.record_empty_card(
                tmp, bot="commodity-15m", seconds=5.0, series="KXGOLD15M",
            )
            board = desk_roi_plan.empty_card_series_board(tmp)
            self.assertTrue(board["observe_only"])
            self.assertTrue(board["fee_floors_locked"])
            self.assertFalse(board["ok"])
            self.assertIn("KXGOLD15M", board["alerts"])
            by_s = {r["series"]: r for r in board["series"]}
            self.assertEqual(len(board["series"]), 10)
            self.assertTrue(by_s["KXBTC15M"]["pass"])
            self.assertAlmostEqual(by_s["KXBTC15M"]["median_time_to_book_s"], 1.0)
            self.assertFalse(by_s["KXGOLD15M"]["pass"])
            self.assertGreater(by_s["KXGOLD15M"]["empty_rate"], 0)

    def test_empty_card_status_densify(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_empty_card(
                tmp, bot="btc15m", seconds=0.9, series="KXBTC15M",
            )
            ok = desk_roi_plan.empty_card_status(tmp)
            self.assertTrue(ok["pass"])
            desk_roi_plan.record_empty_card(
                tmp, bot="commodity-15m", seconds=8.0, series="KXWTI15M",
            )
            desk_roi_plan.record_empty_card(
                tmp, bot="commodity-15m", seconds=9.0, series="KXWTI15M",
            )
            slow = desk_roi_plan.empty_card_status(tmp)
            self.assertFalse(slow["pass"])
            self.assertIn("KXWTI15M", slow.get("series_alerts") or [])


class DepthAdjustedEdgeBoard(unittest.TestCase):
    def test_raw_vs_depth_rank(self):
        cands = [
            {"bot": "btc15m", "ticker": "A", "edge": 0.12, "depth": 2, "series": "KXBTC15M"},
            {"bot": "btc15m", "ticker": "B", "edge": 0.10, "depth": 20, "series": "KXBTC15M"},
            {"bot": "commodity-15m", "ticker": "C", "edge": 0.11, "depth": 10, "series": "KXGOLD15M"},
            {"bot": "memecoin", "ticker": "SKIP", "edge": 0.50, "depth": 100},
        ]
        board = desk_roi_plan.depth_adjusted_edge_board(
            None, candidates=cands, need=10,
        )
        self.assertTrue(board["observe_only"])
        self.assertTrue(board["fee_floors_locked"])
        self.assertEqual(board["n"], 3)  # meme excluded
        self.assertGreaterEqual(board["rank_changed_n"], 1)
        top_raw = [r["ticker"] for r in board["top_raw"]]
        top_adj = [r["ticker"] for r in board["top_depth_adjusted"]]
        self.assertEqual(top_raw[0], "A")  # highest raw edge
        # Thin depth on A haircuts it; B or C should lead depth-adjusted.
        self.assertIn(top_adj[0], ("B", "C"))
        self.assertNotEqual(top_raw, top_adj)

    def test_masters_wire(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_empty_card(
                tmp, bot="btc15m", seconds=0.7, series="KXBTC15M",
            )
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("empty_card", plan)
            self.assertIn("empty_card_series", plan)
            self.assertIn("depth_adjusted_edge", plan)
            self.assertTrue(plan.get("fee_floors_locked"))
            series = plan["empty_card_series"]
            self.assertEqual(len(series.get("series") or []), 10)
            plan2 = desk_roi_plan.plan_summary(tmp, bots=[])
            self.assertIn("empty_card_series", plan2)
            self.assertIn("depth_adjusted_edge", plan2)

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])
        self.assertAlmostEqual(floors["venues"]["kalshi_sports"]["floor"], 0.06)


if __name__ == "__main__":
    unittest.main()
