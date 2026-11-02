"""Top-10 adapt stack: Gate A, fill tax, global queue, history settle harness."""

import tempfile
import unittest

import desk_brain
import desk_profit
import kalshi_history


class DeskTop10Tests(unittest.TestCase):
    def test_gate_a_not_ready_small_n(self):
        hist = [{"pnl": 2, "closed": "2026-11-01T12:00:00Z"}] * 5
        ga = desk_profit.gate_a(hist, min_n=20)
        self.assertFalse(ga["ready"])
        self.assertEqual(ga["n"], 5)

    def test_gate_a_ready_on_taxed_green(self):
        hist = [{"pnl": 3, "contracts": 10, "ask": 0.8, "closed": "2026-11-01T12:00:00Z"}] * 25
        ga = desk_profit.gate_a(hist, min_n=20, fill_tax=0.01)
        self.assertTrue(ga["ready"])
        self.assertGreaterEqual(ga["expectancy_taxed"], 0)

    def test_fill_tax_lowers_expectancy(self):
        hist = [{"pnl": 1.0, "contracts": 20, "closed": "2026-11-01T12:00:00Z"}] * 10
        raw = desk_profit.bot_expectancy(hist, fill_tax=0.0)
        taxed = desk_profit.bot_expectancy(hist, fill_tax=0.01)
        self.assertGreater(raw["expectancy"], taxed["expectancy"])

    def test_global_rank_and_allocate(self):
        rows = [
            {"bot": "btc15m", "ticker": "a", "edge": 0.05, "confidence": 0.9, "stake_est": 60},
            {"bot": "commodity-15m", "ticker": "b", "edge": 0.12, "confidence": 0.88, "stake_est": 40},
            {"bot": "sports-gap", "ticker": "c", "edge": 0.08, "confidence": 0.85, "stake_est": 30},
        ]
        ranked = desk_brain.rank_desk_queue(rows)
        self.assertEqual(ranked[0]["ticker"], "b")
        alloc = desk_brain.allocate_risk(ranked, 50)
        accepted = [r for r in alloc if r["queue_status"] == "accepted"]
        deferred = [r for r in alloc if r["queue_status"] == "deferred"]
        self.assertEqual(len(accepted), 1)
        self.assertGreaterEqual(len(deferred), 1)

    def test_history_settle_record_and_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = kalshi_history.record_settle(
                tmp,
                ticker="KXSILVER15M-TEST",
                series="KXSILVER15M",
                result="no",
                side="NO",
            )
            self.assertTrue(row["hit"])
            self.assertEqual(row["pnl"], 1.0)
            labels = kalshi_history.labeled_rows(tmp)
            self.assertEqual(len(labels), 1)
            summary = kalshi_history.history_summary(tmp)
            self.assertEqual(summary["settle_count"], 1)


if __name__ == "__main__":
    unittest.main()
