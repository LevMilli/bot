"""Timer auto shadow densify — catch-up/tick on schedule; sports in tick; no LIVE/tip invent."""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_profit
import desk_roi_plan
import pimp_desk


ROOT = Path(HERE)
BTC = ROOT / "btc15m-signal" / "btc15m_signal.py"
COMMODITY = ROOT / "commodity-15m-paper" / "bot.py"
PLAN = ROOT / "POSITIVE_ROI_PLAN.md"


def _write_cfg(tmp: str) -> None:
    cfg = {
        "paper_only": True,
        "shadow": {
            "enabled": True,
            "btc15m": [{"id": "edge08", "params": {"venue_edge": 0.08}}],
        },
    }
    with open(os.path.join(tmp, "pimp-trading.json"), "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)


class ShadowTimerTick(unittest.TestCase):
    def test_plan_documents_timer_auto_densify(self):
        text = PLAN.read_text(encoding="utf-8")
        self.assertIn("Timer auto densify", text)
        self.assertIn("run_scheduled", text)
        self.assertIn("desk_shadow_catchup_at.txt", text)

    def test_run_scheduled_invokes_catchup_when_due(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_cfg(tmp)
            called = {"catchup": 0, "tick": 0}

            def fake_catchup(root, **_kw):
                called["catchup"] += 1
                return {
                    "ok": True,
                    "labeled_n": 0,
                    "backfilled": 0,
                    "repaired": 0,
                    "auto_promote": False,
                    "live": False,
                    "live_orders_enabled": False,
                    "fee_floors_locked": True,
                }

            def fake_tick(root, now=None, *, run_bots=True):
                called["tick"] += 1
                return {
                    "ok": True,
                    "paper_only": True,
                    "live_orders_enabled": False,
                    "live": False,
                    "auto_promote": False,
                    "fee_floors_locked": True,
                    "labeled_n": 0,
                    "shadow_rows": [
                        {"bot": "btc15m", "action": "shadow", "shadow_id": "edge08"},
                        {"bot": "sports-gap", "action": "shadow-smoke"},
                    ],
                }

            with mock.patch.object(pimp_desk, "due_slots", return_value=[]), \
                 mock.patch.object(pimp_desk, "run_bot", return_value={"ok": True, "summary": "noop"}), \
                 mock.patch.object(pimp_desk, "shadow_profiles", return_value=[]), \
                 mock.patch.object(pimp_desk, "run_midnight_broke_reload", return_value=[]), \
                 mock.patch.object(pimp_desk, "keep_closed_settlements"), \
                 mock.patch.object(pimp_desk, "ensure_paper_accounts"), \
                 mock.patch.object(pimp_desk, "touch_heartbeat"), \
                 mock.patch.object(pimp_desk, "snapshot", return_value={"bots": []}), \
                 mock.patch.object(pimp_desk, "run_shadow_tick", side_effect=fake_tick), \
                 mock.patch("desk_roi_plan.run_shadow_catchup", side_effect=fake_catchup), \
                 mock.patch("desk_roi_plan.shadow_ops_alerts", return_value={
                     "alerts": [],
                     "live_orders_enabled": False,
                     "auto_promote": False,
                 }):
                rows = pimp_desk.run_scheduled(root=tmp)
            # First pass: no markers → tick_due True → run_shadow_tick (includes catch-up).
            self.assertGreaterEqual(called["tick"], 1)
            self.assertTrue(any(r.get("bot") == "shadow-tick" for r in rows))
            for row in rows:
                self.assertFalse(row.get("live_orders_enabled", False))
            # Marker written so a second immediate pass skips tick+catchup.
            called["tick"] = 0
            called["catchup"] = 0
            with mock.patch.object(pimp_desk, "due_slots", return_value=[]), \
                 mock.patch.object(pimp_desk, "run_bot", return_value={"ok": True, "summary": "noop"}), \
                 mock.patch.object(pimp_desk, "shadow_profiles", return_value=[]), \
                 mock.patch.object(pimp_desk, "run_midnight_broke_reload", return_value=[]), \
                 mock.patch.object(pimp_desk, "keep_closed_settlements"), \
                 mock.patch.object(pimp_desk, "ensure_paper_accounts"), \
                 mock.patch.object(pimp_desk, "touch_heartbeat"), \
                 mock.patch.object(pimp_desk, "snapshot", return_value={"bots": []}), \
                 mock.patch.object(pimp_desk, "run_shadow_tick", side_effect=fake_tick), \
                 mock.patch("desk_roi_plan.run_shadow_catchup", side_effect=fake_catchup), \
                 mock.patch("desk_roi_plan.shadow_ops_alerts", return_value={
                     "alerts": [],
                     "live_orders_enabled": False,
                     "auto_promote": False,
                 }):
                rows2 = pimp_desk.run_scheduled(root=tmp)
            self.assertEqual(called["tick"], 0)
            self.assertEqual(called["catchup"], 0)
            self.assertFalse(any(r.get("bot") in ("shadow-tick", "shadow-catchup") for r in rows2))

    def test_run_scheduled_catchup_only_when_tick_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_cfg(tmp)
            # Fresh tick marker, stale/missing catchup → catchup path only.
            tick_marker = os.path.join(tmp, "desk_shadow_tick_at.txt")
            with open(tick_marker, "w", encoding="utf-8") as fh:
                fh.write("fresh\n")
            called = {"catchup": 0, "tick": 0}

            def fake_catchup(root, **_kw):
                called["catchup"] += 1
                return {
                    "ok": True,
                    "labeled_n": 1,
                    "backfilled": 0,
                    "repaired": 0,
                    "auto_promote": False,
                    "live": False,
                    "live_orders_enabled": False,
                    "fee_floors_locked": True,
                }

            def fake_tick(*_a, **_k):
                called["tick"] += 1
                return {"ok": True, "shadow_rows": [], "labeled_n": 0}

            with mock.patch.object(pimp_desk, "due_slots", return_value=[]), \
                 mock.patch.object(pimp_desk, "run_bot", return_value={"ok": True}), \
                 mock.patch.object(pimp_desk, "shadow_profiles", return_value=[]), \
                 mock.patch.object(pimp_desk, "run_midnight_broke_reload", return_value=[]), \
                 mock.patch.object(pimp_desk, "keep_closed_settlements"), \
                 mock.patch.object(pimp_desk, "ensure_paper_accounts"), \
                 mock.patch.object(pimp_desk, "touch_heartbeat"), \
                 mock.patch.object(pimp_desk, "snapshot", return_value={"bots": []}), \
                 mock.patch.object(pimp_desk, "run_shadow_tick", side_effect=fake_tick), \
                 mock.patch("desk_roi_plan.run_shadow_catchup", side_effect=fake_catchup), \
                 mock.patch("desk_roi_plan.shadow_ops_alerts", return_value={"alerts": []}):
                rows = pimp_desk.run_scheduled(root=tmp)
            self.assertEqual(called["tick"], 0)
            self.assertEqual(called["catchup"], 1)
            self.assertTrue(any(r.get("bot") == "shadow-catchup" for r in rows))

    def test_run_shadow_tick_includes_sports_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_cfg(tmp)
            seen = []

            def fake_run_bot(bot_id, action="run", root=None, **kw):
                seen.append({"bot": bot_id, "action": action, "shadow": kw.get("shadow_profile")})
                return {"ok": True, "blocked": False, "summary": f"{bot_id} ok", "error": ""}

            with mock.patch.object(pimp_desk, "run_bot", side_effect=fake_run_bot), \
                 mock.patch.object(pimp_desk, "keep_closed_settlements"), \
                 mock.patch.object(pimp_desk, "ensure_paper_accounts"), \
                 mock.patch.object(pimp_desk, "touch_heartbeat"), \
                 mock.patch("desk_roi_plan.run_shadow_catchup", return_value={
                     "ok": True, "labeled_n": 0, "backfilled": 0, "repaired": 0,
                     "auto_promote": False, "live": False, "live_orders_enabled": False,
                     "fee_floors_locked": True,
                 }), \
                 mock.patch("desk_roi_plan.shadow_ops_alerts", return_value={"alerts": []}):
                out = pimp_desk.run_shadow_tick(tmp, run_bots=True)
            self.assertTrue(out["ok"])
            self.assertTrue(out["paper_only"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertFalse(out["live"])
            self.assertFalse(out["auto_promote"])
            self.assertTrue(out["fee_floors_locked"])
            self.assertTrue(out.get("sports_smoked"))
            self.assertTrue(out.get("commodity_smoked"))
            self.assertTrue(out.get("btc_carry_smoked"))
            self.assertTrue(out.get("coinbase_smoked"))
            sports_rows = [r for r in (out.get("shadow_rows") or []) if r.get("bot") == "sports-gap"]
            self.assertEqual(len(sports_rows), 1)
            self.assertEqual(sports_rows[0].get("action"), "shadow-smoke")
            commodity_rows = [
                r for r in (out.get("shadow_rows") or []) if r.get("bot") == "commodity-15m"
            ]
            self.assertEqual(len(commodity_rows), 1)
            self.assertEqual(commodity_rows[0].get("action"), "shadow-smoke")
            self.assertTrue(commodity_rows[0].get("paper_only"))
            self.assertFalse(commodity_rows[0].get("live_orders_enabled"))
            carry_rows = [r for r in (out.get("shadow_rows") or []) if r.get("bot") == "btc-carry"]
            self.assertEqual(len(carry_rows), 1)
            self.assertEqual(carry_rows[0].get("action"), "shadow-smoke")
            coinbase_rows = [
                r for r in (out.get("shadow_rows") or []) if r.get("bot") == "coinbase-spot"
            ]
            self.assertEqual(len(coinbase_rows), 1)
            self.assertEqual(coinbase_rows[0].get("action"), "shadow-smoke")
            self.assertTrue(any(s["bot"] == "sports-gap" for s in seen))
            self.assertTrue(any(s["bot"] == "commodity-15m" for s in seen))
            self.assertTrue(any(s["bot"] == "btc-carry" for s in seen))
            self.assertTrue(any(s["bot"] == "coinbase-spot" for s in seen))
            self.assertTrue(any(s["bot"] == "btc15m" for s in seen))
            # Commodity smoke has no DESK_SHADOW env / shadow_profile.
            commodity_calls = [s for s in seen if s["bot"] == "commodity-15m"]
            self.assertTrue(all(s.get("shadow") is None for s in commodity_calls))

    def test_btc_shadow_journals_ungated(self):
        src = BTC.read_text(encoding="utf-8")
        self.assertIn("Fee ledger + helper fill densify under DESK_SHADOW too", src)
        self.assertIn("History settle + 15m sweep densify under DESK_SHADOW too", src)
        self.assertIn("History snapshot densify under DESK_SHADOW", src)
        # Brain / living stay gated.
        self.assertIn("if desk_brain and not IS_SHADOW:", src)
        self.assertRegex(src, r"if not IS_SHADOW:\s*\n\s*try:\s*\n\s*import desk_living")

    def test_commodity_all_opens_tstop_densify(self):
        src = COMMODITY.read_text(encoding="utf-8")
        self.assertIn("all-opens densify", src)
        self.assertIn("TIME-STOP SHADOW (all-opens)", src)

    def test_no_live_no_force_floors_locked_no_tip_invent(self):
        self.assertFalse(desk_roi_plan.LIVE_ORDERS_ENABLED)
        self.assertFalse(desk_roi_plan.NEAR_MISS_LIVE)
        self.assertFalse(getattr(desk_roi_plan, "SPORTS_HARD_STOP_LIVE", False))
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])
        # Scheduled densify path must not tip-invent.
        src = (ROOT / "pimp_desk.py").read_text(encoding="utf-8")
        m = re.search(
            r"Auto shadow densify[\s\S]*?# Phase 0/1 recycle",
            src,
        )
        self.assertIsNotNone(m)
        block = m.group(0)
        self.assertNotIn("tip_invent", block.lower())
        self.assertNotIn("INSIGHT_HELPER_DIGESTS", block)
        self.assertNotIn("LIVE_ORDERS = True", block)
        self.assertNotIn("LIVE_ORDERS_ENABLED = True", block)
        # run_shadow_tick still asserts paper-only contract.
        tick_src = src[src.find("def run_shadow_tick"): src.find("def _unlink")]
        self.assertIn('live_orders_enabled": False', tick_src)
        self.assertIn("sports-gap", tick_src)
        self.assertIn("commodity-15m", tick_src)
        self.assertIn("btc-carry", tick_src)
        self.assertIn("coinbase-spot", tick_src)
        self.assertIn("commodity_smoked", tick_src)
        self.assertIn("btc_carry_smoked", tick_src)
        self.assertIn("coinbase_smoked", tick_src)
        self.assertNotIn("tip_invent", tick_src.lower())
        self.assertNotIn("LIVE_ORDERS = True", tick_src)


if __name__ == "__main__":
    unittest.main()
