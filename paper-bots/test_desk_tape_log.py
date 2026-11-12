import json
import os
import time

import desk_tape_log as t


def _w(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def test_tally_and_window(tmp_path):
    root = str(tmp_path)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _w(os.path.join(root, "btc15m-signal", "paper_account.json"), {
        "cash": 80.5,
        "open": [{"ticker": "KXBTC15M-A", "side": "YES", "ask": 0.4, "cost": 4.0}],
        "closed": [{"ticker": "KXBTC15M-B", "side": "NO", "cost": 5, "pnl": 2.5},
                   {"ticker": "KXBTC15M-C", "side": "NO", "cost": 5, "pnl": -5}],
    })
    _w(os.path.join(root, "kalshi_crypto_history.json"), {
        "snapshots": [
            {"at": now, "ticker": "KXBTC15M-B", "yes_ask": 0.6, "spot": 100.0, "target": 99, "minutes_left": 9},
            {"at": now, "ticker": "KXBTC15M-B", "yes_ask": 0.2, "spot": 98.0, "side": "NO", "note": "gap ok"},
        ],
        "settles": [{"at": now, "ticker": "KXBTC15M-B", "series": "KXBTC15M", "result": "no"}],
    })
    line = t.tally_line(root, "btc15m")
    assert "open 1" in line and "settled 1-1" in line and "today $-2.50" in line
    t.reset_seen()
    lines = t.window_lines(root)
    assert len(lines) == 1
    rec = json.loads(lines[0].split(" ", 2)[2])
    assert rec["bot"] == "btc15m" and rec["yes_high"] == 0.6 and rec["yes_low"] == 0.2
    assert rec["traded"][0]["pnl"] == 2.5 and rec["last_note"] == "gap ok"
    assert t.window_lines(root) == []  # not repeated


def test_old_settles_skipped(tmp_path):
    root = str(tmp_path)
    _w(os.path.join(root, "kalshi_crypto_history.json"), {
        "settles": [{"at": "2020-01-01T00:00:00Z", "ticker": "KXGOLD15M-X", "result": "yes"},
                    {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                     "ticker": "KXBTCD-26NOV1215-T1", "series": "KXBTCD", "result": "no"}]})
    t.reset_seen()
    assert t.window_lines(root) == []


def test_history_keeps_15m_rows_when_ladder_floods():
    import kalshi_history as kh
    ladder = [{"series": "KXBTCD", "i": i} for i in range(kh.MAX_SNAPSHOTS + 500)]
    early = [{"series": "KXGOLD15M", "i": i} for i in range(50)]
    kept = kh._trim_snapshots(early + ladder)
    assert sum(1 for r in kept if r["series"] == "KXGOLD15M") == 50
    assert sum(1 for r in kept if r["series"] == "KXBTCD") == kh.MAX_SNAPSHOTS
    assert kept[0]["series"] == "KXGOLD15M"  # order kept


def test_commodity_anchor_learns_open_offset(tmp_path, monkeypatch):
    import datetime as dt
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location("cmd_anchor_test", os.path.join(here, "commodity-15m-paper", "bot.py"))
    cmd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cmd)
    monkeypatch.setattr(cmd, "HERE", str(tmp_path))
    now = dt.datetime(2026, 11, 12, 20, 31, tzinfo=dt.timezone.utc)
    m = {"ticker": "KXNATGAS15M-A", "target": 3.68, "close_time": now + dt.timedelta(minutes=14)}
    # Seed applies before any learning (window too old to learn from).
    old = {"ticker": "KXNATGAS15M-0", "target": 3.9, "close_time": now + dt.timedelta(minutes=6)}
    assert abs(cmd.anchored_spot("KXNATGAS15M", 3.665, old, now) - 3.665 * 1.0038) < 1e-9
    # A fresh window learns the open offset, so spot lands on the target.
    assert abs(cmd.anchored_spot("KXNATGAS15M", 3.665, m, now) - 3.68) < 1e-9
    # Metals have no seed and no shift.
    assert cmd.anchored_spot("KXGOLD15M", 3884.0, {"ticker": "G", "target": 3884.0, "close_time": now}, now) == 3884.0
    first = json.load(open(tmp_path / "index_basis.json"))["KXNATGAS15M"]
    assert first["last"] == "KXNATGAS15M-A" and first["n"] == 1
    # Old window: no re-learning.
    late = {"ticker": "KXNATGAS15M-B", "target": 3.9, "close_time": now + dt.timedelta(minutes=5)}
    cmd.anchored_spot("KXNATGAS15M", 3.665, late, now)
    assert json.load(open(tmp_path / "index_basis.json"))["KXNATGAS15M"]["n"] == 1
