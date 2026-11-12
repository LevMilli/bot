"""What-if lab. Offline."""
import datetime as dt
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "whatif-lab-paper"))

import whatif_model as wm  # noqa: E402

NOW = dt.datetime(2026, 11, 12, 18, tzinfo=dt.timezone.utc)


def _d(ticker, edge, ask=0.40, side="yes", action="skip", reason="logged for calibration; not a buy window",
       bid=None):
    return dict(ticker=ticker, side=side, edge=edge, ask=ask, fee=0.02, fair=ask + edge + 0.02,
                action=action, reason=reason, bid=ask - 0.03 if bid is None else bid)


def _check(minutes, *decisions):
    return {"at": (NOW - dt.timedelta(minutes=minutes)).isoformat(timespec="seconds"), "decisions": list(decisions)}


def _write(folder, rows):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "research.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_buckets():
    assert wm.bucket_of(_d("A", 0.08), 0.05) == "log_only"
    assert wm.bucket_of(_d("A", 0.03), 0.05) is None
    assert wm.bucket_of(_d("A", 0.30, reason="edge 0.300 over trust cap 0.15: x"), 0.05) == "trust_cap"
    assert wm.bucket_of(_d("A", 0.08, action="buy", reason="fair"), 0.05) == "rule_buy"
    assert wm.bucket_of(_d("A", 0.08, reason="ask 0.97 outside 0.05-0.95"), 0.05) is None
    assert wm.bucket_of(_d("A", 0.08, ask=1.0), 0.05) is None


def test_first_sighting_is_the_entry():
    log = [_check(30, _d("A", 0.06, ask=0.40)), _check(20, _d("A", 0.20, ask=0.30))]
    got = wm.first_sightings(log, 0.05)
    assert got[("log_only", "A", "yes")]["ask"] == 0.40


def test_missed_grades_and_flags():
    wins = [_check(500 + i, _d(f"W{i}", 0.08, ask=0.40)) for i in range(60)]
    log = wins + [_check(10, _d("L", 0.30, ask=0.50, reason="edge 0.300 over trust cap 0.15"))]
    results, waiting = {}, {}
    fetch = lambda t: {"result": "no" if t == "L" else "yes"}  # noqa: E731
    report, reads, pending = wm.missed([("weather-high", 0.05, log)], results, waiting, fetch, NOW, max_reads=100)
    assert reads == 61 and pending == 0
    lo = report["weather-high"]["log_only"]
    assert lo["n"] == 60 and abs(lo["avg"] - 0.58) < 1e-9 and lo["worth_a_look"]
    assert report["weather-high"]["trust_cap"]["avg"] == -0.52 and not report["weather-high"]["trust_cap"]["worth_a_look"]


def test_reads_capped_and_open_contracts_wait():
    log = [_check(100 - i, _d(f"T{i}", 0.08)) for i in range(5)]
    results, waiting, calls = {}, {}, []

    def fetch(t):
        calls.append(t)
        return {"result": ""}

    _, reads, pending = wm.missed([("x", 0.05, log)], results, waiting, fetch, NOW, max_reads=2)
    assert reads == 2 and pending == 5 and calls == ["T0", "T1"]          # oldest first
    calls.clear()
    wm.missed([("x", 0.05, log)], results, waiting, fetch, NOW + dt.timedelta(hours=1), max_reads=10)
    assert calls == ["T2", "T3", "T4"]                                   # T0/T1 wait 12h
    calls.clear()
    wm.missed([("x", 0.05, log)], results, waiting, fetch, NOW + dt.timedelta(hours=13), max_reads=10)
    assert sorted(calls) == ["T0", "T1", "T2", "T3", "T4"]


def test_gap_episodes():
    log = [
        _check(30, _d("A", 0.08), _d("B", 0.07)),
        _check(25, _d("A", 0.10), _d("B", 0.01)),
        _check(20, _d("A", 0.09)),
        _check(15, _d("A", 0.01)),
        _check(60 * 24 * 9, _d("OLD", 0.2)),
    ]
    g = wm.gaps(sorted(log, key=lambda r: r["at"]), 0.06, 300, NOW)
    assert g["checks"] == 4 and g["episodes"] == 2
    assert g["longest_minutes"] == 15.0 and g["one_check_share"] == 0.5 and g["median_peak_edge"] == 0.085
    assert wm.gaps([], 0.06, 300, NOW)["episodes"] == 0


def test_bot_main(tmp_path):
    spec = importlib.util.spec_from_file_location("whatif_bot", os.path.join(HERE, "whatif-lab-paper", "bot.py"))
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    _write(tmp_path / "weather-high-paper", [_check(60, _d("KXHIGHNY-A", 0.08))])
    _write(tmp_path / "poly-sports-lean-paper", [_check(10, _d("KXNBAGAME-A", 0.09))])
    assert bot.main([], root=str(tmp_path), fetch=lambda t: {"result": "yes"},
                    trades_fetch=lambda t, a, b: [{"taker_side": "no", "yes_price_dollars": "0.37"}], now=NOW) == 0
    body = json.loads((tmp_path / "whatif-lab-paper" / "whatif.json").read_text())
    assert body["missed"]["weather-high"]["log_only"]["n"] == 1
    assert body["gaps"]["poly-sports-lean"]["episodes"] == 1
    assert "calibration-lab" not in body["missed"] and "whatif-lab" not in body["missed"]
    assert wm.card(body).startswith("What-if lab: 2 settled")
    assert body["maker"]["weather-high"]["n"] == 1 and body["maker"]["weather-high"]["fill_rate"] == 1.0


def test_registry_and_desk_wiring():
    import new_towers
    import pimp_desk

    assert "whatif-lab" in new_towers.RESEARCH
    assert pimp_desk._account_body("whatif-lab")["cash"] == 0.0
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("whatif-lab")["ok"]


def test_research_logs_survive_a_deploy():
    import pimp_desk

    assert "weather-high-paper/research.jsonl" in pimp_desk.SETTLEMENT_FILES
    assert "weather-high-paper/research.jsonl.1" in pimp_desk.SETTLEMENT_FILES
    assert "whatif-lab-paper/research.jsonl" not in pimp_desk.SETTLEMENT_FILES


def test_rotation_keeps_the_volume_link(tmp_path, monkeypatch):
    import kalshi_shadow_tower as engine

    volume, tower = tmp_path / "data", tmp_path / "tower"
    volume.mkdir()
    tower.mkdir()
    (volume / "research.jsonl").write_text("x" * 50 + "\n")
    os.symlink(volume / "research.jsonl", tower / "research.jsonl")
    os.symlink(volume / "research.jsonl.1", tower / "research.jsonl.1")
    monkeypatch.setattr(engine, "RESEARCH_MAX_BYTES", 10)
    engine._append_research(str(tower), NOW, [], "note")
    assert os.path.islink(tower / "research.jsonl") and os.path.islink(tower / "research.jsonl.1")
    assert (volume / "research.jsonl.1").read_text().startswith("xxx")
    assert json.loads((volume / "research.jsonl").read_text())["note"] == "note"


def test_maker_fill_rule():
    assert wm.maker_price({"bid": 0.37, "ask": 0.40}) == 0.38
    assert wm.maker_price({"bid": 0.39, "ask": 0.40}) is None            # no room inside the spread
    assert wm.maker_price({"bid": None, "ask": 0.40}) is None
    sold_yes = {"taker_side": "no", "yes_price_dollars": "0.37", "no_price_dollars": "0.63"}
    bought_yes = {"taker_side": "yes", "yes_price_dollars": "0.40", "no_price_dollars": "0.60"}
    assert wm.maker_filled([sold_yes], "yes", 0.38)
    assert not wm.maker_filled([dict(sold_yes, yes_price_dollars="0.39")], "yes", 0.38)
    assert not wm.maker_filled([bought_yes], "yes", 0.38)
    assert wm.maker_filled([dict(bought_yes, no_price_dollars="0.58")], "no", 0.60)


def test_maker_report_waits_for_window_and_grades():
    log = [_check(120, _d("A", 0.08, ask=0.40, bid=0.37)), _check(120, _d("B", 0.08, ask=0.40, bid=0.37)),
           _check(10, _d("C", 0.08, ask=0.40, bid=0.37))]
    trades = {"A": [{"taker_side": "no", "yes_price_dollars": "0.38"}], "B": []}
    calls = []

    def tf(ticker, a, b):
        calls.append(ticker)
        assert b - a == 30 * 60
        return trades[ticker]

    quotes = {}
    report, reads = wm.maker([("x", 0.05, log)], {"A": "yes", "B": "yes"}, quotes, tf, NOW)
    assert sorted(calls) == ["A", "B"] and reads == 2                  # C's window has not closed
    r = report["x"]
    assert r["n"] == 2 and r["fill_rate"] == 0.5
    assert abs(r["maker_avg"] - (1 - 0.38 - 0.0175 * 0.38 * 0.62)) < 1e-4
    assert r["taker_avg_same"] == 0.58
    calls.clear()
    wm.maker([("x", 0.05, log)], {"A": "yes", "B": "yes"}, quotes, tf, NOW)
    assert calls == []                                                  # cached
