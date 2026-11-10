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
    _write(os.path.join(tmp, "kalshi-sp500-paper", "calendar.json"), "{}\n")
    _write(os.path.join(tmp, "kalshi-sized-paper", "bot.py"), script)
    _write(os.path.join(tmp, "kalshi-sized-paper", "config.json"), json.dumps({"paper_mode": True}))
    _write(os.path.join(tmp, "kalshi-sized-paper", "calendar.json"), "{}\n")
    _write(os.path.join(tmp, "btc15m-signal", "btc15m_signal.py"), script)
    _write(os.path.join(tmp, "commodity-15m-paper", "bot.py"), script)
    _write(os.path.join(tmp, "memecoin-paper", "bot.py"), script)
    _write(os.path.join(tmp, "memecoin-paper", "config.py"), "PAPER = True\n")
    _write(os.path.join(tmp, "coinbase-spot-paper", "bot.py"), script)
    _write(os.path.join(tmp, "coinbase-spot-paper", "config.json"),
           json.dumps({"paper_only": True, "live_orders": False}))
    _write(os.path.join(tmp, "btc-carry-paper", "bot.py"), script)
    _write(os.path.join(tmp, "btc-carry-paper", "config.json"),
           json.dumps({"paper_only": True, "live_orders": False}))


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


def _checkout_snapshot():
    """Read this checkout without binding it to a host volume."""
    previous = os.environ.get("PAPER_KEEP_SETTLEMENTS")
    os.environ["PAPER_KEEP_SETTLEMENTS"] = "0"
    try:
        return pimp_desk.snapshot(ROOT)
    finally:
        if previous is None:
            os.environ.pop("PAPER_KEEP_SETTLEMENTS", None)
        else:
            os.environ["PAPER_KEEP_SETTLEMENTS"] = previous


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
            "stake_hi_min": 5, "stake_hi_max": 150, "stake_lo_max": 10,
            "daily_loss_stop": 50, "max_open_risk": 100, "max_open_positions": 4,
        })
        self.assertIsNone(bad)
        self.assertTrue(err)
        cfg, err = pimp_desk.parse_settings({
            "stake_hi_min": 20, "stake_hi_max": 80, "stake_lo_max": 20,
            "daily_loss_stop": 40, "max_open_risk": 80, "max_open_positions": 3,
        })
        self.assertIsNone(err)
        self.assertTrue(cfg["paper_only"])
        self.assertEqual(cfg["stake_hi_prob"], 0.8)
        self.assertEqual(cfg["stake_lo_max"], 20)

    def test_checkout_snapshot_is_empty_and_paper(self):
        snap = _checkout_snapshot()
        self.assertTrue(snap["paper_only"])
        self.assertIn("PAPER ONLY", snap["banner"])
        self.assertEqual([b["id"] for b in snap["bots"]],
                         ["sports-gap", "kalshi-sp", "btc15m", "commodity-15m", "memecoin", "kalshi-sized", "coinbase-spot", "btc-carry", "sports-sharp-lag", "fed-watch", "wall-street"])
        sized = next(b for b in snap["bots"] if b["id"] == "kalshi-sized")
        coinbase = next(b for b in snap["bots"] if b["id"] == "coinbase-spot")
        self.assertTrue(coinbase["shadow_only"])
        self.assertEqual(coinbase["book_id"], "coinbase")
        self.assertTrue(sized["present"])
        self.assertTrue(sized["actions"])
        expected_cash = {
            "sports-gap": 100.0,
            "kalshi-sp": 500.0,
            "btc15m": 100.0,
            "commodity-15m": 100.0,
            "memecoin": 100.0,
            "kalshi-sized": 500.0,
            "coinbase-spot": 500.0,
            "btc-carry": 500.0,
            "sports-sharp-lag": None,
            "fed-watch": None,
            "wall-street": 0.0,
        }
        for bot in snap["bots"]:
            self.assertTrue(bot["present"], bot["id"])
            self.assertTrue(bot["has_state"], bot["id"])
            self.assertEqual(bot["cash"], expected_cash[bot["id"]], bot["id"])
            self.assertEqual(bot["positions"], [])
            self.assertEqual(bot["trades"], [])
            plans = bot["plans"]
            self.assertTrue(plans["buy"], bot["id"])
            self.assertTrue(plans["sell"], bot["id"])
            self.assertTrue(plans["failsafes"], bot["id"])
            self.assertIn(plans["exit_quality"], ("strong", "partial", "weak"), bot["id"])
            self.assertIn("gates_hit", bot)
            self.assertNotIn("absent", bot["gates_hit"], bot["id"])
        self.assertEqual(sized["plans"]["exit_quality"], "partial")
        self.assertTrue(sized["plans"]["entry_gated"])
        self.assertTrue(next(b for b in snap["bots"] if b["id"] == "btc15m")["plans"]["entry_gated"])
        self.assertTrue(next(b for b in snap["bots"] if b["id"] == "sports-gap")["plans"]["entry_gated"])
        self.assertEqual(snap["desk"]["ops"]["strong_exits"], ["memecoin"])
        # ops.weak_exits includes partial books (sports / kalshi / btc).
        self.assertIn("btc15m", snap["desk"]["ops"]["weak_exits"])
        self.assertIn("sports-gap", snap["desk"]["ops"]["entry_gated_bots"])
        self.assertIn("btc15m", snap["desk"]["ops"]["entry_gated_bots"])
        self.assertIn("kalshi-sized", snap["desk"]["ops"]["entry_gated_bots"])
        self.assertIn("kalshi-sized", snap["desk"]["ops"]["weak_exits"])
        self.assertTrue(snap["roi_system"]["ok"])
        self.assertTrue(snap["roi_system"]["paper_only"])
        self.assertEqual(snap["roi_system"]["version"], 2)
        self.assertTrue(snap["desk"]["ops"]["roi_ok"])
        self.assertIn("venue_min_edge", snap["limits"])
        self.assertEqual(snap["limits"]["sizing"], "kelly_lite")
        btc = next(b for b in snap["bots"] if b["id"] == "btc15m")
        self.assertEqual(btc["plans"]["exit_quality"], "partial")
        self.assertTrue(any("KXETH15M" in line or "parlay" in line.lower() for line in btc["plans"]["buy"]))
        self.assertIn("crypto_history", snap["desk"])
        self.assertIn("crypto_parlays", snap["desk"])
        self.assertIn("adapt", snap["desk"])
        self.assertTrue(snap["desk"]["adapt"].get("paper_only"))
        self.assertIn("KXPALLADIUM15M", snap["desk"]["adapt"].get("series_15m") or [])
        self.assertIn("kalshi_tape", snap["desk"])
        self.assertTrue(snap["desk"]["kalshi_tape"].get("paper_only"))
        self.assertIn("KXBTC15M", snap["desk"]["kalshi_tape"].get("tracked_series") or [])
        self.assertIn("brain", snap["desk"])
        self.assertTrue(snap["desk"]["brain"].get("paper_only"))
        self.assertIn("rank", snap["desk"]["brain"].get("loop") or [])
        self.assertIn("expectancy_n", btc)
        self.assertIn("starved", btc)
        self.assertEqual(btc["sizing_mode"], "kelly_lite")
        self.assertIn("shadow_count", snap["desk"]["ops"])
        btc_comp = next(c for c in snap["roi_system"]["compliance"] if c["bot"] == "btc15m")
        self.assertTrue(btc_comp["ok"])
        self.assertTrue(btc_comp["entry_gated"])
        self.assertTrue(pimp_desk.ACTIONS["btc15m"]["run"]["entry"])
        self.assertEqual(snap["desk"]["curve"], [])
        self.assertEqual(snap["desk"]["equity"], [])
        self.assertEqual(snap["desk"]["pace_line"], "0 of 12 this hour")
        self.assertFalse(snap["desk"]["pace_loosened"])
        self.assertIn("does not waive", snap["desk"]["pace_note"])
        self.assertEqual(snap["desk"]["cash"], 1400.0)
        self.assertIn("Run one check", [a["label"] for a in snap["bots"][0]["actions"]])
        self.assertIn("Morning brief", [a["label"] for a in snap["bots"][1]["actions"]])
        self.assertIn("20.00", snap["limits_text"])
        self.assertIn("100.00", snap["limits_text"])
        self.assertIn("do not waive", snap["limits_text"])
        self.assertNotIn("without the strict edge", snap["limits_text"])
        self.assertIn("150.00", snap["limits_text"])
        self.assertIn("0.06", snap["limits_text"])
        self.assertIn("0.08", snap["limits_text"])

    def test_reads_state_and_blocks_entry_without_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "sports-gap-paper", "gap_bot.py"), STUB)
            _write(os.path.join(tmp, "sports-gap-paper", "state.json"), json.dumps({
                "cash": 11.0,
                "open": [{"contracts": 1, "team": "Bills", "ticker": "KX", "game": "Bills at Chiefs",
                          "cost": 3, "opened": "2026-10-30 12:00:00 CT"}] * pimp_desk.DEFAULTS["max_open_positions"],
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
            self.assertEqual(sports["open_count"], pimp_desk.DEFAULTS["max_open_positions"])
            self.assertEqual(sports["realized"], -2.5)
            self.assertEqual(len(sports["positions"]), pimp_desk.DEFAULTS["max_open_positions"])
            self.assertTrue(sports["trades"])
            self.assertTrue(snap["desk"]["gate"])
            # Sports still runs exits when the desk gate is hit; new buys stay off.
            managed = pimp_desk.run_bot("sports-gap", "run", tmp)
            self.assertTrue(managed["ok"])
            self.assertTrue(managed.get("entries_blocked"))
            self.assertFalse(managed.get("blocked"))
            self.assertTrue(os.path.exists(os.path.join(tmp, "sports-gap-paper", "ran")))
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

    def test_child_env_passes_block_reason_with_entries(self):
        """Post-#550 Prefer-1: manage-when-gated must densify real gate, not bland ENTRIES=1."""
        env = pimp_desk._child_env(
            block_entries=True,
            block_reason="ruin drill soft: new entries off. Settles/exits still run under soft.",
        )
        self.assertEqual(env.get("DESK_BLOCK_ENTRIES"), "1")
        self.assertIn("ruin drill", env.get("DESK_BLOCK_REASON", "").lower())
        self.assertEqual(env.get("PAPER_ONLY"), "1")
        # No reason → do not invent a bland DESK_BLOCK_REASON key.
        bare = pimp_desk._child_env(block_entries=True)
        self.assertEqual(bare.get("DESK_BLOCK_ENTRIES"), "1")
        self.assertNotIn("DESK_BLOCK_REASON", bare)

    def test_save_roundtrip_and_unknown_bot(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, err = pimp_desk.save_settings({
                "stake_hi_min": "25", "stake_hi_max": "80", "stake_lo_max": "20",
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
            self.assertEqual(loaded["stake_hi_min"], 25)
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
        meme = next(s for s in pimp_desk.AUTO if s["id"] == "memecoin")
        self.assertEqual(sports["every_sec"], 180)  # tip-soon + dual lanes
        self.assertEqual(btc["every_sec"], 60)
        self.assertEqual(meme["every_sec"], 180)
        brief = next(s for s in pimp_desk.AUTO if s["id"] == "kalshi-sp" and s["action"] == "brief")
        scans = [s for s in pimp_desk.AUTO if s["id"] == "kalshi-sp" and s["action"] == "run"]
        settles = [s for s in pimp_desk.AUTO if s["id"] == "kalshi-sp" and s["action"] == "settle"]
        self.assertEqual(brief["at_ct"], "08:00")
        self.assertEqual([s["at_ct"] for s in scans], ["12:05", "13:05", "13:40"])
        self.assertEqual(scans[2]["until_ct"], "14:00")
        self.assertEqual([s["at_ct"] for s in settles], ["13:00", "16:00"])
        self.assertEqual(settles[0]["until_ct"], "15:55")
        self.assertEqual(pimp_desk.ACTIONS["kalshi-sp"]["brief"]["argv"], ("bot.py", "brief", "--dry-run"))
        self.assertFalse(pimp_desk.ACTIONS["kalshi-sp"]["brief"]["entry"])
        self.assertTrue(pimp_desk.ACTIONS["kalshi-sp"]["run"]["entry"])
        self.assertEqual([s for s in pimp_desk.AUTO if s["id"] == "memecoin" and "at_ct" in s], [])
        text = pimp_desk.timer_text().lower()
        self.assertIn("every 3 minutes", text)
        self.assertIn("60 seconds", text)
        self.assertIn("90 seconds", text)
        self.assertIn("trade tape", text)
        self.assertIn("stop-bleed", text)
        self.assertIn("dual lanes", text)
        self.assertIn("8:00", text)
        self.assertIn("12:05", text)
        self.assertIn("13:05", text)
        self.assertIn("13:40", text)
        self.assertNotIn("14:20", text)
        self.assertIn("dry run", text)
        self.assertNotIn("guarantee", text)
        with tempfile.TemporaryDirectory() as tmp:
            def names(when):
                return [(s["id"], s["action"], s.get("at_ct")) for s in pimp_desk.due_slots(when, tmp)]
            morning = dt.datetime(2026, 10, 30, 8, 5, tzinfo=pimp_desk.CT)
            noon = dt.datetime(2026, 10, 30, 12, 10, tzinfo=pimp_desk.CT)
            mid = dt.datetime(2026, 10, 30, 13, 10, tzinfo=pimp_desk.CT)
            third_slot = dt.datetime(2026, 10, 30, 13, 45, tzinfo=pimp_desk.CT)
            late = dt.datetime(2026, 10, 30, 14, 56, tzinfo=pimp_desk.CT)
            night = dt.datetime(2026, 10, 30, 3, 0, tzinfo=pimp_desk.CT)
            saturday = dt.datetime(2026, 10, 31, 12, 10, tzinfo=pimp_desk.CT)
            self.assertIn(("kalshi-sp", "brief", "08:00"), names(morning))
            self.assertNotIn(("kalshi-sp", "run", "12:05"), names(morning))
            self.assertIn(("kalshi-sp", "run", "12:05"), names(noon))
            self.assertIn(("kalshi-sp", "run", "13:05"), names(mid))
            self.assertIn(("kalshi-sp", "run", "13:40"), names(third_slot))
            self.assertNotIn(("kalshi-sp", "brief", "08:00"), names(noon))
            self.assertIn(("memecoin", "run", None), names(noon))
            self.assertNotIn(("kalshi-sp", "run", "12:05"), names(late))
            self.assertEqual([row[0] for row in names(night)],
                             ["sports-gap", "btc15m", "commodity-15m", "memecoin", "coinbase-spot", "btc-carry"])
            self.assertNotIn(("kalshi-sized", "settle", "13:00"), names(night))
            self.assertIn(("kalshi-sp", "run", "12:05"), names(saturday))
            saturday_scan = dt.datetime(2026, 10, 31, 12, 35, tzinfo=pimp_desk.CT)
            self.assertIn(("kalshi-sized", "run", "12:05"), names(saturday_scan))
        snap = _checkout_snapshot()
        self.assertIn("PAPER ONLY", snap["banner"])
        self.assertIn("timer", snap["banner"].lower())
        self.assertIn("stop-bleed", snap["timer"].lower())
        self.assertIn("every 3 minutes", snap["timer"].lower())

    def test_scheduler_once_places_no_orders(self):
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, QUIET)
            noon = dt.datetime(2026, 10, 30, 12, 10, tzinfo=pimp_desk.CT)
            rows = pimp_desk.run_scheduled(noon, tmp)
            by = {(row["bot"], row["action"]): row for row in rows}
            self.assertEqual(set(by), {
                ("sports-gap", "run"), ("btc15m", "run"), ("btc15m", "shadow"),
                ("commodity-15m", "run"), ("kalshi-sp", "run"), ("kalshi-sized", "run"),
                ("memecoin", "run"), ("coinbase-spot", "run"), ("btc-carry", "run"),
                ("shadow-tick", "auto"),
            })
            for row in rows:
                if row["bot"] == "shadow-tick":
                    self.assertTrue(row["ok"], row)
                    continue
                self.assertTrue(row["ok"], row)
                self.assertFalse(row["blocked"])
                self.assertIn("no trade", row["summary"])
            # Slot run plus shadow-tick smoke. Counts stay above the slot itself.
            self.assertGreaterEqual((_ran(tmp, "sports-gap-paper") or "").count("\n"), 1)
            self.assertGreaterEqual((_ran(tmp, "btc15m-signal") or "").count("\n"), 2)
            self.assertTrue((_ran(tmp, "kalshi-sp500-paper") or "").startswith("scan\n"))
            self.assertTrue((_ran(tmp, "kalshi-sized-paper") or "").startswith("scan\n"))
            self.assertGreaterEqual((_ran(tmp, "memecoin-paper") or "").count("\n"), 1)
            self.assertGreaterEqual((_ran(tmp, "coinbase-spot-paper") or "").count("\n"), 1)
            self.assertGreaterEqual((_ran(tmp, "btc-carry-paper") or "").count("\n"), 1)
            for folder in (
                "sports-gap-paper", "btc15m-signal", "kalshi-sp500-paper",
                "kalshi-sized-paper", "memecoin-paper", "coinbase-spot-paper",
                "btc-carry-paper",
            ):
                text = _ran(tmp, folder).lower()
                for word in ("order", "wallet", "api_key", "any-time", "live"):
                    self.assertNotIn(word, text, folder)
            again = pimp_desk.run_scheduled(noon, tmp)
            self.assertTrue(all(row["bot"] == "shadow-tick" for row in again))
            self.assertTrue((_ran(tmp, "kalshi-sp500-paper") or "").startswith("scan\n"))
            later = dt.datetime(2026, 10, 30, 12, 35, tzinfo=pimp_desk.CT)
            more = pimp_desk.run_scheduled(later, tmp)
            # Sized already took its daily scan at noon; interval bots still fire.
            got = {(row["bot"], row["action"]) for row in more}
            self.assertTrue({
                ("sports-gap", "run"), ("btc15m", "run"), ("btc15m", "shadow"),
                ("commodity-15m", "run"), ("memecoin", "run"), ("coinbase-spot", "run"),
                ("btc-carry", "run"),
            }.issubset(got))
            self.assertTrue(got <= {
                ("sports-gap", "run"), ("btc15m", "run"), ("btc15m", "shadow"),
                ("commodity-15m", "run"), ("memecoin", "run"), ("coinbase-spot", "run"),
                ("btc-carry", "run"),
                ("shadow-tick", "auto"),
            })
            self.assertTrue(all(row["ok"] for row in more))
            self.assertTrue((_ran(tmp, "kalshi-sp500-paper") or "").startswith("scan\n"))
            self.assertEqual((_ran(tmp, "kalshi-sized-paper") or "").count("scan"), 1)
            # Memecoin / sports re-fire on the shorter interval.
            self.assertGreaterEqual((_ran(tmp, "memecoin-paper") or "").count("\n"), 2)
            self.assertGreaterEqual((_ran(tmp, "sports-gap-paper") or "").count("\n"), 2)

    def test_morning_brief_is_dry_run_and_limits_skip_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, QUIET)
            morning = dt.datetime(2026, 10, 30, 8, 5, tzinfo=pimp_desk.CT)
            rows = pimp_desk.run_scheduled(morning, tmp)
            kalshi = [row for row in rows if row["bot"] == "kalshi-sp"]
            self.assertEqual([row["action"] for row in kalshi], ["brief"])
            self.assertTrue(kalshi[0]["ok"], kalshi[0])
            # Shadow-tick also smokes an INX settle. The morning slot itself is only the brief.
            ran = _ran(tmp, "kalshi-sp500-paper") or ""
            self.assertTrue(ran.startswith("brief --dry-run\n"), ran)
            self.assertNotIn("scan", ran)
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, QUIET)
            _write(os.path.join(tmp, "sports-gap-paper", "state.json"), json.dumps({
                "cash": 11.0,
                "open": [{"contracts": 1, "team": "Bills", "ticker": "KX", "game": "Bills at Chiefs",
                          "cost": 3, "opened": "2026-10-30 12:00:00 CT"}] * pimp_desk.DEFAULTS["max_open_positions"],
                "closed": [],
            }))
            noon = dt.datetime(2026, 10, 30, 12, 10, tzinfo=pimp_desk.CT)
            rows = pimp_desk.run_scheduled(noon, tmp)
            by = {(row["bot"], row["action"]): row for row in rows}
            # Kalshi scan stays hard-blocked. Sports/BTC/memecoin still run exits
            # with DESK_BLOCK_ENTRIES=1 so a full book can unwind.
            self.assertTrue(by[("kalshi-sp", "run")]["blocked"])
            self.assertFalse(by[("sports-gap", "run")].get("blocked"))
            self.assertTrue(by[("sports-gap", "run")]["ok"])
            self.assertTrue(by[("sports-gap", "run")].get("entries_blocked"))
            self.assertFalse(by[("memecoin", "run")].get("blocked"))
            self.assertTrue(by[("memecoin", "run")]["ok"])
            self.assertTrue(by[("btc15m", "run")]["ok"])
            self.assertTrue(by[("btc15m", "run")].get("entries_blocked"))
            self.assertIn("entry_gate", by[("sports-gap", "run")]["summary"].lower())
            self.assertIsNotNone(_ran(tmp, "sports-gap-paper"))
            # Blocked scan does not start. Shadow-tick may still smoke settle.
            kalshi_ran = _ran(tmp, "kalshi-sp500-paper") or ""
            self.assertNotIn("scan", kalshi_ran)
            self.assertIsNotNone(_ran(tmp, "memecoin-paper"))
            self.assertIsNotNone(_ran(tmp, "btc15m-signal"))
            again = pimp_desk.run_scheduled(noon, tmp)
            self.assertTrue(all(row["bot"] == "shadow-tick" for row in again))

    def test_scheduler_keeps_a_crashed_script_a_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, "import sys\nsys.exit(1)\n")
            night = dt.datetime(2026, 10, 30, 3, 0, tzinfo=pimp_desk.CT)
            rows = pimp_desk.run_scheduled(night, tmp)
            self.assertEqual(sorted((row["bot"], row["action"], row["ok"]) for row in rows),
                             [("btc-carry", "run", False),
                              ("btc15m", "run", False), ("btc15m", "shadow", False),
                              ("coinbase-spot", "run", False),
                              ("commodity-15m", "run", False),
                              ("desk", "midnight-reload", True),
                              ("memecoin", "run", False),
                              ("shadow-tick", "auto", True),
                              ("sports-gap", "run", False)])
            self.assertTrue(all(not row["blocked"] for row in rows))


    def test_new_gates_stake_stop_and_staff(self):
        over, err = pimp_desk.parse_settings({
            "stake_hi_min": 10, "stake_hi_max": 101, "stake_lo_max": 9,
            "daily_loss_stop": 50, "max_open_risk": 100, "max_open_positions": 4,
        })
        self.assertIsNone(over)
        self.assertTrue(err)
        zero, err = pimp_desk.parse_settings({
            "stake_hi_min": 20, "stake_hi_max": 100, "stake_lo_max": 20,
            "daily_loss_stop": 0, "max_open_risk": 100, "max_open_positions": 4,
        })
        self.assertIsNone(zero)
        self.assertIn("zero", err.lower())
        cfg, err = pimp_desk.parse_settings({
            "stake_hi_min": 20, "stake_hi_max": 100, "stake_lo_max": 20,
            "daily_loss_stop": 50, "max_open_risk": 100, "max_open_positions": 4,
        })
        self.assertIsNone(err)
        self.assertIn("saved max", pimp_desk.stake_allowed(101, 0.9, cfg))
        self.assertIn("saved max", pimp_desk.stake_allowed(20.01, 0.5, cfg))
        self.assertEqual(pimp_desk.stake_allowed(20, 0.5, cfg), "")
        self.assertEqual(pimp_desk.stake_allowed(100, 0.95, cfg), "")
        self.assertFalse(pimp_desk.role_can("", "view"))
        self.assertFalse(pimp_desk.role_can("mod", "run"))
        self.assertFalse(pimp_desk.role_can("admin", "save"))
        self.assertFalse(pimp_desk.role_can("owner", "run"))
        self.assertTrue(pimp_desk.role_can("owner", "save"))
        self.assertTrue(pimp_desk.role_can("developer", "run"))
        self.assertTrue(pimp_desk.role_can("mod", "view"))
        self.assertIn("Staff only", pimp_desk.auth_error("guest", "view"))
        self.assertIn("Developer", pimp_desk.auth_error("mod", "run"))
        self.assertTrue(pimp_desk.confirm_reset("nope"))
        self.assertEqual(pimp_desk.confirm_reset("RESET PAPER"), "")
        self.assertFalse(pimp_desk.live_switch_status()["built"])

    def test_under_eighty_buys_near_twenty_not_one_contract(self):
        self.assertEqual(pimp_desk.DEFAULTS["pace_min"], 6)
        self.assertEqual(pimp_desk.DEFAULTS["pace_target"], 12)
        self.assertEqual(pimp_desk.PACE_MIN, 6)
        self.assertEqual(pimp_desk.PACE_TARGET, 12)
        self.assertEqual(pimp_desk.paper_stake_dollars(0.657), 20.0)
        self.assertEqual(pimp_desk.paper_stake_dollars(0.799), 20.0)
        self.assertEqual(pimp_desk.paper_stake_dollars(0.80), 20.0)
        self.assertEqual(pimp_desk.paper_stake_dollars(0.90), 60.0)
        self.assertEqual(pimp_desk.paper_stake_dollars(1), 100.0)
        per = 0.67 + 0.02
        n = pimp_desk.contracts_for_stake(per, pimp_desk.paper_stake_dollars(0.657))
        cost = round(n * per, 2)
        self.assertEqual((n, cost), (28, 19.32))
        self.assertGreater(n, 1)
        self.assertEqual(pimp_desk.contracts_for_stake(5, 1), 0)
        starter = {"cash": 14, "open": [], "closed": []}
        self.assertTrue(pimp_desk.lift_sports_starter(starter))
        self.assertEqual(starter["cash"], 100.0)
        kept = {"cash": 14, "open": [], "closed": [{"pnl": -1}]}
        self.assertFalse(pimp_desk.lift_sports_starter(kept))
        self.assertEqual(kept["cash"], 14)
        other = {"cash": 20, "open": [], "closed": []}
        self.assertFalse(pimp_desk.lift_sports_starter(other))
        self.assertEqual(other["cash"], 20)
        strong = pimp_desk.contracts_for_stake(per, 100)
        self.assertGreater(strong, 1)
        self.assertLessEqual(round(strong * per, 2), 100)
        self.assertGreater(round(strong * per, 2), 100 - per)

    def test_sports_model_stake_lands_near_twenty(self):
        import importlib.util
        path = os.path.join(ROOT, "sports-gap-paper", "gap_bot.py")
        spec = importlib.util.spec_from_file_location("gap_bot_stake", path)
        gap = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gap)
        self.assertEqual(gap.START_BANKROLL, 100.0)
        self.assertNotIn("stake_for_gap", gap.__dict__)
        self.assertEqual(gap.stake_for_model(0.657, pimp_desk), 20.0)
        self.assertEqual(gap.stake_for_model(0.80, pimp_desk), 20.0)
        # Phase 1 tower budgets soft-cap sports-gap to 35% of desk $100 → $35.
        sports_cap = round(100.0 * float(pimp_desk.DEFAULTS["tower_risk_budgets"]["sports-gap"]), 2)
        self.assertEqual(gap.stake_for_model(0.90, pimp_desk), min(60.0, sports_cap))
        self.assertEqual(gap.stake_for_model(1, pimp_desk), min(100.0, sports_cap))
        per = 0.55 + gap.fee(0.55)
        count = pimp_desk.contracts_for_stake(per, gap.stake_for_model(0.62, pimp_desk))
        cost = round(count * per, 2)
        self.assertGreater(count, 1)
        self.assertLessEqual(cost, 20.0)
        self.assertGreater(cost, 20.0 - per)
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, QUIET)
            account = os.path.join(tmp, "sports-gap-paper", "state.json")
            _write(account, json.dumps({"cash": 14, "open": [], "closed": [], "runs": 2}))
            pimp_desk.ensure_paper_accounts(tmp)
            with open(account, encoding="utf-8") as handle:
                lifted = json.load(handle)
            self.assertEqual(lifted["cash"], 100.0)
            self.assertEqual(lifted["closed"], [])

    def test_prices_are_ask_fee_and_unknown(self):
        # Board fill includes +1¢ realism tax by default; raw ask still available untaxed.
        self.assertEqual(pimp_desk.paper_fill(0.40, 0.42), 0.43)
        self.assertEqual(pimp_desk.paper_fill(0.40, 0.42, adverse=0.0), 0.42)
        self.assertIsNone(pimp_desk.paper_fill(0.40, None))
        self.assertNotEqual(pimp_desk.paper_fill(0.40, 0.50, adverse=0.0), 0.45)
        edge = pimp_desk.edge_after_fee(0.60, 0.50)
        self.assertLess(edge, 0.60 - 0.50)
        self.assertEqual(pimp_desk.price_age_flag(""), "unknown")
        old = "2020-01-01T00:00:00+00:00"
        self.assertEqual(pimp_desk.price_age_flag(old), "stale")
        self.assertEqual(pimp_desk.disagree_flag(0.70, 0.40), "ESPN and Kalshi disagree")
        self.assertEqual(pimp_desk.disagree_flag(None, 0.40), "")
        self.assertEqual(pimp_desk.settle_call("in", 1, 0), "wait")
        self.assertEqual(pimp_desk.settle_call("final", 1, 1), "hold")
        self.assertEqual(pimp_desk.settle_call("final", 2, 1), "settle")
        self.assertEqual(pimp_desk.source_status(0, ""), "no games")
        self.assertEqual(pimp_desk.source_status(0, "down"), "api down")
        calls = {"n": 0}

        def opener(_url):
            calls["n"] += 1
            if calls["n"] < 3:
                raise TimeoutError("nope")
            return {"ok": True}

        data, err = pimp_desk.public_get("https://example.test/quote", opener, tries=3)
        self.assertEqual(data, {"ok": True})
        self.assertEqual(err, "")
        self.assertEqual(calls["n"], 3)
        data, err = pimp_desk.public_get("https://example.test/quote", lambda _url: None, tries=2)
        self.assertIsNone(data)
        self.assertEqual(err, "failed")
        self.assertNotIn("example.test", err)
        night = dt.datetime(2026, 10, 30, 23, 30, tzinfo=pimp_desk.CT)
        day = dt.datetime(2026, 10, 30, 12, 0, tzinfo=pimp_desk.CT)
        self.assertTrue(pimp_desk.in_quiet(night))
        self.assertFalse(pimp_desk.in_quiet(day))
        self.assertIn("Central", pimp_desk.central_text(day))
        self.assertFalse(pimp_desk.page_has_key("PAPER ONLY. There is no wallet connect on this desk."))
        self.assertTrue(pimp_desk.page_has_key("api_key = 'secret-value'"))

    def test_half_written_state_calendar_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "sports-gap-paper", "gap_bot.py"), "print('x')\n")
            _write(os.path.join(tmp, "sports-gap-paper", "state.json"), "{")
            snap = pimp_desk.snapshot(tmp)
            sports = snap["bots"][0]
            self.assertIn("half-written", sports["read_error"])
            self.assertIn("No paper trades yet", sports["idle_copy"])
            self.assertIn("No edge", sports["idle_copy"])
            _write(os.path.join(tmp, "kalshi-sp500-paper", "bot.py"), QUIET)
            _write(os.path.join(tmp, "kalshi-sp500-paper", "config.json"), json.dumps({"paper_mode": True}))
            ran = pimp_desk.run_bot("kalshi-sp", "run", tmp)
            self.assertFalse(ran.get("blocked"))
            self.assertIn("News calendar", ran.get("warning") or "")
            self.assertTrue(ran.get("ok"), ran)
            self.assertTrue(os.path.exists(os.path.join(tmp, "kalshi-sp500-paper", "ran")))
            blob = pimp_desk.export_xlsx(tmp)
            self.assertTrue(blob.startswith(b"PK"))
            cfg, err = pimp_desk.save_settings({
                "stake_hi_min": "20", "stake_hi_max": "60", "stake_lo_max": "20",
                "daily_loss_stop": "25", "max_open_risk": "40", "max_open_positions": "2",
            }, tmp, who="Ada")
            self.assertIsNone(err, err)
            mode = os.stat(pimp_desk.config_path(tmp)).st_mode & 0o777
            self.assertEqual(mode, 0o600)
            rows = pimp_desk.audit_rows(tmp)
            self.assertTrue(any(row.get("who") == "Ada" for row in rows))
            self.assertTrue(any("limits" in str(row.get("what")).lower() for row in rows))
            self.assertIn("status_line", snap["desk"])
            self.assertIn("Last check", snap["desk"]["status_line"])

    def test_open_cards_and_closed_rows_keep_every_fact(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "sports-gap-paper", "gap_bot.py"), QUIET)
            _write(os.path.join(tmp, "sports-gap-paper", "state.json"), json.dumps({
                "cash": 10,
                "open": [{
                    "contracts": 2, "team": "Bills", "ticker": "KXNFL-BILLS", "game": "Bills at Chiefs",
                    "side": "home", "cost": 1.5, "ask": 0.42, "bid": 0.40, "fee": 0.02,
                    "fair_at_entry": 0.62, "gap_at_entry": 0.12, "score_at_entry": "7-3 Q2",
                    "opened": "2026-10-30 14:00:00 CT",
                    "price_source": "https://api.elections.kalshi.com/trade-api/v2",
                    "price_at": "2026-10-30T19:00:00Z", "fill_id": "KXNFL-BILLS|1",
                }],
                "closed": [{
                    "contracts": 1, "team": "Chiefs", "ticker": "KXNFL-KC", "game": "Bills at Chiefs",
                    "side": "away", "cost": 1.0, "ask": 0.55, "fee": 0.02, "payout": 0, "pnl": -1.02,
                    "exit": "settled", "closed": "2026-10-30 16:00:00 CT", "fair_at_entry": 0.40,
                    "score_at_entry": "14-14 H",
                    "price_source": "https://api.elections.kalshi.com/trade-api/v2",
                    "price_at": "2026-10-30T18:00:00Z", "fill_id": "KXNFL-KC|1",
                }],
            }))
            snap = pimp_desk.snapshot(tmp)
            sports = snap["bots"][0]
            pos = sports["positions"][0]
            self.assertEqual(pos["name"], "Sports gap")
            self.assertEqual(pos["ticker"], "KXNFL-BILLS")
            self.assertEqual(pos["game"], "Bills at Chiefs")
            self.assertEqual(pos["side"], "home")
            self.assertEqual(pos["contracts"], 2)
            self.assertEqual(pos["cost"], 1.5)
            self.assertEqual(pos["ask"], 0.42)
            self.assertEqual(pos["fee"], 0.02)
            self.assertEqual(pos["prob"], 0.62)
            self.assertEqual(pos["score"], "7-3 Q2")
            self.assertIn("Paper buy", pos["why_open"])
            self.assertEqual(pos["risk"], 1.5)
            self.assertEqual(pos["reward"], 0.5)
            self.assertEqual(pos["risk_reward"], 0.3333)
            self.assertIn("kalshi.com", pos["source"])
            self.assertIn("Central", pos["priced_central"])
            closed = sports["history"][0]
            self.assertIn("Central", closed["closed_at"])
            self.assertEqual(closed["exit_reason"], "settled")
            self.assertEqual(closed["payout"], 0)
            self.assertEqual(closed["pnl"], -1.02)
            self.assertEqual(closed["risk"], 1.0)
            self.assertEqual(closed["reward"], 0)
            self.assertEqual(closed["risk_reward"], 0)
            self.assertEqual(sports["warning"], "No news calendar on this bot.")
            self.assertNotIn("bought nothing", sports.get("why") or "")
            self.assertNotIn("bought nothing", pimp_desk.plain_reason("No news calendar on this bot."))
            self.assertNotIn("bought nothing", pimp_desk.plain_reason("News calendar did not load. Entry stays off."))
            book = snap["book"]["rows"]
            self.assertTrue(any(row.get("state") == "open" for row in book))
            self.assertTrue(any(row.get("state") == "settled" and row.get("closed_at") for row in book))
            sparse = pimp_desk._fill_row({"ticker": "T", "cost": 1, "fill_id": "sparse"}, "T", "", 1, "")
            self.assertIsNone(sparse["prob"])
            self.assertEqual(sparse["score"], "")
            self.assertEqual(sparse["side"], "")
            self.assertEqual(sparse["source"], "")

    def test_every_open_trade_stays_on_the_book(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "sports-gap-paper", "gap_bot.py"), QUIET)
            opens = [{
                "contracts": 1, "team": f"Team {i}", "ticker": f"T{i}", "game": f"Game {i}",
                "side": "home", "cost": 1, "ask": 0.4, "fee": 0.01, "fair_at_entry": 0.6,
                "gap_at_entry": 0.1, "score_at_entry": "0-0", "opened": "2026-10-30 14:00:00 CT",
                "price_source": "https://api.elections.kalshi.com/trade-api/v2",
                "price_at": "2026-10-30T19:00:00Z", "fill_id": f"open-{i}",
            } for i in range(25)]
            closed = [{
                "contracts": 1, "team": f"Old {i}", "ticker": f"C{i}", "game": f"Old game {i}",
                "side": "away", "cost": 1, "ask": 0.5, "fee": 0.01, "payout": 0, "pnl": -1,
                "exit": "settled", "closed": "2026-10-30 16:00:00 CT", "fill_id": f"closed-{i}",
            } for i in range(25)]
            _write(os.path.join(tmp, "sports-gap-paper", "state.json"), json.dumps({
                "cash": 10, "open": opens, "closed": closed,
            }))
            snap = pimp_desk.snapshot(tmp)
            self.assertEqual(len(snap["bots"][0]["positions"]), 25)
            book = snap["book"]
            open_rows = [row for row in book["rows"] if row.get("state") == "open"]
            closed_rows = [row for row in book["rows"] if row.get("state") != "open"]
            self.assertEqual(len(open_rows), 25)
            self.assertEqual(len(closed_rows), pimp_desk.PAGE_SIZE)
            self.assertTrue(all(row.get("closed_at") for row in closed_rows))
            page2 = pimp_desk.snapshot(tmp, page=2)["book"]
            self.assertEqual(len([row for row in page2["rows"] if row.get("state") == "open"]), 25)
            self.assertEqual(len([row for row in page2["rows"] if row.get("state") != "open"]), 5)
        with tempfile.TemporaryDirectory() as bare:
            self.assertEqual(pimp_desk.snapshot(bare)["book"]["rows"], [])
            self.assertEqual(pimp_desk.snapshot(bare)["desk"]["curve"], [])
            self.assertEqual(pimp_desk.snapshot(bare)["desk"]["equity"], [])
            self.assertEqual(pimp_desk.snapshot(bare)["desk"]["spikes"], [])

    def test_equity_curve_is_chicago_time_and_blank_without_settles(self):
        october = pimp_desk._ct_when("October 30, 2026, 4:00 PM Central")
        self.assertEqual(october.astimezone(pimp_desk.CT).hour, 16)
        self.assertEqual(october.utcoffset(), dt.timedelta(hours=-5))
        noon = pimp_desk._ct_when("2026-10-30T17:00:00Z")
        self.assertEqual(noon.astimezone(pimp_desk.CT).hour, 12)
        self.assertIsNone(pimp_desk._ct_when(""))
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "sports-gap-paper", "gap_bot.py"), QUIET)
            _write(os.path.join(tmp, "sports-gap-paper", "state.json"), json.dumps({
                "cash": 20,
                "open": [{
                    "contracts": 1, "team": "Bills", "ticker": "OPEN", "game": "Bills at Chiefs",
                    "cost": 3, "opened": "2026-10-30 12:00:00 CT", "fill_id": "open-1",
                }],
                "closed": [
                    {"team": "Later", "pnl": 4.0, "closed": "November 2, 2026, 3:00 PM Central", "fill_id": "b"},
                    {"team": "Earlier", "pnl": -2.5, "closed": "2026-10-28 14:00:00 CT", "fill_id": "a"},
                ],
            }))
            desk = pimp_desk.snapshot(tmp)["desk"]
            curve = desk["curve"]
            self.assertEqual([point["v"] for point in curve], [-2.5, 1.5])
            self.assertEqual(curve[0]["t"], "2026-10-28T14:00:00-05:00")
            self.assertEqual(curve[1]["t"], "2026-11-02T15:00:00-06:00")
            self.assertFalse(any(point.get("day") for point in curve))
            self.assertEqual(desk["equity"], [-2.5, 1.5])
            self.assertEqual(curve[0]["name"], "Earlier")
            self.assertEqual(curve[0]["pnl"], -2.5)
            self.assertEqual(curve[0]["when"], "October 28, 2026, 2:00 PM Central")
            self.assertEqual(len(curve), 2)
            self.assertEqual(desk["spikes"], [{"from": 0, "to": 1, "dollars": 4.0, "pct": 160.0}])
            line = desk["chart"]["open_line"]
            self.assertEqual(desk["chart"]["zone"], "America/Chicago")
            self.assertEqual(desk["chart"]["default"], "ytd")
            self.assertEqual([row["id"] for row in desk["chart"]["ranges"]], ["ytd", "3m", "6m", "9m", "12m"])
            self.assertFalse(line["settled"])
            self.assertEqual(line["label"], "Live · not settled")
            self.assertEqual(line["n"], 1)
            self.assertNotIn("pnl", line["opens"][0])
            self.assertNotIn("v", line["opens"][0])
            self.assertTrue(line["opens"][0]["t"].startswith("2026-10-30T12:00:00"))
            self.assertNotIn("Bills", " ".join(point.get("name") or "" for point in curve))
        page = os.path.join(os.path.dirname(ROOT), "bot.py")
        with open(page, encoding="utf-8") as handle:
            text = handle.read()
        start = text.find('<div class="wrap" id="pimp"')
        end = text.find('<div class="looksheet"', start)
        chunk = text[start:end]
        order = ["paperban", 'id="pimpchart"', 'id="pimpopen"', 'id="pimpbook"', 'id="pimpdesk"']
        spots = [chunk.find(token) for token in order]
        self.assertTrue(all(spot >= 0 for spot in spots), spots)
        self.assertEqual(spots, sorted(spots))
        self.assertNotIn("innerHTML", chunk)
        self.assertIn('id="pimpslips"', chunk)
        self.assertIn('id="eqranges"', chunk)
        self.assertIn('data-range="ytd" aria-pressed="true"', chunk)
        for key in ("3m", "6m", "9m", "12m"):
            self.assertIn(f'data-range="{key}"', chunk)
        ranges = chunk[chunk.find('id="eqranges"'):chunk.find('id="pimpchart"')]
        self.assertNotIn("navchip", ranges)
        self.assertNotIn(".navchip{", chunk.replace(" ", ""))
        self.assertNotIn(".pill{", chunk.replace(" ", ""))
        self.assertIn("No settled paper trades in this range.", text)
        self.assertIn("Live · not settled", text)
        self.assertIn("Settled paper P/L", text)
        self.assertIn('id="eqwl"', chunk)
        self.assertIn('>Record</p>', chunk)
        self.assertIn('aria-label="Paper wins and losses"', chunk)
        self.assertIn('data-side="win"', chunk)
        self.assertIn('data-side="loss"', chunk)
        self.assertIn('id="eqresults"', chunk)
        bubble = chunk[chunk.find('id="pimpeqk"'):chunk.find('id="pimpeqv"')]
        self.assertNotIn("navchip", bubble)
        self.assertNotIn("pill", bubble)
        script = text[end:]
        self.assertIn("function paintResults", script)
        self.assertIn("function resultCard", script)
        self.assertIn("!Number.isFinite(n)||n===0", script)
        self.assertIn("No paper wins yet.", script)
        self.assertIn("No paper losses yet.", script)
        self.assertIn("function slipCard", script)
        self.assertIn("America/Chicago", script)
        self.assertIn("spikeText", script)
        self.assertLess(script.find("function slipCard"), script.find("</script>"))
        self.assertIn("function eqScrub", text)
        self.assertIn("function bindEquity", text)
        self.assertIn("function drawEquity", text)
        self.assertIn("Risk/reward", text)
        self.assertIn('id="pimppace"', text)
        brand = text.split('<a class="brand" href="/" title="Dashboard">', 1)[1].split("</a>", 1)[0]
        self.assertEqual(brand, "PIMP<b>-</b>BOT · STAFF")
        self.assertIn(">PIMP<b>-</b>BOT · STAFF · TRADING</a>", text)
        self.assertIn("function paintWordmark", text)
        self.assertIn("BOT · STAFF · TRADING", text)

    def test_chart_ranges_are_chicago_and_do_not_invent_points(self):
        now = dt.datetime(2026, 10, 30, 18, 0, tzinfo=pimp_desk.CT)
        rows = pimp_desk.chart_windows(now)
        self.assertEqual([row["label"] for row in rows], ["YTD", "3M", "6M", "9M", "12M"])
        by = {row["id"]: row for row in rows}
        self.assertEqual(by["ytd"]["start"], "2026-01-01T00:00:00-06:00")
        self.assertEqual(by["3m"]["start"], "2026-07-30T18:00:00-05:00")
        self.assertEqual(by["6m"]["start"], "2026-04-30T18:00:00-05:00")
        self.assertEqual(by["9m"]["start"], "2026-01-30T18:00:00-06:00")
        self.assertEqual(by["12m"]["start"], "2025-10-30T18:00:00-05:00")
        self.assertTrue(all(row["end"] == "2026-10-30T18:00:00-05:00" for row in rows))
        march = dt.datetime(2026, 3, 31, 15, 30, tzinfo=pimp_desk.CT)
        self.assertTrue(pimp_desk.chart_windows(march)[1]["start"].startswith("2025-12-31T15:30:00"))
        points = [
            {"t": "2025-03-01T12:00:00-06:00", "v": 1},
            {"t": "2026-01-15T12:00:00-06:00", "v": -5},
            {"t": "2026-09-15T12:00:00-05:00", "v": 3},
            {"t": "", "v": 9},
        ]
        self.assertEqual([p["v"] for p in pimp_desk.curve_in_window(points, by["ytd"]["start"], by["ytd"]["end"])], [-5, 3])
        self.assertEqual([p["v"] for p in pimp_desk.curve_in_window(points, by["3m"]["start"], by["3m"]["end"])], [3])
        self.assertEqual([p["v"] for p in pimp_desk.curve_in_window(points, by["12m"]["start"], by["12m"]["end"])], [-5, 3])
        self.assertEqual(pimp_desk.curve_in_window([{"t": "", "v": 9}], by["ytd"]["start"], by["ytd"]["end"]), [])
        self.assertEqual(pimp_desk.curve_in_window(
            [{"t": "2025-03-01T12:00:00-06:00", "v": 1}], by["ytd"]["start"], by["ytd"]["end"]), [])
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "sports-gap-paper", "gap_bot.py"), QUIET)
            start = dt.date(2026, 4, 14)
            closed = [{
                "team": f"Day {i}", "pnl": 1, "closed": f"{(start + dt.timedelta(days=i)).isoformat()} 12:00:00 CT",
                "fill_id": f"day-{i}",
            } for i in range(200)]
            _write(os.path.join(tmp, "sports-gap-paper", "state.json"), json.dumps({"cash": 10, "open": [], "closed": closed}))
            curve = pimp_desk.snapshot(tmp)["desk"]["curve"]
            self.assertEqual(len(curve), 200)
            self.assertTrue(curve[0]["t"].startswith("2026-04-14"))
            self.assertEqual(curve[-1]["v"], 200)

    def test_open_trade_draws_without_waiting_for_a_settle(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "btc15m-signal", "btc15m_signal.py"), QUIET)
            _write(os.path.join(tmp, "btc15m-signal", "paper_account.json"), json.dumps({
                "cash": 51.28,
                "open": [{
                    "ticker": "KXBTC15M", "team": "KXBTC15M", "game": "BTC 15-minute",
                    "side": "YES", "contracts": 56, "cost": 48.72,
                    "opened": "2026-10-30 18:00:00 UTC", "fill_id": "open-btc", "paper_only": True,
                }],
                "closed": [{
                    "ticker": "KXBTC15M-OLD", "team": "KXBTC15M-OLD", "game": "BTC 15-minute",
                    "side": "YES", "contracts": 10, "cost": 4.0, "payout": 10.0, "pnl": 6.0,
                    "exit": "settled", "closed": "2026-09-15 16:00:00 UTC",
                    "fill_id": "closed-btc", "paper_only": True,
                }],
            }))
            desk = pimp_desk.snapshot(tmp)["desk"]
            curve = desk["curve"]
            self.assertEqual([point["v"] for point in curve], [6.0])
            self.assertEqual(curve[0]["pnl"], 6.0)
            self.assertNotIn("48.72", json.dumps(curve))
            self.assertNotIn("KXBTC15M", curve[0]["name"])
            line = desk["chart"]["open_line"]
            self.assertEqual(line["n"], 1)
            self.assertFalse(line["settled"])
            self.assertEqual(line["opens"][0]["name"], "56 YES KXBTC15M")
            self.assertEqual(line["opens"][0]["stake"], 48.72)
            self.assertNotIn("pnl", line["opens"][0])
            self.assertNotIn("v", line["opens"][0])
            self.assertTrue(line["opens"][0]["t"].startswith("2026-10-30T13:00:00"))
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "btc15m-signal", "btc15m_signal.py"), QUIET)
            _write(os.path.join(tmp, "btc15m-signal", "paper_account.json"), json.dumps({
                "cash": 51.28,
                "open": [{
                    "ticker": "KXBTC15M", "team": "KXBTC15M", "game": "BTC 15-minute",
                    "side": "YES", "contracts": 56, "cost": 48.72,
                    "opened": "2026-08-15 18:00:00 UTC", "fill_id": "open-btc", "paper_only": True,
                }],
                "closed": [],
            }))
            desk = pimp_desk.snapshot(tmp)["desk"]
            self.assertEqual(desk["curve"], [])
            line = desk["chart"]["open_line"]
            self.assertEqual(line["n"], 1)
            self.assertEqual(line["opens"][0]["name"], "56 YES KXBTC15M")
            self.assertEqual(line["opens"][0]["stake"], 48.72)
            self.assertNotIn("v", line["opens"][0])
        page = os.path.join(os.path.dirname(ROOT), "bot.py")
        with open(page, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("if(!points.length && !openN)", text)
        self.assertIn("function drawLiveOnly", text)
        self.assertIn("host.dataset.live", text)
        self.assertIn("const t0=indexed[0].ms;", text)
        self.assertIn("if(openN>0 && Number.isFinite(endMs) && endMs>t1) t1=endMs;", text)
        self.assertNotIn("if(!points.length){put(host, h('p',{class:'eqempty'", text)

    def test_spikes_are_percent_and_slips_stay_real(self):
        quiet = [
            {"v": 10, "stake": 2, "pnl": 0.4},
            {"v": 10.4, "stake": 2, "pnl": 0.4},
            {"v": 10.1, "stake": 2, "pnl": -0.3},
            {"v": 10.5, "stake": 2, "pnl": 0.4},
        ]
        self.assertEqual(pimp_desk._equity_spikes(quiet), [])
        self.assertEqual(pimp_desk._equity_spikes([]), [])
        self.assertEqual(pimp_desk._equity_spikes([{"v": 3, "stake": 3, "pnl": 3}]), [])
        zero = [
            {"v": 0, "stake": 10, "pnl": 0},
            {"v": 5, "stake": 10, "pnl": 5},
        ]
        self.assertEqual(pimp_desk._equity_spikes(zero), [{"from": 0, "to": 1, "dollars": 5.0, "pct": 50.0}])
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "sports-gap-paper", "gap_bot.py"), QUIET)
            _write(os.path.join(tmp, "sports-gap-paper", "state.json"), json.dumps({
                "cash": 40,
                "open": [],
                "closed": [
                    {"team": "A", "ticker": "AAA", "game": "A at B", "cost": 10, "payout": 0, "pnl": -2.5,
                     "closed": "2026-10-28 14:00:00 CT", "fill_id": "a"},
                    {"team": "C", "ticker": "CCC", "game": "C at D", "cost": 5, "payout": 9, "pnl": 4.0,
                     "closed": "November 2, 2026, 3:00 PM Central", "fill_id": "b"},
                    {"team": "E", "ticker": "EEE", "game": "E at F", "cost": 8, "payout": 26, "pnl": 18.0,
                     "closed": "2026-11-03 15:30:00 CT", "fill_id": "c"},
                    {"team": "G", "ticker": "GGG", "game": "G at H", "cost": 4, "payout": 3, "pnl": -1.0,
                     "closed": "2026-11-04 11:00:00 CT", "fill_id": "d"},
                ],
            }))
            desk = pimp_desk.snapshot(tmp)["desk"]
            curve = desk["curve"]
            self.assertEqual([point["v"] for point in curve], [-2.5, 1.5, 19.5, 18.5])
            self.assertEqual(len(curve), 4)
            self.assertEqual(curve[2]["name"], "E at F")
            self.assertEqual(curve[2]["stake"], 8)
            self.assertEqual(curve[2]["payout"], 26)
            self.assertEqual(curve[2]["pnl"], 18)
            self.assertIn("Central", curve[2]["when"])
            self.assertEqual(desk["spikes"], [{"from": 1, "to": 2, "dollars": 18.0, "pct": 1200.0}])
            self.assertTrue(all(point["t"] for point in curve))

    def test_four_opens_stay_under_the_new_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "sports-gap-paper", "gap_bot.py"), QUIET)
            _write(os.path.join(tmp, "sports-gap-paper", "state.json"), json.dumps({
                "cash": 11.0,
                "open": [{"contracts": 1, "team": "Bills", "ticker": "KX", "game": "Bills at Chiefs",
                          "cost": 3, "opened": "2026-10-30 12:00:00 CT", "fill_id": f"open-{i}"} for i in range(4)],
                "closed": [],
            }))
            snap = pimp_desk.snapshot(tmp)
            self.assertEqual(snap["bots"][0]["open_count"], 4)
            self.assertEqual(snap["desk"]["gate"], "")
            allowed = pimp_desk.run_bot("sports-gap", "run", tmp)
            self.assertTrue(allowed["ok"], allowed)
            self.assertFalse(allowed.get("blocked"))

    def test_risk_reward_and_learning_skip(self):
        row = pimp_desk.risk_reward(1.5, 2.0)
        self.assertEqual(row, {"risk": 1.5, "reward": 0.5, "risk_reward": 0.3333})
        self.assertIsNone(pimp_desk.risk_reward(0, 1.0)["risk_reward"])
        self.assertIsNone(pimp_desk.risk_reward(None, 1.0)["risk"])

        def rows(hits, misses):
            made = [{"market": "NFL", "bucket": "0.6-0.7", "result": "hit", "stake": 1} for _ in range(hits)]
            made += [{"market": "NFL", "bucket": "0.6-0.7", "result": "miss", "stake": 1} for _ in range(misses)]
            return made

        skip = pimp_desk.learning_skip(rows(3, 5), "NFL", "0.6-0.7")
        self.assertIn("under 40%", skip)
        self.assertNotIn("smarter", skip.lower())
        self.assertEqual(pimp_desk.learning_skip(rows(4, 4), "NFL", "0.6-0.7"), "")
        self.assertEqual(pimp_desk.learning_skip(rows(0, 7), "NFL", "0.6-0.7"), "")
        self.assertEqual(pimp_desk.learning_skip(rows(4, 6), "NFL", "0.6-0.7"), "")
        self.assertEqual(pimp_desk.prob_bucket(0.60), "0.6-0.7")
        self.assertEqual(pimp_desk.edge_for_hour(0, 0.04), (0.04, False))
        self.assertEqual(pimp_desk.edge_for_hour(4, 0.04), (0.04, False))
        self.assertEqual(pimp_desk.edge_for_hour(11, 0.04), (0.04, False))
        self.assertEqual(pimp_desk.edge_for_hour(12, 0.04), (0.04, False))

    def test_hour_pace_counts_this_chicago_hour_only(self):
        now = dt.datetime(2026, 10, 30, 16, 15, tzinfo=pimp_desk.CT)
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, QUIET)
            self.assertEqual(pimp_desk.hour_pace(tmp, now)["line"], "0 of 12 this hour")
            self.assertFalse(pimp_desk.hour_pace(tmp, now)["loosened"])
            self.assertEqual(pimp_desk.hour_pace(tmp, now)["edge"], 0.06)
            self.assertNotIn("without the strict edge", pimp_desk.hour_pace(tmp, now)["note"])
            self.assertEqual(pimp_desk.snapshot(tmp)["desk"]["curve"], [])
            opens = []
            for i in range(4):
                opens.append({
                    "ticker": f"T{i}", "fill_id": f"hour-{i}", "cost": 1, "contracts": 1,
                    "opened": "2026-10-30 16:05:00 CT",
                })
            opens.append({
                "ticker": "OLD", "fill_id": "old-1", "cost": 1, "contracts": 1,
                "opened": "2026-10-30 15:05:00 CT",
            })
            closed = [{
                "ticker": "T0", "fill_id": "hour-0", "cost": 1, "contracts": 1,
                "opened": "2026-10-30 16:05:00 CT", "closed": "2026-10-30 16:20:00 CT", "pnl": 1,
            }]
            _write(os.path.join(tmp, "sports-gap-paper", "state.json"), json.dumps({
                "cash": 14, "open": opens, "closed": closed,
            }))
            pace = pimp_desk.hour_pace(tmp, now)
            self.assertEqual(pace["line"], "4 of 12 this hour")
            self.assertFalse(pace["loosened"])
            self.assertEqual(pace["edge"], 0.06)
            self.assertEqual(pace["count"], 4)
            full = []
            for i in range(12):
                full.append({
                    "ticker": f"F{i}", "fill_id": f"full-{i}", "cost": 1, "contracts": 1,
                    "opened": "2026-10-30 16:10:00 CT",
                })
            _write(os.path.join(tmp, "sports-gap-paper", "state.json"), json.dumps({
                "cash": 14, "open": full, "closed": [],
            }))
            done = pimp_desk.hour_pace(tmp, now)
            self.assertEqual(done["count"], 12)
            self.assertFalse(done["loosened"])
            self.assertEqual(done["edge"], 0.06)

    def test_short_hour_does_not_waive_the_edge(self):
        for count in (0, 4, 11, 12):
            edge, loose = pimp_desk.edge_for_hour(count, 0.04)
            self.assertEqual((edge, loose), (0.04, False))
        sports = os.path.join(ROOT, "sports-gap-paper", "gap_bot.py")
        with open(sports, encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn("loosened", text)
        self.assertNotIn("without the strict", text)
        self.assertIn("gap < need", text)
        import importlib.util
        path = os.path.join(ROOT, "btc15m-signal", "btc15m_signal.py")
        spec = importlib.util.spec_from_file_location("btc15m_edge_gate", path)
        btc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(btc)
        with tempfile.TemporaryDirectory() as tmp:
            btc.ACCOUNT = os.path.join(tmp, "paper_account.json")
            state = {"cash": 100.0, "open": [], "closed": [], "paper_only": True}
            quiet = btc.paper_buy(
                state, "KXBTC15M-TEST", "YES", 0.70, 0.02, 0.71, "2026-10-31T16:00:00Z", False,
            )
            self.assertEqual(quiet, "Checked all open BTC 15-minute markets. No paper buy.")
            self.assertEqual(state["open"], [])
            self.assertEqual(state["cash"], 100.0)
            self.assertFalse(os.path.exists(btc.ACCOUNT))
            bought = btc.paper_buy(
                state, "KXBTC15M-TEST", "YES", 0.70, 0.02, 0.80, "2026-10-31T16:00:00Z", True,
            )
            self.assertEqual(bought, "Checked all open BTC 15-minute markets. Paper buy.")
            self.assertEqual(len(state["open"]), 1)
            cost = state["open"][0]["cost"]
            self.assertGreaterEqual(cost, 19)
            self.assertLessEqual(cost, 20)
            self.assertNotIn("without the strict", state["open"][0]["why"])
            self.assertTrue(state["open"][0]["paper_only"])

    def test_btc_skip_prefers_densified_card_over_no_skip_lie(self):
        # Commodity (#397) prints evaluate reasons on CARD only — never SIGNAL:.
        commodity = (
            "commodity-15m paper check (no live orders)\n"
            "  KXGOLD15M KXGOLD-1 spot=2650 reasons=['edge < 0.05 after fees']\n"
            "CARD: edge < 0.05 after fees; z < 1.0\n"
        )
        self.assertEqual(
            pimp_desk._btc_skip(commodity),
            "edge < 0.05 after fees; z < 1.0",
        )
        self.assertEqual(
            pimp_desk.card_copy(commodity),
            "edge < 0.05 after fees; z < 1.0",
        )
        # Generic empty CARD is not a skip reason — keep honest empty message.
        empty = "CARD: Checked commodity 15m markets. No paper buy.\n"
        self.assertEqual(
            pimp_desk._btc_skip(empty),
            "The last run did not include a skip line.",
        )
        # SIGNAL: still wins when present (BTC evaluate path).
        btc = (
            "  SIGNAL: SKIP -> z < 1.25 (0.91)\n"
            "CARD: z < 1.25 (0.91)\n"
        )
        self.assertIn("SIGNAL: SKIP", pimp_desk._btc_skip(btc))
        # No-window line densifies skip when CARD is bland (#499 twin).
        no_win = (
            "No open KXBTC15M window right now — still tracking ETH/ladder history.\n"
            "CARD: Checked all open BTC 15-minute markets. No paper buy.\n"
        )
        self.assertIn("no open kxbtc15m window", pimp_desk._btc_skip(no_win).lower())
        self.assertNotIn("did not include a skip line", pimp_desk._btc_skip(no_win).lower())

    def test_sports_skip_prefers_densified_card(self):
        sports = (
            "## Check …\n"
            "CARD: gap < 6 (accurate) - no trade\n"
        )
        self.assertEqual(
            pimp_desk._sports_skip(sports),
            "gap < 6 (accurate) - no trade",
        )
        self.assertEqual(
            pimp_desk._sports_skip("CARD: No paper buy (lanes clear, no fee-aware edge).\n"),
            "The last run did not include a skip line.",
        )
        self.assertIn(
            "no Kalshi match",
            pimp_desk._sports_skip("CARD: no Kalshi match - skip\n"),
        )
        # Idle no-live CARD is the skip reason — not "did not include a skip line".
        idle = (
            "Kalshi tape: +0 new prints\n"
            "CARD: No live or tip-soon games, so this check bought nothing.\n"
        )
        self.assertIn("no live or tip-soon", pimp_desk._sports_skip(idle).lower())
        self.assertNotIn("did not include a skip line", pimp_desk._sports_skip(idle).lower())

    def test_kalshi_skip_prefers_densified_card_over_calendar(self):
        summary = (
            "Event KXINXU-26NOV10: 8 active contracts\n"
            "NO TRADE 2026-11-10: post-CPI blackout 30m\n"
            "CARD: post-CPI blackout 30m\n"
        )
        self.assertEqual(
            pimp_desk._kalshi_skip(".", None, summary=summary),
            "post-CPI blackout 30m",
        )
        self.assertEqual(
            pimp_desk.card_copy(summary),
            "post-CPI blackout 30m",
        )

    def test_kalshi_skip_surfaces_drawdown_halt_without_kill_flag(self):
        """$444 bankroll ≤ $460 drawdown halt must densify even when halted=False."""
        with tempfile.TemporaryDirectory() as tmp:
            sp = os.path.join(tmp, "kalshi-sp500-paper")
            os.makedirs(sp, exist_ok=True)
            with open(os.path.join(sp, "config.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "starting_bankroll": 500.0,
                    "drawdown_halt_bankroll": 460.0,
                    "kill_switch_bankroll": 400.0,
                    "staff_clear_drawdown_halt": False,
                }, fh)
            with open(os.path.join(sp, "calendar.json"), "w", encoding="utf-8") as fh:
                json.dump({}, fh)
            state = {"bankroll": 444.37, "halted": False, "open": [], "closed": []}
            out = pimp_desk._kalshi_skip(tmp, state, summary="")
            self.assertIn("drawdown halt", out.lower())
            self.assertIn("444.37", out)
            self.assertIn("460", out)
            # Bland settle CARD must not hide the halt (HUD sibling).
            bland = pimp_desk._kalshi_skip(
                tmp, state, summary="CARD: No open paper positions.\n",
            )
            self.assertIn("drawdown halt", bland.lower())
            # Above halt → no mystery drawdown line.
            ok = pimp_desk._kalshi_skip(
                tmp, {"bankroll": 500.0, "halted": False}, summary="",
            )
            self.assertNotIn("drawdown halt", ok.lower())
            # Staff clear densifies resume truth (not bland empty settle); kill still stone.
            with open(os.path.join(sp, "config.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "starting_bankroll": 500.0,
                    "drawdown_halt_bankroll": 460.0,
                    "kill_switch_bankroll": 400.0,
                    "staff_clear_drawdown_halt": True,
                }, fh)
            cleared = pimp_desk._kalshi_skip(tmp, state, summary="")
            self.assertIn("staff cleared soft drawdown", cleared.lower())
            self.assertIn("444.37", cleared)
            self.assertNotIn("new buys off", cleared.lower())
            bland_clear = pimp_desk._kalshi_skip(
                tmp, state, summary="CARD: No open paper positions.\n",
            )
            self.assertIn("staff cleared soft drawdown", bland_clear.lower())

    def test_kalshi_sized_skip_reads_own_staff_clear_not_sp(self):
        """Sized tip must not inherit S&P staff-clear when its own soft DD is still on."""
        with tempfile.TemporaryDirectory() as tmp:
            sp = os.path.join(tmp, "kalshi-sp500-paper")
            sized = os.path.join(tmp, "kalshi-sized-paper")
            os.makedirs(sp, exist_ok=True)
            os.makedirs(sized, exist_ok=True)
            with open(os.path.join(sp, "config.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "starting_bankroll": 500.0,
                    "drawdown_halt_bankroll": 460.0,
                    "kill_switch_bankroll": 400.0,
                    "staff_clear_drawdown_halt": True,
                }, fh)
            with open(os.path.join(sized, "config.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "starting_bankroll": 500.0,
                    "drawdown_halt_bankroll": 460.0,
                    "kill_switch_bankroll": 400.0,
                    "staff_clear_drawdown_halt": False,
                }, fh)
            for folder in (sp, sized):
                with open(os.path.join(folder, "calendar.json"), "w", encoding="utf-8") as fh:
                    json.dump({}, fh)
            state = {"bankroll": 444.0, "halted": False, "open": [], "closed": []}
            # Default (S&P folder) still shows staff clear.
            sp_line = pimp_desk._kalshi_skip(tmp, state, summary="")
            self.assertIn("staff cleared soft drawdown", sp_line.lower())
            # Sized folder must densify halt — not the S&P clear lie.
            sized_line = pimp_desk._kalshi_skip(
                tmp, state, summary="", bot_id="kalshi-sized", folder="kalshi-sized-paper",
            )
            self.assertIn("drawdown halt", sized_line.lower())
            self.assertNotIn("staff cleared", sized_line.lower())
            # Sized staff clear densifies resume truth on its own tower.
            with open(os.path.join(sized, "config.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "starting_bankroll": 500.0,
                    "drawdown_halt_bankroll": 460.0,
                    "kill_switch_bankroll": 400.0,
                    "staff_clear_drawdown_halt": True,
                }, fh)
            sized_clear = pimp_desk._kalshi_skip(
                tmp, state, summary="CARD: No open paper positions.\n",
                bot_id="kalshi-sized", folder="kalshi-sized-paper",
            )
            self.assertIn("staff cleared soft drawdown", sized_clear.lower())

    def test_finish_bot_prefers_hold_why_over_entry_skip_card(self):
        """Open BTC must not show speed-floor entry skips as the tower why."""
        spec = {
            "id": "btc15m",
            "name": "BTC 15m signal",
            "kind": "btc",
            "folder": "btc15m-signal",
            "state": "paper_account.json",
            "log": "",
            "empty": "empty",
        }
        view = {
            "id": "btc15m",
            "present": True,
            "has_state": True,
            "open_count": 1,
            "positions": [{"ticker": "KXBTC15M-T"}],
            "trades": [],
            "history": [],
            "cash": 96.49,
            "realized": -2.03,
            "today": 0.0,
            "why": "p 0.619 < speed floor 0.70; p 0.619 < ask+fee+buf (accurate) = 0.710; z 0.30 < 0.60",
            "skip": "",
            "paused": False,
            "read_error": "",
            "central_check": "1:50 AM",
            "last_check": "1:50 AM",
        }
        run = {"ok": True, "summary": "CARD: p 0.619 < speed floor 0.70\n", "at": ""}
        # Bind run onto view the way _bot_view does before _finish_bot.
        view["last_run"] = run
        out = pimp_desk._finish_bot(view, spec, ".")
        self.assertIn("Holding 1 open paper position", out.get("why") or "")
        self.assertNotIn("speed floor", (out.get("why") or "").lower())

    def test_finish_bot_inx_settle_empty_leads_with_next_scan(self):
        """Settle empty must not lead tip why (#497 twin)."""
        from unittest import mock

        spec = {
            "id": "kalshi-sp",
            "name": "Kalshi S&P",
            "kind": "kalshi",
            "folder": "kalshi-sp500-paper",
            "state": "paper_state.json",
            "log": "",
            "empty": "empty",
        }
        view = {
            "id": "kalshi-sp",
            "present": True,
            "has_state": True,
            "open_count": 0,
            "positions": [],
            "trades": [],
            "history": [],
            "cash": 500.0,
            "realized": 0.0,
            "today": 0.0,
            "why": "No open paper positions.",
            "skip": "",
            "paused": False,
            "read_error": "",
            "central_check": "12:30 PM",
            "last_check": "12:30 PM",
            "last_run": {"ok": True, "summary": "No open paper positions.", "action": "settle"},
        }
        with mock.patch.object(
            pimp_desk, "next_inx_scan_line", return_value="Next scan 13:05 CT.",
        ):
            out = pimp_desk._finish_bot(view, spec, ".")
        why = out.get("why") or ""
        self.assertTrue(why.startswith("Next scan 13:05 CT."))
        self.assertIn("Settle smoke: empty book", why)
        self.assertFalse(why.lower().startswith("no open paper"))

    def test_finish_bot_staff_clear_outside_window_leads_with_next_scan(self):
        """Soft-DD staff-clear must not lead the tip after the entry window."""
        from unittest import mock

        spec = {
            "id": "kalshi-sp",
            "name": "Kalshi S&P",
            "kind": "kalshi",
            "folder": "kalshi-sp500-paper",
            "state": "paper_state.json",
            "log": "",
            "empty": "empty",
        }
        clear = (
            "Staff cleared soft drawdown halt: bankroll $444.37 ≤ $460.00 "
            "(start $500). Paper buys may resume; kill $400 + fee/band/max-1/day stay stone."
        )
        view = {
            "id": "kalshi-sp",
            "present": True,
            "has_state": True,
            "open_count": 0,
            "positions": [],
            "trades": [],
            "history": [],
            "cash": 444.37,
            "realized": -55.63,
            "today": 0.0,
            "why": clear,
            "skip": clear,
            "paused": False,
            "read_error": "",
            "central_check": "3:10 PM",
            "last_check": "3:10 PM",
            "last_run": {"ok": True, "summary": "No open paper positions.", "action": "settle"},
        }
        with mock.patch.object(
            pimp_desk, "next_inx_scan_line",
            return_value="Next scan tomorrow 12:05 CT.",
        ):
            out = pimp_desk._finish_bot(view, spec, ".")
        why = out.get("why") or ""
        self.assertTrue(why.startswith("Next scan tomorrow 12:05 CT."))
        self.assertIn("Staff cleared soft drawdown", why)
        self.assertFalse(why.lower().startswith("staff cleared"))

    def test_finish_bot_inx_in_scan_prefers_skip_over_settle_smoke(self):
        """In-window sized tip must keep densified NO TRADE, not settle boilerplate."""
        from unittest import mock

        spec = {
            "id": "kalshi-sized",
            "name": "Sized Kalshi",
            "kind": "kalshi",
            "folder": "kalshi-sized-paper",
            "state": "paper_state.json",
            "log": "",
            "empty": "empty",
        }
        view = {
            "id": "kalshi-sized",
            "present": True,
            "has_state": True,
            "open_count": 0,
            "positions": [],
            "trades": [],
            "history": [],
            "cash": 500.0,
            "realized": 0.0,
            "today": 0.0,
            "why": "No open paper positions.",
            "skip": "inx fair: 45m to settle < 60m entry floor (refuse late σ-collapse arm)",
            "paused": False,
            "read_error": "",
            "central_check": "2:14 PM",
            "last_check": "2:14 PM",
            "last_run": {"ok": True, "summary": "No open paper positions.", "action": "settle"},
        }
        with mock.patch.object(
            pimp_desk, "next_inx_scan_line",
            return_value="In scan window until 14:55 CT.",
        ):
            out = pimp_desk._finish_bot(view, spec, ".")
        why = (out.get("why") or "").lower()
        self.assertIn("60m entry floor", why)
        self.assertNotIn("settle smoke", why)

    def test_inx_settle_keeps_scan_tip_in_run_window(self):
        """Empty settle during sized scan window must not wipe densified CARD."""
        from unittest import mock
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            prior = (
                "NO TRADE 2026-11-09: inx fair: 45m to settle < 60m entry floor "
                "(refuse late σ-collapse arm)\n"
                "CARD: inx fair: 45m to settle < 60m entry floor "
                "(refuse late σ-collapse arm)"
            )
            pimp_desk._save_run(tmp, "kalshi-sized", {
                "at": "2026-11-09 20:00:00 UTC",
                "ok": True,
                "summary": prior,
                "action": "run",
            })

            def fake_popen(*_a, **_k):
                class Proc:
                    returncode = 0

                    def communicate(self, timeout=None):
                        return ("No open paper positions.\n", None)

                    def kill(self):
                        return None
                return Proc()

            with mock.patch.object(pimp_desk, "inx_in_run_window", return_value=True), \
                 mock.patch.object(pimp_desk.subprocess, "Popen", side_effect=fake_popen), \
                 mock.patch.object(pimp_desk, "keep_closed_settlements"), \
                 mock.patch.object(pimp_desk, "ensure_paper_accounts"), \
                 mock.patch.object(pimp_desk, "_folder_ok", return_value=True), \
                 mock.patch.object(pimp_desk, "_paper_ok", return_value=""), \
                 mock.patch.object(pimp_desk, "_kalshi_paper", return_value=True), \
                 mock.patch.object(pimp_desk, "_note_state_mtime"), \
                 mock.patch.object(pimp_desk, "_lock") as lock_m:
                lock = mock.Mock()
                lock.acquire.return_value = True
                lock_m.return_value = lock
                # Need real folder layout for script path check — stub argv via ACTIONS.
                sized_dir = os.path.join(tmp, "kalshi-sized-paper")
                os.makedirs(sized_dir, exist_ok=True)
                with open(os.path.join(sized_dir, "bot.py"), "w", encoding="utf-8") as fh:
                    fh.write("print('hi')\n")
                with open(os.path.join(sized_dir, "config.json"), "w", encoding="utf-8") as fh:
                    fh.write('{"paper_mode": true}\n')
                out = pimp_desk.run_bot("kalshi-sized", "settle", tmp)
            self.assertTrue(out.get("kept_scan_tip"))
            self.assertIn("60m entry floor", out.get("summary") or "")
            saved = pimp_desk._load_runs(tmp).get("kalshi-sized") or {}
            self.assertIn("60m entry floor", saved.get("summary") or "")
            self.assertEqual(saved.get("action"), "run")

    def test_inx_no_trade_retries_inside_window(self):
        """NO TRADE must not burn the daily INX stamp — retry so band can clear."""
        slot = {"id": "kalshi-sized", "action": "run", "at_ct": "12:05", "until_ct": "14:55"}
        now = dt.datetime(2026, 11, 9, 13, 10, tzinfo=pimp_desk.CT)
        saved = {}
        pimp_desk._remember(
            saved, slot, now,
            {"ok": True, "summary": "NO TRADE: inx fair p 0.66 < 0.80\nCARD: inx fair p 0.66 < 0.80"},
        )
        key = "kalshi-sized:run:12:05"
        self.assertIsNone(saved.get(key))
        self.assertIn(key + ":retry", saved)
        # Late-σ ends retries (stone 60m floor — no legal entry left).
        saved_late = {}
        pimp_desk._remember(
            saved_late, slot, now,
            {
                "ok": True,
                "summary": (
                    "CARD: inx fair: 38m to settle < 60m entry floor "
                    "(refuse late σ-collapse arm)"
                ),
            },
        )
        self.assertEqual(saved_late.get(key), "2026-11-09")
        with tempfile.TemporaryDirectory() as tmp:
            # After retry cooldown, sized run is due again inside the window.
            pimp_desk._atomic_write(
                pimp_desk.auto_path(tmp),
                json.dumps({key + ":retry": pimp_desk._iso(now)}) + "\n",
            )
            later = now + dt.timedelta(seconds=pimp_desk.AUTO_RETRY_SEC + 1)
            due = pimp_desk.due_slots(later, tmp)
            self.assertTrue(any(
                s.get("id") == "kalshi-sized" and s.get("action") == "run" for s in due
            ))

    def test_next_for_never_past_inside_open_window(self):
        """Open settle/run windows must not show a past clock start as next_run."""
        with tempfile.TemporaryDirectory() as tmp:
            now = dt.datetime(2026, 11, 9, 14, 39, tzinfo=pimp_desk.CT)
            # Run already done today; settle window 13:00–15:55 still open → due now,
            # not "1:00 PM" in the past.
            pimp_desk._atomic_write(
                pimp_desk.auto_path(tmp),
                json.dumps({"kalshi-sized:run:12:05": "2026-11-09"}) + "\n",
            )
            text = pimp_desk._next_for("kalshi-sized", tmp, now)
            self.assertNotIn("1:00 PM", text)
            self.assertIn("2026", text)
            # Parse-ish: afternoon next (settle due now → ~2:39) or evening settle.
            self.assertTrue(
                "2:39 PM" in text or "2:3" in text or "4:00 PM" in text or "4:05 PM" in text,
                msg=text,
            )
            # All S&P scans done; settle open → next is now, not 1:00 PM.
            pimp_desk._atomic_write(
                pimp_desk.auto_path(tmp),
                json.dumps({
                    "kalshi-sp:run:12:05": "2026-11-09",
                    "kalshi-sp:run:13:05": "2026-11-09",
                    "kalshi-sp:run:13:40": "2026-11-09",
                }) + "\n",
            )
            sp = pimp_desk._next_for("kalshi-sp", tmp, now)
            self.assertNotIn("1:00 PM", sp)

    def test_card_copy_is_plain_and_accounts_keep_cash(self):
        raw = (
            "No news calendar on this bot.\n"
            "run d5166c8a @ 2026-10-30T21:09:16+00:00 cash $100.00 open 0 "
            "1) managing open paper positions 2) scanning for candidates "
            "source profiles: 26 solana tokens"
        )
        text = pimp_desk.card_copy(raw)
        self.assertEqual(text, "Checked 26 Solana tokens. No paper buy.")
        self.assertNotIn("d5166c8a", text)
        self.assertNotIn("2026-10-30T21:09:16", text)
        self.assertEqual(pimp_desk.card_copy("No news calendar on this bot."), "")
        preferred = pimp_desk.card_copy("tokens checked: 3\nsource profiles: 9 solana tokens")
        self.assertEqual(preferred, "Checked 3 Solana tokens. No paper buy.")
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, QUIET)
            made = pimp_desk.ensure_paper_accounts(tmp)
            self.assertEqual(set(made), {
                "sports-gap", "kalshi-sp", "btc15m", "commodity-15m", "memecoin",
                "kalshi-sized", "coinbase-spot", "btc-carry",
            })
            snap = pimp_desk.snapshot(tmp)
            by_id = {bot["id"]: bot for bot in snap["bots"]}
            self.assertEqual(by_id["sports-gap"]["cash"], 100.0)
            self.assertEqual(by_id["kalshi-sp"]["cash"], 500.0)
            self.assertEqual(by_id["btc15m"]["cash"], 100.0)
            self.assertEqual(by_id["commodity-15m"]["cash"], 100.0)
            self.assertEqual(by_id["memecoin"]["cash"], 100.0)
            self.assertEqual(by_id["kalshi-sized"]["cash"], 500.0)
            self.assertEqual(by_id["coinbase-spot"]["cash"], 500.0)
            self.assertTrue(by_id["coinbase-spot"]["shadow_only"])
            self.assertEqual(by_id["btc-carry"]["cash"], 500.0)
            self.assertTrue(by_id["btc-carry"]["shadow_only"])
            self.assertTrue(by_id["kalshi-sized"]["present"])
            self.assertIn("gate_a", snap["desk"])
            self.assertIn("prove_it", snap["desk"])
            self.assertEqual(snap["desk"]["ops"].get("fill_tax"), 0.01)
            self.assertEqual(snap["desk"]["curve"], [])
            self.assertEqual(by_id["sports-gap"]["positions"], [])
            path = os.path.join(tmp, "sports-gap-paper", "state.json")
            with open(path, encoding="utf-8") as handle:
                state = json.load(handle)
            state["cash"] = 20
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(state, handle)
            self.assertEqual(pimp_desk.ensure_paper_accounts(tmp), [])
            self.assertEqual(pimp_desk.snapshot(tmp)["bots"][0]["cash"], 20.0)
            _write(os.path.join(tmp, "sports-gap-paper", "state.json"), "{")
            broken = pimp_desk.snapshot(tmp)["bots"][0]
            self.assertIn("half-written", broken["read_error"])
        with tempfile.TemporaryDirectory() as bare:
            self.assertEqual(pimp_desk.ensure_paper_accounts(bare), [])
            self.assertEqual(pimp_desk.snapshot(bare)["desk"]["curve"], [])

    def test_closed_settlements_survive_an_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            volume = os.path.join(tmp, "volume")
            root = os.path.join(tmp, "app", "paper-bots")
            _tree(root, QUIET)
            state_path = os.path.join(root, "sports-gap-paper", "state.json")
            log_path = os.path.join(root, "sports-gap-paper", "paper_trades.md")
            _write(state_path, json.dumps({
                "cash": 90.08,
                "open": [],
                "closed": [{
                    "team": "Bills",
                    "game": "Bills at Chiefs",
                    "exit": "settled",
                    "pnl": 9.92,
                    "cost": 19.5,
                    "closed": "2026-10-30 17:33:00 CT",
                }],
                "runs": 1,
                "paper_only": True,
            }))
            _write(log_path, "settled bill 9.92\n")
            linked = pimp_desk.keep_closed_settlements(root, durable=volume)
            self.assertIn("sports-gap-paper/state.json", linked)
            self.assertIn("sports-gap-paper/paper_trades.md", linked)
            self.assertTrue(os.path.islink(state_path))
            self.assertTrue(os.path.islink(log_path))
            snap = pimp_desk.snapshot(root)
            self.assertEqual([point["v"] for point in snap["desk"]["curve"]], [9.92])
            # A push replaces the working tree with the empty file from the image.
            os.remove(state_path)
            os.remove(log_path)
            _write(state_path, json.dumps({
                "cash": 100, "open": [], "closed": [], "runs": 0, "paper_only": True,
            }))
            _write(log_path, "fresh image\n")
            self.assertFalse(os.path.islink(state_path))
            again = pimp_desk.keep_closed_settlements(root, durable=volume)
            self.assertIn("sports-gap-paper/state.json", again)
            with open(state_path, encoding="utf-8") as handle:
                restored = json.load(handle)
            self.assertEqual(restored["closed"][0]["pnl"], 9.92)
            with open(log_path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "settled bill 9.92\n")
            with open(os.path.join(volume, "sports-gap-paper", "state.json"), encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["closed"][0]["pnl"], 9.92)
            snap = pimp_desk.snapshot(root)
            self.assertEqual([point["v"] for point in snap["desk"]["curve"]], [9.92])
            self.assertEqual(pimp_desk.keep_closed_settlements(root), [])
            self.assertEqual(pimp_desk.keep_closed_settlements(root, durable=os.path.join(root, "inside")), [])
            pimp_desk._atomic_write(state_path, json.dumps({
                "cash": 1,
                "open": [],
                "closed": [{"team": "Bills", "pnl": 9.92, "closed": "2026-10-30 17:33:00 CT"}],
                "paper_only": True,
            }))
            self.assertTrue(os.path.islink(state_path))
            with open(os.path.join(volume, "sports-gap-paper", "state.json"), encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["cash"], 1)
            self.assertFalse(os.path.exists(state_path + ".tmp"))

    def test_reset_clears_the_durable_settlement(self):
        with tempfile.TemporaryDirectory() as tmp:
            volume = os.path.join(tmp, "volume")
            root = os.path.join(tmp, "root")
            _write(os.path.join(root, "kalshi-sp500-paper", "bot.py"), STUB)
            _write(os.path.join(root, "kalshi-sp500-paper", "config.json"), json.dumps({"paper_mode": True}))
            _write(os.path.join(root, "kalshi-sp500-paper", "paper_state.json"), json.dumps({
                "bankroll": 500,
                "open": [],
                "closed": [{"pnl": 3, "ticker": "KX", "settled_at": "2026-10-30"}],
                "paper_only": True,
            }))
            _write(os.path.join(root, "kalshi-sp500-paper", "Trade_Ledger.md"), "row\n")
            pimp_desk.keep_closed_settlements(root, durable=volume)
            durable = os.path.join(volume, "kalshi-sp500-paper", "paper_state.json")
            self.assertTrue(os.path.isfile(durable))
            result = pimp_desk.reset_bot("kalshi-sp", root)
            self.assertTrue(result["ok"], result)
            self.assertFalse(os.path.exists(durable))
            snap = pimp_desk.snapshot(root)
            kalshi = next(bot for bot in snap["bots"] if bot["id"] == "kalshi-sp")
            self.assertEqual(kalshi["trades"], [])
            self.assertEqual(snap["desk"]["curve"], [])

    def test_settlement_save_follows_the_symlink(self):
        import importlib.util
        modules = (
            ("gap_save", os.path.join(ROOT, "sports-gap-paper", "gap_bot.py"), "STATE", "save_state",
             {"cash": 1, "open": [], "closed": [{"pnl": 9.92}], "paper_only": True}),
            ("btc_save", os.path.join(ROOT, "btc15m-signal", "btc15m_signal.py"), "ACCOUNT", "save_account",
             {"cash": 1, "open": [], "closed": [{"pnl": 4}], "paper_only": True}),
            ("kalshi_save", os.path.join(ROOT, "kalshi-sp500-paper", "paper_sim.py"), "STATE_PATH", "save_state",
             {"bankroll": 500, "open": [], "closed": [{"pnl": 2}], "paper_only": True}),
        )
        for name, path, attr, fn, payload in modules:
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            with tempfile.TemporaryDirectory() as tmp:
                remote = os.path.join(tmp, "account.json")
                local = os.path.join(tmp, "link.json")
                _write(remote, "{}\n")
                os.symlink(remote, local)
                setattr(mod, attr, local)
                if name == "kalshi_save":
                    mod.save_state(payload, local)
                else:
                    getattr(mod, fn)(payload)
                self.assertTrue(os.path.islink(local), name)
                with open(remote, encoding="utf-8") as handle:
                    saved = json.load(handle)
                self.assertEqual(saved["closed"][0]["pnl"], payload["closed"][0]["pnl"], name)
                self.assertFalse(os.path.exists(local + ".tmp"), name)


    def test_importlib_load_like_discord_host(self):
        """bot.py loads pimp_desk via importlib; desk_profit must still import."""
        import importlib.util
        folder = os.path.dirname(os.path.abspath(pimp_desk.__file__))
        # Drop paper-bots from path to mimic the Discord process.
        kept = list(sys.path)
        try:
            sys.path[:] = [p for p in sys.path if os.path.realpath(p) != os.path.realpath(folder)]
            path = os.path.join(folder, "pimp_desk.py")
            name = "pimp_desk_host_load_test"
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
            self.assertTrue(hasattr(mod, "desk_profit"))
            snap = mod.snapshot(folder)
            self.assertTrue(snap["paper_only"])
            self.assertEqual(snap["roi_system"]["version"], 2)
        finally:
            sys.path[:] = kept
            sys.modules.pop("pimp_desk_host_load_test", None)

    def test_venue_min_edge_and_kelly_lite(self):
        cfg, err = pimp_desk.parse_settings({
            "stake_hi_min": 20, "stake_hi_max": 100, "stake_lo_max": 20,
            "daily_loss_stop": 50, "max_open_risk": 100, "max_open_positions": 4,
            "min_edge": 0.06,
            "venue_min_edge": {"kalshi_sports": 0.07, "kalshi_btc15m": 0.05,
                               "kalshi_inx": 0.02, "solana_dex": 0.02},
            "sizing": "kelly_lite",
            "kelly_fraction": 0.25,
        })
        self.assertIsNone(err)
        self.assertEqual(cfg["venue_min_edge"]["kalshi_sports"], 0.07)
        self.assertEqual(pimp_desk.venue_min_edge("kalshi_btc15m", cfg), 0.05)
        bad, err = pimp_desk.parse_settings({
            "stake_hi_min": 20, "stake_hi_max": 100, "stake_lo_max": 20,
            "daily_loss_stop": 50, "max_open_risk": 100, "max_open_positions": 4,
            "venue_min_edge": {"nope": 0.1},
        })
        self.assertIsNone(bad)
        self.assertIn("Unknown venue", err)
        soft, soft_err = pimp_desk.parse_settings({
            "stake_hi_min": 20, "stake_hi_max": 100, "stake_lo_max": 20,
            "daily_loss_stop": 50, "max_open_risk": 100, "max_open_positions": 4,
            "venue_min_edge": {"kalshi_btc15m": 0.01},
        })
        self.assertIsNone(soft)
        self.assertIn("locked floor", soft_err)
        small = pimp_desk.kelly_lite_dollars(0.85, 0.04, cfg=cfg, open_risk_used=0, ask=0.75)
        big = pimp_desk.kelly_lite_dollars(0.92, 0.10, cfg=cfg, open_risk_used=0, ask=0.75)
        self.assertGreater(big, small)
        capped = pimp_desk.kelly_lite_dollars(0.95, 0.12, cfg=cfg, open_risk_used=90, ask=0.70)
        self.assertLessEqual(capped, 10.0 + 1e-9)
        zero = pimp_desk.kelly_lite_dollars(0.95, 0.12, cfg=cfg, open_risk_used=100, ask=0.70)
        self.assertEqual(zero, 0.0)

    def test_correlation_veto_btc_vs_kalshi(self):
        import desk_profit
        open_rows = [{
            "bot": "btc15m", "side": "YES", "factor": "risk_on_btc",
            "edge": 0.08, "risk": 20, "what": "KXBTC",
        }]
        blocked = desk_profit.correlation_veto_reason(
            "kalshi-sp", "yes", 0.05, open_rows
        )
        self.assertIn("correlation veto", blocked)
        allowed = desk_profit.correlation_veto_reason(
            "kalshi-sp", "yes", 0.12, open_rows
        )
        # Higher candidate edge still vetoes stacking heat in current rule.
        self.assertIn("correlation veto", allowed)
        clear = desk_profit.correlation_veto_reason(
            "kalshi-sp", "no", 0.05, open_rows
        )
        self.assertEqual(clear, "")

    def test_expectancy_starve_and_shadow_excluded(self):
        import desk_profit
        now = dt.datetime(2026, 11, 1, 12, 0, tzinfo=dt.timezone.utc)
        history = []
        for i in range(10):
            history.append({
                "pnl": -2.0 if i < 7 else 1.0,
                "closed": (now - dt.timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S UTC"),
            })
        exp = desk_profit.bot_expectancy(history, window_days=20, now=now)
        self.assertEqual(exp["n"], 10)
        self.assertIsNotNone(exp["expectancy"])
        self.assertLess(exp["expectancy"], 0)
        starve = desk_profit.starve_state(exp, {
            "starve_min_n": 8, "starve_expectancy": 0.0, "starve_factor": 0.25,
        })
        self.assertTrue(starve["starved"])
        self.assertEqual(starve["starve_factor"], 0.25)
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, STUB)
            cfg = {
                "stake_hi_min": 20, "stake_hi_max": 100, "stake_lo_max": 20,
                "daily_loss_stop": 150, "max_open_risk": 100, "max_open_positions": 12,
                "min_edge": 0.06, "pace_min": 6, "pace_target": 12,
            }
            pimp_desk.save_settings(cfg, tmp)
            # Seed a shadow account with cash that must not enter desk.cash.
            pimp_desk.save_shadow_account(tmp, "btc15m", "edge08", {
                "cash": 999.0, "open": [], "closed": [], "paper_only": True,
            })
            snap = pimp_desk.snapshot(tmp)
            self.assertNotEqual(snap["desk"]["cash"], 999.0)
            self.assertGreaterEqual(snap["desk"]["ops"]["shadow_count"], 1)
            board = snap["desk"]["shadow_leaderboard"]
            self.assertTrue(any(r.get("variant_id") == "edge08" for r in board))
            self.assertAlmostEqual(board[0]["cash"], 999.0)

    def test_model_flip_adverse_helper(self):
        import desk_profit
        self.assertTrue(desk_profit.model_flip_adverse("YES", 0.85, 0.70, 0.08))
        self.assertFalse(desk_profit.model_flip_adverse("YES", 0.85, 0.80, 0.08))
        # Held-side fair: away/NO adverse is a DROP, not a rise (LALDET false-flip class).
        self.assertTrue(desk_profit.model_flip_adverse("away", 0.8907, 0.8277, 0.06))
        self.assertFalse(desk_profit.model_flip_adverse("away", 0.826, 0.915, 0.06))
        self.assertTrue(desk_profit.model_flip_adverse("NO", 0.85, 0.70, 0.08))
        self.assertFalse(desk_profit.model_flip_adverse("NO", 0.20, 0.35, 0.08))

    def test_midnight_reloads_broke_towers_only(self):
        broke = {
            "id": "memecoin", "present": True, "open_count": 0,
            "cash": 5.09, "today": -94.91, "realized": -94.91, "history": [
                {"pnl": -25.0, "fill_id": "a", "ask": 0.5},
                {"pnl": -30.0, "fill_id": "b", "ask": 0.5},
            ],
        }
        winner = {
            "id": "btc15m", "present": True, "open_count": 0,
            "cash": 120.0, "today": 8.0, "realized": 20.0, "history": [],
        }
        armed = {
            "id": "sports-gap", "present": True, "open_count": 0,
            "cash": 79.0, "today": 0.0, "realized": 0.0, "history": [],
        }
        open_book = {
            "id": "kalshi-sp", "present": True, "open_count": 1,
            "cash": 5.0, "today": -10.0, "realized": -40.0, "history": [],
        }
        self.assertTrue(pimp_desk.tower_needs_midnight_reload(broke))
        self.assertFalse(pimp_desk.tower_needs_midnight_reload(winner))
        self.assertTrue(pimp_desk.tower_doing_good(winner))
        self.assertTrue(pimp_desk.tower_doing_good(armed))
        self.assertFalse(pimp_desk.tower_needs_midnight_reload(armed))
        self.assertTrue(pimp_desk.tower_doing_good(open_book))  # open → leave alone
        # Sticky INX / sports losers do not get fresh midnight ammo.
        sticky_sp = {
            "id": "kalshi-sp", "present": True, "open_count": 0,
            "cash": 444.37, "today": 0.0, "realized": -55.63, "history": [],
        }
        sticky_sports = {
            "id": "sports-gap", "present": True, "open_count": 0,
            "cash": 83.38, "today": 0.0, "realized": -16.62, "history": [],
        }
        self.assertFalse(pimp_desk.tower_needs_midnight_reload(sticky_sp))
        self.assertFalse(pimp_desk.tower_needs_midnight_reload(sticky_sports))
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, QUIET)
            # Broke memecoin account on disk.
            meme = os.path.join(tmp, "memecoin-paper")
            os.makedirs(meme, exist_ok=True)
            with open(os.path.join(meme, "positions.json"), "w", encoding="utf-8") as handle:
                json.dump({
                    "cash_usd": 5.09, "open": [], "cooldown": {},
                    "realized_pnl_usd": -94.91, "paper_only": True,
                }, handle)
            with open(os.path.join(meme, "trades.csv"), "w", encoding="utf-8") as handle:
                handle.write("ts,side,pnl_usd\n2026-11-01,SELL,-25\n")
            # Healthy BTC stays.
            btc = os.path.join(tmp, "btc15m-signal")
            os.makedirs(btc, exist_ok=True)
            with open(os.path.join(btc, "paper_account.json"), "w", encoding="utf-8") as handle:
                json.dump({"cash": 120.0, "open": [], "closed": [], "paper_only": True}, handle)
            night = dt.datetime(2026, 11, 2, 0, 15, tzinfo=pimp_desk.CT)
            rows = pimp_desk.run_midnight_broke_reload(tmp, night)
            self.assertTrue(any(r.get("bot") == "memecoin" and r.get("action") == "midnight-reload" for r in rows))
            with open(os.path.join(meme, "positions.json"), encoding="utf-8") as handle:
                after = json.load(handle)
            self.assertEqual(after["cash_usd"], 100.0)
            self.assertEqual(after.get("realized_pnl_usd"), 0.0)
            self.assertFalse(os.path.exists(os.path.join(meme, "trades.csv")))
            with open(os.path.join(btc, "paper_account.json"), encoding="utf-8") as handle:
                btc_after = json.load(handle)
            self.assertEqual(btc_after["cash"], 120.0)
            with open(pimp_desk.midnight_path(tmp), encoding="utf-8") as handle:
                marker = json.load(handle)
            self.assertEqual(marker["day"], "2026-11-02")
            self.assertIn("memecoin", marker["reloaded"])
            self.assertIn("btc15m", marker["left_alone"])
            # Second pass same day is a no-op.
            self.assertEqual(pimp_desk.run_midnight_broke_reload(tmp, night), [])
            # Outside the early window: skip.
            afternoon = dt.datetime(2026, 11, 2, 15, 0, tzinfo=pimp_desk.CT)
            self.assertEqual(pimp_desk.run_midnight_broke_reload(tmp, afternoon), [])


if __name__ == "__main__":
    unittest.main()
