"""Replay lab (time machine): plan steps 318-342. Paper only, read only."""
from __future__ import annotations

import datetime as dt
import json
import os
import random
import re
import tempfile
import unittest

import desk_profit
import kalshi_shadow_tower as engine
import replay_lab as R

ROOT = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(ROOT, "fixtures", "replay", "more-15m-day")


def _fixture():
    spec = R.load_spec(os.path.join(ROOT, "more-15m-paper"))
    checks = R.engine_checks(R.read_jsonl(os.path.join(FIX, "research.jsonl")))
    with open(os.path.join(FIX, "results.json"), encoding="utf-8") as fh:
        results = json.load(fh)
    live = engine.read_json(os.path.join(FIX, "paper_account.json"))
    cfg = engine.read_json(os.path.join(FIX, "config.json"))
    return spec, checks, results, live, cfg


def _snap(at, ticker, side, p, yes_ask, no_ask, left, note="", series="KXBTC15M"):
    return {"at": at, "series": series, "ticker": ticker, "side": side, "model_p": p,
            "yes_ask": yes_ask, "no_ask": no_ask, "minutes_left": left, "note": note}


class EngineReplay(unittest.TestCase):
    """Steps 318, 319, 322, 323, 324, 325."""

    def test_recorded_day_replays_to_live_results(self):
        spec, checks, results, live, cfg = _fixture()
        self.assertGreater(len(checks), 60)
        out = R.replay_engine(spec, checks, results, config=cfg)
        self.assertEqual(len(out["closed"]), len(live["closed"]))
        self.assertAlmostEqual(float(out["cash"]), float(live["cash"]), delta=R.REPLAY_GAP_TOLERANCE)
        gaps = R.gap_report(out["closed"], live["closed"])
        self.assertTrue(gaps)
        for row in gaps:
            self.assertTrue(row["within_tolerance"], row)
        rep = sorted((r["ticker"], r["side"], r["exit"], r["pnl"]) for r in out["closed"])
        got = sorted((r["ticker"], r["side"], r["exit"], r["pnl"]) for r in live["closed"])
        self.assertEqual(rep, got)

    def test_replay_uses_live_fill_rules(self):
        spec, checks, results, _live, cfg = _fixture()
        self.assertTrue(spec["tape_check"])
        self.assertTrue(spec["fee_per_order"])
        out = R.replay_engine(spec, checks, results, config=cfg)
        for row in out["closed"]:
            # fee once per order, on the whole order
            self.assertAlmostEqual(row["order_fee"], engine.order_fee(row["contracts"], row["ask"]))
            self.assertAlmostEqual(row["cost"], round(row["contracts"] * row["ask"] + row["order_fee"], 2))
            # the tape check passed with enough real contracts
            self.assertGreaterEqual(row["tape_volume"] + 1e-9, row["contracts"])
            self.assertTrue(row["paper_only"] and row["shadow_only"])
            if row["exit"] == "settled":
                self.assertEqual(row["payout"], float(row["contracts"]) if row["result"] == row["side"] else 0.0)

    def test_unknown_tape_is_cautious_by_default(self):
        spec, checks, results, _live, cfg = _fixture()
        base = R.replay_engine(spec, checks, results, config=cfg)
        loose = R.replay_engine(spec, checks, results, config=cfg, changes={"unknown_tape": "pass"})
        self.assertGreaterEqual(len(loose["closed"]), len(base["closed"]))
        self.assertEqual(R.ENGINE_SWITCHES["unknown_tape"], "fail")

    def test_replay_never_touches_the_tower_folder(self):
        folder = os.path.join(ROOT, "more-15m-paper")
        before = sorted(os.listdir(folder))
        spec, checks, results, _live, cfg = _fixture()
        R.replay_engine(spec, checks[:20], results, config=cfg)
        self.assertEqual(sorted(os.listdir(folder)), before)
        self.assertIsNone(os.environ.get("DESK_BLOCK_ENTRIES"))

    def test_gate_closed_check_buys_nothing(self):
        spec, checks, results, _live, cfg = _fixture()
        shut = [dict(c, gate_closed=True) for c in checks]
        out = R.replay_engine(spec, shut, results, config=cfg)
        self.assertEqual(out["closed"], [])
        self.assertEqual(out["open"], [])

    def test_unsettled_stays_open_never_guessed(self):
        spec, checks, results, _live, cfg = _fixture()
        out = R.replay_engine(spec, checks, {}, config=cfg)
        self.assertTrue(all(r["exit"] != "settled" for r in out["closed"]))
        self.assertTrue(out["open"])
        for pos in out["open"]:
            self.assertNotIn("result", pos)

    def test_log_only_rows_stay_log_only(self):
        d = {"reason": "learning the open offset (needs 3 window opens)", "action": "skip", "edge": 0.3}
        self.assertTrue(R.recorded_log_only(d))
        for reason in ("edge 0.010 < floor 0.05 (fair 0.5 ask 0.48 fee 0.02)", "max open",
                       "one new buy per check", "Kalshi tape: 0 contracts", "already holding this market",
                       "same-direction cap (2 per window: coins up 12:00)", "desk entry gate"):
            self.assertFalse(R.recorded_log_only({"reason": reason, "action": "skip"}), reason)

    def test_daily_ladder_towers_load_their_live_rules(self):
        for folder in ("crypto-ladder-paper", "nasdaq-paper", "weather-high-paper", "more-15m-paper"):
            spec = R.load_spec(os.path.join(ROOT, folder))
            self.assertIn("floor", spec)
            self.assertGreaterEqual(float(spec["floor"]), 0.02)

    def test_ladder_replay_runs_on_engine(self):
        spec = R.load_spec(os.path.join(ROOT, "crypto-ladder-paper"))
        at = dt.datetime(2026, 11, 12, 15, tzinfo=dt.timezone.utc)
        q = {"ticker": "KXBTCD-26NOV1217-T100000", "event": "KXBTCD-26NOV1217", "side": "yes",
             "fair": 0.62, "ask": 0.50, "bid": 0.48, "label": "BTC above 100k", "why": "test"}
        checks = [{"at": at, "quotes": [q]},
                  {"at": at + dt.timedelta(minutes=5), "quotes": []}]
        out = R.replay_engine(spec, checks, {q["ticker"]: "yes"})
        self.assertEqual(len(out["closed"]), 1)
        self.assertGreater(out["closed"][0]["pnl"], 0)


class WhatIf(unittest.TestCase):
    """Steps 326-332."""

    def test_more15m_higher_bar_under_20c(self):
        spec, checks, results, _live, cfg = _fixture()
        out = R.replay_engine(spec, checks, results, config=cfg, changes={"low_ask_min_edge": 0.10})
        for row in out["closed"]:
            if row["ask"] < 0.20:
                self.assertGreaterEqual(row["edge"] + 1e-9, 0.10)

    def test_more15m_take_profit_levels(self):
        spec, checks, results, _live, cfg = _fixture()
        for tp in (0.10, 0.20):
            out = R.replay_engine(spec, checks, results, config=cfg, changes={"take_profit": tp})
            tps = [r for r in out["closed"] if r["exit"] == "what-if take-profit"]
            self.assertTrue(tps, tp)
            for row in tps:
                self.assertGreaterEqual(row["exit_bid"] + 1e-9, min(0.99, row["ask"] + tp))

    def test_unknown_switch_refused(self):
        with self.assertRaises(KeyError):
            R.engine_switches({"venue_min_edge": 0.01})
        with self.assertRaises(KeyError):
            R.window_rules("btc15m", {"floor": 0.0})

    def test_what_if_never_lowers_locked_floor(self):
        rules = R.window_rules("btc15m", {"edge_buf": 0.0})
        self.assertEqual(rules["edge_buf"], desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"])
        rules = R.window_rules("commodity-15m", {"edge_buf": 0.01})
        self.assertEqual(rules["edge_buf"], desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_commodity15m"])

    def test_window_replay_today_rules(self):
        # BTC window, YES at 0.80 with p 0.90: edge after fee + 0.05 buffer clears.
        s = [_snap("2026-11-12T15:02:00Z", "KXBTC15M-A", "YES", 0.90, 0.80, 0.21, 12.0),
             _snap("2026-11-12T15:03:00Z", "KXBTC15M-A", "YES", 0.95, 0.86, 0.15, 11.0)]
        out = R.replay_windows("btc15m", s, {"KXBTC15M-A": "yes"})
        self.assertEqual(len(out["closed"]), 1)
        row = out["closed"][0]
        self.assertEqual(row["exit"], "settled")
        self.assertEqual(row["contracts"], int(25 // (0.80 + engine.fee(0.80))))

    def test_window_replay_keeps_recorded_blocks(self):
        s = [_snap("2026-11-12T15:02:00Z", "KXBTC15M-A", "YES", 0.90, 0.80, 0.21, 12.0,
                   note="spread 0.06 > 0.04; USD high-impact news near this block")]
        out = R.replay_windows("btc15m", s, {"KXBTC15M-A": "yes"})
        self.assertEqual(out["closed"], [])
        self.assertEqual(R.kept_blocks(s[0]), ["spread 0.06 > 0.04", "USD high-impact news near this block"])
        # a depth note mentions "ask" but is not the ask band: it stays a block
        self.assertEqual(R._tag("only 2 contracts at/below ask (< 3)"), "kept")
        self.assertEqual(R._tag("ask 0.95 outside 0.70-0.92"), "ask")
        self.assertEqual(R._tag("only 6.0 min left (< 10)"), "time")

    def test_btc_5_minute_rule(self):
        s = [_snap("2026-11-12T15:08:00Z", "KXBTC15M-B", "NO", 0.93, 0.18, 0.82, 6.5,
                   note="only 6.5 min left (< 10)")]
        self.assertEqual(R.replay_windows("btc15m", s, {"KXBTC15M-B": "no"})["closed"], [])
        out = R.replay_windows("btc15m", s, {"KXBTC15M-B": "no"}, changes={"min_minutes": 5.0})
        self.assertEqual(len(out["closed"]), 1)

    def test_btc_take_profit_10_and_20(self):
        s = [_snap("2026-11-12T15:02:00Z", "KXBTC15M-C", "YES", 0.90, 0.78, 0.23, 12.0),
             _snap("2026-11-12T15:04:00Z", "KXBTC15M-C", "YES", 0.95, 0.92, 0.10, 10.0)]
        tp10 = R.replay_windows("btc15m", s, {"KXBTC15M-C": "no"}, changes={"take_profit": 0.10})
        self.assertEqual(tp10["closed"][0]["exit"], "take-profit")
        self.assertEqual(tp10["closed"][0]["exit_bid"], 0.90)  # yes bid = 1 - no ask
        tp20 = R.replay_windows("btc15m", s, {"KXBTC15M-C": "no"}, changes={"take_profit": 0.20})
        self.assertEqual(tp20["closed"][0]["exit"], "settled")
        self.assertLess(tp20["closed"][0]["pnl"], 0)  # the loss counts

    def test_commodity_85_cap_and_extra_edge(self):
        s = [_snap("2026-11-12T15:02:00Z", "KXWTI15M-D", "YES", 0.99, 0.88, 0.13, 12.0, series="KXWTI15M")]
        self.assertEqual(len(R.replay_windows("commodity-15m", s, {"KXWTI15M-D": "yes"})["closed"]), 1)
        cap = R.replay_windows("commodity-15m", s, {"KXWTI15M-D": "yes"}, changes={"ask_max": 0.85})
        self.assertEqual(cap["closed"], [])
        extra = R.replay_windows("commodity-15m", s, {"KXWTI15M-D": "yes"},
                                 changes={"high_ask": 0.85, "high_ask_extra": 0.08})
        self.assertEqual(extra["closed"], [])
        ok = R.replay_windows("commodity-15m", s, {"KXWTI15M-D": "yes"},
                              changes={"high_ask": 0.85, "high_ask_extra": 0.03})
        self.assertEqual(len(ok["closed"]), 1)

    def test_history_snaps_split_by_tower(self):
        hist = {"snapshots": [_snap("t", "a", "YES", 0.9, 0.8, 0.2, 10, series=s)
                              for s in ("KXBTC15M", "KXETH15M", "KXWTI15M", "KXBTCD")]}
        self.assertEqual({s["series"] for s in R.history_snaps(hist, "btc15m")}, {"KXBTC15M", "KXETH15M"})
        self.assertEqual({s["series"] for s in R.history_snaps(hist, "commodity-15m")}, {"KXWTI15M"})

    def test_every_named_idea_is_a_single_known_rule(self):
        for name, (tower, changes) in R.IDEAS.items():
            self.assertEqual(len(changes) if "high_ask" not in changes else 1, 1, name)
            if tower == "more-15m":
                R.engine_switches(changes)
            else:
                R.window_rules(tower, changes)


class Stats(unittest.TestCase):
    """Steps 333-339."""

    @staticmethod
    def _closed(daily):
        rows = []
        for i, pnl in enumerate(daily):
            day = dt.datetime(2026, 11, 1, 18, tzinfo=dt.timezone.utc) + dt.timedelta(days=i)
            rows.append({"closed": day.isoformat(), "pnl": pnl})
        return rows

    def test_tune_and_check_days(self):
        days = [f"2026-11-{d:02d}" for d in range(1, 11)]
        tune, check = R.split_days(days)
        self.assertEqual(len(check), 4)
        self.assertEqual(tune + check, days)
        self.assertLess(max(tune), min(check))  # the check period comes after

    def test_results_only_on_check_days(self):
        s = R.summarize({"closed": self._closed([100] * 6 + [-5] * 4)})
        self.assertEqual(s["check_pnl"], -20)  # the tune-day wins are not in the report
        self.assertIn("not proven", s["verdict"])

    def test_needs_seven_days(self):
        s = R.summarize({"closed": self._closed([5] * 6)})
        self.assertIn("not enough days", s["verdict"])
        s = R.summarize({"closed": self._closed([5, 6, 4, 7, 5, 6, 5, 6, 4, 5])})
        self.assertEqual(s["verdict"], "worth a practice twin")

    def test_losses_always_count(self):
        rows = self._closed([10, -30])
        rows.append({"closed": rows[1]["closed"], "pnl": -0.01})
        self.assertEqual(R.daily_pnl(rows), {"2026-11-01": 10, "2026-11-02": -30.01})

    def test_lower_bound_is_below_the_mean(self):
        rng = random.Random(3)
        vals = [rng.gauss(2, 10) for _ in range(30)]
        low = R.block_bootstrap_low(vals)
        self.assertLess(low, sum(vals) / len(vals))
        self.assertEqual(R.block_bootstrap_low(vals), low)  # seeded, repeatable

    def test_block_bootstrap_sees_streaks(self):
        # Same days, but streaky order: the block bootstrap should not be more confident.
        vals = [8.0] * 10 + [-6.0] * 10
        mixed = [v for pair in zip(vals[:10], vals[10:]) for v in pair]
        self.assertLessEqual(R.block_bootstrap_low(vals, block=5), R.block_bootstrap_low(mixed, block=1) + 1e-9)

    def test_many_variants_make_the_bar_stricter(self):
        vals = [3, -1, 4, 2, -2, 5, 1, 3, 0, 2, 4, -1]
        one = R.block_bootstrap_low(vals, alpha=R.adjusted_alpha(1))
        twenty = R.block_bootstrap_low(vals, alpha=R.adjusted_alpha(20))
        self.assertLess(twenty, one)
        s = R.summarize({"closed": self._closed(vals)}, variants_tried=20)
        self.assertIn("fresh test period", s["warning"])
        self.assertAlmostEqual(s["alpha"], 0.0025)


class RunLog(unittest.TestCase):
    """Steps 336, 340, 341."""

    def test_runs_are_stored_with_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            R.store_run(tmp, {"tower": "more-15m", "changes": {}, "summary": {}})
            R.store_run(tmp, {"tower": "more-15m", "changes": {"take_profit": 0.1}, "summary": {}})
            R.store_run(tmp, {"tower": "more-15m", "changes": {"take_profit": 0.1}, "summary": {}})
            R.store_run(tmp, {"tower": "btc15m", "changes": {}, "summary": {}})
            rows = R.runs(tmp)
            self.assertEqual(len(rows), 4)
            self.assertTrue(all(r["paper_only"] for r in rows))
            self.assertEqual(rows[1]["changes"], {"take_profit": 0.1})
            self.assertEqual(R.variants_tried(tmp, "more-15m"), 2)
            self.assertEqual(R.variants_tried(tmp, "nasdaq"), 1)

    def test_report_is_plain(self):
        spec, checks, results, live, cfg = _fixture()
        out = R.replay_engine(spec, checks, results, config=cfg, changes={"take_profit": 0.2})
        run = {"tower": "more-15m", "changes": out["changes"], "summary": R.summarize(out),
               "gaps": R.gap_report(out["closed"], live["closed"])}
        text = R.report_text(run)
        self.assertIn("Check days", text)
        self.assertIn("Verdict", text)
        self.assertIn("Paper only", text)
        self.assertNotIn("!", text)
        self.assertIsNone(re.search(r"scrap|crawl", text, re.I))

    def test_cli_runs_offline_without_saving(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(R.main(["more-15m", "--root", ROOT, "--no-save"]), 0)
            self.assertEqual(R.main(["btc15m", "--root", tmp, "--no-save"]), 0)
            self.assertFalse(os.path.exists(os.path.join(ROOT, "replay-runs")))

    def test_fixture_is_rebuildable(self):
        import importlib.util
        path = os.path.join(ROOT, "fixtures", "replay", "make_more15m_day.py")
        spec = importlib.util.spec_from_file_location("make_more15m_day", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as tmp:
            state = mod.build(os.path.join(tmp, "day"))
        live = engine.read_json(os.path.join(FIX, "paper_account.json"))
        self.assertEqual(state["cash"], live["cash"])
        self.assertEqual(len(state["closed"]), len(live["closed"]))


if __name__ == "__main__":
    unittest.main()
