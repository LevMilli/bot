"""INX scan skips densify into desk_brain / skip_board + desk CARD/skip strip."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_inx
import desk_more
import pimp_desk


def _load_alerts(folder: str):
    path = os.path.join(HERE, folder, "alerts.py")
    spec = importlib.util.spec_from_file_location(f"{folder}_alerts", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class InxSkipDensify(unittest.TestCase):
    def test_densify_skip_feeds_skip_board_by_bot(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_inx.densify_skip(
                tmp,
                bot="kalshi-sp",
                reason="no candidate cleared inx fair venue edge",
                note="unit densify",
            )
            desk_inx.densify_skip(
                tmp,
                bot="kalshi-sized",
                reason="anti-double vs kalshi-sp",
                note="unit densify sized",
            )
            board = desk_more.skip_leaderboard(tmp)
            by_bot = board.get("by_bot") or {}
            self.assertIn("kalshi-sp", by_bot)
            self.assertIn("kalshi-sized", by_bot)
            self.assertGreater(sum(int(v) for v in by_bot["kalshi-sp"].values()), 0)
            self.assertGreater(sum(int(v) for v in by_bot["kalshi-sized"].values()), 0)

    def test_alerts_format_skip_includes_card(self):
        sp_alerts = _load_alerts("kalshi-sp500-paper")
        note = sp_alerts.format_skip_note("2026-11-10", "twin edge short")
        self.assertIn("NO TRADE", note)
        self.assertIn("CARD: twin edge short", note)

        sized_alerts = _load_alerts("kalshi-sized-paper")
        note2 = sized_alerts.format_skip_note("2026-11-10", "anti-double vs kalshi-sp")
        self.assertIn("CARD: anti-double vs kalshi-sp", note2)

        for folder in ("kalshi-sp500-paper", "kalshi-sized-paper"):
            path = os.path.join(HERE, folder, "bot.py")
            with open(path, encoding="utf-8") as handle:
                src = handle.read()
            self.assertIn("def _densify_scan_skip(", src)
            self.assertIn("_densify_scan_skip(", src)
            self.assertGreater(src.count("_densify_scan_skip("), 3)

    def test_kalshi_skip_prefers_densified_card(self):
        summary = (
            "Sized Kalshi event KXINXU-26NOV10: 12 active contracts\n"
            "NO TRADE 2026-11-10: no candidate cleared inx fair venue edge\n"
            "CARD: no candidate cleared inx fair venue edge\n"
        )
        self.assertEqual(
            pimp_desk._kalshi_skip("/tmp", None, summary=summary),
            "no candidate cleared inx fair venue edge",
        )
        self.assertEqual(
            pimp_desk.card_copy(summary),
            "no candidate cleared inx fair venue edge",
        )
        # No run skip → calendar/empty path still available.
        self.assertEqual(pimp_desk._kalshi_skip_run_body(""), "")


if __name__ == "__main__":
    unittest.main()
