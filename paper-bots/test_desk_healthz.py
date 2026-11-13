"""The trading service's /healthz shows the last pass and the build, without the key."""
import json
import unittest
import urllib.request

from test_desk_split import FakeDesk, Server


class HealthzTests(unittest.TestCase):
    def test_healthz_keeps_old_fields_and_adds_last_pass(self):
        desk = FakeDesk("/x")
        desk._read_json = lambda p: {"at": "2026-11-13 17:58:00 UTC"}
        desk.heartbeat_path = lambda root=None: "/x/beat.json"
        desk._root = lambda root=None: "/nonexistent-desk"
        server = Server(desk)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{server.port}/healthz", timeout=10) as resp:
                body = json.loads(resp.read())
        finally:
            server.stop()
        for key in ("ok", "paper_only", "service", "timer_alive", "has_books", "imported"):
            self.assertIn(key, body)
        self.assertTrue(body["ok"])
        self.assertTrue(body["last_pass_at"].startswith("2026-11-13T17:58:00"))
        self.assertIsInstance(body["last_pass_age_s"], int)
        self.assertIn("build", body)
        self.assertIn("uptime_s", body)
