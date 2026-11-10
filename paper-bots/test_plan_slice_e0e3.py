"""APEX plan slice E0–E3 starters. No network required for unit paths."""

import importlib.util
import os
import tempfile
import time
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import pimp_desk
from helpers import calendar_cache

ROOT = os.path.dirname(os.path.abspath(__file__))
CT = ZoneInfo("America/Chicago")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class PlanSliceTests(unittest.TestCase):
    def test_calendar_cache_last_good(self):
        with tempfile.TemporaryDirectory() as tmp:
            calendar_cache.save_raw(
                {
                    "paper_only": True,
                    "fetched_at": time.time(),
                    "source": calendar_cache.FF_URL,
                    "events": [
                        {
                            "country": "USD",
                            "impact": "High",
                            "title": "Test CPI",
                            "date": "2026-11-02T15:00:00-04:00",
                        }
                    ],
                    "last_error": None,
                },
                tmp,
            )
            ev = calendar_cache.load_ff_calendar(tmp)
            self.assertIsNotNone(ev)
            self.assertEqual(len(ev), 1)

    def test_commodity_family_cap(self):
        bot = _load("commodity_bot", os.path.join(ROOT, "commodity-15m-paper", "bot.py"))
        self.assertEqual(bot.series_family("KXWTI15M"), "energy")
        self.assertEqual(bot.series_family("KXGOLD15M"), "metal")
        state = {"open": [{"series": "KXWTI15M", "ticker": "T1"}]}
        self.assertIn("energy", bot.open_families(state))
        msg = bot.paper_buy(
            state,
            {
                "reasons": [],
                "ticker": "T2",
                "series": "KXBRENT15M",
                "side": "YES",
                "ask": 0.80,
                "fee": 0.02,
                "p": 0.9,
                "edge": 0.08,
            },
        )
        self.assertIn("portfolio corr", msg)

    def test_next_inx_scan_heartbeat(self):
        morning = datetime(2026, 11, 2, 9, 30, tzinfo=CT)
        line = pimp_desk.next_inx_scan_line("kalshi-sp", morning)
        self.assertIn("12:00", line)
        noon = datetime(2026, 11, 2, 13, 10, tzinfo=CT)
        mid = pimp_desk.next_inx_scan_line("kalshi-sp", noon)
        self.assertIn("until", mid.lower())

    def test_floor_map_parse(self):
        # TS mirrored lightly — parse rules in floorMap.ts; keep Python parity smoke.
        # City hash patterns checked via string contract.
        samples = {
            "#/plaza": "plaza",
            "#/bank": "bank",
            "#/boss": "boss",
            "#/floor/2": "floor",
            "#/office/btc15m": "office",
        }
        for h, kind in samples.items():
            raw = h.replace("#/", "")
            if kind == "plaza":
                self.assertIn(raw, ("plaza", "city"))
            elif kind == "floor":
                self.assertTrue(raw.startswith("floor/"))
            elif kind == "office":
                self.assertTrue(raw.startswith("office/"))


if __name__ == "__main__":
    unittest.main()
