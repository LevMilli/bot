"""City page cards and look rules (plan steps 806-885). Paper only. Read only."""
import ast
import datetime as dt
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import city_card
import desk_lifetime
import pimp_desk
from test_pimp_desk import QUIET, _tree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CITY = ROOT / "trading-city"
DAY = dt.date(2026, 11, 13)
NOW = dt.datetime(2026, 11, 13, 18, 0, tzinfo=dt.timezone.utc)


def _row(pnl, when="2026-11-13T16:00:00+00:00", exit_reason="settled", fee=0.1, what="t"):
    return {"what": what, "pnl": pnl, "closed_at": when, "settled_at": when, "exit_reason": exit_reason, "fee": fee}


class TodayStatsTests(unittest.TestCase):
    def test_losses_count_and_sum(self):
        rows = [_row(5.0, what="win"), _row(-7.5, what="loss"), _row(0.0, what="flat")]
        s = city_card.today_stats(rows, DAY, pimp_desk._ct_date)
        self.assertEqual((s["settled"], s["wins"], s["losses"], s["flat"]), (3, 1, 1, 1))
        self.assertEqual(s["pnl"], -2.5)
        self.assertEqual(s["fees"], 0.3)
        self.assertEqual(s["best"]["what"], "win")
        self.assertEqual(s["worst"]["what"], "loss")

    def test_central_day_not_utc_day(self):
        # 03:00 UTC on Nov 14 is 9 PM CT on Nov 13: still today in Chicago.
        late = _row(-4.0, when="2026-11-14T03:00:00+00:00")
        # 07:00 UTC on Nov 13 is 1 AM CT on Nov 13: today. 05:00 UTC Nov 13 is Nov 12 CT.
        early_prev = _row(9.0, when="2026-11-13T05:00:00+00:00")
        s = city_card.today_stats([late, early_prev], DAY, pimp_desk._ct_date)
        self.assertEqual(s["settled"], 1)
        self.assertEqual(s["pnl"], -4.0)

    def test_central_text_rows(self):
        row = {"what": "x", "pnl": -1.0, "closed_at": "November 13, 2026, 8:56 PM Central"}
        s = city_card.today_stats([row], DAY, pimp_desk._ct_date)
        self.assertEqual(s["losses"], 1)

    def test_early_sales_and_held_split(self):
        rows = [
            _row(2.0, exit_reason="take-profit bid"),
            _row(-1.0, exit_reason="model-flip"),
            _row(3.0, exit_reason="settled"),
        ]
        s = city_card.today_stats(rows, DAY, pimp_desk._ct_date)
        self.assertEqual((s["early_sales"], s["held"]), (2, 1))
        self.assertEqual((s["early_pnl"], s["held_pnl"]), (1.0, 3.0))

    def test_one_losing_trade_is_worst_not_best(self):
        s = city_card.today_stats([_row(-2.0)], DAY, pimp_desk._ct_date)
        self.assertIsNone(s["best"])
        self.assertEqual(s["worst"]["pnl"], -2.0)


class CardTests(unittest.TestCase):
    AUTO = (
        {"id": "btc15m", "action": "run", "every_sec": 60},
        {"id": "kalshi-sp", "action": "run", "at_ct": "13:05", "until_ct": "13:25"},
        {"id": "kalshi-sp", "action": "run", "at_ct": "12:05", "until_ct": "12:25"},
        {"id": "kalshi-sp", "action": "settle", "at_ct": "13:00", "until_ct": "15:55"},
    )

    def _card(self, bot, saved=None, spec=None):
        return city_card.card_for(bot, spec=spec, auto=self.AUTO, saved_auto=saved or {}, day=DAY,
                                  now=NOW, ct_date=pimp_desk._ct_date)

    def test_timer_and_next_check(self):
        saved = {"btc15m:run": (NOW - dt.timedelta(seconds=20)).isoformat()}
        c = self._card({"id": "btc15m", "present": True}, saved)
        self.assertEqual(c["every_sec"], 60)
        self.assertEqual(c["next_check_in_sec"], 40)

    def test_scan_times(self):
        c = self._card({"id": "kalshi-sp", "present": True})
        self.assertIsNone(c["every_sec"])
        self.assertEqual(c["scan_times"], ["12:05", "13:05"])

    def test_progress_only_on_practice_towers(self):
        self.assertIsNone(self._card({"id": "btc15m"})["progress"])
        p = self._card({"id": "twin", "shadow_only": True, "lifetime": {"trades": 12}})["progress"]
        self.assertEqual((p["have"], p["need"], p["counts"]), (12, 50, False))
        p = self._card({"id": "twin", "shadow_only": True, "lifetime": {"trades": 51}})["progress"]
        self.assertTrue(p["counts"])
        self.assertIn("Levi's OK", p["note"])
        research = self._card({"id": "calibration-lab", "shadow_only": True},
                              spec={"kind": "shadow", "category": "research"})
        self.assertIsNone(research["progress"])

    def test_error_light_clears_after_clean_run(self):
        bad = {"id": "btc15m", "last_run": {"ok": False, "exit": 2}}
        self.assertIn("exit code 2", self._card(bad)["error"])
        self.assertEqual(self._card({"id": "btc15m", "last_run": {"ok": True, "exit": 0}})["error"], "")
        # A desk gate block is not an error.
        self.assertEqual(self._card({"id": "btc15m", "last_run": {"ok": False, "blocked": True}})["error"], "")

    def test_learning_skip_flag_and_why(self):
        bot = {"id": "btc15m", "skip": "Skipping KXBTC YES hour=9 CT in 0.6. Fine paper bucket has 2/9 hits under 40% (learn v2)."}
        c = self._card(bot)
        self.assertTrue(c["learning_skip"])
        self.assertTrue(c["why_no_trade"])
        self.assertEqual(self._card({"id": "btc15m", "open_count": 1})["why_no_trade"], "")
        self.assertEqual(self._card({"id": "btc15m", "paused": True})["why_no_trade"], "Paused by staff.")

    def test_districts(self):
        self.assertEqual(city_card.district_for({"id": "btc15m"}), "vault")
        self.assertEqual(city_card.district_for({"id": "more-15m", "shadow_only": True}, {"category": "crypto"}), "crypto")
        self.assertEqual(city_card.district_for({"id": "weather-high", "shadow_only": True}, {"category": "weather"}), "weather")
        self.assertEqual(city_card.district_for({"id": "poly-sports-lean", "shadow_only": True}, {"category": "sports"}), "sports")
        self.assertEqual(city_card.district_for({"id": "scorekeeper", "shadow_only": True}, {"category": "research"}), "research")
        self.assertEqual(city_card.district_for({"id": "nasdaq", "shadow_only": True}, {"category": "index"}), "markets")


class BannerTests(unittest.TestCase):
    CFG = {"daily_loss_stop": 150.0, "max_open_positions": 12, "max_open_risk": 100.0}

    def test_real_money_off_and_stop_distance(self):
        b = city_card.city_banner({"today": -40.0, "open_count": 3, "open_risk": 50.0,
                                   "lifetime": {"realized": -10.0, "wins": 2, "losses": 5}}, self.CFG, [])
        self.assertEqual(b["real_money"], "off")
        self.assertEqual(b["stop_left"], 110.0)
        self.assertEqual((b["open_count"], b["max_open"], b["max_open_risk"]), (3, 12, 100.0))
        self.assertEqual((b["lifetime_realized"], b["lifetime_losses"]), (-10.0, 5))
        self.assertFalse(b["halted"])

    def test_wins_do_not_widen_the_stop(self):
        self.assertEqual(city_card.city_banner({"today": 80.0}, self.CFG, [])["stop_left"], 150.0)

    def test_halted_banner(self):
        b = city_card.city_banner({"today": -151.0, "gate": "Daily loss stop is hit ($151.00 against $150.00)."},
                                  self.CFG, [])
        self.assertTrue(b["halted"])
        self.assertEqual(b["stop_left"], 0.0)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self._tmp.name, "app", "paper-bots")
        _tree(self.root, QUIET)
        desk_lifetime._BACKFILLED.discard(os.path.realpath(self.root))

    def tearDown(self):
        pimp_desk._BOUND_DURABLE.pop(os.path.realpath(self.root), None)
        desk_lifetime._BACKFILLED.discard(os.path.realpath(self.root))
        self._tmp.cleanup()

    def test_every_tower_gets_a_card_and_the_desk_gets_a_banner(self):
        snap = pimp_desk.snapshot(self.root)
        for bot in snap["bots"]:
            self.assertIn("card", bot, bot["id"])
            self.assertIn(bot["card"]["district"], city_card.DISTRICTS)
        city = snap["desk"]["city"]
        self.assertEqual(city["real_money"], "off")
        self.assertNotIn("error", city)
        btc = next(b for b in snap["bots"] if b["id"] == "btc15m")
        self.assertEqual(btc["card"]["every_sec"], 60)

    def test_cards_do_not_change_tower_numbers(self):
        snap = pimp_desk.snapshot(self.root)
        keep = {b["id"]: (b.get("cash"), b.get("realized"), b.get("today"), b.get("open_count"), b.get("open_risk"))
                for b in snap["bots"]}
        snap2 = pimp_desk.snapshot(self.root)
        self.assertEqual(keep, {b["id"]: (b.get("cash"), b.get("realized"), b.get("today"), b.get("open_count"),
                                          b.get("open_risk")) for b in snap2["bots"]})

    def test_city_card_writes_no_files(self):
        before = sorted(p for p, _, _ in os.walk(self.root))
        bots = [{"id": "btc15m", "history": [_row(-1.0)]}]
        city_card.attach(bots, {}, {}, specs=pimp_desk.BOTS, auto=pimp_desk.AUTO, saved_auto={}, day=DAY,
                         now=NOW, ct_date=pimp_desk._ct_date)
        self.assertEqual(before, sorted(p for p, _, _ in os.walk(self.root)))


def _bot_funcs(names):
    src = (ROOT / "bot.py").read_text()
    tree = ast.parse(src)
    parts = ["import os"]
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            parts.append(ast.get_source_segment(src, node))
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") in names for t in node.targets):
            parts.append(ast.get_source_segment(src, node))
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") in names:
            parts.append(ast.get_source_segment(src, node))
    ns = {}
    exec("\n\n".join(parts), ns)
    return ns


class ServerTests(unittest.TestCase):
    def test_snapshot_is_shared_for_15_seconds(self):
        ns = _bot_funcs({"pimp_snapshot_cached", "pimp_snapshot_cache_clear", "PIMP_SNAPSHOT_TTL_SEC",
                         "_PIMP_SNAPSHOT_CACHE"})
        calls = []

        class Desk:
            def snapshot(self, q="", filt="all", page=1):
                calls.append((q, filt, page))
                return {"bots": [], "n": len(calls)}

        d = Desk()
        a = ns["pimp_snapshot_cached"](d, now=100.0)
        b = ns["pimp_snapshot_cached"](d, now=110.0)
        self.assertEqual(len(calls), 1)
        self.assertIs(a, b)
        self.assertIn("cached_at", a)
        ns["pimp_snapshot_cached"](d, now=116.0)
        self.assertEqual(len(calls), 2)
        # A search always reads fresh.
        ns["pimp_snapshot_cached"](d, q="btc", now=116.5)
        self.assertEqual(len(calls), 3)
        # A staff change clears the shared copy.
        ns["pimp_snapshot_cache_clear"]()
        ns["pimp_snapshot_cached"](d, now=117.0)
        self.assertEqual(len(calls), 4)

    def test_city_health(self):
        ns = _bot_funcs({"pimp_city_health", "pimp_city_root"})
        ns["__file__"] = str(ROOT / "bot.py")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(ns["pimp_city_health"](tmp)["ok"])
            os.makedirs(os.path.join(tmp, "assets"))
            Path(tmp, "index.html").write_text("<html></html>")
            Path(tmp, "assets", "index-x.js").write_text("")
            body = ns["pimp_city_health"](tmp)
            self.assertTrue(body["ok"])
            self.assertEqual(body["real_money"], "off")
        self.assertTrue(ns["pimp_city_health"](str(CITY / "dist"))["ok"])

    def test_health_route_comes_before_the_city_catch_all(self):
        src = (ROOT / "bot.py").read_text()
        self.assertLess(src.index('web.get("/apex-city/health"'), src.index('web.get(r"/apex-city/{tail:.*}"'))


class FrontEndTests(unittest.TestCase):
    SECRET = re.compile(
        r"DESK_SERVICE_KEY|KALSHI_API_KEY|ODDS_API_KEY|DISCORD_TOKEN|BEGIN [A-Z ]*PRIVATE KEY|"
        r"\bsk-[A-Za-z0-9]{20,}|\bghp_[A-Za-z0-9]{20,}|xox[bp]-[A-Za-z0-9-]{10,}"
    )

    def test_built_page_has_no_secrets(self):
        files = [p for p in (CITY / "dist").rglob("*") if p.is_file() and p.suffix in (".js", ".html", ".css", ".json")]
        self.assertTrue(files)
        for path in files:
            hit = self.SECRET.search(path.read_text(errors="ignore"))
            self.assertIsNone(hit, f"{path.name}: {hit and hit.group(0)}")

    def test_vault_keeps_exactly_three_lines(self):
        src = (CITY / "src" / "hud" / "Holograms.tsx").read_text()
        rows = re.findall(r'className="vault-line(?: [a-z-]+)?" role="row"', src)
        body = [r for r in rows if "vault-line-head" not in r]
        self.assertEqual(len(body), 3, rows)

    def test_closed_towers_black_in_scene(self):
        src = (CITY / "src" / "scene" / "Tower.tsx").read_text()
        self.assertNotIn("#2a3348", src, "closed windows must be blacked out, not slate")
        self.assertIn("BLACKED_OUT", src)
        self.assertIn("windowLitShare(bot, closed)", src)
        self.assertIn("roofColor(bot, closed)", src)

    def test_city_and_window_hide_inactive_practice_towers(self):
        for name in ("CityScene.tsx", "WindowCity.tsx"):
            src = (CITY / "src" / "scene" / name).read_text()
            self.assertIn("bots.filter(towerInCity)", src, name)

    def test_built_bundle_is_current(self):
        html = (CITY / "dist" / "index.html").read_text()
        self.assertIn("/apex-city/assets/", html)
        self.assertTrue((CITY / "dist" / "guide.html").is_file())

    @unittest.skipUnless((CITY / "node_modules" / "vite").is_dir() and shutil.which("node"),
                         "trading-city node_modules not installed")
    def test_front_end_look_rules(self):
        out = subprocess.run(["node", "--test", "tests/"], cwd=CITY, capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stdout[-2000:] + out.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
