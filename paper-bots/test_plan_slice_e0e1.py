"""APEX plan slice E0/E1: weekday timer alert, skip taxonomy, INX slots, sports scale-out."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import desk_more
import desk_top25
import pimp_desk

CT = ZoneInfo("America/Chicago")
ROOT = os.path.dirname(os.path.abspath(__file__))


class PlanSliceE0E1Tests(unittest.TestCase):
    def test_weekday_timer_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc)  # Mon
            pimp_desk.touch_heartbeat(tmp, stale)
            now = stale + timedelta(minutes=12)
            health = pimp_desk.timer_health(tmp, now=now)
            self.assertFalse(health["alive"])
            self.assertTrue(health["weekday_alert"])
            self.assertIn("WEEKDAY ALERT", health["alert"])

            # Weekend: still dead, but no weekday alert flag.
            sun = datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc)
            pimp_desk.touch_heartbeat(tmp, sun)
            sun_now = sun + timedelta(minutes=12)
            wh = pimp_desk.timer_health(tmp, now=sun_now)
            self.assertFalse(wh["alive"])
            self.assertFalse(wh["weekday_alert"])

    def test_skip_taxonomy_stable(self):
        self.assertEqual(desk_more.stable_skip_code("edge"), "EDGE")
        self.assertEqual(desk_more.stable_skip_code("z"), "Z")
        self.assertEqual(desk_more.stable_skip_code("correlation"), "CORR")
        with tempfile.TemporaryDirectory() as tmp:
            desk_more.record_skip_codes(
                tmp, bot="btc15m", reasons=["edge short of min"], weekday=0, day="2026-11-02",
            )
            board = desk_more.skip_leaderboard(tmp, day="2026-11-02")
            self.assertTrue(board["stable_top"])
            self.assertEqual(board["stable_top"][0]["code"], "EDGE")
            self.assertIn("EDGE", board["taxonomy"])

    def test_inx_forced_slots(self):
        slots = [s for s in pimp_desk.AUTO if s["id"] == "kalshi-sp" and s["action"] == "run"]
        self.assertEqual([s["at_ct"] for s in slots], ["12:00"])
        self.assertEqual(slots[0]["until_ct"], "14:00")
        morning = datetime(2026, 11, 2, 9, 0, tzinfo=CT)
        self.assertIn("12:00", pimp_desk.next_inx_scan_line("kalshi-sp", morning))

    def test_sports_scale_out_constants(self):
        import importlib.util
        path = os.path.join(ROOT, "sports-gap-paper", "gap_bot.py")
        spec = importlib.util.spec_from_file_location("gap_bot_scale", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.SCALE_OUT_FAIR_MOVE, 0.08)
        self.assertEqual(mod.SCALE_OUT_FRAC, 0.50)

    def test_sports_scale_out_densifies_closed_and_phase2(self):
        """Partial scale-out must stamp closed[] clip + remember_scale_out."""
        path = os.path.join(ROOT, "sports-gap-paper", "gap_bot.py")
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        densify = src.find("Densify clip into closed[]")
        self.assertGreater(densify, 0)
        end = src.find("exit_reason = f\"scale-out +{SCALE_OUT_FAIR_MOVE", densify)
        chunk = src[densify:end if end > densify else densify + 4000]
        self.assertIn('s.setdefault("closed", []).append(clip_row)', chunk)
        self.assertIn('"scale_out_clip": True', chunk)
        self.assertIn('"exit_price": round(float(bid), 4)', chunk)
        self.assertIn("desk_phase2.remember_scale_out", chunk)
        # Runner stays open — still.append after densify.
        self.assertIn("still.append(p)", chunk)

    def test_doctor_traceback_and_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            clean = desk_top25.desk_doctor(tmp, health={"alive": True})
            self.assertTrue(clean["ok"])
            with open(os.path.join(tmp, "pimp-runs.json"), "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "sports-gap": {
                            "ok": False,
                            "summary": "Traceback (most recent call last):\nUnboundLocalError",
                        },
                        "btc15m": {
                            "ok": True,
                            "summary": "CARD: Checked all open BTC markets. No paper buy.",
                        },
                    },
                    handle,
                )
            bad = desk_top25.desk_doctor(tmp, health={"alive": True})
            names = {c["name"]: c for c in bad["checks"]}
            self.assertFalse(names["no_traceback_in_runs"]["ok"])
            self.assertTrue(names["card_line_present"]["ok"])


if __name__ == "__main__":
    unittest.main()
