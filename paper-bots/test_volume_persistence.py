"""Desk files on the /data volume survive a redeploy, and midnight reloads stick.

These run against a fake app folder plus a fake volume, the same way
test_pimp_desk.test_closed_settlements_survive_an_update does. Paper only.
"""
import datetime as dt
import json
import os
import tempfile
import unittest

import pimp_desk
from test_pimp_desk import QUIET, _tree, _write


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class VolumePersistenceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.volume = os.path.join(self._tmp.name, "volume")
        self.root = os.path.join(self._tmp.name, "app", "paper-bots")
        _tree(self.root, QUIET)

    def tearDown(self):
        pimp_desk._BOUND_DURABLE.pop(os.path.realpath(self.root), None)
        pimp_desk._LINKED.clear()  # a redeploy is a new process
        self._tmp.cleanup()

    def _bind(self):
        return pimp_desk.keep_closed_settlements(self.root, durable=self.volume)

    def _redeploy(self):
        """A new image: every desk file is back to what git ships (here: nothing)."""
        for rel in pimp_desk.SETTLEMENT_FILES:
            local = os.path.join(self.root, *rel.split("/"))
            if os.path.lexists(local):
                os.remove(local)
        pimp_desk._BOUND_DURABLE.pop(os.path.realpath(self.root), None)
        pimp_desk._LINKED.clear()  # a redeploy is a new process

    def test_desk_control_files_are_on_the_saved_list(self):
        for name in (
            "pimp-pause.json",
            "pimp-trading.json",
            "pimp-bot-params.json",
            "pimp-midnight.json",
            "pimp-audit.json",
            "pimp-runs.json",
        ):
            self.assertIn(name, pimp_desk.SETTLEMENT_FILES)

    def test_a_pause_survives_a_redeploy(self):
        self._bind()
        pimp_desk.set_pause(self.root, all_bots=True, on=True, who="test")
        self.assertTrue(pimp_desk.bot_paused(self.root, "btc15m"))
        self._redeploy()
        self.assertFalse(pimp_desk.bot_paused(self.root, "btc15m"))  # before rebind
        self._bind()
        self.assertTrue(pimp_desk.bot_paused(self.root, "btc15m"))
        on_volume = json.loads(_read(os.path.join(self.volume, "pimp-pause.json")))
        self.assertTrue(on_volume.get("all"))

    def test_staff_limits_survive_a_redeploy(self):
        _write(pimp_desk.config_path(self.root), json.dumps({"paper_only": True, "daily_loss_stop": 150.0}))
        self._bind()
        raw = dict(pimp_desk.load_settings(self.root))
        raw["daily_loss_stop"] = 90.0
        _cfg, err = pimp_desk.save_settings(raw, root=self.root, who="test")
        self.assertFalse(err)
        # A new image ships the committed limits again.
        self._redeploy()
        _write(pimp_desk.config_path(self.root), json.dumps({"paper_only": True, "daily_loss_stop": 150.0}))
        self._bind()
        self.assertEqual(float(pimp_desk.load_settings(self.root)["daily_loss_stop"]), 90.0)

    def test_midnight_reload_sticks_on_the_volume(self):
        meme = os.path.join(self.root, "memecoin-paper")
        os.makedirs(meme, exist_ok=True)
        _write(os.path.join(meme, "positions.json"), json.dumps({
            "cash_usd": 5.09, "open": [], "cooldown": {},
            "realized_pnl_usd": -94.91, "paper_only": True,
        }))
        _write(os.path.join(meme, "trades.csv"), "ts,side,pnl_usd\n2026-11-01,SELL,-25\n")
        self._bind()
        self.assertTrue(os.path.islink(os.path.join(meme, "positions.json")))

        night = dt.datetime(2026, 11, 2, 0, 15, tzinfo=pimp_desk.CT)
        rows = pimp_desk.run_midnight_broke_reload(self.root, night)
        self.assertFalse(any(r.get("bot") == "memecoin" for r in rows))

        # The next timer pass rebinds the volume. The real loss must stay.
        self._bind()
        after = json.loads(_read(os.path.join(meme, "positions.json")))
        self.assertEqual(after["cash_usd"], 5.09)
        self.assertEqual(after["realized_pnl_usd"], -94.91)
        on_volume = json.loads(_read(os.path.join(self.volume, "memecoin-paper", "positions.json")))
        self.assertEqual(on_volume["cash_usd"], 5.09)
        trades = os.path.join(meme, "trades.csv")
        self.assertIn("-25", _read(trades))

        # The midnight marker is on the volume too, so a redeploy in the
        # early window does not run the pass twice.
        self._redeploy()
        self._bind()
        self.assertEqual(pimp_desk.run_midnight_broke_reload(self.root, night), [])

    def test_midnight_reload_without_a_volume_is_unchanged(self):
        meme = os.path.join(self.root, "memecoin-paper")
        os.makedirs(meme, exist_ok=True)
        _write(os.path.join(meme, "positions.json"), json.dumps({
            "cash_usd": 5.09, "open": [], "cooldown": {},
            "realized_pnl_usd": -94.91, "paper_only": True,
        }))
        night = dt.datetime(2026, 11, 2, 0, 15, tzinfo=pimp_desk.CT)
        pimp_desk.run_midnight_broke_reload(self.root, night)
        archived = os.path.join(self.root, "midnight-archive", "2026-11-02", "memecoin-paper__positions.json")
        self.assertFalse(os.path.isfile(archived))
        after = json.loads(_read(os.path.join(meme, "positions.json")))
        self.assertEqual(after["cash_usd"], 5.09)
        self.assertEqual(after.get("realized_pnl_usd"), -94.91)


if __name__ == "__main__":
    unittest.main()
