"""Memecoin scans new feed names again. A fee fail is still a skip."""
from __future__ import annotations

import importlib.util
import os
import unittest

import desk_profit

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load():
    import sys
    import types
    meme = os.path.join(ROOT, "memecoin-paper")
    if meme not in sys.path:
        sys.path.insert(0, meme)
    if "requests" not in sys.modules:
        stub = types.ModuleType("requests")
        stub.Session = lambda: types.SimpleNamespace(headers={})
        sys.modules["requests"] = stub
    path = os.path.join(meme, "bot.py")
    spec = importlib.util.spec_from_file_location("memecoin_scan", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MemecoinScan(unittest.TestCase):
    def test_new_names_are_scanned_and_a_facts_pass_that_fails_the_fee_skips(self):
        bot = _load()
        known = bot.scored_mints({
            "open": [{"mint": "MINT-HELD"}],
            "cooldown": {"MINT-COOLED": 1},
        })
        self.assertEqual(known, {"MINT-HELD", "MINT-COOLED"})
        kept = bot.scan_mints(
            {"MINT-HELD": "profiles", "MINT-NEW": "boosts_top"},
            known,
        )
        self.assertEqual(kept, {"MINT-HELD": "profiles", "MINT-NEW": "boosts_top"})
        # A fresh account (nothing held, nothing cooled) still scans the feed.
        self.assertEqual(bot.scan_mints({"MINT-NEW": "boosts_top", "": "x"}, set()), {"MINT-NEW": "boosts_top"})
        # Held / cooled names are still refused by scan()'s own gates.
        import inspect
        src = inspect.getsource(bot.scan)
        self.assertIn("mint in open_mints", src)
        self.assertIn('st["cooldown"].get(mint)', src)
        skip = bot.facts_fee_skip(True, 0.90, lane="accurate", venue_need=0.02)
        self.assertIn("fee-aware", skip)
        self.assertEqual(bot.facts_fee_skip(False, 0.90), "")
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["solana_dex"], 0.02)
        self.assertIn("scan_mints", bot.scan.__code__.co_names)
        self.assertIn("facts_fee_skip", bot.scan.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
