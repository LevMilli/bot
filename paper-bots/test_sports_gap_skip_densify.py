#!/usr/bin/env python3
"""Sports-gap evaluate densify: skips surface on CARD; book-unchanged still logs."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
GAP = HERE / "sports-gap-paper" / "gap_bot.py"


def _load_gap():
    spec = importlib.util.spec_from_file_location("gap_bot_under_test", GAP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SportsGapSkipDensify(unittest.TestCase):
    def test_card_prefers_evaluate_skip_over_lanes_clear(self):
        gap = _load_gap()
        card = gap._card_line({
            "trades": [],
            "skips": ["gap < 6 (accurate) - no trade"],
            "live_games": 8,
            "matched": 13,
        })
        self.assertIn("gap < 6", card)
        self.assertNotIn("lanes clear", card)

    def test_card_lanes_clear_only_when_skips_empty(self):
        gap = _load_gap()
        card = gap._card_line({
            "trades": [],
            "skips": [],
            "live_games": 8,
            "matched": 13,
        })
        self.assertIn("lanes clear", card)

    def test_card_data_error_not_false_friend_empty(self):
        """ESPN/Kalshi down must not CARD as 'No live or tip-soon' (#432 leftover)."""
        gap = _load_gap()
        # Skips path (primary densify): first skip wins.
        card_skip = gap._card_line({
            "trades": [],
            "skips": ["data error: ESPN down (NHL)"],
            "data_errors": [{"league": "NHL", "source": "ESPN", "error": "failed"}],
            "live_games": 0,
            "matched": 0,
        })
        self.assertIn("data error", card_skip)
        self.assertIn("ESPN", card_skip)
        self.assertNotIn("No live or tip-soon", card_skip)
        # Defense: data_errors alone still beat empty-market false-friend.
        card_err = gap._card_line({
            "trades": [],
            "skips": [],
            "data_errors": [{"league": "NBA", "source": "Kalshi", "error": "failed"}],
            "live_games": 0,
            "matched": 0,
        })
        self.assertIn("data error", card_err)
        self.assertIn("Kalshi", card_err)
        self.assertNotIn("No live or tip-soon", card_err)
        self.assertNotIn("lanes clear", card_err)

    def test_data_error_paths_call_early_densify(self):
        """ESPN/Kalshi except blocks densify skips + brain (match-miss sibling)."""
        src = GAP.read_text(encoding="utf-8")
        for needle in (
            'miss = f"data error: ESPN down ({league})"',
            'miss = f"data error: Kalshi down ({league})"',
        ):
            idx = src.find(needle)
            self.assertGreater(idx, 0, msg=needle)
            chunk = src[idx:idx + 650]
            self.assertIn('summary_out["skips"].append(miss)', chunk)
            self.assertIn("_densify_early_eval_skip", chunk)
            self.assertIn('ticker=""', chunk)

    def test_early_eval_skip_densifies_brain_and_features(self):
        gap = _load_gap()
        with tempfile.TemporaryDirectory() as tmp:
            gap.DESK_ROOT = tmp
            gap._densify_early_eval_skip(
                reason="gap < 6 (accurate) - no trade",
                ticker="KXNHL-TEST",
                side="home",
                series="KXNHLGAME",
                league="NHL",
                fair=0.62,
                gap=0.04,
                ask=0.55,
                bid=0.52,
                lane="accurate",
            )
            import desk_brain
            journal = desk_brain.load_journal(tmp)
            decisions = journal.get("decisions") or []
            self.assertTrue(decisions)
            last = decisions[-1]
            self.assertEqual(last.get("action"), "skip")
            self.assertEqual(last.get("bot"), "sports-gap")
            self.assertEqual(last.get("ticker"), "KXNHL-TEST")
            self.assertIn("gap < 6", str((last.get("reasons") or [""])[0]))
            self.assertEqual(
                int((journal.get("by_bot") or {}).get("sports-gap", {}).get("skips") or 0),
                1,
            )
            feat_path = os.path.join(tmp, "desk_feature_store.jsonl")
            self.assertTrue(os.path.isfile(feat_path))
            with open(feat_path, encoding="utf-8") as fh:
                lines = [ln for ln in fh.read().splitlines() if ln.strip()]
            self.assertTrue(lines)
            row = json.loads(lines[-1])
            self.assertEqual(row.get("bot"), "sports-gap")
            self.assertEqual(row.get("action"), "skip")
            self.assertIn("gap < 6", str(row.get("skip_codes") or row.get("note") or ""))

    def test_match_miss_path_calls_early_densify(self):
        """Match-miss CARD densify must also hit brain (honest empty ticker)."""
        src = GAP.read_text(encoding="utf-8")
        miss_idx = src.find('miss = "no Kalshi match - skip"')
        self.assertGreater(miss_idx, 0)
        chunk = src[miss_idx:miss_idx + 700]
        self.assertIn("_densify_early_eval_skip", chunk)
        self.assertIn("ticker=\"\"", chunk)
        gap = _load_gap()
        with tempfile.TemporaryDirectory() as tmp:
            gap.DESK_ROOT = tmp
            gap._densify_early_eval_skip(
                reason="no Kalshi match - skip",
                ticker="",
                series="KXNHLGAME",
                league="NHL",
            )
            import desk_brain
            import desk_more
            last = (desk_brain.load_journal(tmp).get("decisions") or [])[-1]
            self.assertEqual(last.get("bot"), "sports-gap")
            self.assertEqual(last.get("action"), "skip")
            self.assertEqual(last.get("ticker"), "")
            self.assertIn("no Kalshi match", str((last.get("reasons") or [""])[0]))
            board = desk_more.skip_leaderboard(tmp)
            self.assertIn("sports-gap", board.get("by_bot") or {})

    def test_cached_idle_not_when_tip_soon_pre_in_cache(self):
        """Prefer-1: tip-soon in ESPN cache must not look idle / invent empty (#433)."""
        from datetime import datetime, timedelta, timezone

        gap = _load_gap()
        path = "basketball/nba"
        url = gap.league_url(path)
        tip_iso = (datetime.now(timezone.utc) + timedelta(minutes=45)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        # Seed cache like pre-tip warm: pre games only (no live ``in``).
        gap._cache_put(
            url,
            {
                "events": [
                    {
                        "id": "tip1",
                        "date": tip_iso,
                        "status": {"type": {"state": "pre", "shortDetail": "45'"}},
                    }
                ]
            },
        )
        self.assertFalse(
            gap.league_cached_idle(path),
            msg="tip-soon pre in cache must not idle-skip the league",
        )
        # Truly idle: only final/post games in cache → idle ok.
        gap._cache_put(
            url,
            {
                "events": [
                    {
                        "id": "done1",
                        "date": tip_iso,
                        "status": {"type": {"state": "post", "shortDetail": "Final"}},
                    }
                ]
            },
        )
        self.assertTrue(gap.league_cached_idle(path))
        # Live in cache → not idle.
        gap._cache_put(
            url,
            {
                "events": [
                    {
                        "id": "live1",
                        "date": tip_iso,
                        "status": {"type": {"state": "in", "shortDetail": "Q2"}},
                    }
                ]
            },
        )
        self.assertFalse(gap.league_cached_idle(path))
        src = GAP.read_text(encoding="utf-8")
        idle_fn = src.split("def league_cached_idle", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("tip_within_minutes", idle_fn)
        self.assertIn('state == "pre"', idle_fn)

    def test_daily_r_settle_only_prepends_card_skip(self):
        """#482 twin: sports daily-R must prepend so CARD beats earlier evaluate/cool skips."""
        src = GAP.read_text(encoding="utf-8")
        idx = src.find('daily_r_blocks("sports-gap"')
        self.assertGreater(idx, 0)
        chunk = src[idx:idx + 900]
        self.assertIn("skips.insert(0, r_block)", chunk)
        self.assertNotIn("skips\"].append(r_block)", chunk)
        # #482 leftover: brain densify at settle-only + refuse max-buys invent.
        self.assertIn("sports daily-r densify", chunk)
        self.assertIn("settle_lock", src)
        gap = _load_gap()
        card = gap._card_line({
            "trades": [],
            "skips": [
                "daily R budget hit for sports-gap: today $30.00 ≥ 1.5R ($30) — settle-only",
                "gap < 6 (accurate) - no trade",
            ],
            "live_games": 4,
            "matched": 4,
        })
        self.assertIn("settle-only", card.lower())
        self.assertNotIn("gap < 6", card)

    def test_daily_r_settle_only_classifies_budget_not_other(self):
        """Settle-only skip taxonomy is BUDGET (fee-clear profit lock), not DATA/other."""
        import desk_more
        import desk_roi_plan

        msg = desk_roi_plan.daily_r_blocks("sports-gap", 30.0)
        self.assertIn("settle-only", msg.lower())
        self.assertEqual(desk_more.classify_skip(msg), "budget")
        self.assertEqual(desk_more.stable_skip_code("budget"), "BUDGET")


if __name__ == "__main__":
    unittest.main()
