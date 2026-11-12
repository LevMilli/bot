"""Market snapshots. Offline."""
import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "market-snapshots-paper"))

import snapshot_model as rm  # noqa: E402

NOW = dt.datetime(2026, 11, 12, 18, tzinfo=dt.timezone.utc)
MARKET = {"ticker": "KXHIGHNY-26NOV12-T66", "yes_bid_dollars": "0.0100", "yes_ask_dollars": "0.0300",
          "yes_bid_size_fp": "10.00", "yes_ask_size_fp": "16219.30", "last_price_dollars": "0.0200",
          "volume_fp": "2260.74", "open_interest_fp": "2226.74"}


def test_compact_and_snapshot():
    assert rm.compact(MARKET) == ["KXHIGHNY-26NOV12-T66", 0.01, 0.03, 10.0, 16219.3, 0.02, 2260.74, 2226.74]
    assert rm.compact({"ticker": ""}) is None

    def list_open(series, limit):
        if series == "BAD":
            raise TimeoutError
        return [MARKET] if series == "KXHIGHNY" else []

    snap, notes = rm.snapshot(list_open, NOW, series=("KXHIGHNY", "BAD", "EMPTY"))
    assert list(snap["series"]) == ["KXHIGHNY"] and notes == ["BAD read failed (TimeoutError)"]


def test_save_appends_and_prune_keeps_today(tmp_path):
    snap = {"at": NOW.isoformat(), "series": {"X": [["X-1", 0.1]]}}
    for day in (1, 2, 3):
        rm.save(str(tmp_path), snap, NOW.replace(day=day))
    path = rm.save(str(tmp_path), snap, NOW.replace(day=3))
    assert len(rm.read_day(path)) == 2
    size = os.path.getsize(path)
    gone = rm.prune(str(tmp_path), max_bytes=size)
    assert gone == ["2026-11-01.jsonl.gz", "2026-11-02.jsonl.gz"]
    assert rm.prune(str(tmp_path), max_bytes=0) == []          # today's file is never deleted
    assert rm.usage(str(tmp_path))["days"] == 1


def test_bot_main(tmp_path):
    spec = importlib.util.spec_from_file_location("snap_bot", os.path.join(HERE, "market-snapshots-paper", "bot.py"))
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    out = io.StringIO()
    folder = tmp_path / "rec"
    with contextlib.redirect_stdout(out):
        assert bot.main([], here=str(tmp_path), list_open=lambda s, n: [dict(MARKET, ticker=s + "-1")],
                        now=NOW, folder=str(folder)) == 0
    day = rm.read_day(str(folder / "2026-11-12.jsonl.gz"))
    assert len(day[0]["series"]) == len(rm.SERIES)
    assert "no trade" in out.getvalue()
    state = json.loads((tmp_path / "paper_account.json").read_text())
    assert state["cash"] == 0.0 and state["recordings"]["days"] == 1


def test_recordings_go_to_the_volume(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("snap_bot2", os.path.join(HERE, "market-snapshots-paper", "bot.py"))
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    monkeypatch.setenv("PAPER_DATA_DIR", str(tmp_path / "data"))
    assert bot.recordings_dir(str(tmp_path)) == str(tmp_path / "data" / "market-snapshots-paper" / "recordings")


def test_registry_and_desk_wiring():
    import new_towers
    import pimp_desk

    assert "market-snapshots" in new_towers.RESEARCH
    assert pimp_desk._account_body("market-snapshots")["cash"] == 0.0
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("market-snapshots")["ok"]
