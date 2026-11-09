"""Rest-we-can densify — news FP carve-out, markers, edge08 helper, commodity nm, INX tick.

Paper only. Floors locked. Never LIVE / force-arm / tip invent.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_more
import desk_profit
import desk_roi_plan
import pimp_desk


ROOT = Path(HERE)
COMMODITY = ROOT / "commodity-15m-paper" / "bot.py"
MEME = ROOT / "memecoin-paper" / "bot.py"
MAKEFILE = ROOT / "Makefile"
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


class RestWeCanDensify(unittest.TestCase):
    def test_near_miss_calendar_fail_closed_not_hard_news(self):
        # Soft z + fail-closed calendar reason must qualify (not wiped by "news").
        nm = desk_more.is_near_miss(
            reasons=["USD news calendar unavailable (fail-closed)", "ask outside band"],
            z=0.58,
            p=0.90,
            edge=0.06,
            min_edge=0.05,
        )
        self.assertTrue(nm["near_miss"], nm)
        self.assertEqual(nm["soft"], ["z"])

    def test_real_news_window_still_hard_blocks(self):
        nm = desk_more.is_near_miss(
            reasons=["high-impact news window / FOMC blackout"],
            z=0.58,
            p=0.90,
            edge=0.06,
            min_edge=0.05,
        )
        self.assertFalse(nm["near_miss"], nm)

    def test_generic_news_substring_still_hard(self):
        nm = desk_more.is_near_miss(
            reasons=["USD news event live"],
            z=0.58,
            p=0.90,
            edge=0.06,
            min_edge=0.05,
        )
        self.assertFalse(nm["near_miss"], nm)

    def test_run_shadow_tick_writes_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_cfg(tmp)
            with mock.patch.object(pimp_desk, "run_bot", return_value={"ok": True, "summary": "noop"}), \
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
            tick = os.path.join(tmp, "desk_shadow_tick_at.txt")
            catch = os.path.join(tmp, "desk_shadow_catchup_at.txt")
            self.assertTrue(os.path.isfile(tick), "tick marker missing")
            self.assertTrue(os.path.isfile(catch), "catchup marker missing")

    def test_run_shadow_catchup_writes_catchup_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.run_shadow_catchup(tmp)
            self.assertTrue(out["ok"])
            self.assertTrue(os.path.isfile(os.path.join(tmp, "desk_shadow_catchup_at.txt")))

    def test_helper_backfill_reads_edge08_account(self):
        with tempfile.TemporaryDirectory() as tmp:
            acct_dir = os.path.join(tmp, "btc15m-signal")
            os.makedirs(acct_dir, exist_ok=True)
            with open(os.path.join(acct_dir, "paper_account.json"), "w", encoding="utf-8") as fh:
                json.dump({"cash": 100, "open": [], "closed": []}, fh)
            edge08 = {
                "cash": 100,
                "open": [],
                "closed": [
                    {
                        "ticker": "KXBTC-E08",
                        "calendar_loaded": True,
                        "pnl": 0.08,
                        "contracts": 1,
                        "fill_id": "edge08-fill-1",
                        "closed": "2026-11-07 03:00:00 UTC",
                    }
                ],
            }
            with open(
                os.path.join(acct_dir, "shadow_edge08_account.json"), "w", encoding="utf-8"
            ) as fh:
                json.dump(edge08, fh)
            out = desk_roi_plan.backfill_helper_fills_from_btc_closed(tmp)
            self.assertTrue(out["ok"])
            self.assertEqual(out["recorded"], 1)
            self.assertIn("shadow_edge08_account.json", out.get("sources") or [])
            again = desk_roi_plan.backfill_helper_fills_from_btc_closed(tmp)
            self.assertEqual(again["recorded"], 0)
            self.assertFalse(out["places_orders"])
            self.assertFalse(out["auto_promote"])
            self.assertFalse(out["live"])

    def test_settlement_files_include_fee_ledger(self):
        self.assertIn("desk_fee_ledger.json", pimp_desk.SETTLEMENT_FILES)

    def test_commodity_source_records_near_miss(self):
        src = COMMODITY.read_text(encoding="utf-8")
        self.assertIn("record_near_miss", src)
        self.assertIn("label_near_miss_from_result", src)
        self.assertIn("commodity-15m settle label", src)
        self.assertNotIn("LIVE_ORDERS = True", src)

    def test_meme_source_records_near_miss_on_soft_skip(self):
        src = MEME.read_text(encoding="utf-8")
        self.assertIn("record_near_miss", src)
        self.assertIn("label_near_miss_from_result", src)
        self.assertIn("memecoin sell label", src)

    def test_run_shadow_tick_includes_inx_and_commodity(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_cfg(tmp)
            seen = []

            def fake_run_bot(bot_id, action="run", root=None, **kw):
                seen.append({"bot": bot_id, "action": action})
                return {"ok": True, "blocked": False, "summary": f"{bot_id} ok", "error": ""}

            # Outside INX AUTO run windows → settle smoke only (no scan invent).
            with mock.patch.object(pimp_desk, "run_bot", side_effect=fake_run_bot), \
                 mock.patch.object(pimp_desk, "keep_closed_settlements"), \
                 mock.patch.object(pimp_desk, "ensure_paper_accounts"), \
                 mock.patch.object(pimp_desk, "touch_heartbeat"), \
                 mock.patch.object(pimp_desk, "_window_open", return_value=False), \
                 mock.patch("desk_roi_plan.run_shadow_catchup", return_value={
                     "ok": True, "labeled_n": 0, "backfilled": 0, "repaired": 0,
                     "auto_promote": False, "live": False, "live_orders_enabled": False,
                     "fee_floors_locked": True,
                 }), \
                 mock.patch("desk_roi_plan.shadow_ops_alerts", return_value={"alerts": []}):
                out = pimp_desk.run_shadow_tick(tmp, run_bots=True)
            self.assertTrue(out.get("commodity_smoked"))
            self.assertTrue(out.get("btc_carry_smoked"))
            self.assertTrue(out.get("coinbase_smoked"))
            self.assertTrue(out.get("inx_sp_smoked"))
            self.assertTrue(out.get("inx_sized_smoked"))
            self.assertFalse(out["live_orders_enabled"])
            self.assertFalse(out["live"])
            self.assertFalse(out["auto_promote"])
            self.assertTrue(out["fee_floors_locked"])
            self.assertTrue(any(s["bot"] == "commodity-15m" for s in seen))
            self.assertTrue(any(s["bot"] == "btc-carry" for s in seen))
            self.assertTrue(any(s["bot"] == "coinbase-spot" for s in seen))
            self.assertTrue(any(
                s["bot"] == "kalshi-sp" and s["action"] == "settle" for s in seen
            ))
            self.assertTrue(any(
                s["bot"] == "kalshi-sized" and s["action"] == "settle" for s in seen
            ))
            self.assertFalse(any(
                s["bot"] in ("kalshi-sp", "kalshi-sized") and s["action"] == "run"
                for s in seen
            ))

    def test_run_shadow_tick_inx_scan_smoke_in_run_window(self):
        """During AUTO run window, smoke paper scan — not settle empty (#496 twin)."""
        with tempfile.TemporaryDirectory() as tmp:
            _write_cfg(tmp)
            seen = []

            def fake_run_bot(bot_id, action="run", root=None, **kw):
                seen.append({"bot": bot_id, "action": action})
                return {"ok": True, "blocked": False, "summary": f"{bot_id} {action}", "error": ""}

            with mock.patch.object(pimp_desk, "run_bot", side_effect=fake_run_bot), \
                 mock.patch.object(pimp_desk, "keep_closed_settlements"), \
                 mock.patch.object(pimp_desk, "ensure_paper_accounts"), \
                 mock.patch.object(pimp_desk, "touch_heartbeat"), \
                 mock.patch.object(pimp_desk, "_window_open", return_value=True), \
                 mock.patch("desk_roi_plan.run_shadow_catchup", return_value={
                     "ok": True, "labeled_n": 0, "backfilled": 0, "repaired": 0,
                     "auto_promote": False, "live": False, "live_orders_enabled": False,
                     "fee_floors_locked": True,
                 }), \
                 mock.patch("desk_roi_plan.shadow_ops_alerts", return_value={"alerts": []}):
                out = pimp_desk.run_shadow_tick(tmp, run_bots=True)
            self.assertTrue(out.get("inx_sp_smoked"))
            self.assertTrue(out.get("inx_sized_smoked"))
            self.assertTrue(any(
                s["bot"] == "kalshi-sp" and s["action"] == "run" for s in seen
            ))
            self.assertTrue(any(
                s["bot"] == "kalshi-sized" and s["action"] == "run" for s in seen
            ))
            rows = out.get("shadow_rows") or []
            self.assertTrue(any(
                r.get("bot") == "kalshi-sp" and r.get("action") == "scan-smoke"
                for r in rows
            ))
            self.assertFalse(out["live_orders_enabled"])
            self.assertFalse(out["live"])

    def test_shadow_ops_near_miss_thin_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_cfg(tmp)
            alerts = desk_roi_plan.shadow_ops_alerts(tmp)
            self.assertIn("near_miss_journal_thin", alerts.get("alerts") or [])
            self.assertIn("fee_ledger_missing", alerts.get("alerts") or [])
            self.assertFalse(alerts.get("live_orders_enabled"))
            self.assertFalse(alerts.get("auto_promote"))

    def test_makefile_living_shadow_ops(self):
        text = MAKEFILE.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^living-shadow-ops:")
        self.assertIn("shadow-ops", text)

    def test_plan_documents_rest_we_can(self):
        text = PLAN.read_text(encoding="utf-8")
        self.assertIn("Rest we can densify", text)

    def test_no_live_no_force_floors_locked(self):
        self.assertFalse(desk_roi_plan.LIVE_ORDERS_ENABLED)
        self.assertFalse(desk_roi_plan.NEAR_MISS_LIVE)
        self.assertFalse(getattr(desk_roi_plan, "SPORTS_HARD_STOP_LIVE", False))
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])
        tick_src = (ROOT / "pimp_desk.py").read_text(encoding="utf-8")
        block = tick_src[tick_src.find("def run_shadow_tick"): tick_src.find("def _unlink")]
        self.assertIn('live_orders_enabled": False', block)
        self.assertNotIn("LIVE_ORDERS = True", block)
        self.assertNotIn("tip_invent", block.lower())


if __name__ == "__main__":
    unittest.main()
