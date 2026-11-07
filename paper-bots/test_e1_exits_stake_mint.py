"""E1 money-path guards: exits-first, INX stake shrink, meme mint learning key."""
from __future__ import annotations

import ast
import math
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pimp_desk


class SportsExitsBeforeEntries(unittest.TestCase):
    """E1 #118 — sell/settle block stays before paper buys in sports run()."""

    def test_exits_block_precedes_buys_in_source(self):
        path = os.path.join(HERE, "sports-gap-paper", "gap_bot.py")
        with open(path, encoding="utf-8") as handle:
            src = handle.read()
        exits_marker = "# ---- exits / settlement (before new paper buys) ----"
        buys_marker = "# ---- paper buys after exits, capped by desk open risk ----"
        self.assertIn(exits_marker, src)
        self.assertIn(buys_marker, src)
        self.assertLess(src.index(exits_marker), src.index(buys_marker))
        # AST: run() body mentions exits comment before buy loop assignment use
        tree = ast.parse(src)
        run_fn = None
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "run":
                run_fn = node
                break
        self.assertIsNotNone(run_fn)
        # Ensure buy_candidates append happens, then exits comment region, then buy loop
        text = ast.get_source_segment(src, run_fn) or src
        self.assertIn("buy_candidates.append", text)
        self.assertLess(
            text.index(exits_marker),
            text.index(buys_marker),
        )


class InxStakeContractsShrink(unittest.TestCase):
    """E1 #119 — both INX bots fee-aware bankroll shrink; n≥1 skip stays green."""

    def _load(self, which: str):
        folder = "kalshi-sp500-paper" if which == "sp" else "kalshi-sized-paper"
        path = os.path.join(HERE, folder)
        if path not in sys.path:
            sys.path.insert(0, path)
        # Fresh import name
        import importlib
        mod_name = f"_risk_{which}"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            mod_name, os.path.join(path, "risk_manager.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_sp_and_sized_bankroll_shrink(self):
        for which in ("sp", "sized"):
            rm = self._load(which)
            # Uncapped floor(25/0.85)=29; fee-aware bankroll 24.80 → shrink
            n_full = rm.stake_contracts(0.85)
            self.assertGreaterEqual(n_full, 1)
            n_shrink = rm.stake_contracts(0.85, bankroll=24.80)
            self.assertLess(n_shrink, n_full)
            self.assertGreaterEqual(n_shrink, 1)
            # Tiny bankroll → 0 contracts (n≥1 skip stays green / no forced buy)
            self.assertEqual(rm.stake_contracts(0.85, bankroll=0.50), 0)
            # Invalid ask → 0
            self.assertEqual(rm.stake_contracts(0), 0)
            self.assertEqual(rm.stake_contracts(None), 0)


class MemeLearningSkipMintKey(unittest.TestCase):
    """E1 #120 — learning_skip keys on mint, not colliding symbols."""

    def test_mint_key_not_symbol_collision(self):
        rows = []
        mint_a = "So11111111111111111111111111111111111111112"
        mint_b = "So22222222222222222222222222222222222222222"
        # learning_skip cleans market to 40 chars — store rows under cleaned key
        key_a = pimp_desk._clean(mint_a, 40)
        key_b = pimp_desk._clean(mint_b, 40)
        self.assertNotEqual(key_a, key_b)
        # Poison mint_a bucket under 40% with ≥8 settles
        for i in range(10):
            rows.append({
                "market": key_a,
                "bucket": "0.6-0.7",
                "result": "hit" if i < 2 else "miss",
            })
        # Same symbol-looking noise must not skip mint_b
        for i in range(10):
            rows.append({
                "market": "PEPE",  # symbol label — must not collide with mint_b
                "bucket": "0.6-0.7",
                "result": "miss",
            })
        skip_a = pimp_desk.learning_skip(rows, mint_a, "0.6-0.7")
        skip_b = pimp_desk.learning_skip(rows, mint_b, "0.6-0.7")
        self.assertTrue(skip_a)
        self.assertIn(key_a[:12], skip_a)
        self.assertEqual(skip_b, "")
        # Symbol key alone would skip PEPE, but mint_b stays clear
        skip_pepe = pimp_desk.learning_skip(rows, "PEPE", "0.6-0.7")
        self.assertTrue(skip_pepe)

    def test_meme_bot_passes_mint_to_learning_skip(self):
        path = os.path.join(HERE, "memecoin-paper", "bot.py")
        with open(path, encoding="utf-8") as handle:
            src = handle.read()
        # Call site must prefer mint over symbol
        self.assertIn("desk.learning_skip(", src)
        self.assertIn("mint or row.get(\"symbol\")", src)
        # Must not call learning_skip with symbol alone as first market key
        # (naive symbol-only would look like learning_skip(..., row.get("symbol"), ...)
        self.assertNotIn(
            'learning_skip(\n                            desk.load_learning(os.path.dirname(BASE)),\n                            row.get("symbol")',
            src,
        )


class FeeFloorsLocked(unittest.TestCase):
    def test_floors(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertAlmostEqual(floors["venues"]["kalshi_sports"]["floor"], 0.06)
        self.assertAlmostEqual(floors["venues"]["kalshi_btc15m"]["floor"], 0.05)
        self.assertAlmostEqual(floors["venues"]["kalshi_inx"]["floor"], 0.02)


if __name__ == "__main__":
    unittest.main()
