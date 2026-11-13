"""The desk timer runs without the Discord bot. Paper only."""
import os
import unittest
from unittest import mock

import desk_service


class FakeDesk:
    def __init__(self, alert="", notes=(), recap="", fail=False):
        self.calls = []
        self._alert, self._notes, self._recap, self._fail = alert, list(notes), recap, fail

    def touch_heartbeat(self):
        self.calls.append("heartbeat")

    def timer_health(self):
        self.calls.append("health")
        return {"alert": self._alert}

    def run_scheduled(self):
        self.calls.append("run")
        if self._fail:
            raise RuntimeError("boom")

    def drain_alerts(self):
        self.calls.append("drain")
        return list(self._notes)

    def take_recap(self):
        self.calls.append("recap")
        return self._recap


class DeskServiceTests(unittest.TestCase):
    def test_one_pass_runs_the_same_steps_as_the_discord_timer(self):
        desk = FakeDesk(alert="Timer late", notes=["Paper buy BTC", "Paper file changed outside a bot run"], recap="Day recap")
        notes = desk_service.one_pass(desk)
        self.assertEqual(desk.calls, ["health", "run", "drain", "recap"])
        self.assertEqual(notes["audit"], ["Timer late", "Paper file changed outside a bot run"])
        self.assertEqual(notes["recap"], ["Paper buy BTC", "Day recap"])

    def test_timer_mode_defaults_to_the_discord_bot(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PAPER_TIMER", None)
            self.assertEqual(desk_service.timer_mode(), "internal")
        for value in ("external", "OFF", "service"):
            with mock.patch.dict(os.environ, {"PAPER_TIMER": value}):
                self.assertEqual(desk_service.timer_mode(), "external")

    def test_notes_go_to_webhooks_with_no_pings(self):
        sent = []

        class Resp:
            status = 204

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_open(req, timeout=0):
            sent.append((req.full_url, req.data))
            return Resp()

        env = {"PAPER_RECAP_WEBHOOK": "https://discord.test/recap", "PAPER_AUDIT_WEBHOOK": "https://discord.test/audit"}
        with mock.patch.dict(os.environ, env), mock.patch("urllib.request.urlopen", fake_open):
            desk_service.send_notes({"audit": ["a1"], "recap": ["r1"]})
        self.assertEqual([url for url, _ in sent], ["https://discord.test/audit", "https://discord.test/recap"])
        self.assertIn(b'"parse": []', sent[0][1])

    def test_a_failed_pass_does_not_stop_the_loop(self):
        desk = FakeDesk(fail=True)
        with mock.patch.object(desk_service, "send_notes") as send:
            desk_service.run_forever(desk, sleep=lambda s: None, passes=2)
        self.assertEqual(desk.calls.count("run"), 2)
        self.assertEqual(desk.calls[0], "heartbeat")
        self.assertIn("Paper timer failed", send.call_args_list[-1].args[0]["audit"][0])


if __name__ == "__main__":
    unittest.main()


class DeskOpenLogTests(unittest.TestCase):
    def setUp(self):
        desk_service._last_open_log[0] = 0.0

    def test_logs_open_count_every_five_minutes(self):
        class D:
            n = 0
            def desk_open_summary(self):
                D.n += 1
                return {"open": 3, "max_open": 12, "open_risk": 21.5, "max_open_risk": 100.0, "by_bot": {"btc15m": 3}}
        d = D()
        line = desk_service.log_desk_open(d, now=1000.0)
        self.assertTrue(line.startswith("desk open "))
        self.assertIn('"open": 3', line)
        self.assertEqual(desk_service.log_desk_open(d, now=1100.0), "")
        self.assertTrue(desk_service.log_desk_open(d, now=1301.0))
        self.assertEqual(D.n, 2)

    def test_a_failing_count_never_stops_the_pass(self):
        class D:
            def desk_open_summary(self):
                raise RuntimeError("boom")
        self.assertEqual(desk_service.log_desk_open(D(), now=5000.0), "")

    def test_desk_without_the_helper_is_fine(self):
        self.assertEqual(desk_service.log_desk_open(FakeDesk(), now=9000.0), "")


class DeskOpenSummaryTests(unittest.TestCase):
    def test_counts_like_the_entry_gate(self):
        import tempfile
        import pimp_desk
        bots = [
            {"id": "btc15m", "open_count": 2, "open_risk": 30},
            {"id": "sports-gap", "open_count": 1, "open_risk": 20},
            {"id": "more-15m", "open_count": 4, "open_risk": 50, "shadow_only": True},
        ]
        with tempfile.TemporaryDirectory() as root:
            s = pimp_desk.desk_open_summary(root, bots=bots)
        self.assertEqual(s["open"], 3)
        self.assertEqual(s["max_open"], 12)
        self.assertEqual(s["open_risk"], 50.0)
        self.assertEqual(s["by_bot"], {"btc15m": 2, "sports-gap": 1})
