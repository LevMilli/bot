"""Cross-tower firm rank queue — sports+btc+commodity soft defer gate."""
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


class FirmQueue(unittest.TestCase):
    def test_ranks_best_score_first_and_defers(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.offer_firm_candidates(
                tmp,
                [
                    {
                        "bot": "sports-gap",
                        "ticker": "KXSPORT",
                        "side": "yes",
                        "edge": 0.07,
                        "confidence": 0.70,
                        "stake_est": 40,
                    },
                    {
                        "bot": "btc15m",
                        "ticker": "KXBTC",
                        "side": "yes",
                        "edge": 0.12,
                        "confidence": 0.90,
                        "depth": 30,
                        "stake_est": 40,
                    },
                    {
                        "bot": "commodity-15m",
                        "ticker": "KXGOLD",
                        "side": "no",
                        "edge": 0.06,
                        "confidence": 0.80,
                        "stake_est": 40,
                    },
                ],
            )
            card = desk_roi_plan.rebuild_firm_queue(tmp, remaining_risk=50.0)
            self.assertGreaterEqual(card["n"], 3)
            self.assertEqual(card["accepted_n"], 1)
            self.assertEqual(card["deferred_n"], 2)
            top = (card.get("rows") or [None])[0]
            self.assertEqual(top.get("bot"), "btc15m")
            self.assertEqual(top.get("status"), "accepted")
            self.assertTrue(desk_roi_plan.firm_queue_allows(tmp, "btc15m", "KXBTC")["allowed"])
            blocked = desk_roi_plan.firm_queue_blocks(tmp, "sports-gap", "KXSPORT")
            self.assertTrue(blocked.startswith("firm-queue deferred"))

    def test_bot_replace_offers(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.offer_firm_candidates(
                tmp,
                [{"bot": "btc15m", "ticker": "OLD", "edge": 0.1, "confidence": 0.9}],
                bot="btc15m",
            )
            desk_roi_plan.offer_firm_candidates(
                tmp,
                [{"bot": "btc15m", "ticker": "NEW", "edge": 0.11, "confidence": 0.9}],
                bot="btc15m",
            )
            store = desk_roi_plan._firm_queue_store(tmp)
            ticks = {
                str(v.get("ticker"))
                for v in (store.get("offers") or {}).values()
                if isinstance(v, dict) and v.get("bot") == "btc15m"
            }
            self.assertEqual(ticks, {"NEW"})

    def test_fail_open_non_fee_clear_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                desk_roi_plan.firm_queue_blocks(tmp, "memecoin", "X"),
                "",
            )
            self.assertEqual(
                desk_roi_plan.firm_queue_blocks(tmp, "btc15m", "MISSING"),
                "",
            )

    def test_ignores_non_fee_clear_offers(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.offer_firm_candidates(
                tmp,
                [{"bot": "memecoin", "ticker": "MEME", "edge": 0.5, "confidence": 0.9}],
            )
            self.assertEqual(out["offered"], 0)

    def test_master_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.offer_firm_candidates(
                tmp,
                [
                    {
                        "bot": "commodity-15m",
                        "ticker": "KXWTI",
                        "side": "yes",
                        "edge": 0.08,
                        "confidence": 0.85,
                        "stake_est": 20,
                    }
                ],
                bot="commodity-15m",
            )
            desk_roi_plan.rebuild_firm_queue(tmp, remaining_risk=100.0)
            summary = desk_master.master_summary(
                tmp,
                bots=[
                    {"id": "commodity-15m", "open_risk": 0, "history": [], "gate_a": {}},
                    {"id": "btc15m", "open_risk": 0, "history": [], "gate_a": {}},
                    {"id": "sports-gap", "open_risk": 0, "history": [], "gate_a": {}},
                ],
                cfg={"max_open_risk": 100},
            )
            plan = summary.get("roi_plan") or {}
            self.assertIn("firm_queue", plan)
            self.assertTrue(plan.get("fee_floors_locked"))
            fq = plan.get("firm_queue") or {}
            self.assertGreaterEqual(int(fq.get("offers_n") or 0), 1)

    def test_fee_floors_untouched(self):
        import desk_profit
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])


if __name__ == "__main__":
    unittest.main()
