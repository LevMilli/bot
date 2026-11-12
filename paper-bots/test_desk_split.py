"""The Discord bot reaches the trading service only through the private desk API. Paper only."""
import asyncio
import io
import json
import os
import socket
import tarfile
import tempfile
import threading
import types
import unittest
from unittest import mock

import desk_remote
import desk_service
import desk_web

KEY = "k" * 32


class FakeDesk(types.SimpleNamespace):
    """Stands in for pimp_desk. Records every call."""

    def __init__(self, root):
        super().__init__()
        self.ROOT = root
        self.SETTLEMENT_FILES = ("memecoin-paper/positions.json", "pimp-pause.json")
        self.seen = []

    def settlement_dir(self):
        return None

    def keep_closed_settlements(self, *a, **k):
        self.seen.append(("keep",))
        return []

    def audit(self, *a, **k):
        self.seen.append(("audit", a[2] if len(a) > 2 else ""))

    def timer_health(self):
        return {"alive": True}

    def snapshot(self, q="", filt="all", page=1):
        self.seen.append(("snapshot", q, filt, page))
        return {"paper_only": True, "bots": [], "desk": {"lifetime": {"realized": -5.0}}}

    def save_settings(self, raw, root=None, who=""):
        self.seen.append(("save", raw, root, who))
        return dict(raw), ""

    def set_pause(self, root, bot, on, who, all_bots=False):
        self.seen.append(("pause", root, bot, on, who, all_bots))
        return {"ok": True, "summary": "paused"}

    def export_xlsx(self):
        return b"PK\x03\x04xlsx"

    def public_error(self, text):
        return str(text or "")[:80]

    def role_can(self, role, what):
        return role == "Owner"


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Server:
    def __init__(self, desk):
        from aiohttp import web

        self.port = _free_port()
        self.loop = asyncio.new_event_loop()
        self.runner = web.AppRunner(desk_web.make_app(desk))
        ready = threading.Event()

        def run():
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.runner.setup())
            self.loop.run_until_complete(web.TCPSite(self.runner, "127.0.0.1", self.port).start())
            ready.set()
            self.loop.run_forever()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        ready.wait(10)

    def stop(self):
        asyncio.run_coroutine_threadsafe(self.runner.cleanup(), self.loop).result(10)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(10)


class DeskApiTests(unittest.TestCase):
    def test_key_must_match_and_be_long_enough(self):
        self.assertTrue(desk_web.key_ok(f"Bearer {KEY}", KEY))
        self.assertFalse(desk_web.key_ok("Bearer nope", KEY))
        self.assertFalse(desk_web.key_ok("Bearer short", "short"))
        self.assertFalse(desk_web.key_ok("", ""))

    def test_only_listed_calls_run_and_root_is_forced(self):
        desk = FakeDesk("/x")
        with self.assertRaises(KeyError):
            desk_web.call(desk, "keep_closed_settlements", [], {})
        with self.assertRaises(KeyError):
            desk_web.call(desk, "__class__", [], {})
        desk_web.call(desk, "set_pause", ["/etc", "btc15m", True, "staff"], {})
        self.assertEqual(desk.seen[-1][1], None)
        desk_web.call(desk, "save_settings", [{"daily_loss_stop": 90}], {"root": "/etc", "who": "s"})
        self.assertEqual(desk.seen[-1][2], None)

    def test_bytes_and_tuples_survive_the_trip(self):
        value = ({"a": 1}, "", b"\x00\x01")
        self.assertEqual(desk_web.decode(json.loads(json.dumps(desk_web.encode(value)))), value)

    def test_import_fills_an_empty_service_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk = FakeDesk(tmp)
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w:gz") as tar:
                data = b'{"cash_usd": 5}'
                info = tarfile.TarInfo("memecoin-paper/positions.json")
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
                bad = tarfile.TarInfo("../escape.txt")
                bad.size = 1
                tar.addfile(bad, io.BytesIO(b"x"))
            out = desk_web.import_books(desk, buf.getvalue())
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["files"], 1)
            self.assertFalse(os.path.exists(os.path.join(os.path.dirname(tmp), "escape.txt")))
            with open(os.path.join(tmp, "memecoin-paper", "positions.json")) as handle:
                self.assertIn("5", handle.read())
            again = desk_web.import_books(desk, buf.getvalue())
            self.assertFalse(again["ok"])

    def test_pack_then_import_moves_the_books(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            os.makedirs(os.path.join(src, "memecoin-paper"))
            with open(os.path.join(src, "memecoin-paper", "positions.json"), "w") as handle:
                handle.write('{"cash_usd": 42}')
            os.makedirs(os.path.join(src, "midnight-archive", "2026-11-02"))
            with open(os.path.join(src, "midnight-archive", "2026-11-02", "memecoin-paper__trades.csv"), "w") as handle:
                handle.write("ts,side,pnl_usd\n")
            blob = desk_web.pack_books(FakeDesk(src))
            out = desk_web.import_books(FakeDesk(dst), blob)
            self.assertTrue(out["ok"], out)
            self.assertTrue(os.path.isfile(os.path.join(dst, "midnight-archive", "2026-11-02", "memecoin-paper__trades.csv")))


class RemoteDeskTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.desk = FakeDesk(self._tmp.name)
        self.server = Server(self.desk)
        self.url = f"http://127.0.0.1:{self.server.port}"

    def tearDown(self):
        self.server.stop()
        self._tmp.cleanup()

    def test_staff_calls_reach_the_service(self):
        with mock.patch.dict(os.environ, {"DESK_SERVICE_KEY": KEY}):
            remote = desk_remote.RemoteDesk(self.desk, self.url, KEY)
            snap = remote.snapshot(q="btc", filt="open", page=2)
            self.assertEqual(snap["desk"]["lifetime"]["realized"], -5.0)
            self.assertIn(("snapshot", "btc", "open", 2), self.desk.seen)
            cfg, err = remote.save_settings({"daily_loss_stop": 90.0}, who="Levi")
            self.assertEqual((cfg, err), ({"daily_loss_stop": 90.0}, ""))
            self.assertTrue(remote.set_pause(None, "", True, "Levi", True)["ok"])
            self.assertEqual(remote.export_xlsx(), b"PK\x03\x04xlsx")
            # Pure staff rules run locally.
            self.assertTrue(remote.role_can("Owner", "save"))
            self.assertEqual(remote.backup_paper(dest="/tmp/x"), [])

    def test_a_wrong_key_is_refused(self):
        with mock.patch.dict(os.environ, {"DESK_SERVICE_KEY": KEY}):
            remote = desk_remote.RemoteDesk(self.desk, self.url, "w" * 32)
            with self.assertRaises(desk_remote.RemoteDeskError):
                remote.snapshot()
        self.assertFalse(any(row[0] == "snapshot" for row in self.desk.seen))

    def test_a_down_service_is_a_clear_error(self):
        remote = desk_remote.RemoteDesk(self.desk, f"http://127.0.0.1:{_free_port()}", KEY)
        with self.assertRaises(desk_remote.RemoteDeskError) as caught:
            remote.snapshot()
        self.assertIn("did not answer", str(caught.exception))

    def test_push_books_only_fills_an_empty_service(self):
        with tempfile.TemporaryDirectory() as bot_root:
            os.makedirs(os.path.join(bot_root, "memecoin-paper"))
            with open(os.path.join(bot_root, "memecoin-paper", "positions.json"), "w") as handle:
                handle.write('{"cash_usd": 42}')
            with mock.patch.dict(os.environ, {"DESK_SERVICE_KEY": KEY}):
                remote = desk_remote.RemoteDesk(FakeDesk(bot_root), self.url, KEY)
                first = remote.push_books()
                self.assertTrue(first.get("ok"), first)
                second = remote.push_books()
                self.assertFalse(second.get("ok"))


class WiringTests(unittest.TestCase):
    def test_wrap_stays_local_without_a_service(self):
        local = object()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DESK_SERVICE_URL", None)
            self.assertIs(desk_remote.wrap(local), local)

    def test_wrap_needs_a_long_key(self):
        with mock.patch.dict(os.environ, {"DESK_SERVICE_URL": "http://desk:8080", "DESK_SERVICE_KEY": "short"}):
            with self.assertRaises(desk_remote.RemoteDeskError):
                desk_remote.wrap(object())

    def test_a_bot_pointed_at_a_service_never_runs_the_timer(self):
        with mock.patch.dict(os.environ, {"DESK_SERVICE_URL": "http://desk:8080"}):
            os.environ.pop("PAPER_TIMER", None)
            self.assertEqual(desk_service.timer_mode(), "external")


if __name__ == "__main__":
    unittest.main()
