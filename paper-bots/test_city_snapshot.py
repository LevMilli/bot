"""City tests (plan steps 365-369) and snapshot schema tests (374-376).

The city is a React/three.js page, so these tests check two things without a
browser: the desk snapshot carries what each part of the city reads, and the
city source still holds the look rules ("towers not television"):

* every tower card has what it needs to render
* closed towers render black with blacked-out windows
* practice towers stay hidden until they trade (research buildings stand)
* the vault shows three lines: Desk counts, Practice not counted, All paper
* the offline banner shows on the fixture snapshot
* the snapshot schema matches the city type, is versioned, and an old city
  build is fine with a new field

Screenshot tests need a WebGL browser and are not covered here.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import unittest

import new_towers
import snapshot_schema as S

ROOT = os.path.dirname(os.path.abspath(__file__))
CITY = os.path.join(os.path.dirname(ROOT), "trading-city")
SRC = os.path.join(CITY, "src")
HAS_SRC = os.path.isdir(SRC)
FIXTURES = [p for p in (os.path.join(CITY, "public", "fixture-snapshot.json"),
                        os.path.join(CITY, "dist", "fixture-snapshot.json")) if os.path.exists(p)]

_SNAP = None


def live_snapshot() -> dict:
    """pimp_desk.snapshot() on a throwaway copy of the desk (never writes into the checkout)."""
    global _SNAP
    if _SNAP is None:
        import pimp_desk
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "paper-bots")
            shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(
                "__pycache__", ".pytest_cache", "fixtures", "*.jsonl", "*.jsonl.1", "recordings"))
            old = os.environ.get("PAPER_KEEP_SETTLEMENTS")
            os.environ["PAPER_KEEP_SETTLEMENTS"] = "0"
            try:
                _SNAP = json.loads(json.dumps(pimp_desk.snapshot(dest), default=str))
            finally:
                if old is None:
                    os.environ.pop("PAPER_KEEP_SETTLEMENTS", None)
                else:
                    os.environ["PAPER_KEEP_SETTLEMENTS"] = old
    return _SNAP


def src(rel: str) -> str:
    with open(os.path.join(SRC, rel), encoding="utf-8") as fh:
        return fh.read()


def ts_type_keys(text: str, name: str) -> list[str]:
    m = re.search(r"export type " + re.escape(name) + r" = \{(.*?)\n\}", text, re.S)
    assert m, name
    keys, depth = [], 0
    for line in m.group(1).split("\n"):
        stripped = line.strip()
        if depth == 0:
            k = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\??\s*:", stripped)
            if k:
                keys.append(k.group(1))
        depth += line.count("{") - line.count("}")
    return keys


def fn_body(text: str, name: str) -> str:
    m = re.search(r"export function " + re.escape(name) + r"\(.*?\{(.*?)\n\}", text, re.S)
    assert m, name
    return m.group(1)


# Python mirrors of the city's two look rules (data/format.ts), tested against the source below.
RESEARCH_ROWS = {r["id"] for r in new_towers.ACTIVE if int(r.get("max_open") or 0) == 0}


def _city_landmarks() -> set:
    path = os.path.join(SRC, "data", "format.ts")
    if os.path.exists(path):
        with open(path) as fh:
            m = re.search(r"const LANDMARKS = new Set\(\[(.*?)\]\)", fh.read(), re.S)
        if m:
            return set(re.findall(r"'([a-z0-9-]+)'", m.group(1)))
    return set(RESEARCH_ROWS)


LANDMARKS = _city_landmarks()


def tower_in_city(bot: dict) -> bool:
    if not bot.get("shadow_only") or bot.get("id") in LANDMARKS:
        return True
    if (float(bot.get("open_count") or 0)) > 0:
        return True
    if bot.get("realized") is not None and float(bot["realized"]) != 0:
        return True
    if bot.get("today") is not None and float(bot["today"]) != 0:
        return True
    return len(bot.get("trades") or []) > 0


def tower_closed(bot: dict) -> bool:
    return bot.get("present") is False or bool(bot.get("paused"))


class TowerCards(unittest.TestCase):
    """Step 365."""

    def test_every_tower_card_has_what_it_renders(self):
        snap = live_snapshot()
        self.assertEqual(S.problems(snap, require_version=True), [])
        ids = [b["id"] for b in snap["bots"]]
        self.assertEqual(len(ids), len(set(ids)))
        for bot in snap["bots"]:
            for key in ("id", "name", "present", "cash", "open_count", "trades", "history", "status"):
                self.assertIn(key, bot, (bot.get("id"), key))
            self.assertIsInstance(bot["trades"], list)
            self.assertIsInstance(bot["history"], list)
        for row in new_towers.ACTIVE:
            self.assertIn(row["id"], ids)

    @unittest.skipUnless(HAS_SRC, "city source not in this image")
    def test_every_tower_has_a_stable_color(self):
        # Towers without a named color fall back to an index color in
        # beamColorFor, so a brand new tower is fine. Named colors must not
        # be shared by two towers.
        text = src("data/format.ts")
        self.assertIn("function beamColorFor", text)
        pairs = re.findall(r"^\s*'?([a-z0-9-]+)'?: '(#[0-9a-fA-F]{3,8})'", text, re.M)
        ids = {b["id"] for b in live_snapshot()["bots"]}
        named = [c.lower() for k, c in pairs if k in ids]
        self.assertEqual(len(named), len(set(named)), "two towers share a color")


@unittest.skipUnless(HAS_SRC, "city source not in this image")
class ClosedTowers(unittest.TestCase):
    """Step 366."""

    def test_closed_rule(self):
        body = fn_body(src("data/format.ts"), "towerClosed")
        self.assertIn("bot.present === false", body)
        self.assertIn("bot.paused", body)
        self.assertTrue(tower_closed({"present": False}))
        self.assertTrue(tower_closed({"present": True, "paused": True}))
        self.assertFalse(tower_closed({"present": True}))

    def test_closed_towers_are_black_with_dark_windows(self):
        tower = src("scene/Tower.tsx")
        self.assertIn("towerClosed(bot)", tower)
        self.assertGreaterEqual(tower.count("emissive={closed ? '#000000'"), 3)
        self.assertGreaterEqual(tower.count("emissiveIntensity={closed ? 0"), 3)
        self.assertIn("offline={closed}", tower)  # blacked-out windows
        self.assertGreaterEqual(tower.count("{!closed && ("), 3)  # no beam, no neon

    def test_fixture_has_a_closed_tower(self):
        for path in FIXTURES:
            with open(path, encoding="utf-8") as fh:
                snap = json.load(fh)
            self.assertTrue([b for b in snap["bots"] if tower_closed(b)], path)


@unittest.skipUnless(HAS_SRC, "city source not in this image")
class HiddenPractice(unittest.TestCase):
    """Step 367."""

    def test_landmarks_match_research_rows(self):
        text = src("data/format.ts")
        m = re.search(r"const LANDMARKS = new Set\(\[(.*?)\]\)", text, re.S)
        city = set(re.findall(r"'([a-z0-9-]+)'", m.group(1)))
        # Every city landmark must be a research row. A brand new research
        # row may not have a landmark yet; it then just hides when quiet.
        self.assertLessEqual(city, RESEARCH_ROWS)

    def test_rule_in_source(self):
        body = fn_body(src("data/format.ts"), "towerInCity")
        for bit in ("bot.shadow_only", "LANDMARKS.has(bot.id)", "open_count", "realized", "today", "trades"):
            self.assertIn(bit, body)
        self.assertIn("bots.filter(towerInCity)", src("scene/CityScene.tsx"))

    def test_quiet_practice_towers_hidden_desk_towers_stand(self):
        snap = live_snapshot()  # a fresh checkout: nobody has traded
        for bot in snap["bots"]:
            if not bot.get("shadow_only"):
                self.assertTrue(tower_in_city(bot), bot["id"])
            elif bot["id"] in LANDMARKS:
                self.assertTrue(tower_in_city(bot), bot["id"])
            else:
                self.assertFalse(tower_in_city(bot), bot["id"])
        quiet = {"id": "more-15m", "shadow_only": True, "open_count": 0, "realized": 0, "today": 0, "trades": []}
        self.assertFalse(tower_in_city(quiet))
        self.assertTrue(tower_in_city(dict(quiet, open_count=1)))
        self.assertTrue(tower_in_city(dict(quiet, realized=-3.5)))  # a loss still counts as trading


class VaultLines(unittest.TestCase):
    """Step 368."""

    def test_snapshot_feeds_three_lines(self):
        roll = live_snapshot()["desk"]["bankroll"]
        for key in ("towers", "shadow_towers", "cash", "realized", "today", "shadow_cash",
                    "shadow_realized", "shadow_today", "missing"):
            self.assertIn(key, roll)
        bots = {b["id"]: b for b in live_snapshot()["bots"]}
        self.assertEqual(set(roll["towers"]), {i for i, b in bots.items() if not b.get("shadow_only")})
        self.assertEqual(set(roll["shadow_towers"]), {i for i, b in bots.items() if b.get("shadow_only")})

    @unittest.skipUnless(HAS_SRC, "city source not in this image")
    def test_vault_source_has_three_lines(self):
        holo = src("hud/Holograms.tsx")
        self.assertIn("<em>counts</em>", holo)
        self.assertIn("Practice ({shadowTowers}) <em>not counted</em>", holo)
        self.assertIn("All paper", holo)
        self.assertEqual(len(re.findall(r'className="vault-line[ "]', holo)), 4)  # head + three lines


class OfflineBanner(unittest.TestCase):
    """Step 369."""

    def test_fixture_is_a_valid_snapshot(self):
        self.assertTrue(FIXTURES)
        for path in FIXTURES:
            with open(path, encoding="utf-8") as fh:
                snap = json.load(fh)
            self.assertEqual(S.problems(snap), [], path)
            self.assertTrue(snap["paper_only"])

    @unittest.skipUnless(HAS_SRC, "city source not in this image")
    def test_fixture_load_shows_offline_banner(self):
        hook = src("data/useSnapshot.ts")
        self.assertIn("fixture-snapshot.json", hook)
        self.assertIn("mode: 'offline'", hook)
        banners = src("hud/Banners.tsx")
        self.assertIn("mode === 'offline'", banners)
        self.assertIn('className="banner offline"', banners)
        self.assertIn("Fixture only; not inventing fills.", banners)


class SnapshotSchema(unittest.TestCase):
    """Steps 374-376."""

    @unittest.skipUnless(HAS_SRC, "city source not in this image")
    def test_schema_matches_city_type(self):
        self.assertEqual(sorted(ts_type_keys(src("types.ts"), "Snapshot")), sorted(S.FIELDS))

    def test_snapshot_sends_every_always_key(self):
        snap = live_snapshot()
        for key in S.ALWAYS:
            self.assertIn(key, snap)
        self.assertEqual(snap["schema_version"], S.SCHEMA_VERSION)

    def test_version_table_is_current(self):
        self.assertIn(S.SCHEMA_VERSION, S.FIELDS_BY_VERSION)
        self.assertEqual(max(S.FIELDS_BY_VERSION), S.SCHEMA_VERSION)
        self.assertIn("schema_version", S.FIELDS)

    def test_old_city_build_accepts_new_field(self):
        snap = dict(live_snapshot())
        snap["brand_new_field"] = {"anything": [1, 2, 3]}
        snap["bots"] = [dict(b, new_card_field="x") for b in snap["bots"]]
        self.assertEqual(S.problems(snap), [])
        # an old desk without the version is still fine for the city
        old = {k: v for k, v in snap.items() if k != "schema_version"}
        self.assertEqual(S.problems(old), [])
        self.assertEqual(S.problems(old, require_version=True), ["schema_version missing"])

    @unittest.skipUnless(HAS_SRC, "city source not in this image")
    def test_city_loader_does_not_reject_unknown_keys(self):
        hook = src("data/useSnapshot.ts")
        # the only shape check is bots[]; unknown keys pass straight through
        self.assertIn("if (!snap.bots || !Array.isArray(snap.bots))", hook)
        self.assertNotRegex(hook, r"Object\.keys\(snap|hasOwnProperty|schema_version\s*!==")

    def test_problems_catch_breaks(self):
        self.assertEqual(S.problems([]), ["snapshot is not an object"])
        self.assertIn("bots[] missing", S.problems({"paper_only": True}))
        self.assertIn("paper_only must be true", S.problems({"paper_only": False, "bots": []}))
        self.assertTrue(S.problems({"paper_only": True, "bots": [{"id": "a"}]}))
        self.assertTrue(S.problems({"paper_only": True, "bots": [{"id": "a", "name": "A"}] * 2}))
        self.assertTrue(S.problems({"paper_only": True, "bots": [], "schema_version": "1"}))


if __name__ == "__main__":
    unittest.main()
