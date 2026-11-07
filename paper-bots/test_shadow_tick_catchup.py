"""Shadow tick + catch-up densify — paper only, no LIVE / tip invent / auto-promote."""
from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_more
import desk_profit
import desk_roi_plan
import kalshi_history
import pimp_desk


class ShadowTickCatchup(unittest.TestCase):
    def test_makefile_targets_exist(self):
        makefile = os.path.join(HERE, "Makefile")
        with open(makefile, encoding="utf-8") as fh:
            text = fh.read()
        self.assertRegex(text, r"(?m)^living-shadow-catchup:")
        self.assertRegex(text, r"(?m)^living-shadow-tick:")
        self.assertIn("shadow-catchup", text)
        self.assertIn("shadow-tick", text)

    def test_run_shadow_catchup_surfaces_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_more.record_near_miss(
                tmp,
                {
                    "bot": "btc15m",
                    "ticker": "KX-CATCH-TICK",
                    "side": "YES",
                    "soft": ["z"],
                    "z": 0.58,
                },
            )

            def fetch(ticker: str):
                return "yes" if ticker == "KX-CATCH-TICK" else None

            out = desk_roi_plan.run_shadow_catchup(tmp, fetch_result=fetch)
            self.assertTrue(out["ok"])
            self.assertFalse(out["auto_promote"])
            self.assertFalse(out["live"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertTrue(out["fee_floors_locked"])
            self.assertGreaterEqual(out["labeled"], 1)
            self.assertEqual(out["labeled_n"], 1)
            self.assertIn("backfilled", out)
            self.assertIn("repaired", out)

    def test_run_shadow_tick_paper_only_no_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Minimal pimp-trading so shadow profiles resolve.
            cfg = {
                "paper_only": True,
                "shadow": {
                    "enabled": True,
                    "btc15m": [{"id": "edge08", "params": {"venue_edge": 0.08}}],
                },
            }
            with open(os.path.join(tmp, "pimp-trading.json"), "w", encoding="utf-8") as fh:
                import json
                json.dump(cfg, fh)
            out = pimp_desk.run_shadow_tick(tmp, run_bots=False)
            self.assertTrue(out["ok"])
            self.assertTrue(out["paper_only"])
            self.assertFalse(out["live_orders_enabled"])
            self.assertFalse(out["live"])
            self.assertFalse(out["auto_promote"])
            self.assertTrue(out["fee_floors_locked"])
            self.assertTrue(out["heartbeat_touched"])
            self.assertTrue(out["shadow_edge08_present"])
            self.assertTrue(os.path.isfile(pimp_desk.heartbeat_path(tmp)))
            self.assertTrue(out["history_present"])
            self.assertTrue(os.path.isfile(kalshi_history.history_path(tmp)))

    def test_sports_near_miss_record_and_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Soft-p only (edge well clear of near-miss band so exactly one soft).
            nm = desk_more.is_near_miss(
                reasons=["gap < 6 (accurate) - no trade"],
                z=None,
                p=0.78,
                edge=0.02,
                min_edge=0.06,
            )
            self.assertTrue(nm.get("near_miss"), nm)
            self.assertEqual(nm.get("soft"), ["p"])
            desk_more.record_near_miss(
                tmp,
                {
                    "bot": "sports-gap",
                    "ticker": "KXNBA-SPORTS-NM-1",
                    "side": "YES",
                    "soft": nm.get("soft"),
                    "p": 0.78,
                    "edge": 0.02,
                    "note": "sports soft near-miss",
                },
            )
            before = desk_roi_plan.near_miss_promote_status(tmp)
            self.assertEqual(before["labeled_n"], 0)
            out = desk_roi_plan.label_near_miss_from_result(
                tmp,
                ticker="KXNBA-SPORTS-NM-1",
                result="yes",
                bot="sports-gap",
                note="sports settle label",
            )
            self.assertGreaterEqual(out["labeled"], 1)
            after = desk_roi_plan.near_miss_promote_status(tmp)
            self.assertEqual(after["labeled_n"], 1)
            self.assertFalse(after["auto_promote"])
            self.assertFalse(after.get("live"))

    def test_history_settle_labels_near_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            kalshi_history.ensure_history_file(tmp)
            self.assertTrue(os.path.isfile(kalshi_history.history_path(tmp)))
            kalshi_history.record_snapshot(
                tmp,
                series="KXBTC15M",
                ticker="KXBTC15M-HIST-1",
                spot=100.0,
                target=99.0,
                side="YES",
                yes_ask=0.55,
                no_ask=0.48,
                model_p=0.60,
                minutes_left=0.0,
                regime="skip",
            )
            desk_more.record_near_miss(
                tmp,
                {
                    "bot": "btc15m",
                    "ticker": "KXBTC15M-HIST-1",
                    "side": "YES",
                    "soft": ["z"],
                    "z": 0.58,
                },
            )
            row = kalshi_history.record_settle(
                tmp,
                ticker="KXBTC15M-HIST-1",
                series="KXBTC15M",
                result="yes",
                side="YES",
                note="test history settle",
            )
            self.assertGreaterEqual(int(row.get("near_miss_labeled") or 0), 1)
            st = desk_roi_plan.near_miss_promote_status(tmp)
            self.assertEqual(st["labeled_n"], 1)
            self.assertFalse(st["auto_promote"])

    def test_shadow_ops_alerts_missing_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {
                "paper_only": True,
                "shadow": {
                    "enabled": True,
                    "btc15m": [{"id": "edge08", "params": {"venue_edge": 0.08}}],
                },
            }
            with open(os.path.join(tmp, "pimp-trading.json"), "w", encoding="utf-8") as fh:
                import json
                json.dump(cfg, fh)
            alerts = desk_roi_plan.shadow_ops_alerts(tmp)
            self.assertIn("heartbeat_missing", alerts.get("alerts") or [])
            self.assertIn("shadow_edge08_missing", alerts.get("alerts") or [])
            self.assertFalse(alerts["live_orders_enabled"])
            self.assertFalse(alerts["auto_promote"])

    def test_no_live_no_force_floors_locked(self):
        self.assertFalse(desk_roi_plan.LIVE_ORDERS_ENABLED)
        self.assertFalse(desk_roi_plan.NEAR_MISS_LIVE)
        self.assertFalse(desk_roi_plan.SPORTS_HARD_STOP_LIVE)
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])
        # Catch-up / tick helpers must not tip-invent wrappers.
        with open(os.path.join(HERE, "desk_roi_plan.py"), encoding="utf-8") as fh:
            src = fh.read()
        # run_shadow_catchup block should not reference tip invent chips.
        m = re.search(
            r"def run_shadow_catchup\([\s\S]*?\n\ndef ",
            src,
        )
        self.assertIsNotNone(m)
        block = m.group(0)
        self.assertNotIn("INSIGHT_HELPER_DIGESTS", block)
        self.assertNotIn("tip_invent", block.lower())


if __name__ == "__main__":
    unittest.main()
