"""Tax/fee ledger completeness for true ROI honesty."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_master
import desk_roi_plan


class FeeLedger(unittest.TestCase):
    def test_estimate_kalshi_fee(self):
        # ceil(0.07 * 0.5 * 0.5 * 1 * 100) / 100 = ceil(1.75)/100 → wait:
        # raw = 0.07 * p * (1-p) * n; ceil(round(raw*100,6))/100
        self.assertEqual(desk_roi_plan.estimate_kalshi_fee(0.50, 1), 0.02)
        self.assertEqual(desk_roi_plan.estimate_kalshi_fee(0.10, 1), 0.01)
        self.assertEqual(desk_roi_plan.estimate_kalshi_fee(0.0, 1), 0.0)
        self.assertEqual(desk_roi_plan.estimate_kalshi_fee(None, 1), 0.0)

    def test_record_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.record_fee_ledger(
                tmp,
                bot="btc15m",
                ticker="KXBTC-1",
                side="YES",
                price=0.60,
                contracts=2,
                fee=0.03,
                pnl=0.40,
                fill_id="f1",
                kind="sell",
            )
            self.assertTrue(out["recorded"])
            row = out["row"]
            self.assertEqual(row["fill_tax"], 0.02)  # 1¢ × 2
            self.assertEqual(row["fee"], 0.03)
            self.assertEqual(row["fee_plus_tax"], 0.05)
            self.assertEqual(row["pnl_taxed"], 0.38)
            summ = desk_roi_plan.fee_ledger_summary(tmp)
            self.assertEqual(summ["n"], 1)
            self.assertEqual(summ["fee_sum"], 0.03)
            self.assertEqual(summ["fill_tax_sum"], 0.02)
            self.assertTrue(summ["fee_floors_locked"])

    def test_completeness_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = []
            for i in range(5):
                tick = f"KX-{i}"
                fid = f"id-{i}"
                desk_roi_plan.record_fee_ledger(
                    tmp, bot="sports-gap", ticker=tick, price=0.55,
                    contracts=1, pnl=0.05, fill_id=fid, kind="sell",
                )
                hist.append({"ticker": tick, "pnl": 0.05, "fill_id": fid})
            bots = [{"id": "sports-gap", "history": hist}]
            c = desk_roi_plan.fee_ledger_completeness(tmp, bots=bots)
            self.assertEqual(c["matched"], 5)
            self.assertEqual(c["rate"], 1.0)
            self.assertTrue(c["pass"])
            self.assertTrue(c["fee_floors_locked"])

    def test_completeness_fail_when_thin_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = [
                {"ticker": f"MISS-{i}", "pnl": -0.1, "fill_id": f"m-{i}"}
                for i in range(5)
            ]
            # Only one ledger row → 20% match < 80%.
            desk_roi_plan.record_fee_ledger(
                tmp, bot="btc15m", ticker="MISS-0", fill_id="m-0",
                price=0.4, pnl=-0.1, kind="sell",
            )
            c = desk_roi_plan.fee_ledger_completeness(
                tmp, bots=[{"id": "btc15m", "history": hist}],
            )
            self.assertEqual(c["matched"], 1)
            self.assertFalse(c["pass"])

    def test_master_exposes_fee_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_fee_ledger(
                tmp, bot="commodity-15m", ticker="KXWTI", price=0.5,
                contracts=1, pnl=0.1, fill_id="c1", kind="sell",
            )
            summary = desk_master.master_summary(
                tmp,
                bots=[{
                    "id": "commodity-15m",
                    "open_risk": 0,
                    "history": [{"ticker": "KXWTI", "pnl": 0.1, "fill_id": "c1"}],
                    "gate_a": {},
                }],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("fee_ledger", plan)
            self.assertEqual((plan.get("fee_ledger") or {}).get("n"), 1)
            self.assertIn("fee_ledger_completeness", plan)
            self.assertTrue(plan.get("fee_floors_locked"))

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])

    def test_record_fill_id_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = desk_roi_plan.record_fee_ledger(
                tmp, bot="btc15m", ticker="KX-1", price=0.5,
                fee=0.02, pnl=0.1, fill_id="same-id", kind="sell",
            )
            b = desk_roi_plan.record_fee_ledger(
                tmp, bot="btc15m", ticker="KX-1", price=0.5,
                fee=0.02, pnl=0.1, fill_id="same-id", kind="sell",
            )
            self.assertTrue(a["recorded"])
            self.assertFalse(b["recorded"])
            self.assertTrue(b.get("idempotent"))
            self.assertEqual(desk_roi_plan.fee_ledger_summary(tmp)["n"], 1)

    def test_backfill_fee_ledger_from_closed(self):
        import json

        with tempfile.TemporaryDirectory() as tmp:
            btc_dir = os.path.join(tmp, "btc15m-signal")
            os.makedirs(btc_dir)
            closed = [
                {
                    "ticker": "KXBTC-CATCH-1",
                    "side": "YES",
                    "ask": 0.55,
                    "fee": 0.02,
                    "contracts": 1,
                    "pnl": 0.12,
                    "fill_id": "catch-f1",
                    "closed": "2026-11-08T12:00:00Z",
                },
                {
                    "ticker": "KXBTC-CATCH-2",
                    "ask": 0.40,
                    "fee": 0.01,
                    "pnl": -0.05,
                    "fill_id": "catch-f2",
                    "closed": "2026-11-08T13:00:00Z",
                },
                # No fee and no price → must skip (never invent).
                {"ticker": "KXBTC-SKIP", "pnl": 0.01, "closed": "2026-11-08T14:00:00Z"},
            ]
            with open(os.path.join(btc_dir, "paper_account.json"), "w", encoding="utf-8") as fh:
                json.dump({"cash": 1000, "open": [], "closed": closed}, fh)

            out = desk_roi_plan.backfill_fee_ledger_from_closed(tmp)
            self.assertTrue(out["ok"])
            self.assertEqual(out["recorded"], 2)
            self.assertFalse(out["live"])
            self.assertTrue(out["fee_floors_locked"])
            summ = desk_roi_plan.fee_ledger_summary(tmp)
            self.assertEqual(summ["n"], 2)

            bots = [{"id": "btc15m", "history": [
                {"ticker": "KXBTC-CATCH-1", "pnl": 0.12, "fill_id": "catch-f1"},
                {"ticker": "KXBTC-CATCH-2", "pnl": -0.05, "fill_id": "catch-f2"},
            ]}]
            c = desk_roi_plan.fee_ledger_completeness(tmp, bots=bots)
            self.assertEqual(c["matched"], 2)
            self.assertEqual(c["rate"], 1.0)

            again = desk_roi_plan.backfill_fee_ledger_from_closed(tmp)
            self.assertEqual(again["recorded"], 0)
            self.assertEqual(desk_roi_plan.fee_ledger_summary(tmp)["n"], 2)

    def test_catchup_refuses_exit_price_fee_invent(self):
        """Prefer-1: exit_price-only closed must not invent fee rows (#449 sibling)."""
        import json

        with tempfile.TemporaryDirectory() as tmp:
            sport = os.path.join(tmp, "sports-gap-paper")
            os.makedirs(sport)
            closed = [
                # Wipe exit only — no stored fee / entry-side price → refuse invent.
                {
                    "ticker": "KXEXIT-ONLY",
                    "side": "YES",
                    "exit_price": 0.02,
                    "pnl": -2.5,
                    "contracts": 5,
                    "closed": "2026-11-08T15:00:00Z",
                },
                # Entry companion bid only — also refuse (not an entry fill price).
                {
                    "ticker": "KXBID-ONLY",
                    "side": "YES",
                    "bid": 0.55,
                    "pnl": 0.10,
                    "contracts": 1,
                    "closed": "2026-11-08T15:30:00Z",
                },
                # Honest: stored ask → estimate allowed.
                {
                    "ticker": "KXASK-OK",
                    "side": "YES",
                    "ask": 0.55,
                    "pnl": 0.10,
                    "contracts": 1,
                    "closed": "2026-11-08T16:00:00Z",
                },
                # Honest: stored fee without ask still densifies (fee truth).
                {
                    "ticker": "KXFEE-OK",
                    "side": "YES",
                    "exit_price": 0.01,
                    "fee": 0.02,
                    "pnl": -1.0,
                    "contracts": 1,
                    "closed": "2026-11-08T16:30:00Z",
                },
            ]
            with open(os.path.join(sport, "state.json"), "w", encoding="utf-8") as fh:
                json.dump({"cash": 1000, "open": [], "closed": closed}, fh)

            out = desk_roi_plan.backfill_fee_ledger_from_closed(tmp)
            self.assertTrue(out["ok"])
            self.assertEqual(out["recorded"], 2)
            summ = desk_roi_plan.fee_ledger_summary(tmp)
            self.assertEqual(summ["n"], 2)
            with open(os.path.join(tmp, "desk_fee_ledger.json"), encoding="utf-8") as fh:
                ticks = {
                    str(r.get("ticker"))
                    for r in (json.load(fh).get("rows") or [])
                }
            self.assertEqual(ticks, {"KXASK-OK", "KXFEE-OK"})
            self.assertNotIn("KXEXIT-ONLY", ticks)
            self.assertNotIn("KXBID-ONLY", ticks)

    def test_catchup_surfaces_fee_ledger_backfill(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.run_shadow_catchup(tmp)
            self.assertTrue(out["ok"])
            self.assertIn("fee_ledger_recorded", out)
            self.assertIn("fee_ledger_backfill", out)
            self.assertEqual(out["fee_ledger_recorded"], 0)


if __name__ == "__main__":
    unittest.main()
