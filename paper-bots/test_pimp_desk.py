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
        snap = pimp_desk.snapshot(ROOT)
        self.assertTrue(snap["paper_only"])
        self.assertIn("PAPER ONLY", snap["banner"])
        self.assertEqual([b["id"] for b in snap["bots"]],
                         ["sports-gap", "kalshi-sp", "btc15m", "memecoin", "kalshi-sized"])
        sized = snap["bots"][-1]
        self.assertFalse(sized["present"])
        self.assertEqual(sized["actions"], [])
        expected_cash = {"sports-gap": 100.0, "kalshi-sp": 500.0, "btc15m": 100.0, "memecoin": 100.0}
        for bot in snap["bots"][:-1]:
            self.assertTrue(bot["present"], bot["id"])
            self.assertTrue(bot["has_state"], bot["id"])
            self.assertEqual(bot["cash"], expected_cash[bot["id"]], bot["id"])
            self.assertEqual(bot["positions"], [])
            self.assertEqual(bot["trades"], [])
        self.assertEqual(snap["desk"]["curve"], [])
        self.assertEqual(snap["desk"]["equity"], [])
        self.assertEqual(snap["desk"]["pace_line"], "0 of 12 this hour")
        self.assertTrue(snap["desk"]["pace_loosened"])
        self.assertEqual(snap["desk"]["cash"], 800.0)
        self.assertIn("Run one check", [a["label"] for a in snap["bots"][0]["actions"]])
        self.assertIn("Morning brief", [a["label"] for a in snap["bots"][1]["actions"]])
        self.assertIn("20.00", snap["limits_text"])
        self.assertIn("100.00", snap["limits_text"])
        self.assertIn("6 to 12", snap["limits_text"])
        self.assertIn("150.00", snap["limits_text"])
        self.assertIn("0.04", snap["limits_text"])
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
                          "cost": 3, "opened": "2026-10-30 12:00:00 CT"}] * pimp_desk.DEFAULTS["max_open_positions"],
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
        self.assertEqual(gap.stake_for_model(0.90, pimp_desk), 60.0)
        self.assertEqual(gap.stake_for_model(1, pimp_desk), 100.0)
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
        self.assertEqual(pimp_desk.paper_fill(0.40, 0.42), 0.42)
        self.assertIsNone(pimp_desk.paper_fill(0.40, None))
        self.assertNotEqual(pimp_desk.paper_fill(0.40, 0.50), 0.45)
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
        script = text[end:]
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
        self.assertEqual(pimp_desk.edge_for_hour(0, 0.04), (0.0, True))
        self.assertEqual(pimp_desk.edge_for_hour(4, 0.04), (0.0, True))
        self.assertEqual(pimp_desk.edge_for_hour(12, 0.04), (0.04, False))

    def test_hour_pace_counts_this_chicago_hour_only(self):
        now = dt.datetime(2026, 10, 30, 16, 15, tzinfo=pimp_desk.CT)
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, QUIET)
            self.assertEqual(pimp_desk.hour_pace(tmp, now)["line"], "0 of 12 this hour")
            self.assertTrue(pimp_desk.hour_pace(tmp, now)["loosened"])
            self.assertEqual(pimp_desk.hour_pace(tmp, now)["edge"], 0.0)
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
            self.assertTrue(pace["loosened"])
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
            self.assertEqual(done["edge"], 0.04)

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
            self.assertEqual(set(made), {"sports-gap", "kalshi-sp", "btc15m", "memecoin"})
            snap = pimp_desk.snapshot(tmp)
            by_id = {bot["id"]: bot for bot in snap["bots"]}
            self.assertEqual(by_id["sports-gap"]["cash"], 100.0)
            self.assertEqual(by_id["kalshi-sp"]["cash"], 500.0)
            self.assertEqual(by_id["btc15m"]["cash"], 100.0)
            self.assertEqual(by_id["memecoin"]["cash"], 100.0)
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


if __name__ == "__main__":
    unittest.main()
