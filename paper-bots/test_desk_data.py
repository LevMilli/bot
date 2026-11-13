"""Shared decision rows, privacy, calibration, quality, exports, queries, rule versions. Offline."""
import csv
import datetime as dt
import gzip
import io
import json

import pytest

import desk_data as dd

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 13, 18, 0, tzinfo=UTC)


def _row(**kw):
    base = dict(tower="more-15m", at=NOW, market="KXBNB15M-26NOV131315-15", side="yes", fair=0.6, price=0.5,
                edge=0.08, action="buy", reason="fair 0.600 ask 0.50", inputs={"bid": 0.48})
    base.update(kw)
    return dd.decision_row(**base)


def test_decision_row_shape_and_check():
    row = _row()
    assert set(dd.REQUIRED) <= set(row) and row["family"] == "15m" and dd.check_row(row) == []
    assert dd.check_row(_row(action="skip", reason="")) == ["a skip needs a reason"]
    assert "action 'maybe' is not one of buy, skip, sell, hold" in dd.check_row(_row(action="maybe"))
    assert "fair 1.4 is outside 0-1" in dd.check_row(_row(fair=1.4))
    assert dd.check_row({"v": 1}) [0] == "missing tower"
    assert "a buy needs fair, price and edge" in dd.check_row(_row(edge=None))
    bad = _row()
    bad["inputs"] = {"session": "abc"}
    assert "holds something private" in dd.check_row(bad)
    assert dd.family_of("KXHIGHNY-26NOV13-T66") == "daily"


def test_from_research_keeps_every_side_with_fair_and_reason():
    line = {"at": NOW.isoformat(), "note": "", "decisions": [
        {"ticker": "KXSOL15M-X", "event": "E", "side": "no", "fair": 0.41, "ask": 0.45, "bid": 0.43, "fee": 0.02,
         "edge": -0.06, "action": "skip", "reason": "edge -0.060 < floor 0.05 (fair 0.410 ask 0.45 fee 0.02)",
         "floor": 0.05, "why": "SOL ...", "label": "SOL"}]}
    rows = dd.from_research("more-15m", line)
    assert len(rows) == 1 and dd.check_row(rows[0]) == []
    assert rows[0]["fair"] == 0.41 and rows[0]["price"] == 0.45 and rows[0]["inputs"]["floor"] == 0.05


def test_privacy_finder_and_stripper():
    obj = {"a": 1, "API_KEY": "x", "nested": [{"cookie": "c"}, {"note": "write to me@example.com"}],
           "Authorization": "Bearer abcdefghijklmnop", "ok": "fine"}
    assert set(dd.find_private(obj)) == {"API_KEY", "nested[0].cookie", "nested[1].note", "Authorization"}
    clean = dd.strip_private(obj)
    assert dd.find_private(clean) == [] and clean["ok"] == "fine" and clean["nested"][1]["note"] == "[removed]"


def test_day_files_load_and_180_day_prune(tmp_path):
    today = NOW.date()
    for back in (0, 179, 181):
        dd.write_rows(str(tmp_path), today - dt.timedelta(days=back),
                      [{"series": "KXSOL15M", "ticker": "KXSOL15M-1"}, {"series": "KXBNB15M", "ticker": "KXBNB15M-1"}])
    assert len(dd.load_day(str(tmp_path), today, "KXSOL15M")) == 1
    gone = dd.prune_days(str(tmp_path), today)
    assert gone == [(today - dt.timedelta(days=181)).isoformat() + ".jsonl.gz"]
    assert len(dd.day_files(str(tmp_path))) == 2


def test_daily_summary_groups_reasons_by_words():
    rows = [_row(), _row(action="skip", reason="edge 0.010 < floor 0.05 (fair 0.5 ask 0.48)"),
            _row(action="skip", reason="edge 0.020 < floor 0.05 (fair 0.6 ask 0.57)"),
            _row(action="skip", reason="ask 0.97 outside 0.05-0.95", at=NOW + dt.timedelta(minutes=1))]
    s = dd.daily_summary(rows)
    assert s["checks"] == 2 and s["buys"] == 1 and s["skips"] == 3
    assert s["skip_reasons"][0] == ("edge # < floor #", 2)
    assert s["towers"]["more-15m"] == {"checks": 2, "buys": 1, "skips": 3}


def test_calibration_flag_needs_50_and_5_points():
    honest = [(0.7, i < 7) for i in range(10)] * 6          # said 70, won 70, n=60
    assert dd.calibration(honest)["flag"] is False
    proud = [(0.7, i < 6) for i in range(10)] * 6            # said 70, won 60
    cal = dd.calibration(proud)
    assert cal["flag"] is True and cal["off_points"] == -10.0 and cal["bands"][0]["band"] == "0.70-0.80"
    assert dd.calibration(proud[:40])["flag"] is False       # under 50 results never flags


def test_tower_calibration_uses_last_fair_and_splits_families():
    rows = [_row(at=NOW, fair=0.2, minutes_left=10, volume=50),
            _row(at=NOW + dt.timedelta(minutes=5), fair=0.9, minutes_left=5, volume=50),
            _row(market="KXHIGHNY-26NOV13-T66", fair=0.3)]
    table = dd.tower_calibration(rows, {"KXBNB15M-26NOV131315-15": "yes", "KXHIGHNY-26NOV13-T66": "no"})
    t = table["more-15m"]
    assert t["15m"]["n"] == 1 and t["15m"]["said"] == 0.9            # last fair before settle
    assert t["daily"]["n"] == 1 and "15m 3-6 min left" in t and "15m thin" in t
    many = [_row(market=f"KXBNB15M-{i}", fair=0.8) for i in range(60)]
    res = {f"KXBNB15M-{i}": ("yes" if i % 2 else "no") for i in range(60)}
    lines = dd.flagged_towers(dd.tower_calibration(many, res))
    assert lines and lines[0].startswith("more-15m 15m: said 80%, won 50% over 60 results")


def test_quality_check_and_gap_fill():
    times = [NOW + dt.timedelta(minutes=m) for m in (0, 1, 1, 4, 3)]
    q = dd.quality_check(times)
    assert q["duplicates"] == 1 and q["out_of_order"] == 1 and q["missing"] == 1 and not q["ok"]
    pts = [{"at": NOW.isoformat(), "px": 1}, {"at": (NOW + dt.timedelta(minutes=3)).isoformat(), "px": 2}]
    filled = dd.fill_small_gaps(pts, lambda at: {"px": 1.5}, kind="candles")
    assert len(filled) == 4 and [p.get("filled") for p in filled] == [None, True, True, None]
    far = [pts[0], {"at": (NOW + dt.timedelta(minutes=30)).isoformat(), "px": 2}]
    assert len(dd.fill_small_gaps(far, lambda at: {"px": 1}, kind="candles")) == 2   # big gaps stay gaps
    for kind in ("trades", "closed", "paper_account", "ledger"):
        with pytest.raises(ValueError):
            dd.fill_small_gaps(pts, lambda at: {}, kind=kind)


def test_exports_keep_losses():
    closed = {"more-15m": [
        {"ticker": "KXBNB15M-1", "side": "yes", "opened": "2026-11-13T10:00:00+00:00",
         "closed": "2026-11-13T10:15:00+00:00", "pnl": -12.5, "cost": 12.5},
        {"ticker": "KXBNB15M-2", "side": "no", "opened": "2026-11-13T11:00:00+00:00",
         "closed": "2026-11-13T11:15:00+00:00", "pnl": 9.0},
        {"ticker": "KXBNB15M-3", "side": "no", "closed": "2026-10-31T11:15:00+00:00", "pnl": 1.0}]}
    rows = list(csv.DictReader(io.StringIO(dd.trades_csv(closed, "2026-11"))))
    assert [r["pnl"] for r in rows] == ["-12.5", "9.0"] and rows[0]["tower"] == "more-15m"
    blob = dd.decisions_gz([_row(), _row(at="2026-10-01T00:00:00+00:00")], "2026-11")
    assert len(gzip.decompress(blob).decode().splitlines()) == 1


def test_queries_and_index():
    trades = [{"ticker": "KXBNB15M-1", "label": "BNB 15m up", "opened": NOW.isoformat(), "pnl": -3},
              {"ticker": "KXSOL15M-1", "label": "SOL 15m up", "opened": NOW.isoformat(), "pnl": 2},
              {"ticker": "KXBNB15M-0", "label": "BNB 15m up", "opened": "2026-11-01T00:00:00+00:00", "pnl": 1}]
    week = dd.trades_this_week(trades, "BNB", NOW)
    assert [t["ticker"] for t in week] == ["KXBNB15M-1"]
    rows = [_row(), _row(action="skip", reason="ask 0.97 outside 0.05-0.95"),
            _row(action="skip", reason="edge 0.01 < floor 0.05")]
    assert len(dd.skips_outside_range(rows)) == 1
    idx = dd.DecisionIndex(rows + [_row(tower="nasdaq", market="KXNASDAQ100U-X")])
    assert len(idx.find(tower="more-15m")) == 3 and len(idx.find(market="KXNASDAQ100U-X")) == 1
    assert len(idx.find(tower="more-15m", hour="2026-11-13T18")) == 3 and idx.find(hour="2026-11-13T19") == []


def test_rule_versions_split_results_and_count_losses():
    versions = [{"tower": "more-15m", "version": "v1", "start": "2026-11-12T00:00:00+00:00"},
                {"tower": "more-15m", "version": "v2", "start": "2026-11-13T08:00:00+00:00"},
                {"tower": "btc15m", "version": "v9", "start": "2026-11-01T00:00:00+00:00"}]
    trades = [{"opened": "2026-11-11T23:00:00+00:00", "pnl": 5},
              {"opened": "2026-11-12T10:00:00+00:00", "pnl": -4},
              {"opened": "2026-11-13T09:00:00+00:00", "pnl": -2},
              {"opened": "2026-11-13T10:00:00+00:00", "pnl": 3}]
    assert [t["rule_version"] for t in dd.tag_trades(trades, versions, "more-15m")] == ["v0", "v1", "v2", "v2"]
    split = {r["version"]: r for r in dd.results_by_version(trades, versions, "more-15m")}
    assert split["v1"] == {"version": "v1", "n": 1, "wins": 0, "losses": 1, "pnl": -4.0}
    assert split["v2"]["pnl"] == 1.0 and split["v2"]["losses"] == 1


def test_shipped_rule_versions_file():
    rows = dd.load_rule_versions()
    towers = {r["tower"] for r in rows}
    assert {"more-15m", "commodity-15m", "btc15m"} <= towers
    assert dd.version_at(rows, "more-15m", "2026-11-13T12:00:00+00:00") != "v0"
    with open(dd.RULE_VERSIONS_FILE, encoding="utf-8") as handle:
        assert json.load(handle)["paper_only"] is True
