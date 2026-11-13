"""Lifetime record: losses cleared by the midnight refill or a reset still count. Paper only."""
import datetime as dt
import json
import os
import shutil
import tempfile
import unittest

import desk_lifetime
import pimp_desk
from test_pimp_desk import QUIET, _tree, _write

NIGHT = dt.datetime(2026, 11, 2, 0, 15, tzinfo=pimp_desk.CT)


class LifetimeLedgerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.volume = os.path.join(self._tmp.name, "volume")
        self.root = os.path.join(self._tmp.name, "app", "paper-bots")
        _tree(self.root, QUIET)
        desk_lifetime._BACKFILLED.discard(os.path.realpath(self.root))

    def tearDown(self):
        pimp_desk._BOUND_DURABLE.pop(os.path.realpath(self.root), None)
        desk_lifetime._BACKFILLED.discard(os.path.realpath(self.root))
        self._tmp.cleanup()

    def _broke_meme(self, rows="2026-11-01T10:00:00,SELL,-25\n2026-11-01T11:00:00,SELL,10\n2026-11-01T12:00:00,SELL,-40\n"):
        meme = os.path.join(self.root, "memecoin-paper")
        os.makedirs(meme, exist_ok=True)
        _write(os.path.join(meme, "positions.json"), json.dumps({
            "cash_usd": 5.09, "open": [], "cooldown": {},
            "realized_pnl_usd": -94.91, "paper_only": True,
        }))
        _write(os.path.join(meme, "trades.csv"), "ts,side,pnl_usd\n" + rows)
        return meme

    def _meme(self, snap):
        return next(b for b in snap["bots"] if b["id"] == "memecoin")

    def test_lifetime_file_is_on_the_saved_list(self):
        self.assertIn("pimp-lifetime.json", pimp_desk.SETTLEMENT_FILES)

    def _wipe_meme(self):
        view = self._meme(pimp_desk.snapshot(self.root))
        return pimp_desk.reload_broke_tower(self.root, view, "2026-11-02")

    def test_midnight_leaves_the_loss_on_the_book(self):
        self._broke_meme()
        rows = pimp_desk.run_midnight_broke_reload(self.root, NIGHT)
        self.assertFalse(any(r.get("bot") == "memecoin" for r in rows))
        snap = pimp_desk.snapshot(self.root)
        meme = self._meme(snap)
        self.assertEqual(meme["realized"], -55.0)
        life = meme["lifetime"]
        self.assertEqual(life["realized"], -55.0)
        self.assertEqual(life["resets"], 0)
        self.assertEqual(life["current"], -55.0)
        self.assertEqual((life["trades"], life["wins"], life["losses"]), (3, 1, 2))
        self.assertEqual(snap["desk"]["realized"], -55.0)

    def test_lifetime_is_banked_plus_the_current_book(self):
        self._broke_meme()
        self._wipe_meme()
        meme = os.path.join(self.root, "memecoin-paper")
        _write(os.path.join(meme, "trades.csv"), "ts,side,pnl_usd\n2026-11-02T15:00:00,SELL,7.5\n")
        life = self._meme(pimp_desk.snapshot(self.root))["lifetime"]
        self.assertEqual(life["current"], 7.5)
        self.assertEqual(life["banked"], -55.0)
        self.assertEqual(life["realized"], -47.5)
        self.assertEqual(life["trades"], 4)

    def test_drawdown_measures_peak_to_trough(self):
        self.assertEqual(desk_lifetime._drawdown([10, 5, -20, 30, -4]), 20.0)
        self.assertEqual(desk_lifetime._drawdown([5, 5]), 0.0)
        self.assertIsNone(desk_lifetime._drawdown([]))

    def test_a_missing_number_stays_missing(self):
        life = desk_lifetime._bot_lifetime({"id": "x", "realized": None, "history": []}, {})
        self.assertIsNone(life["realized"])
        self.assertIsNone(life["max_drawdown"])

    def test_the_record_survives_a_redeploy(self):
        self._broke_meme()
        pimp_desk.keep_closed_settlements(self.root, durable=self.volume)
        self._wipe_meme()
        self.assertTrue(os.path.isfile(os.path.join(self.volume, "pimp-lifetime.json")))
        # New image: desk files are gone from the app folder.
        for rel in pimp_desk.SETTLEMENT_FILES:
            local = os.path.join(self.root, *rel.split("/"))
            if os.path.lexists(local):
                os.remove(local)
        pimp_desk._BOUND_DURABLE.pop(os.path.realpath(self.root), None)
        pimp_desk.keep_closed_settlements(self.root, durable=self.volume)
        life = self._meme(pimp_desk.snapshot(self.root))["lifetime"]
        self.assertEqual(life["realized"], -55.0)

    def test_old_wipes_are_rebuilt_from_the_archive_once(self):
        self._broke_meme()
        self._wipe_meme()
        # Pretend the wipe happened before this ledger existed.
        os.remove(desk_lifetime.ledger_path(self.root))
        _write(pimp_desk.audit_path(self.root), json.dumps({"rows": []}))
        self.assertEqual(desk_lifetime.backfill(self.root), 1)
        self.assertEqual(desk_lifetime.backfill(self.root), 0)
        ledger = desk_lifetime.load_ledger(self.root)
        self.assertEqual(ledger["keys"], ["memecoin:2026-11-02"])
        reset = ledger["bots"]["memecoin"]["resets"][0]
        self.assertEqual(reset["source"], "archive")
        self.assertEqual(reset["realized"], -55.0)
        self.assertEqual(len(ledger["bots"]["memecoin"]["trades"]), 3)

    def test_audit_row_fills_in_when_no_archive_copy_is_left(self):
        self._broke_meme()
        self._wipe_meme()
        os.remove(desk_lifetime.ledger_path(self.root))
        shutil.rmtree(os.path.join(self.root, "midnight-archive"))
        self.assertEqual(desk_lifetime.backfill(self.root), 1)
        reset = desk_lifetime.load_ledger(self.root)["bots"]["memecoin"]["resets"][0]
        self.assertEqual(reset["source"], "audit")
        self.assertEqual(reset["realized"], -55.0)
        self.assertEqual(desk_lifetime.backfill(self.root), 0)

    def test_midnight_does_not_bank_the_same_day_twice(self):
        bot = {"id": "memecoin", "realized": -10.0, "today": 0.0, "cash": 5.0,
               "history": [{"when": "2026-11-01T10:00:00", "pnl": -10.0}]}
        self.assertTrue(desk_lifetime.bank_before_reset(self.root, bot, "2026-11-02"))
        self.assertFalse(desk_lifetime.bank_before_reset(self.root, bot, "2026-11-02"))
        self.assertEqual(len(desk_lifetime.load_ledger(self.root)["bots"]["memecoin"]["resets"]), 1)

    def test_undo_puts_the_wiped_loss_back_on_the_live_book(self):
        self._broke_meme()
        view = self._meme(pimp_desk.snapshot(self.root))
        pimp_desk.reload_broke_tower(self.root, view, pimp_desk.UNDO_WIPE_DAY)
        live = os.path.join(self.root, "memecoin-paper", "positions.json")
        wiped = json.loads(open(live, encoding="utf-8").read())
        self.assertEqual(wiped["cash_usd"], 100.0)
        self.assertEqual(wiped["realized_pnl_usd"], 0.0)
        restored = pimp_desk.undo_midnight_wipe(self.root)
        self.assertEqual(restored, ["memecoin"])
        back = json.loads(open(live, encoding="utf-8").read())
        self.assertEqual(back["cash_usd"], 5.09)
        self.assertEqual(back["realized_pnl_usd"], -94.91)
        self.assertIn("-25", open(os.path.join(self.root, "memecoin-paper", "trades.csv"), encoding="utf-8").read())
        life = self._meme(pimp_desk.snapshot(self.root))["lifetime"]
        self.assertEqual(life["realized"], -55.0)
        self.assertEqual(life["resets"], 0)
        # A second pass does not apply the archive again.
        self.assertEqual(pimp_desk.undo_midnight_wipe(self.root), [])

    def test_staff_reset_keeps_the_record(self):
        self._broke_meme()
        out = pimp_desk.reset_bot("memecoin", root=self.root, who="test")
        self.assertTrue(out.get("ok"), out)
        resets = desk_lifetime.load_ledger(self.root)["bots"]["memecoin"]["resets"]
        self.assertEqual(len(resets), 1)
        self.assertEqual(resets[0]["source"], "reset")
        self.assertEqual(resets[0]["realized"], -55.0)

class WorseFillTests(unittest.TestCase):
    def test_contract_buy_held_to_settlement_pays_once(self):
        hit = desk_lifetime.trade_hit({"contracts": 10, "ask": 0.4, "payout": 10.0}, "contract", 0)
        self.assertAlmostEqual(hit, 0.10)
        hit = desk_lifetime.trade_hit({"contracts": 10, "ask": 0.4, "payout": 0.0}, "contract", 1)
        self.assertAlmostEqual(hit, 0.20)

    def test_contract_sold_early_pays_on_both_fills(self):
        hit = desk_lifetime.trade_hit({"contracts": 10, "payout": 6.2}, "contract", 0)
        self.assertAlmostEqual(hit, 0.20)

    def test_contracts_come_from_cost_over_ask_when_missing(self):
        hit = desk_lifetime.trade_hit({"cost": 4.0, "ask": 0.4}, "contract", 0)
        self.assertAlmostEqual(hit, 0.10)

    def test_spot_pays_a_percent_each_way(self):
        self.assertAlmostEqual(desk_lifetime.trade_hit({"cost": 100.0}, "spot", 0), 0.20)
        self.assertAlmostEqual(desk_lifetime.trade_hit({"cost": 100.0}, "spot", 1), 0.50)

    def test_unmeasurable_trades_are_left_out_not_guessed(self):
        self.assertIsNone(desk_lifetime.trade_hit({"pnl": 1.0}, "contract", 0))
        self.assertIsNone(desk_lifetime.trade_hit({"cost": 5.0}, "", 0))

    def test_bot_board_shows_worse_fill_lifetime(self):
        bot = {"id": "btc15m", "realized": 3.0, "history": [
            {"when": "2026-11-01T10:00:00", "pnl": 5.0, "contracts": 10, "ask": 0.5, "payout": 10.0},
            {"when": "2026-11-01T11:00:00", "pnl": -2.0, "contracts": 4, "ask": 0.5, "payout": 0.0},
            {"when": "2026-11-01T12:00:00", "pnl": 0.0},
        ]}
        life = desk_lifetime._bot_lifetime(bot, {})
        worse = life["worse"]
        self.assertEqual(worse["kind"], "contract")
        self.assertEqual(worse["measured"], 2)
        self.assertEqual(worse["realized_1"], round(3.0 - 0.14, 2))
        self.assertEqual(worse["realized_2"], round(3.0 - 0.28, 2))

    def test_no_measured_trades_means_no_worse_number(self):
        life = desk_lifetime._bot_lifetime({"id": "btc15m", "realized": 1.0, "history": [{"pnl": 1.0}]}, {})
        self.assertIsNone(life["worse"])

    def test_banked_trades_keep_what_the_report_needs(self):
        with tempfile.TemporaryDirectory() as root:
            bot = {"id": "btc15m", "realized": -2.0, "history": [
                {"when": "2026-11-01T10:00:00", "pnl": -2.0, "contracts": 4, "ask": 0.5, "payout": 0.0, "cost": 2.0}]}
            desk_lifetime.bank_before_reset(root, bot, "2026-11-02")
            trade = desk_lifetime.load_ledger(root)["bots"]["btc15m"]["trades"][0]
            self.assertEqual((trade["contracts"], trade["payout"], trade["ask"]), (4.0, 0.0, 0.5))
            board = desk_lifetime.lifetime_board(root, [{"id": "btc15m", "realized": 0.0, "history": []}])
            self.assertEqual(board["bots"]["btc15m"]["worse"]["realized_1"], -2.04)
            self.assertEqual(board["desk"]["worse"]["realized_2"], -2.08)


if __name__ == "__main__":
    unittest.main()
