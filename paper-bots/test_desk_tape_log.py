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
