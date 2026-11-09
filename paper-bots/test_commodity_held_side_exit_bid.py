"""Commodity exits / t-stop densify must mark held-side bid — never model complement."""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BOT_PATH = os.path.join(HERE, "commodity-15m-paper", "bot.py")


def _load_commodity():
    spec = importlib.util.spec_from_file_location("commodity_15m_bot", BOT_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["commodity_15m_bot"] = mod
    spec.loader.exec_module(mod)
    return mod


class CommodityHeldSideExitBid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bot = _load_commodity()

    def _yes_open(self, **extra):
        pos = {
            "ticker": "KXGOLD15M-T",
            "side": "YES",
            "ask": 0.55,
            "contracts": 10,
            "cost": 5.5,
            "fair_at_entry": 0.70,
            "close_time": "2099-01-01T00:00:00+00:00",
            "series": "KXGOLD15M",
        }
        pos.update(extra)
        return pos

    def test_flip_sells_at_held_listing_bid(self):
        state = {"cash": 100.0, "open": [self._yes_open()], "closed": [], "paper_only": True}
        market = {
            "ticker": "KXGOLD15M-T",
            "yes_bid": 0.35,
            "yes_ask": 0.40,
            "no_bid": 0.62,
            "no_ask": 0.66,
            "target": 100.0,
        }
        sold = self.bot.manage_model_flips(
            state,
            side_now="NO",
            prob_now=0.82,
            bid=0.62,  # complementary model side — must not be the mark
            fee=0.02,
            delta=0.06,
            ticker="KXGOLD15M-T",
            market=market,
        )
        self.assertEqual(len(sold), 1)
        self.assertEqual(len(state["open"]), 0)
        closed = state["closed"][0]
        self.assertAlmostEqual(float(closed["exit_price"]), 0.35)
        self.assertIn("model-flip side YES→NO", closed["exit"])
        self.assertLess(float(closed["pnl"]), 0.0)

    def test_flip_refuses_complement_without_listing(self):
        state = {"cash": 100.0, "open": [self._yes_open()], "closed": [], "paper_only": True}
        sold = self.bot.manage_model_flips(
            state,
            side_now="NO",
            prob_now=0.82,
            bid=0.90,
            fee=0.02,
            delta=0.06,
            ticker="KXGOLD15M-T",
            market=None,
        )
        self.assertEqual(sold, [])
        self.assertEqual(len(state["open"]), 1)

    def test_phase3_densify_source_uses_held_listing(self):
        with open(BOT_PATH, encoding="utf-8") as fh:
            text = fh.read()
        # Phase-3 densify must not raw-use model-side ev bid.
        densify = text.find("Phase 3 densify BEFORE model-flip")
        flip = text.find("Exits before entries — model-flip")
        self.assertGreater(densify, 0)
        self.assertGreater(flip, densify)
        chunk = text[densify:flip]
        self.assertIn("listing_bid_for_side(m, held)", chunk)
        # Same-side fallback only — never raw model-side as the primary mark.
        self.assertIn(
            'if bid_ts is None and held == str(ev.get("side") or "").upper():',
            chunk,
        )
        self.assertIn("market=m", text[flip:flip + 1200])

    def test_tstop_hit_with_held_bid_not_complement(self):
        """Held YES underwater hits; complementary NO bid would miss."""
        import desk_roi_plan

        close = "2026-11-08T12:15:00Z"
        # rem≈2m via now near close
        from datetime import datetime, timezone, timedelta

        now = datetime.fromisoformat(close.replace("Z", "+00:00")) - timedelta(minutes=2)
        held_hit = desk_roi_plan.commodity_time_stop_hit(
            close, 0.35, 0.55, cost=5.5, contracts=10, now=now,
        )
        complement_miss = desk_roi_plan.commodity_time_stop_hit(
            close, 0.62, 0.55, cost=5.5, contracts=10, now=now,
        )
        self.assertTrue(held_hit["hit"], held_hit)
        self.assertFalse(complement_miss["hit"], complement_miss)


if __name__ == "__main__":
    unittest.main()
