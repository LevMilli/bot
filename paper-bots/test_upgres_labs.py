"""B12 exit lab, B13 15-minute calibration families, B14 promotion card, B19 fast snapshots. Offline."""
from __future__ import annotations

import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for sub in ("whatif-lab-paper", "scorekeeper-paper", "market-snapshots-paper"):
    sys.path.insert(0, os.path.join(HERE, sub))

import calibration_lab as lab  # noqa: E402
import exit_model as em  # noqa: E402
import score_model as sm  # noqa: E402
import snapshot_model as rm  # noqa: E402

NOW = dt.datetime(2026, 11, 13, 18, tzinfo=dt.timezone.utc)
RESEARCH_IDS = ("calibration-lab", "scorekeeper", "whatif-lab", "market-snapshots")


def _load(name, folder):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, folder, "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _candle(ts, bid, ask):
    return {"end_period_ts": ts, "yes_bid": {"close_dollars": str(bid)}, "yes_ask": {"close_dollars": str(ask)}}


# ------------------------------------------------------------------ registry safety
def test_research_rows_stay_research_only():
    import new_towers

    for tid in RESEARCH_IDS:
        row = new_towers.BY_ID[tid]
        assert row["max_open"] == 0 and row.get("research") is True and row["kind"] == "research"
    assert new_towers.BY_ID["market-snapshots"]["every_sec"] == 60
    assert "calibration_rows_15m.jsonl" in new_towers.BY_ID["calibration-lab"]["keep"]
    assert "exits.json" in new_towers.BY_ID["whatif-lab"]["keep"]


def test_research_rows_still_pass_the_desk_check():
    import pimp_desk

    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower

    for tid in RESEARCH_IDS:
        assert new_tower.check_tower(tid)["ok"], tid
        assert pimp_desk.TOWER_STARTER_CASH[tid] == 0.0
    assert "calibration-lab-paper/calibration_rows_15m.jsonl" in pimp_desk.SETTLEMENT_FILES
    assert "whatif-lab-paper/exits.json" in pimp_desk.SETTLEMENT_FILES


# ------------------------------------------------------------------ B13 calibration 15m
def test_daily_families_unchanged_and_15m_kept_apart():
    # The original five keep their members; Nov 13 added five more for the new towers.
    assert set(lab.FAMILIES) == {"weather", "gas", "crypto_daily", "nasdaq", "sp", "weather_low",
                                 "weather_cities", "precip_monthly", "gas_monthly", "crypto_hourly"}
    assert lab.FAMILIES["weather"] == ("KXHIGHNY", "KXHIGHCHI", "KXHIGHMIA", "KXHIGHAUS", "KXHIGHDEN",
                                       "KXHIGHPHIL", "KXHIGHLAX")
    assert lab.FAMILIES["gas"] == ("KXAAAGASW",) and lab.FAMILIES["crypto_daily"] == ("KXBTCD", "KXETHD")
    assert lab.HORIZONS == (1, 3, 6)
    assert set(lab.FAMILIES_15M) == {"crypto_15m", "commodity_15m", "fx_15m", "index_15m"}
    every = [s for m in lab.FAMILIES_15M.values() for s in m]
    assert all(s.endswith("15M") for s in every) and len(every) == len(set(every))
    assert not set(every) & {s for m in lab.FAMILIES.values() for s in m}
    assert lab.family_of("KXBTC15M") is None                       # daily lookups never see 15m
    assert lab.family_of("KXBTC15M", lab.FAMILIES_15M) == "crypto_15m"
    assert set(every) == set(rm.SERIES_15M)                        # snapshots record the same series


def test_15m_row_uses_minutes():
    close = "2026-11-13T17:15:00Z"
    cts = int(dt.datetime(2026, 11, 13, 17, 15, tzinfo=dt.timezone.utc).timestamp())
    m = {"ticker": "KXBTC15M-X", "close_time": close, "result": "yes"}
    candles = [_candle(cts - 600, 0.40, 0.42), _candle(cts - 120, 0.80, 0.82), _candle(cts - 60, 0.90, 0.92)]
    row = lab.make_row(m, "KXBTC15M", candles, lab.HORIZONS_15M, 60, lab.FAMILIES_15M)
    assert row["family"] == "crypto_15m"
    assert row["q"] == {"1": [0.9, 0.92], "2": [0.8, 0.82], "5": [0.4, 0.42], "10": [0.4, 0.42]}


def _fake_get(markets_by_series, candles, calls):
    def get(url, *a, **k):
        if "/markets/candlesticks" in url:
            calls.append(url)
            tickers = url.split("market_tickers=")[1].split("&")[0].split(",")
            return {"markets": [{"market_ticker": t, "candlesticks": candles.get(t, [])} for t in tickers]}
        series = url.split("series_ticker=")[1].split("&")[0]
        return {"markets": markets_by_series.get(series, []), "cursor": ""}
    return get


def test_run_builds_table_15m_without_touching_daily(tmp_path):
    base = dt.datetime(2026, 11, 13, 17, 0, tzinfo=dt.timezone.utc)
    markets, candles, calls = {}, {}, []
    for i in range(60):
        close = base - dt.timedelta(minutes=15 * (i % 4))
        t = f"KXBTC15M-{i}"
        markets.setdefault("KXBTC15M", []).append(
            {"ticker": t, "close_time": close.isoformat().replace("+00:00", "Z"), "result": "yes" if i % 10 else "no"})
        candles[t] = [_candle(int(close.timestamp()) - 120, 0.88, 0.90)]
    get = _fake_get(markets, candles, calls)
    body = lab.run(str(tmp_path / "desk"), str(tmp_path / "lab"), NOW, get=get, market_get=lambda t: None)
    assert body["table"] == {} and body["families"]["weather"] == 0
    assert body["rows_15m"] == 60 and body["families_15m"]["crypto_15m"] == 60
    cell = lab.lookup_15m("crypto_15m", 2, 0.90, body["table_15m"])
    assert cell["n"] == 60 and cell["wins"] == 54
    assert all("period_interval=1" in u for u in calls) and len(calls) == 1
    again = lab.run(str(tmp_path / "desk"), str(tmp_path / "lab"), NOW, get=get, market_get=lambda t: None)
    assert again["new_rows_15m"] == 0 and len(calls) == 1          # never fetched twice
    assert os.path.exists(tmp_path / "lab" / "calibration_rows_15m.jsonl")
    assert "15m families: 60 windows" in lab.card(again)


def test_15m_chunks_respect_candle_cap():
    base = dt.datetime(2026, 11, 13, tzinfo=dt.timezone.utc)
    ms = [{"ticker": f"T{i}", "close_time": (base - dt.timedelta(minutes=15 * i)).isoformat()} for i in range(400)]
    for chunk in lab.chunks(ms, size=100, span_h=lab.CHUNK_15M_MIN / 60):
        span_min = (lab._ts(chunk[0]["close_time"]) - lab._ts(chunk[-1]["close_time"])) / 60
        assert len(chunk) <= 100 and len(chunk) * (span_min + max(lab.HORIZONS_15M) + 2) <= 10000


def test_15m_failure_never_stops_daily_lab(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, "collect_15m", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    body = lab.run(str(tmp_path / "desk"), str(tmp_path / "lab"), NOW, get=lambda u: {"markets": []},
                   market_get=lambda t: None)
    assert "15m families skipped (RuntimeError)" in body["notes"] and body["rows_15m"] == 0


def test_favorite_harvest_still_reads_only_daily_families():
    src = open(os.path.join(HERE, "favorite-harvest-paper", "bot.py"), encoding="utf-8").read()
    assert "lab.FAMILIES.items()" in src and "FAMILIES_15M" not in src


# ------------------------------------------------------------------ B12 exit lab
OPEN = dt.datetime(2026, 11, 13, 16, 0, tzinfo=dt.timezone.utc)
CLOSE = OPEN + dt.timedelta(minutes=14)


def _trade(**kw):
    row = dict(ticker="KXBTC15M-26NOV131615-15", side="YES", contracts=10, ask=0.50, fee=0.02, cost=5.20,
               opened=OPEN.strftime("%Y-%m-%d %H:%M:%S UTC"), closed=CLOSE.strftime("%Y-%m-%d %H:%M:%S UTC"),
               pnl=1.0, exit="take-profit", close_time=CLOSE.isoformat())
    row.update(kw)
    return row


def test_trade_of_normalizes_both_formats():
    t = em.trade_of("btc15m", _trade())
    assert t["side"] == "yes" and t["entry"] == 0.52 and t["opened"] == OPEN.isoformat()
    t2 = em.trade_of("weather-high", dict(ticker="KXHIGHNY-1", side="no", contracts=5, ask=0.3, fee=0.02,
                                           cost=1.6, opened=OPEN.isoformat(), pnl=-1.6, result="yes"))
    assert t2["result"] == "yes" and t2["entry"] == 0.32
    assert em.trade_of("x", dict(ticker="SOL", side="yes", contracts=1, pnl=1, opened=OPEN.isoformat())) is None
    assert em.trade_of("x", _trade(pnl=None)) is None


def test_grade_rules():
    t = em.trade_of("btc15m", _trade())
    ots, cts = int(OPEN.timestamp()), int(CLOSE.timestamp())
    path = [(ots + 60, 0.55), (ots + 180, 0.61), (ots + 300, 0.66), (ots + 600, 0.30)]
    g = em.grade(t, "no", cts, path)
    assert g["actual"] == 0.1
    assert g["hold"] == -0.52                                    # held to a loss: the loss counts
    assert g["plus10"] == round(0.61 - em.fee(0.61) - 0.52, 4)
    assert g["plus15"] == round(0.66 - em.fee(0.66) - 0.52, 4)
    assert g["time_stop"] == round(0.66 - em.fee(0.66) - 0.52, 4)   # last bid by the 7-minute half-way point
    assert g["model_flip"] is None
    flips = [(ots + 120, 0.70, 0.60)]
    assert em.grade(t, "no", cts, path, flips)["model_flip"] == round(0.70 - em.fee(0.70) - 0.52, 4)
    never = em.grade(t, "yes", cts, [(ots + 60, 0.55)])
    assert never["plus10"] == never["hold"] == 0.48


def test_side_bids_for_no_is_one_minus_yes_ask():
    c = [_candle(200, 0.40, 0.45), _candle(100, 0.30, 0.35)]
    assert em.side_bids(c, "yes") == [(100, 0.3), (200, 0.4)]
    assert em.side_bids(c, "no") == [(100, 0.65), (200, 0.55)]


def test_candle_groups_stay_under_kalshi_caps():
    todo = []
    for i in range(300):
        o = int(OPEN.timestamp()) + i * 900
        todo.append({"ticker": f"T{i}", "_open_ts": o, "_close_ts": o + 840})
    groups = em.candle_groups(todo)
    for group, period in groups:
        span = (max(t["_close_ts"] for t in group) - min(t["_open_ts"] for t in group)) / 60 / period + 2
        assert len(group) <= 100 and span * len(group) <= 10000 and period == 1
    long = [{"ticker": "L", "_open_ts": 0, "_close_ts": 3 * 86400}]
    assert em.candle_groups(long)[0][1] == 60


def _exit_get(results, candles, log):
    def get(url, *a, **k):
        log.append(url)
        if "/markets/candlesticks" in url:
            tickers = url.split("market_tickers=")[1].split("&")[0].split(",")
            return {"markets": [{"market_ticker": t, "candlesticks": candles.get(t, [])} for t in tickers]}
        tickers = url.split("tickers=")[1].split("&")[0].split(",")
        return {"markets": [{"ticker": t, "result": results.get(t, ""), "close_time": CLOSE.isoformat()}
                            for t in tickers]}
    return get


def test_exit_lab_run_grades_once_and_counts_losses(tmp_path):
    closed = []
    candles = {}
    ots = int(OPEN.timestamp())
    for i in range(60):
        t = f"KXBTC15M-{i}"
        win = i % 3 != 0
        closed.append(_trade(ticker=t, pnl=-5.2 if not win else 4.8, exit="settled"))
        candles[t] = [_candle(ots + 120, 0.62, 0.64)]
    closed.append(_trade(ticker="KXOPEN-1", pnl=1.0))           # market not settled yet
    path = tmp_path / "acct.json"
    path.write_text(json.dumps({"closed": closed}))
    results = {f"KXBTC15M-{i}": ("yes" if i % 3 else "no") for i in range(60)}
    log = []
    get = _exit_get(results, candles, log)
    body = em.run([("btc15m", str(path))], {}, {}, get, NOW)
    allr = body["report"]["all"]
    assert allr["hold"]["n"] == 60 and allr["actual"]["n"] == 60
    assert allr["actual"]["total"] == round(40 * 4.8 - 20 * 5.2, 2)  # losses included
    assert allr["plus10"]["n"] == 60 and allr["plus10"]["ready"]
    assert body["pending"] == 1
    reads = len(log)
    again = em.run([("btc15m", str(path))], {}, body, get, NOW)
    assert again["report"]["all"]["hold"]["n"] == 60
    assert len(log) == reads                                    # graded trades are never read again
    line = em.card(again)
    assert line.startswith("Exit lab: 60 closed Kalshi trades graded") and "Suggests only." in line
    assert "!" not in line


def test_whatif_bot_writes_exits_json(tmp_path):
    bot = _load("whatif_bot_x", "whatif-lab-paper")
    path = tmp_path / "acct.json"
    path.write_text(json.dumps({"closed": [_trade()]}))
    get = _exit_get({"KXBTC15M-26NOV131615-15": "yes"}, {}, [])
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert bot.main([], root=str(tmp_path), fetch=lambda t: {}, trades_fetch=lambda *a: [], now=NOW,
                        exit_get=get, exit_accounts=[("btc15m", str(path))]) == 0
    text = out.getvalue()
    assert "EXITS: Exit lab: 1 closed" in text and "no trade" in text
    body = json.loads((tmp_path / "whatif-lab-paper" / "exits.json").read_text())
    assert body["suggest_only"] and body["report"]["bots"]["btc15m"]["hold"]["n"] == 1
    state = json.loads((tmp_path / "whatif-lab-paper" / "paper_account.json").read_text())
    assert state["cash"] == 0.0 and state["open"] == []


def test_whatif_accounts_cover_trading_towers_only():
    bot = _load("whatif_bot_y", "whatif-lab-paper")
    ids = {bid for bid, _ in bot.accounts(HERE)}
    assert {"btc15m", "commodity-15m", "more-15m"} <= ids
    assert not ids & set(RESEARCH_IDS)


# ------------------------------------------------------------------ B14 promotion card
def test_promotion_row_flags_ready_at_50_and_counts_losses():
    r = sm.promotion_row("x", "X", [1.0] * 30 + [-1.0] * 19)
    assert r["n"] == 49 and r["to_go"] == 1 and not r["ready_to_review"] and r["verdict"] == "counting"
    r = sm.promotion_row("x", "X", [1.0] * 30 + [-1.0] * 20)
    assert r["ready_to_review"] and r["total"] == 10.0 and r["needs_levi_ok"]
    assert r["verdict"] in ("mixed", "looks good")
    bad = sm.promotion_row("y", "Y", [-1.0] * 50 + [0.5])
    assert bad["ready_to_review"] and bad["verdict"] == "not good"
    good = sm.promotion_row("z", "Z", [1.0, 1.2] * 30)
    assert good["verdict"] == "looks good" and good["low"] > 0


def test_promotion_reads_every_row_in_new_towers(tmp_path, monkeypatch):
    import new_towers

    twin = dict(new_towers.BY_ID["more-15m"], id="more-15m-twin-test", name="More 15m twin",
                folder="more-15m-twin-test-paper")
    monkeypatch.setattr(new_towers, "TOWERS", new_towers.TOWERS + (twin,))
    folder = tmp_path / twin["folder"]
    folder.mkdir()
    closed = [dict(ticker=f"K{i}", contracts=10, pnl=2.0 if i % 2 else -1.0) for i in range(52)]
    (folder / "paper_account.json").write_text(json.dumps({"closed": closed}))
    bot = _load("score_bot_promo", "scorekeeper-paper")
    rows = bot.promotion_rows(str(tmp_path), 0.01)
    ids = [r["id"] for r in rows]
    practice = [r["id"] for r in new_towers.TOWERS if not r.get("research")]
    assert ids == practice                                       # nothing hard-coded, research rows skipped
    row = next(r for r in rows if r["id"] == twin["id"])
    assert row["n"] == 52 and row["ready_to_review"]
    assert abs(row["total"] - round(26 * 1.9 + 26 * -1.1, 2)) < 1e-6
    promo = sm.promotion(rows, NOW)
    assert promo["ready"] == [twin["id"]] and promo["auto_promote"] is False
    line = sm.promotion_card(promo)
    assert line.startswith(f"Promotion card: 1 of {len(rows)} practice towers at 50 results")
    assert "needs Levi's OK" in line and "!" not in line


def test_scorekeeper_main_writes_promotion(tmp_path):
    bot = _load("score_bot_main", "scorekeeper-paper")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert bot.main([], root=str(tmp_path), now=NOW) == 0
    assert "CARD: Promotion card: 0 of" in out.getvalue()
    card = json.loads((tmp_path / "scorekeeper-paper" / "scorecard.json").read_text())
    assert card["promotion"]["min_n"] == 50 and card["promotion"]["suggest_only"]
    assert len(card["promotion"]["towers"]) >= 10


# ------------------------------------------------------------------ B19 fast snapshots
def _m(ticker, close, bid=0.4, ask=0.45):
    return {"ticker": ticker, "close_time": close.isoformat(), "yes_bid_dollars": str(bid),
            "yes_ask_dollars": str(ask)}


def test_full_due():
    assert rm.full_due({}, NOW)
    assert not rm.full_due({"last_full": (NOW - dt.timedelta(minutes=5)).isoformat()}, NOW)
    assert rm.full_due({"last_full": (NOW - dt.timedelta(minutes=15)).isoformat()}, NOW)


def test_fast_snapshot_reads_once_and_only_last_14_minutes():
    windows = {}
    lists = []
    close = NOW + dt.timedelta(minutes=10)

    def list_open(series, limit):
        lists.append(series)
        return [_m(f"{series}-A", close)] if series in ("KXBTC15M", "KXGOLD15M") else []

    batches = []

    def read(tickers):
        batches.append(tickers)
        return [_m(t, close) for t in tickers]

    snap, notes, reads = rm.fast_snapshot(list_open, read, windows, NOW)
    assert snap["fast"] and set(snap["series"]) == {"KXBTC15M", "KXGOLD15M"}
    assert len(batches) == 1 and reads == len(rm.SERIES_15M) + 1
    lists.clear()
    # Next minute: known windows still open, so only the series without one are listed again.
    snap, _, reads = rm.fast_snapshot(list_open, read, windows, NOW + dt.timedelta(minutes=1))
    assert "KXBTC15M" not in lists and len(batches) == 2
    # A window with more than 14 minutes left is not recorded yet.
    far = {"KXBTC15M": {"KXBTC15M-B": (NOW + dt.timedelta(minutes=14, seconds=30)).isoformat()}}
    assert rm.live_tickers(far, NOW) == []


def test_snapshot_bot_full_then_fast(tmp_path):
    bot = _load("snap_bot_fast", "market-snapshots-paper")
    close = NOW + dt.timedelta(minutes=8)

    def list_open(series, limit):
        return [_m(series + "-1", close)]

    def read(tickers):
        return [_m(t, close) for t in tickers]

    folder = tmp_path / "rec"
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert bot.main([], here=str(tmp_path), list_open=list_open, now=NOW, folder=str(folder),
                        tickers_read=read) == 0
        assert bot.main([], here=str(tmp_path), list_open=list_open, now=NOW + dt.timedelta(minutes=1),
                        folder=str(folder), tickers_read=read) == 0
    day = rm.read_day(str(folder / "2026-11-13.jsonl.gz"))
    full = [d for d in day if not d.get("fast")]
    fast = [d for d in day if d.get("fast")]
    assert len(full) == 1 and len(full[0]["series"]) == len(rm.SERIES)
    assert len(fast) == 2 and len(fast[1]["series"]) == len(rm.SERIES_15M)
    text = out.getvalue()
    assert "full snapshot not due" in text and "15m every minute" in text and "no trade" in text
    state = json.loads((tmp_path / "paper_account.json").read_text())
    assert state["cash"] == 0.0 and state["fast_15m"]["runs"] == 2
