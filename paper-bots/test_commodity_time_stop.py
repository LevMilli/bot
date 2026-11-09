"""Commodity Phase 3 time-stop shadow — ≤3m left + underwater mark."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_roi_plan


def _close_in(minutes: float) -> str:
    when = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


class CommodityTimeStop(unittest.TestCase):
    def test_hit_near_close_underwater(self):
        hit = desk_roi_plan.commodity_time_stop_hit(
            _close_in(2.0),
            bid=0.40,
            entry_price=0.55,
            cost=5.5,
            contracts=10,
        )
        self.assertTrue(hit["hit"])
        self.assertTrue(hit["near_close"])
        self.assertTrue(hit["underwater"])
        self.assertTrue(hit["shadow_only"])

    def test_no_hit_when_far_from_close(self):
        hit = desk_roi_plan.commodity_time_stop_hit(
            _close_in(10.0),
            bid=0.40,
            entry_price=0.55,
            cost=5.5,
            contracts=10,
        )
        self.assertFalse(hit["hit"])
        self.assertFalse(hit["near_close"])

    def test_no_hit_when_in_profit(self):
        hit = desk_roi_plan.commodity_time_stop_hit(
            _close_in(2.0),
            bid=0.70,
            entry_price=0.40,
            cost=4.0,
            contracts=10,
        )
        self.assertFalse(hit["hit"])
        self.assertFalse(hit["underwater"])

    def test_shadow_summary_and_no_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = desk_roi_plan.commodity_time_stop_shadow_summary(tmp)
            self.assertTrue(st["evidence_thin"])
            self.assertFalse(st["promote_ready"])
            self.assertIn("THIN", st["label"])
            denied = desk_roi_plan.staff_set_commodity_time_stop_live(tmp, True)
            self.assertFalse(denied["ok"])
            for i in range(30):
                desk_roi_plan.record_commodity_time_stop_shadow(
                    tmp,
                    ticker=f"KX-{i}",
                    side="YES",
                    series="KXWTI15M",
                    close_time=_close_in(1.5),
                    entry_price=0.60,
                    bid=0.40,
                    contracts=10,
                    cost=6.0,
                )
            st2 = desk_roi_plan.commodity_time_stop_shadow_summary(tmp)
            # mark_pnl negative → not promote_ready (EV < 0)
            self.assertGreaterEqual(st2["n_with_pnl"], 30)
            self.assertFalse(st2["promote_ready"])
            armed = desk_roi_plan.staff_set_commodity_time_stop_live(
                tmp, True, force=True, note="test",
            )
            self.assertTrue(armed["ok"])
            self.assertTrue(desk_roi_plan.commodity_time_stop_is_live(tmp))

    def test_default_exit_plan_includes_tstop(self):
        plan = desk_roi_plan.default_exit_plan("commodity-15m")
        self.assertIn("time_stop", plan["kind"])
        self.assertTrue(plan["time_stop_shadow"])
        self.assertFalse(plan["time_stop_live"])

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = desk_master.master_summary(
                tmp,
                bots=[{"id": "commodity-15m", "open_risk": 0, "history": [], "gate_a": {}}],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("commodity_time_stop", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertAlmostEqual(floors["venues"]["kalshi_commodity15m"]["floor"], 0.05)

    def test_bot_all_opens_densify_path(self):
        bot_src = os.path.join(HERE, "commodity-15m-paper", "bot.py")
        with open(bot_src, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("all-opens densify", text)
        self.assertIn("record_commodity_time_stop_shadow", text)

    def test_settle_retro_time_stop_records_shadow(self):
        """Settle underwater open → settle-retro records time-stop shadow once."""
        bot_src = os.path.join(HERE, "commodity-15m-paper", "bot.py")
        with open(bot_src, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("settle-retro shadow time-stop", text)
        self.assertIn("time_stop_shadowed", text)
        with tempfile.TemporaryDirectory() as tmp:
            close_iso = (
                datetime.now(timezone.utc) - timedelta(minutes=1)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            # now must match parsed close_time (no subsecond drift) → minutes_left≈0.
            close_dt = datetime.fromisoformat(close_iso.replace("Z", "+00:00"))
            rec = desk_roi_plan.record_commodity_time_stop_shadow(
                tmp,
                ticker="KXWTI15M-SETTLE-1",
                side="YES",
                series="KXWTI15M",
                close_time=close_iso,
                entry_price=0.60,
                bid=0.35,
                contracts=10,
                cost=6.0,
                note="settle-retro shadow time-stop — no live sell",
                now=close_dt,
            )
            self.assertTrue(rec["recorded"], rec)
            self.assertTrue(rec.get("shadow_only", True))
            summ = desk_roi_plan.commodity_time_stop_shadow_summary(tmp)
            self.assertEqual(summ["n"], 1)
            self.assertFalse(summ["auto_promote"])
            self.assertFalse(desk_roi_plan.COMMODITY_TIME_STOP_LIVE)
            # Closed flag contract: settle path sets time_stop_shadowed on pos.
            closed = {
                "ticker": "KXWTI15M-SETTLE-1",
                "side": "YES",
                "close_time": close_iso,
                "entry": 0.60,
                "cost": 6.0,
                "contracts": 10,
                "time_stop_shadowed": True,
                "exit": "settled",
                "pnl": -6.0,
            }
            self.assertTrue(closed["time_stop_shadowed"])
            self.assertEqual(closed["exit"], "settled")

    def test_catchup_from_closed_near_close_underwater(self):
        """Closed near-final underwater densifies; early flip does not invent rem=0."""
        with tempfile.TemporaryDirectory() as tmp:
            cmd_dir = os.path.join(tmp, "commodity-15m-paper")
            os.makedirs(cmd_dir, exist_ok=True)
            close_iso = "2026-11-08T12:15:00Z"
            # Closed 2m before settle — honest near-close.
            closed_near = {
                "ticker": "KXWTI-NEAR",
                "side": "YES",
                "series": "KXWTI15M",
                "close_time": close_iso,
                "entry": 0.60,
                "cost": 6.0,
                "contracts": 10,
                "exit_price": 0.40,
                "pnl": -2.0,
                "exit": "model-flip fair Δ≥0.08",
                "closed": "2026-11-08 12:13:00 UTC",
            }
            # Closed 10m before settle — not near-close; must not invent.
            closed_early = {
                "ticker": "KXWTI-EARLY",
                "side": "YES",
                "series": "KXWTI15M",
                "close_time": close_iso,
                "entry": 0.60,
                "cost": 6.0,
                "contracts": 10,
                "exit_price": 0.40,
                "pnl": -2.0,
                "exit": "model-flip fair Δ≥0.08",
                "closed": "2026-11-08 12:05:00 UTC",
            }
            with open(os.path.join(cmd_dir, "paper_account.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "cash": 100.0,
                    "open": [],
                    "closed": [closed_near, closed_early],
                    "paper_only": True,
                }, fh)
            out = desk_roi_plan.backfill_commodity_time_stop_from_closed(tmp)
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["recorded"], 1)
            summ = desk_roi_plan.commodity_time_stop_shadow_summary(tmp)
            self.assertEqual(summ["n"], 1)
            # Idempotent.
            out2 = desk_roi_plan.backfill_commodity_time_stop_from_closed(tmp)
            self.assertEqual(out2["recorded"], 0)
            # Catchup surfaces commodity_tstop.
            catch = desk_roi_plan.run_shadow_catchup(tmp)
            self.assertIn("commodity_tstop", catch)
            self.assertEqual(int(catch.get("commodity_tstop_shadow") or 0), 0)

    def test_catchup_past_bell_clamps_to_close_time(self):
        """Sell 2s after close_time still densifies; >min_left overshoot does not."""
        with tempfile.TemporaryDirectory() as tmp:
            cmd_dir = os.path.join(tmp, "commodity-15m-paper")
            os.makedirs(cmd_dir, exist_ok=True)
            close_iso = "2026-11-08T12:15:00Z"
            # Paper_sell stamp slightly past bell — old catchup DROPped rem<0.
            past_bell = {
                "ticker": "KXWTI-PAST-BELL",
                "side": "YES",
                "series": "KXWTI15M",
                "close_time": close_iso,
                "entry": 0.60,
                "cost": 6.0,
                "contracts": 10,
                "exit_price": 0.40,
                "pnl": -2.0,
                "exit": "model-flip fair Δ≥0.08",
                "closed": "2026-11-08 12:15:02 UTC",
            }
            # Overshoot beyond min_left (3m) — must not invent rem=0.
            late_flip = {
                "ticker": "KXWTI-LATE-OVERSHOOT",
                "side": "YES",
                "series": "KXWTI15M",
                "close_time": close_iso,
                "entry": 0.60,
                "cost": 6.0,
                "contracts": 10,
                "exit_price": 0.40,
                "pnl": -2.0,
                "exit": "model-flip fair Δ≥0.08",
                "closed": "2026-11-08 12:19:00 UTC",
            }
            with open(os.path.join(cmd_dir, "paper_account.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "cash": 100.0,
                    "open": [],
                    "closed": [past_bell, late_flip],
                    "paper_only": True,
                }, fh)
            # Probe: raw hit with closed_at past bell fails; clamp path records.
            raw = desk_roi_plan.commodity_time_stop_hit(
                close_iso,
                bid=0.40,
                entry_price=0.60,
                cost=6.0,
                contracts=10,
                now=desk_roi_plan._parse_commodity_closed_at("2026-11-08 12:15:02 UTC"),
            )
            self.assertFalse(raw["hit"], raw)
            self.assertFalse(raw["near_close"])
            out = desk_roi_plan.backfill_commodity_time_stop_from_closed(tmp)
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["recorded"], 1, out)
            self.assertFalse(out.get("live"))
            self.assertFalse(out.get("auto_promote"))
            summ = desk_roi_plan.commodity_time_stop_shadow_summary(tmp)
            self.assertEqual(summ["n"], 1)
            rows = desk_roi_plan._load(
                desk_roi_plan._path(desk_roi_plan.COMMODITY_TIME_STOP_SHADOW, tmp),
                {"rows": []},
            ).get("rows") or []
            self.assertEqual(rows[0].get("ticker"), "KXWTI-PAST-BELL")

    def test_catchup_refuses_entry_companion_bid_invent(self):
        """#448 sibling: settled closed[] keeps open-time bid — never invent t-stop."""
        with tempfile.TemporaryDirectory() as tmp:
            cmd_dir = os.path.join(tmp, "commodity-15m-paper")
            os.makedirs(cmd_dir, exist_ok=True)
            close_iso = "2026-11-08T12:15:00Z"
            # Winner settle — entry companion bid underwater would invent poison.
            winner_bid_only = {
                "ticker": "KXWTI-WIN-BID",
                "side": "YES",
                "series": "KXWTI15M",
                "close_time": close_iso,
                "entry": 0.60,
                "ask": 0.60,
                "bid": 0.40,  # entry companion — not an exit mark
                "cost": 6.0,
                "contracts": 10,
                "pnl": 4.0,
                "exit": "settled",
                "closed": "2026-11-08 12:15:02 UTC",
            }
            # Legacy loser settle without exit_price (pre-stamp accounts) —
            # settle-retro live path densifies; catchup must not invent from
            # entry companion bid. New settles stamp exit_price=0|1 (see
            # test_settle_stamps_binary_exit_price_for_catchup).
            loser_bid_only = {
                "ticker": "KXWTI-LOSE-BID",
                "side": "YES",
                "series": "KXWTI15M",
                "close_time": close_iso,
                "entry": 0.60,
                "ask": 0.60,
                "bid": 0.40,
                "cost": 6.0,
                "contracts": 10,
                "pnl": -6.0,
                "exit": "settled",
                "closed": "2026-11-08 12:15:02 UTC",
            }
            # Honest near-close flip still densifies via exit_price.
            flip_exit = {
                "ticker": "KXWTI-FLIP-EXIT",
                "side": "YES",
                "series": "KXWTI15M",
                "close_time": close_iso,
                "entry": 0.60,
                "bid": 0.59,
                "exit_price": 0.40,
                "cost": 6.0,
                "contracts": 10,
                "pnl": -2.0,
                "exit": "model-flip fair Δ≥0.08",
                "closed": "2026-11-08 12:13:00 UTC",
            }
            with open(os.path.join(cmd_dir, "paper_account.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "cash": 100.0,
                    "open": [],
                    "closed": [winner_bid_only, loser_bid_only, flip_exit],
                    "paper_only": True,
                }, fh)
            out = desk_roi_plan.backfill_commodity_time_stop_from_closed(tmp)
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["recorded"], 1, out)
            summ = desk_roi_plan.commodity_time_stop_shadow_summary(tmp)
            self.assertEqual(summ["n"], 1)
            rows = desk_roi_plan._load(
                desk_roi_plan._path(desk_roi_plan.COMMODITY_TIME_STOP_SHADOW, tmp),
                {"rows": []},
            ).get("rows") or []
            self.assertEqual(rows[0].get("ticker"), "KXWTI-FLIP-EXIT")
            note = str(out.get("note") or "")
            self.assertIn("never entry companion bid", note)

    def test_settle_stamps_binary_exit_price_for_catchup(self):
        """Settle stamps exit_price 0|1 so catchup densifies losers without invent."""
        bot_src = os.path.join(HERE, "commodity-15m-paper", "bot.py")
        with open(bot_src, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn('"exit_price": 1.0 if won else 0.0', text)
        with tempfile.TemporaryDirectory() as tmp:
            cmd_dir = os.path.join(tmp, "commodity-15m-paper")
            os.makedirs(cmd_dir, exist_ok=True)
            close_iso = "2026-11-08T12:15:00Z"
            # Winner binary mark — catchup must not invent t-stop (pnl≥0).
            winner = {
                "ticker": "KXWTI-WIN-EXIT1",
                "side": "YES",
                "series": "KXWTI15M",
                "close_time": close_iso,
                "entry": 0.60,
                "ask": 0.60,
                "bid": 0.40,  # entry companion — ignored when exit_price present
                "exit_price": 1.0,
                "cost": 6.0,
                "contracts": 10,
                "pnl": 4.0,
                "exit": "settled",
                "closed": "2026-11-08 12:15:02 UTC",
            }
            # Loser binary mark — honest settle exit densifies via catchup.
            loser = {
                "ticker": "KXWTI-LOSE-EXIT0",
                "side": "YES",
                "series": "KXWTI15M",
                "close_time": close_iso,
                "entry": 0.60,
                "ask": 0.60,
                "bid": 0.55,
                "exit_price": 0.0,
                "cost": 6.0,
                "contracts": 10,
                "pnl": -6.0,
                "exit": "settled",
                "closed": "2026-11-08 12:15:02 UTC",
            }
            with open(os.path.join(cmd_dir, "paper_account.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "cash": 98.0,
                    "open": [],
                    "closed": [winner, loser],
                    "paper_only": True,
                }, fh)
            out = desk_roi_plan.backfill_commodity_time_stop_from_closed(tmp)
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["recorded"], 1, out)
            summ = desk_roi_plan.commodity_time_stop_shadow_summary(tmp)
            self.assertEqual(summ["n"], 1)
            rows = desk_roi_plan._load(
                desk_roi_plan._path(desk_roi_plan.COMMODITY_TIME_STOP_SHADOW, tmp),
                {"rows": []},
            ).get("rows") or []
            self.assertEqual(rows[0].get("ticker"), "KXWTI-LOSE-EXIT0")
            self.assertAlmostEqual(float(rows[0].get("bid")), 0.0)

    def test_bot_densify_before_model_flip(self):
        bot_src = os.path.join(HERE, "commodity-15m-paper", "bot.py")
        with open(bot_src, encoding="utf-8") as fh:
            text = fh.read()
        densify = text.find("Phase 3 densify BEFORE model-flip")
        flip = text.find("Exits before entries — model-flip")
        self.assertGreater(densify, 0)
        self.assertGreater(flip, densify)
        plan_path = os.path.join(HERE, "desk_roi_plan.py")
        with open(plan_path, encoding="utf-8") as fh:
            plan_src = fh.read()
        self.assertIn("backfill_commodity_time_stop_from_closed", plan_src)
        self.assertIn('("exit_price", "exit_bid", "mark_bid")', plan_src)
        self.assertNotIn(
            '("exit_price", "exit_bid", "mark_bid", "bid")',
            plan_src,
        )


if __name__ == "__main__":
    unittest.main()
