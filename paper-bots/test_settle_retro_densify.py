"""Settle-retro densify — sports bid fetch + commodity t-stop + pulse/ops/tick.

Paper only. Floors locked. Soft-max tip invent EXHAUSTED — no tip wrappers.
Never LIVE / force-arm / Discord auto-post.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_profit
import desk_roi_plan
import pimp_desk


GAP = os.path.join(HERE, "sports-gap-paper", "gap_bot.py")
COMMODITY = os.path.join(HERE, "commodity-15m-paper", "bot.py")
STAFF = os.path.join(HERE, "tools", "staff_living_status.py")
PLAN = os.path.join(HERE, "POSITIVE_ROI_PLAN.md")


def _load_gap():
    spec = importlib.util.spec_from_file_location("gap_bot_retro", GAP)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class SettleRetroDensify(unittest.TestCase):
    def test_gap_helpers_fetch_kalshi_bid(self):
        gap = _load_gap()
        self.assertEqual(gap.market_yes_bid({"yes_bid_dollars": "0.42"}), 0.42)
        self.assertEqual(gap.market_yes_bid({"yes_bid": 55}), 0.55)
        self.assertIsNone(gap.market_yes_bid({}))
        with mock.patch.object(gap, "get", return_value={
            "market": {"ticker": "KX-1", "yes_bid_dollars": "0.50"},
        }):
            m = gap.fetch_kalshi_market("KX-1")
        self.assertEqual(m["yes_bid_dollars"], "0.50")
        with mock.patch.object(gap, "get", side_effect=RuntimeError("offline")):
            self.assertIsNone(gap.fetch_kalshi_market("KX-1"))

    def test_sports_settle_retro_wire_no_live(self):
        with open(GAP, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("fetch_kalshi_market", src)
        self.assertIn("bid_settle is None", src)
        self.assertIn("settle-retro shadow hard-stop — no live sell", src)
        # Time-final settle-retro disabled (forced rem=0 invents); mid-open only.
        self.assertIn("Time-final settle-retro disabled", src)
        self.assertNotIn("settle-retro shadow time-final — no live sell", src)
        self.assertNotIn("rem = 0.0  # final → treat as 0 min left", src)
        # Mid-open also densifies when pair missing.
        self.assertIn("When pair missing but ticker known", src)
        self.assertNotIn("LIVE_ORDERS = True", src)
        self.assertNotIn("tip_invent", src.lower())

    def test_sports_final_without_pair_records_via_fetched_bid(self):
        with tempfile.TemporaryDirectory() as tmp:
            bid = 0.55
            hs = desk_roi_plan.record_sports_hard_stop_shadow(
                tmp,
                ticker="KXNBA-NOPAIR",
                side="home",
                league="NBA",
                entry_price=0.80,
                bid=bid,
                fair=None,
                contracts=5,
                cost=4.0,
                note="settle-retro shadow hard-stop — no live sell",
            )
            tf = desk_roi_plan.record_sports_time_final_shadow(
                tmp,
                ticker="KXNBA-NOPAIR",
                side="home",
                league="NBA",
                minutes_left=0.0,
                entry_price=0.80,
                bid=bid,
                contracts=5,
                cost=4.0,
                note="settle-retro shadow time-final — no live sell",
            )
            self.assertTrue(hs["recorded"])
            self.assertTrue(tf["recorded"])
            self.assertEqual(desk_roi_plan.sports_hard_stop_shadow_summary(tmp)["n"], 1)
            self.assertEqual(desk_roi_plan.sports_time_final_shadow_summary(tmp)["n"], 1)
            self.assertFalse(desk_roi_plan.SPORTS_HARD_STOP_LIVE)
            self.assertFalse(desk_roi_plan.SPORTS_TIME_FINAL_LIVE)

    def test_commodity_settle_retro_wire(self):
        with open(COMMODITY, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("settle-retro shadow time-stop — no live sell", src)
        self.assertIn("now=when", src)
        # Still no force-arm default.
        self.assertNotIn("COMMODITY_TIME_STOP_LIVE = True", src)
        with tempfile.TemporaryDirectory() as tmp:
            close_iso = (
                datetime.now(timezone.utc) - timedelta(seconds=30)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            close_dt = datetime.fromisoformat(close_iso.replace("Z", "+00:00"))
            rec = desk_roi_plan.record_commodity_time_stop_shadow(
                tmp,
                ticker="KXGOLD15M-RETRO",
                side="YES",
                series="KXGOLD15M",
                close_time=close_iso,
                entry_price=0.62,
                bid=0.40,
                contracts=8,
                cost=4.96,
                note="settle-retro shadow time-stop — no live sell",
                now=close_dt,
            )
            self.assertTrue(rec["recorded"], rec)
            summ = desk_roi_plan.commodity_time_stop_shadow_summary(tmp)
            self.assertEqual(summ["n"], 1)
            self.assertFalse(summ["auto_promote"])
            self.assertFalse(desk_roi_plan.COMMODITY_TIME_STOP_LIVE)

    def test_money_pulse_surfaces_tstop_tfinal(self):
        with open(STAFF, encoding="utf-8") as fh:
            src = fh.read()
        # Top-level peers of hard_stop in money-pulse block.
        m = re.search(
            r'if args\.action == "money-pulse":([\s\S]*?)(?:\nif args\.action|\Z)',
            src,
        )
        self.assertIsNotNone(m)
        block = m.group(1)
        self.assertIn('"hard_stop": desk_roi_plan.sports_hard_stop_shadow_summary', block)
        self.assertIn(
            '"commodity_time_stop": desk_roi_plan.commodity_time_stop_shadow_summary',
            block,
        )
        self.assertIn(
            '"sports_time_final": desk_roi_plan.sports_time_final_shadow_summary',
            block,
        )
        self.assertNotIn("tip_invent", block.lower())
        self.assertNotIn("INSIGHT_HELPER_DIGESTS", block)

    def test_shadow_ops_alerts_densify_journals_and_catchup(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {
                "paper_only": True,
                "shadow": {
                    "enabled": True,
                    "btc15m": [{"id": "edge08", "params": {"venue_edge": 0.08}}],
                },
            }
            with open(os.path.join(tmp, "pimp-trading.json"), "w", encoding="utf-8") as fh:
                json.dump(cfg, fh)
            alerts = desk_roi_plan.shadow_ops_alerts(tmp)
            got = set(alerts.get("alerts") or [])
            self.assertIn("heartbeat_missing", got)
            self.assertIn("shadow_edge08_missing", got)
            self.assertIn("catchup_stale", got)
            self.assertIn("tick_stale", got)
            self.assertIn("hard_stop_journal_missing", got)
            self.assertIn("commodity_tstop_journal_missing", got)
            self.assertIn("sports_tfinal_journal_missing", got)
            self.assertTrue(alerts["observe_only"])
            self.assertFalse(alerts["live_orders_enabled"])
            self.assertFalse(alerts["auto_promote"])
            # Fresh catch-up markers clear catchup/tick stale.
            for name in ("desk_shadow_catchup_at.txt", "desk_shadow_tick_at.txt"):
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                    fh.write("fresh\n")
            # Catch-up materializes empty journals + edge08 → missing clears; thin may fire.
            ensured = desk_roi_plan.ensure_shadow_densify_journals(tmp)
            self.assertTrue(ensured["ok"], ensured)
            self.assertEqual(ensured["created_n"], 4)  # HS + commodity + t-final + edge08
            self.assertTrue(
                any("shadow_edge08" in str(x) for x in (ensured.get("created") or [])),
                ensured,
            )
            edge = pimp_desk.shadow_account_path(tmp, "btc15m", "edge08")
            self.assertTrue(os.path.isfile(edge), edge)
            pimp_desk.touch_heartbeat(tmp)
            alerts2 = desk_roi_plan.shadow_ops_alerts(tmp)
            got2 = set(alerts2.get("alerts") or [])
            self.assertNotIn("catchup_stale", got2)
            self.assertNotIn("tick_stale", got2)
            self.assertNotIn("hard_stop_journal_missing", got2)
            self.assertNotIn("commodity_tstop_journal_missing", got2)
            self.assertNotIn("sports_tfinal_journal_missing", got2)
            self.assertNotIn("shadow_edge08_missing", got2)
            # Thin boards still observe when n_with_pnl==0.
            self.assertTrue(
                {"hard_stop_promote_thin", "commodity_tstop_promote_thin", "sports_tfinal_promote_thin"}
                & got2
            )
            # Idempotent ensure; catchup surfaces journals_ensured.
            again = desk_roi_plan.ensure_shadow_densify_journals(tmp)
            self.assertEqual(again["created_n"], 0)
            catch = desk_roi_plan.run_shadow_catchup(tmp)
            self.assertIn("journals_ensured", catch)
            self.assertFalse(alerts2["live_orders_enabled"])

    def test_run_shadow_tick_smokes_commodity(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {
                "paper_only": True,
                "shadow": {
                    "enabled": True,
                    "btc15m": [{"id": "edge08", "params": {"venue_edge": 0.08}}],
                },
            }
            with open(os.path.join(tmp, "pimp-trading.json"), "w", encoding="utf-8") as fh:
                json.dump(cfg, fh)
            seen = []

            def fake_run_bot(bot_id, action="run", root=None, **kw):
                seen.append(bot_id)
                return {"ok": True, "blocked": False, "summary": "ok", "error": ""}

            with mock.patch.object(pimp_desk, "run_bot", side_effect=fake_run_bot), \
                 mock.patch.object(pimp_desk, "keep_closed_settlements"), \
                 mock.patch.object(pimp_desk, "ensure_paper_accounts"), \
                 mock.patch.object(pimp_desk, "touch_heartbeat"), \
                 mock.patch("desk_roi_plan.run_shadow_catchup", return_value={
                     "ok": True, "labeled_n": 0, "backfilled": 0, "repaired": 0,
                     "auto_promote": False, "live": False,
                 }), \
                 mock.patch("desk_roi_plan.shadow_ops_alerts", return_value={"alerts": []}):
                out = pimp_desk.run_shadow_tick(tmp, run_bots=True)
            self.assertTrue(out["commodity_smoked"])
            self.assertTrue(out["sports_smoked"])
            self.assertIn("commodity-15m", seen)
            self.assertFalse(out["live_orders_enabled"])
            self.assertFalse(out["live"])
            self.assertTrue(out["fee_floors_locked"])

    def test_doctor_surfaces_shadow_ops_observe_only(self):
        import desk_living
        with tempfile.TemporaryDirectory() as tmp:
            doc = desk_living.living_doctor(tmp, record=False)
            self.assertIn("shadow_ops", doc)
            self.assertIn("shadow_ops_alerts", doc)
            checks = {c["id"]: c for c in (doc.get("checks") or [])}
            self.assertIn("shadow_ops", checks)
            self.assertTrue(checks["shadow_ops"].get("observe_only"))
            self.assertFalse(doc.get("live_orders_enabled"))

    def test_no_live_no_force_floors_locked_no_tip_invent(self):
        self.assertFalse(desk_roi_plan.LIVE_ORDERS_ENABLED)
        self.assertFalse(desk_roi_plan.SPORTS_HARD_STOP_LIVE)
        self.assertFalse(desk_roi_plan.SPORTS_TIME_FINAL_LIVE)
        self.assertFalse(desk_roi_plan.COMMODITY_TIME_STOP_LIVE)
        self.assertFalse(desk_roi_plan.NEAR_MISS_LIVE)
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])
        with open(PLAN, encoding="utf-8") as fh:
            plan = fh.read()
        self.assertIn("Settle-retro densify", plan)
        self.assertIn("fetch_kalshi_market", plan)
        self.assertIn("Never LIVE", plan)
        self.assertNotRegex(
            plan,
            r"Settle-retro densify[\s\S]{0,800}tip invent chip",
        )


if __name__ == "__main__":
    unittest.main()
