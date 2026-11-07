"""Learn-skip v2 — meme/INX/sports record + query side×hour fine keys."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pimp_desk


class LearnV2Wire(unittest.TestCase):
    def test_fine_key_skip_when_side_hour_cold(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(8):
                pimp_desk.record_learning(tmp, {
                    "result": "miss",
                    "market": "S&P",
                    "prob": 0.85,
                    "stake": 25.0,
                    "fill_id": f"sp-{i}",
                    "side": "yes",
                    "hour_ct": 13,
                })
            msg = pimp_desk.learning_skip(
                pimp_desk.load_learning(tmp), "S&P", "0.8-0.9",
                side="yes", hour_ct=13,
            )
            self.assertIn("learn v2", msg.lower())
            # Different hour falls back — coarse still cold (8 misses).
            coarse = pimp_desk.learning_skip(
                pimp_desk.load_learning(tmp), "S&P", "0.8-0.9",
                side="yes", hour_ct=9,
            )
            self.assertIn("under 40%", coarse.lower())

    def test_bots_pass_side_hour_in_source(self):
        root = HERE
        def _read(rel: str) -> str:
            with open(os.path.join(root, rel), encoding="utf-8") as fh:
                return fh.read()
        sp = _read("kalshi-sp500-paper/bot.py")
        sized = _read("kalshi-sized-paper/bot.py")
        meme = _read("memecoin-paper/bot.py")
        sports = _read("sports-gap-paper/gap_bot.py")
        self.assertIn("hour_ct=hour_ct", sp)
        self.assertIn('side=pick.get("side")', sp)
        self.assertIn('"side": pos.get("side")', sp)
        self.assertIn("hour_ct=hour_ct", sized)
        self.assertIn("hour_ct=datetime.now(CT).hour", meme)
        self.assertIn('"side": p.get("side")', sports)

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertAlmostEqual(floors["venues"]["kalshi_inx"]["floor"], 0.02)


if __name__ == "__main__":
    unittest.main()
