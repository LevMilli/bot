"""Scorekeeper. Offline."""
import datetime as dt
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "scorekeeper-paper"))

import score_model as sm  # noqa: E402

NOW = dt.datetime(2026, 11, 12, 18, tzinfo=dt.timezone.utc)


def test_grades():
    assert sm.grade([1.0] * 10)["grade"] == "too few"
    assert sm.grade([])["avg"] is None
    assert sm.grade([1.0, 1.2] * 30)["grade"] == "promote"
    keep = sm.grade([3.0, -2.5] * 30)
    assert keep["grade"] == "keep" and keep["low"] < 0 < keep["avg"]
    pause = sm.grade([2.5, -3.0] * 30)
    assert pause["grade"] == "pause" and pause["avg"] <= 0 < pause["high"]
    assert sm.grade([-1.0, -1.2] * 30)["grade"] == "retire"
    assert sm.grade([1.0, 1.2] * 30, min_n=100)["grade"] == "too few"


def test_run_sorts_and_counts():
    hist = {"a": ("A", [-1.0, -1.2] * 30), "b": ("B", [1.0, 1.2] * 30), "c": ("C", [1.0])}
    body = sm.run(hist, NOW, pnls_of=lambda rows: rows)
    assert [r["id"] for r in body["bots"]] == ["b", "a", "c"]
    assert body["counts"]["promote"] == 1 and body["counts"]["retire"] == 1 and body["suggest_only"]
    assert sm.card(body) == "2 of 3 bots have 50+ trades: 1 promote, 1 retire"


def test_bot_main_reads_desk_history(tmp_path):
    spec = importlib.util.spec_from_file_location("score_bot", os.path.join(HERE, "scorekeeper-paper", "bot.py"))
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    folder = tmp_path / "nasdaq-paper"
    folder.mkdir()
    closed = [dict(ticker=f"KXNASDAQ100-{i}", side="no", contracts=10, cost=5.0, payout=10.0, pnl=4.8,
                   status="settled", settled_at="2026-11-01T20:00:00+00:00", result="no") for i in range(60)]
    (folder / "paper_account.json").write_text(json.dumps({"cash": 100.0, "open": [], "closed": closed}))
    (folder / "bot.py").write_text("")
    assert bot.main([], root=str(tmp_path), now=NOW) == 0
    card = json.loads((tmp_path / "scorekeeper-paper" / "scorecard.json").read_text())
    row = next(r for r in card["bots"] if r["id"] == "nasdaq")
    assert row["n"] == 60 and row["grade"] == "promote"
    assert abs(row["avg"] - (4.8 - 10 * 0.01)) < 1e-6          # fill tax applied
    assert all(r["id"] not in ("scorekeeper", "calibration-lab", "settlement-auditor") for r in card["bots"])


def test_registry_and_desk_wiring():
    import new_towers
    import pimp_desk

    assert "scorekeeper" in new_towers.RESEARCH
    assert pimp_desk._account_body("scorekeeper")["cash"] == 0.0
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("scorekeeper")["ok"]


def test_extra_slot_trades_are_split_out(tmp_path):
    spec = importlib.util.spec_from_file_location("score_bot_x", os.path.join(HERE, "scorekeeper-paper", "bot.py"))
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    folder = tmp_path / "weather-high-paper"
    folder.mkdir()
    closed = [dict(ticker="A", contracts=10, pnl=3.0, extra=True), dict(ticker="B", contracts=10, pnl=-1.0)]
    (folder / "paper_account.json").write_text(json.dumps({"cash": 500.0, "open": [], "closed": closed}))
    got = bot.extra_split(str(tmp_path), 0.01)
    assert got == {"weather-high": {"extra": {"n": 1, "avg": 2.9}, "normal": {"n": 1, "avg": -1.1}}}
    body = {"bots": [], "counts": {g: 0 for g in sm.ORDER}, "min_n": 50, "extra_slots": got}
    assert sm.card(body).endswith("Extra-slot trades closed: 1 (avg $ per trade, extra vs normal: weather-high +2.90 vs -1.10)")
