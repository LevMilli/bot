"""BTC 15-minute decide: 0.05 after the fee, series learning skip, no size-up without 80%."""
from __future__ import annotations

import importlib.util
import os
import unittest

import desk_profit
import pimp_desk

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load_btc():
    path = os.path.join(ROOT, "btc15m-signal", "btc15m_signal.py")
    spec = importlib.util.spec_from_file_location("btc15m_decide", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _misses(market, n=8):
    return [
        {
            "result": "miss",
            "market": market,
            "bucket": "0.8-0.9",
            "side": "YES",
            "hour_ct": 13,
            "stake": 8,
        }
        for _ in range(n)
    ]


class _Desk:
    def __init__(self, rows):
        self.rows = rows
        self.sized = False

    def load_learning(self, root):
        return self.rows

    def learning_skip(self, rows, market, bucket, side=None, hour_ct=None):
        return pimp_desk.learning_skip(rows, market, bucket, side=side, hour_ct=hour_ct)

    def prob_bucket(self, prob):
        return pimp_desk.prob_bucket(prob)

    def load_settings(self, root):
        return {}

    def venue_min_edge(self, venue, cfg):
        return 0.05

    def stake_dollars_for(self, *args, **kwargs):
        self.sized = True
        raise AssertionError("adapt sized a ticket that had not cleared")

    def correlation_blocks(self, *args, **kwargs):
        return ""


class Btc15mDecide(unittest.TestCase):
    def test_floor_stays_and_a_higher_bar_stays(self):
        btc = _load_btc()
        self.assertEqual(btc.decide_floor(0.02), 0.05)
        self.assertEqual(btc.decide_floor(0.08), 0.08)
        self.assertEqual(btc.decide_floor(None), 0.05)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"], 0.05)
        old = os.environ.get("DESK_SHADOW_VENUE_EDGE")
        try:
            os.environ["DESK_SHADOW_VENUE_EDGE"] = "0.02"
            self.assertEqual(btc._edge_buffer(), 0.05)
            os.environ["DESK_SHADOW_VENUE_EDGE"] = "0.08"
            self.assertEqual(btc._edge_buffer(), 0.08)
        finally:
            if old is None:
                os.environ.pop("DESK_SHADOW_VENUE_EDGE", None)
            else:
                os.environ["DESK_SHADOW_VENUE_EDGE"] = old

    def test_series_skip_does_not_cross_btc_and_eth(self):
        eth = _misses("KXETH15M")
        self.assertIn(
            "KXETH15M",
            pimp_desk.learning_skip(eth, "KXETH15M", "0.8-0.9", side="YES", hour_ct=13),
        )
        self.assertEqual(
            pimp_desk.learning_skip(eth, "KXBTC15M", "0.8-0.9", side="YES", hour_ct=13),
            "",
        )
        btc_rows = _misses("KXBTC15M")
        self.assertIn(
            "KXBTC15M",
            pimp_desk.learning_skip(btc_rows, "KXBTC15M", "0.8-0.9", side="YES", hour_ct=13),
        )
        self.assertEqual(
            pimp_desk.learning_skip(btc_rows, "KXETH15M", "0.8-0.9", side="YES", hour_ct=13),
            "",
        )

    def test_near_miss_under_the_floor_is_not_sized(self):
        btc = _load_btc()
        desk = _Desk(_misses("BTC"))
        btc._desk = lambda: desk
        saved = []
        btc.save_account = lambda state: saved.append(state)
        was_shadow = btc.IS_SHADOW
        btc.IS_SHADOW = True
        state = {"cash": 100.0, "open": [], "closed": []}
        try:
            btc_msg = btc.paper_buy(
                state, "KXBTC15M-T", "YES", 0.80, 0.02, 0.88,
                "2026-11-11T18:00:00Z", True, edge=0.06, series="KXBTC15M",
            )
            eth_msg = btc.paper_buy(
                state, "KXETH15M-T", "YES", 0.80, 0.02, 0.86,
                "2026-11-11T18:00:00Z", True, edge=0.04, series="KXETH15M",
            )
        finally:
            btc.IS_SHADOW = was_shadow
        self.assertIn("BTC", btc_msg)
        self.assertNotIn("Paper buy", btc_msg)
        self.assertEqual(eth_msg, "near-miss under the floor")
        self.assertFalse(desk.sized)
        self.assertEqual(saved, [])
        self.assertEqual(state["cash"], 100.0)

    def test_adapt_does_not_size_up_without_80(self):
        btc = _load_btc()
        self.assertEqual(btc.cleared_stake(25, 40, proved_80=False), 25)
        self.assertEqual(btc.cleared_stake(25, 40, proved_80=True), 40)
        self.assertEqual(btc.cleared_stake(25, 10, proved_80=False), 10)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"], 0.05)


if __name__ == "__main__":
    unittest.main()
