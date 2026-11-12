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

    def test_midnight_refill_keeps_the_loss_on_the_lifetime_record(self):
        self._broke_meme()
        rows = pimp_desk.run_midnight_broke_reload(self.root, NIGHT)
        self.assertTrue(any(r.get("bot") == "memecoin" and r.get("action") == "midnight-reload" for r in rows))
        snap = pimp_desk.snapshot(self.root)
        meme = self._meme(snap)
        self.assertEqual(float(meme["realized"] or 0), 0.0)  # today's book is fresh
        life = meme["lifetime"]
        self.assertEqual(life["realized"], -55.0)
        self.assertEqual(life["resets"], 1)
        self.assertEqual(life["wiped_losses"], 55.0)
        self.assertEqual((life["trades"], life["wins"], life["losses"]), (3, 1, 2))
        # Peak +0 → -25 → -15 → -55: worst drop is 55 from the start.
        self.assertEqual(life["max_drawdown"], 55.0)
        self.assertEqual(snap["desk"]["lifetime"]["realized"], -55.0)
        self.assertEqual(snap["desk"]["lifetime"]["wiped_losses"], 55.0)

    def test_lifetime_is_banked_plus_the_current_book(self):
        self._broke_meme()
        pimp_desk.run_midnight_broke_reload(self.root, NIGHT)
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
        pimp_desk.run_midnight_broke_reload(self.root, NIGHT)
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
        pimp_desk.run_midnight_broke_reload(self.root, NIGHT)
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
        pimp_desk.run_midnight_broke_reload(self.root, NIGHT)
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

    def test_staff_reset_keeps_the_record(self):
        self._broke_meme()
        out = pimp_desk.reset_bot("memecoin", root=self.root, who="test")
        self.assertTrue(out.get("ok"), out)
        resets = desk_lifetime.load_ledger(self.root)["bots"]["memecoin"]["resets"]
        self.assertEqual(len(resets), 1)
        self.assertEqual(resets[0]["source"], "reset")
        self.assertEqual(resets[0]["realized"], -55.0)


if __name__ == "__main__":
    unittest.main()
