"""Calibration lab: table math, row building, batching, scorecard and a fake run."""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import calibration_lab as lab  # noqa: E402


def _candle(ts, bid, ask):
    return {"end_period_ts": ts, "yes_bid": {"close_dollars": str(bid)}, "yes_ask": {"close_dollars": str(ask)}}


CLOSE = "2026-11-10T22:00:00Z"
CLOSE_TS = int(dt.datetime(2026, 11, 10, 22, tzinfo=dt.timezone.utc).timestamp())


def test_wilson_and_band():
    lo, hi = lab.wilson(50, 100)
    assert 0.40 < lo < 0.41 and 0.59 < hi < 0.60
    assert lab.wilson(0, 0) == (0.0, 1.0)
    assert lab.band_of(0.10) == "0.10-0.15"
    assert lab.band_of(0.149) == "0.10-0.15"
    assert lab.band_of(0.92) == "0.90-0.95"
    assert lab.family_of("KXBTCD") == "crypto_daily"
    assert lab.family_of("NOPE") is None


def test_quote_at_uses_last_closed_candle():
    candles = [_candle(100, 0.10, 0.12), _candle(200, 0.20, 0.22), _candle(300, 0.30, 0.32)]
    assert lab.quote_at(candles, 250) == [0.2, 0.22]
    assert lab.quote_at(candles, 50) is None
    assert lab.quote_at([{"end_period_ts": 10}], 20) is None


def test_make_row_keeps_markets_without_quotes():
    m = {"ticker": "KXHIGHNY-X", "close_time": CLOSE, "result": "yes"}
    row = lab.make_row(m, "KXHIGHNY", [_candle(CLOSE_TS - 3 * 3600, 0.4, 0.45)])
    assert row["family"] == "weather" and row["q"]["3"] == [0.4, 0.45] and "1" in row["q"]
    assert "6" not in row["q"]
    empty = lab.make_row(m, "KXHIGHNY", [])
    assert empty["q"] == {}
    assert lab.make_row({**m, "result": ""}, "KXHIGHNY", []) is None


def test_build_table_and_lookup():
    rows = []
    for i in range(10):
        rows.append({"ticker": f"T{i}", "family": "gas", "result": "yes" if i < 9 else "no",
                     "q": {"1": [0.88, 0.90]}})
    table = lab.build_table(rows)
    cell = lab.lookup("gas", 1, 0.90, table)
    assert cell["n"] == 10 and cell["wins"] == 9 and cell["avg_price"] == 0.9
    assert cell["edge_lo"] == round(cell["wilson_lo"] - 0.9 - cell["avg_fee"], 4)
    no_side = lab.lookup("gas", 1, 0.12, table)  # 1 − 0.88 bid
    assert no_side["n"] == 10 and no_side["wins"] == 1
    assert lab.lookup("gas", 3, 0.9, table) is None
    assert lab.build_table([{"ticker": "X", "family": "gas", "result": "yes", "q": {}}]) == {}


def test_chunks_split_by_size_and_span():
    base = dt.datetime(2026, 11, 10, tzinfo=dt.timezone.utc)
    ms = [{"ticker": f"T{i}", "close_time": (base - dt.timedelta(hours=i)).isoformat()} for i in range(30)]
    out = lab.chunks(ms, size=10, span_h=24)
    assert [len(c) for c in out] == [10, 10, 10]
    out = lab.chunks(ms, size=100, span_h=5)
    assert all(len(c) <= 6 for c in out) and sum(len(c) for c in out) == 30


def _fake_get(markets_by_series, candles):
    calls = {"candles": 0}

    def get(url, *a, **k):
        if "/markets/candlesticks" in url:
            calls["candles"] += 1
            tickers = url.split("market_tickers=")[1].split("&")[0].split(",")
            return {"markets": [{"market_ticker": t, "candlesticks": candles.get(t, [])} for t in tickers]}
        series = url.split("series_ticker=")[1].split("&")[0]
        return {"markets": markets_by_series.get(series, []), "cursor": ""}

    return get, calls


def test_run_fills_every_family_and_does_not_refetch(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, "FAMILY_BATCHES", 1)
    markets, candles = {}, {}
    for fam, members in lab.FAMILIES.items():
        s = members[0]
        rows = []
        for i in range(150):
            t = f"{s}-{i}"
            rows.append({"ticker": t, "close_time": CLOSE, "result": "yes" if i % 2 else "no"})
            if i % 3:
                candles[t] = [_candle(CLOSE_TS - 3600, 0.48, 0.50)]
        markets[s] = rows
    get, calls = _fake_get(markets, candles)
    now = dt.datetime(2026, 11, 11, tzinfo=dt.timezone.utc)
    desk = tmp_path / "desk"
    desk.mkdir()
    body = lab.run(str(desk), str(tmp_path / "lab"), now, get=get, market_get=lambda t: None)
    assert all(body["families"][f] == 100 for f in lab.FAMILIES), body["families"]
    assert calls["candles"] == len(lab.FAMILIES)
    body = lab.run(str(desk), str(tmp_path / "lab"), now, get=get, market_get=lambda t: None)
    assert body["new_rows"] == 50 * len(lab.FAMILIES)
    body = lab.run(str(desk), str(tmp_path / "lab"), now, get=get, market_get=lambda t: None)
    assert body["new_rows"] == 0  # markets with no candles are not fetched again
    assert "gas" in body["table"]
    assert lab.card(body).startswith("Calibration lab:")


def test_scorecard_reads_research_logs(tmp_path):
    import new_towers

    spec = next(s for s in new_towers.ACTIVE if not s.get("research"))
    folder = tmp_path / spec["folder"]
    folder.mkdir()
    rows = [{"at": "x", "decisions": [
        {"ticker": "A", "side": "yes", "fair": 0.8, "ask": 0.6},
        {"ticker": "B", "side": "no", "fair": 0.7, "ask": 0.5},
        {"ticker": "C", "side": "yes", "fair": 0.5, "ask": 0.5},
    ]}]
    (folder / "research.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    cards = lab.scorecard(str(tmp_path), {"A": "yes", "B": "no"}, get=lambda t: None)
    c = cards[spec["id"]]
    assert c["n"] == 2
    assert c["brier_model"] < c["brier_ask"]
    assert "calibration-lab" not in cards


def test_registry_and_desk_wiring():
    import desk_profit
    import new_towers
    import pimp_desk

    assert "calibration-lab" in new_towers.RESEARCH
    assert desk_profit.BOT_VENUE["calibration-lab"] == "kalshi_econ"
    assert pimp_desk._account_body("calibration-lab")["cash"] == 0.0
    assert "calibration-lab" in pimp_desk._ZERO_STAKE_IDS
    assert pimp_desk.BOT_PLANS["calibration-lab"]["stake"] == "none"
    assert pimp_desk.bot_roi_compliance("calibration-lab")["ok"]
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    res = new_tower.check_tower("calibration-lab")
    assert res["ok"], res
