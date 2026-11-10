"""Memecoin tower: conf−0.5 residual is not fee-aware edge — starve honesty."""

import importlib.util
import os
import re
import unittest


HERE = os.path.dirname(os.path.abspath(__file__))
MEME_DIR = os.path.join(HERE, "memecoin-paper")
BOT_PATH = os.path.join(MEME_DIR, "bot.py")
CFG_PATH = os.path.join(MEME_DIR, "config.py")


def _load_cfg():
    spec = importlib.util.spec_from_file_location("meme_cfg_fee", CFG_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bot_src() -> str:
    with open(BOT_PATH, encoding="utf-8") as handle:
        return handle.read()


def _round_trip_fee(cfg) -> float:
    return 2.0 * float(cfg.PAPER_FILL["swap_fee_pct"]) / 100.0


def _residual(conf: float) -> float:
    return max(0.0, float(conf) - 0.5)


class MemeFeeAwareEdgeTests(unittest.TestCase):
    def test_expand_volume_absent_and_stop_lock_untouched(self):
        cfg = _load_cfg()
        self.assertFalse(hasattr(cfg, "expand_volume") and bool(getattr(cfg, "expand_volume")))
        self.assertEqual(cfg.EXIT["stop_pct"], -12)
        self.assertEqual(cfg.RED_DAY_ENTRY_LOCK_USD, 5)
        self.assertEqual(cfg.PAPER_FILL["swap_fee_pct"], 1.0)
        self.assertTrue(cfg.PAPER)

    def test_residual_always_cleared_old_venue_floor(self):
        """Proof: at speed/accurate floors, conf−0.5 ≫ solana_dex 0.02 (+speed 0.02)."""
        cfg = _load_cfg()
        rt = _round_trip_fee(cfg)
        self.assertAlmostEqual(rt, 0.02)
        speed_r = _residual(cfg.MIN_CONFIDENCE_SPEED)
        acc_r = _residual(cfg.MIN_CONFIDENCE_ACCURATE)
        self.assertAlmostEqual(speed_r, 0.22)
        self.assertAlmostEqual(acc_r, 0.30)
        self.assertGreater(speed_r, 0.04)
        self.assertGreater(acc_r - rt, 0.02)  # fee haircut alone still clears floor

    def test_bot_ships_refuse_helper_and_gate(self):
        src = _bot_src()
        self.assertIn("def refuse_conf_residual_as_edge(", src)
        self.assertIn("def round_trip_swap_fee_frac(", src)
        self.assertIn("def conf_minus_half_residual(", src)
        self.assertIn("refuse_conf_residual_as_edge(", src)
        self.assertIn("starve honesty", src)
        self.assertIn("as fee-aware edge", src)
        # Old clearing compare removed from risk-gate path.
        self.assertIsNone(
            re.search(
                r'gate_reason = f"venue solana_dex edge \{residual:.3f\} < \{need_venue:.3f\} \(\{lane\}\)"',
                src,
            )
        )
        self.assertNotIn("expand_volume = True", src)
        self.assertNotIn("expand_volume=True", src)

    def test_refuse_reason_template_includes_rt_fee(self):
        src = _bot_src()
        self.assertIn("rt_fee=", src)
        self.assertIn("after_fee=", src)
        self.assertIn("refuse conf−0.5 residual", src)

    def test_office_card_matches_live_exits(self):
        """HUD shows the first five plan lines. Those lines must be the live rules.

        The office used to print a −35% stop, a 40% liquidity drop, a 30% trail,
        and a size-up. Config and the NVIDIA trail fill are −12 / 35 / 25 / 4h.
        Copy only: this does not clear the residual refuse.
        """
        import pimp_desk

        plan = pimp_desk.BOT_PLANS["memecoin"]
        buy = " ".join(plan["buy"][:5])
        sell = " ".join(plan["sell"][:5])
        fails = " ".join(plan["failsafes"][:5])
        shown = buy + " " + sell + " " + fails
        self.assertIn("taxed EV ≥ 0", buy)
        self.assertIn("−$5", buy)
        self.assertIn("−12%", sell)
        self.assertIn("35%", sell)
        self.assertIn("25%", sell)
        self.assertIn("4h", sell)
        self.assertIn("−6%", sell)
        self.assertNotIn("−35%", shown)
        self.assertNotIn("40%", shown)
        self.assertNotIn("Trail 30%", shown)
        self.assertNotIn("12 entries", shown)
        self.assertNotIn("Max open 4", shown)
        self.assertIn("No size-up", buy)
        self.assertNotIn("→ size-up", shown)
        self.assertNotIn("settled hit", shown)
        self.assertNotIn("≥6h", shown)
        self.assertEqual(plan["stake"], "$10–$25")
        self.assertTrue(plan["entry_gated"])


if __name__ == "__main__":
    unittest.main()
