"""Paper desk checks. No network, no Discord, no live orders."""

import datetime as dt
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
QUIET = """import sys
open('ran', 'a').write(' '.join(sys.argv[1:]) + '\\n')
print('no trade')
"""


def _tree(tmp, script):
    _write(os.path.join(tmp, "sports-gap-paper", "gap_bot.py"), script)
    _write(os.path.join(tmp, "kalshi-sp500-paper", "bot.py"), script)
    _write(os.path.join(tmp, "kalshi-sp500-paper", "config.json"), json.dumps({"paper_mode": True}))
    _write(os.path.join(tmp, "btc15m-signal", "btc15m_signal.py"), script)
    _write(os.path.join(tmp, "memecoin-paper", "bot.py"), script)
    _write(os.path.join(tmp, "memecoin-paper", "config.py"), "PAPER = True\n")


def _ran(tmp, folder):
    path = os.path.join(tmp, folder, "ran")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return handle.read()


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

    def test_schedule_stays_on_paper_actions(self):
        for slot in pimp_desk.AUTO:
            action = pimp_desk.ACTIONS[slot["id"]][slot["action"]]
            self.assertNotIn("--any-time", action["argv"])
            blob = " ".join(action["argv"]).lower()
            for word in ("api_key", "wallet", "order"):
                self.assertNotIn(word, blob)
        sports = next(s for s in pimp_desk.AUTO if s["id"] == "sports-gap")
        btc = next(s for s in pimp_desk.AUTO if s["id"] == "btc15m")
        self.assertEqual(sports["every_sec"], 300)
        self.assertEqual(btc["every_sec"], 300)
        brief = next(s for s in pimp_desk.AUTO if s["id"] == "kalshi-sp" and s["action"] == "brief")
        scan = next(s for s in pimp_desk.AUTO if s["id"] == "kalshi-sp" and s["action"] == "run")
        settle = next(s for s in pimp_desk.AUTO if s["id"] == "kalshi-sp" and s["action"] == "settle")
        self.assertEqual((brief["at_ct"], scan["at_ct"], settle["at_ct"]), ("08:00", "12:30", "16:00"))
        self.assertEqual(pimp_desk.ACTIONS["kalshi-sp"]["brief"]["argv"], ("bot.py", "brief", "--dry-run"))
        self.assertFalse(pimp_desk.ACTIONS["kalshi-sp"]["brief"]["entry"])
        self.assertTrue(pimp_desk.ACTIONS["kalshi-sp"]["run"]["entry"])
        self.assertEqual([s["at_ct"] for s in pimp_desk.AUTO if s["id"] == "memecoin"],
                         ["09:00", "15:00", "21:00"])
        text = pimp_desk.timer_text().lower()
        self.assertIn("every 5 minutes", text)
        self.assertIn("8:00", text)
        self.assertIn("12:30", text)
        self.assertIn("dry run", text)
        self.assertNotIn("guarantee", text)
        with tempfile.TemporaryDirectory() as tmp:
            def names(when):
                return [(s["id"], s["action"], s.get("at_ct")) for s in pimp_desk.due_slots(when, tmp)]
            morning = dt.datetime(2026, 10, 30, 8, 5, tzinfo=pimp_desk.CT)
            noon = dt.datetime(2026, 10, 30, 12, 30, tzinfo=pimp_desk.CT)
            late = dt.datetime(2026, 10, 30, 14, 56, tzinfo=pimp_desk.CT)
            night = dt.datetime(2026, 10, 30, 3, 0, tzinfo=pimp_desk.CT)
            saturday = dt.datetime(2026, 10, 31, 12, 30, tzinfo=pimp_desk.CT)
            self.assertIn(("kalshi-sp", "brief", "08:00"), names(morning))
            self.assertNotIn(("kalshi-sp", "run", "12:30"), names(morning))
            self.assertIn(("kalshi-sp", "run", "12:30"), names(noon))
            self.assertNotIn(("kalshi-sp", "brief", "08:00"), names(noon))
            self.assertIn(("memecoin", "run", "09:00"), names(noon))
            self.assertNotIn(("kalshi-sp", "run", "12:30"), names(late))
            self.assertEqual([row[0] for row in names(night)], ["sports-gap", "btc15m"])
            self.assertIn(("kalshi-sp", "run", "12:30"), names(saturday))
        snap = pimp_desk.snapshot(ROOT)
        self.assertIn("PAPER ONLY", snap["banner"])
        self.assertIn("timer", snap["banner"].lower())
        self.assertIn("every 5 minutes", snap["timer"].lower())

    def test_scheduler_once_places_no_orders(self):
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, QUIET)
            noon = dt.datetime(2026, 10, 30, 12, 30, tzinfo=pimp_desk.CT)
            rows = pimp_desk.run_scheduled(noon, tmp)
            by = {(row["bot"], row["action"]): row for row in rows}
            self.assertEqual(set(by), {
                ("sports-gap", "run"), ("btc15m", "run"), ("kalshi-sp", "run"), ("memecoin", "run"),
            })
            for row in rows:
                self.assertTrue(row["ok"], row)
                self.assertFalse(row["blocked"])
                self.assertIn("no trade", row["summary"])
            self.assertEqual(_ran(tmp, "sports-gap-paper"), "\n")
            self.assertEqual(_ran(tmp, "btc15m-signal"), "\n")
            self.assertEqual(_ran(tmp, "kalshi-sp500-paper"), "scan\n")
            self.assertEqual(_ran(tmp, "memecoin-paper"), "\n")
            for folder in ("sports-gap-paper", "btc15m-signal", "kalshi-sp500-paper", "memecoin-paper"):
                text = _ran(tmp, folder).lower()
                for word in ("order", "wallet", "api_key", "any-time", "live"):
                    self.assertNotIn(word, text, folder)
            self.assertEqual(pimp_desk.run_scheduled(noon, tmp), [])
            self.assertEqual(_ran(tmp, "kalshi-sp500-paper"), "scan\n")
            later = dt.datetime(2026, 10, 30, 12, 35, tzinfo=pimp_desk.CT)
            more = pimp_desk.run_scheduled(later, tmp)
            self.assertEqual({(row["bot"], row["action"]) for row in more},
                             {("sports-gap", "run"), ("btc15m", "run")})
            self.assertTrue(all(row["ok"] for row in more))
            self.assertEqual(_ran(tmp, "kalshi-sp500-paper"), "scan\n")
            self.assertEqual(_ran(tmp, "memecoin-paper"), "\n")
            self.assertEqual(_ran(tmp, "sports-gap-paper"), "\n\n")

    def test_morning_brief_is_dry_run_and_limits_skip_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, QUIET)
            morning = dt.datetime(2026, 10, 30, 8, 5, tzinfo=pimp_desk.CT)
            rows = pimp_desk.run_scheduled(morning, tmp)
            kalshi = [row for row in rows if row["bot"] == "kalshi-sp"]
            self.assertEqual([row["action"] for row in kalshi], ["brief"])
            self.assertTrue(kalshi[0]["ok"], kalshi[0])
            self.assertEqual(_ran(tmp, "kalshi-sp500-paper"), "brief --dry-run\n")
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, QUIET)
            _write(os.path.join(tmp, "sports-gap-paper", "state.json"), json.dumps({
                "cash": 11.0,
                "open": [{"contracts": 1, "team": "Bills", "ticker": "KX", "game": "Bills at Chiefs",
                          "cost": 3, "opened": "2026-10-30 12:00:00 CT"}] * 4,
                "closed": [],
            }))
            noon = dt.datetime(2026, 10, 30, 12, 30, tzinfo=pimp_desk.CT)
            rows = pimp_desk.run_scheduled(noon, tmp)
            by = {(row["bot"], row["action"]): row for row in rows}
            self.assertTrue(by[("sports-gap", "run")]["blocked"])
            self.assertTrue(by[("kalshi-sp", "run")]["blocked"])
            self.assertTrue(by[("memecoin", "run")]["blocked"])
            self.assertTrue(by[("btc15m", "run")]["ok"])
            self.assertFalse(by[("btc15m", "run")]["blocked"])
            self.assertIn("Max open", by[("sports-gap", "run")]["error"])
            self.assertIsNone(_ran(tmp, "sports-gap-paper"))
            self.assertIsNone(_ran(tmp, "kalshi-sp500-paper"))
            self.assertIsNone(_ran(tmp, "memecoin-paper"))
            self.assertEqual(_ran(tmp, "btc15m-signal"), "\n")
            self.assertEqual(pimp_desk.run_scheduled(noon, tmp), [])

    def test_scheduler_keeps_a_crashed_script_a_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, "import sys\nsys.exit(1)\n")
            night = dt.datetime(2026, 10, 30, 3, 0, tzinfo=pimp_desk.CT)
            rows = pimp_desk.run_scheduled(night, tmp)
            self.assertEqual(sorted((row["bot"], row["ok"]) for row in rows),
                             [("btc15m", False), ("sports-gap", False)])
            self.assertTrue(all(not row["blocked"] for row in rows))


if __name__ == "__main__":
    unittest.main()
