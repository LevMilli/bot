"""Paper desk checks. No network, no Discord, no live orders."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pimp_desk


ROOT = os.path.dirname(os.path.abspath(__file__))
STUB = """import os, sys
open('ran', 'a').write(' '.join(sys.argv[1:]) + '\\n')
print('RAN ' + ' '.join(sys.argv[1:]))
print('ENV ' + ','.join(sorted(os.environ)))
"""
RESET_STUB = """import os, sys
print('RESET ' + ' '.join(sys.argv[1:]))
if '--reset' in sys.argv:
    if os.path.exists('state.json'):
        os.remove('state.json')
    if os.path.exists('paper_trades.md'):
        os.remove('paper_trades.md')
"""


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


class PimpDeskTests(unittest.TestCase):
    def test_allowlist_is_paper_scripts_only(self):
        with open(pimp_desk.__file__, encoding="utf-8") as handle:
            src = handle.read()
        self.assertNotIn("shell=True", src)
        blob = json.dumps(pimp_desk.ACTIONS).lower()
        for word in ("api_key", "wallet", "live", "order", "--any-time"):
            self.assertNotIn(word, blob)

    def test_limits_reject_live_sized_stakes(self):
        bad, err = pimp_desk.parse_settings({
            "stake_hi_min": 5, "stake_hi_max": 40, "stake_lo_max": 10,
            "daily_loss_stop": 50, "max_open_risk": 100, "max_open_positions": 4,
        })
        self.assertIsNone(bad)
        self.assertTrue(err)
        cfg, err = pimp_desk.parse_settings({
            "stake_hi_min": 10, "stake_hi_max": 30, "stake_lo_max": 9.5,
            "daily_loss_stop": 40, "max_open_risk": 80, "max_open_positions": 3,
        })
        self.assertIsNone(err)
        self.assertTrue(cfg["paper_only"])
        self.assertEqual(cfg["stake_hi_prob"], 0.8)
        self.assertEqual(cfg["stake_lo_max"], 9.5)

    def test_checkout_snapshot_is_empty_and_paper(self):
        snap = pimp_desk.snapshot(ROOT)
        self.assertTrue(snap["paper_only"])
        self.assertIn("PAPER ONLY", snap["banner"])
        self.assertEqual([b["id"] for b in snap["bots"]],
                         ["sports-gap", "kalshi-sp", "btc15m", "memecoin", "kalshi-sized"])
        sized = snap["bots"][-1]
        self.assertFalse(sized["present"])
        self.assertEqual(sized["actions"], [])
        for bot in snap["bots"][:-1]:
            self.assertTrue(bot["present"], bot["id"])
            self.assertFalse(bot["has_state"], bot["id"])
            self.assertEqual(bot["positions"], [])
            self.assertEqual(bot["trades"], [])
        self.assertIn("Run one check", [a["label"] for a in snap["bots"][0]["actions"]])
        self.assertIn("Morning brief", [a["label"] for a in snap["bots"][1]["actions"]])
        self.assertIn("10.00", snap["limits_text"])
        self.assertIn("30.00", snap["limits_text"])

    def test_reads_state_and_blocks_entry_without_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "sports-gap-paper", "gap_bot.py"), STUB)
            _write(os.path.join(tmp, "sports-gap-paper", "state.json"), json.dumps({
                "cash": 11.0,
                "open": [{"contracts": 1, "team": "Bills", "ticker": "KX", "game": "Bills at Chiefs",
                          "cost": 3, "opened": "2026-10-30 12:00:00 CT"}] * 4,
                "closed": [{"team": "Bills", "game": "old", "exit": "settled", "pnl": -2.5,
                            "closed": "2026-10-30 13:00:00 CT"}],
            }))
            _write(os.path.join(tmp, "sports-gap-paper", "paper_trades.md"),
                   "| 2026-10-30 12:00:00 CT | NFL | Bills at Chiefs | | | | | | gap < 8 - no trade |\n")
            _write(os.path.join(tmp, "kalshi-sp500-paper", "bot.py"), STUB)
            _write(os.path.join(tmp, "kalshi-sp500-paper", "config.json"), json.dumps({"paper_mode": True}))
            snap = pimp_desk.snapshot(tmp)
            sports = snap["bots"][0]
            self.assertTrue(sports["has_state"])
            self.assertEqual(sports["cash"], 11.0)
            self.assertEqual(sports["open_count"], 4)
            self.assertEqual(sports["realized"], -2.5)
            self.assertEqual(len(sports["positions"]), 4)
            self.assertTrue(sports["trades"])
            self.assertTrue(snap["desk"]["gate"])
            blocked = pimp_desk.run_bot("sports-gap", "run", tmp)
            self.assertFalse(blocked["ok"])
            self.assertTrue(blocked.get("blocked"))
            self.assertFalse(os.path.exists(os.path.join(tmp, "sports-gap-paper", "ran")))
            settled = pimp_desk.run_bot("kalshi-sp", "settle", tmp)
            self.assertTrue(settled["ok"])
            with open(os.path.join(tmp, "kalshi-sp500-paper", "ran"), encoding="utf-8") as handle:
                self.assertIn("settle", handle.read())

    def test_child_env_drops_keys_and_reset_needs_the_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "sports-gap-paper", "gap_bot.py"), STUB)
            os.environ["KALSHI_API_KEY"] = "secret-key"
            os.environ["WALLET_SECRET"] = "seed"
            try:
                result = pimp_desk.run_bot("sports-gap", "run", tmp)
            finally:
                os.environ.pop("KALSHI_API_KEY", None)
                os.environ.pop("WALLET_SECRET", None)
            self.assertTrue(result["ok"], result)
            self.assertNotIn("KALSHI_API_KEY", result["summary"])
            self.assertNotIn("secret-key", result["summary"])
            self.assertNotIn("WALLET_SECRET", result["summary"])
            self.assertIn("PAPER_ONLY", result["summary"])
            self.assertFalse(pimp_desk.run_bot("sports-gap", "scan; rm -rf /", tmp)["ok"])
            _write(os.path.join(tmp, "sports-gap-paper", "gap_bot.py"), RESET_STUB)
            _write(os.path.join(tmp, "sports-gap-paper", "state.json"), "{}")
            _write(os.path.join(tmp, "sports-gap-paper", "paper_trades.md"), "log\n")
            reset = pimp_desk.reset_bot("sports-gap", tmp)
            self.assertTrue(reset["ok"], reset)
            self.assertFalse(os.path.exists(os.path.join(tmp, "sports-gap-paper", "state.json")))
            _write(os.path.join(tmp, "memecoin-paper", "bot.py"), STUB)
            _write(os.path.join(tmp, "memecoin-paper", "config.py"), "PAPER = False\n")
            refused = pimp_desk.run_bot("memecoin", "run", tmp)
            self.assertFalse(refused["ok"])
            self.assertFalse(os.path.exists(os.path.join(tmp, "memecoin-paper", "ran")))

    def test_save_roundtrip_and_unknown_bot(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, err = pimp_desk.save_settings({
                "stake_hi_min": "12", "stake_hi_max": "25", "stake_lo_max": "8",
                "daily_loss_stop": "20", "max_open_risk": "60", "max_open_positions": "2",
                "paper_only": False, "api_key": "nope",
            }, tmp)
            self.assertIsNone(err)
            self.assertTrue(cfg["paper_only"])
            with open(pimp_desk.config_path(tmp), encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertNotIn("api_key", saved)
            self.assertTrue(saved["paper_only"])
            loaded = pimp_desk.load_settings(tmp)
            self.assertEqual(loaded["stake_hi_min"], 12)
            self.assertEqual(loaded["max_open_positions"], 2)
            self.assertFalse(pimp_desk.run_bot("nope", "run", tmp)["ok"])
            self.assertFalse(pimp_desk.reset_bot("kalshi-sized", tmp)["ok"])


if __name__ == "__main__":
    unittest.main()
