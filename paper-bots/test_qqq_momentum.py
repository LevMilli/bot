"""QQQ momentum tower. Offline."""
import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "qqq-momentum-paper"))

import qqq_model as qm  # noqa: E402

START = dt.date(2026, 10, 1)


def _sessions(n=16, last_path=None):
    """n weekday sessions of 78 five-minute bars. Normal days drift ±0.2%; the last can follow a path."""
    ts, o, h, lo, c, v = [], [], [], [], [], []
    day, made, price = START, 0, 100.0
    while made < n:
        if day.weekday() < 5:
            made += 1
            open_ = price
            for k in range(78):
                start = dt.datetime.combine(day, dt.time(9, 30), qm.NY) + dt.timedelta(minutes=5 * k)
                if made == n and last_path:
                    close = open_ * (1 + last_path(k + 1))
                else:
                    close = open_ * (1 + (0.002 if made % 2 else -0.002) * (k + 1) / 78)
                prev = open_ if k == 0 else c[-1]
                ts.append(int(start.timestamp()))
                o.append(prev); c.append(close); h.append(max(prev, close)); lo.append(min(prev, close)); v.append(1000)
            price = c[-1]
        day += dt.timedelta(days=1)
    return {"chart": {"result": [{"timestamp": ts, "indicators": {"quote": [
        {"open": o, "high": h, "low": lo, "close": c, "volume": v}]}}]}}, day - dt.timedelta(days=1)


def _rally(t_end):
    """Up 2% by 11:00, then back to flat by 13:00."""
    m = t_end * 5
    return min(m, 90) / 90 * 0.02 if m <= 90 else max(0.0, 0.02 - (m - 90) / 120 * 0.02)


def _bot():
    spec = importlib.util.spec_from_file_location("qqq_bot", os.path.join(HERE, "qqq-momentum-paper", "bot.py"))
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    return bot


def test_parse_and_bands():
    chart, _ = _sessions(16)
    days = qm.parse_bars(chart)
    assert len(days) == 16 and all(len(d["bars"]) == 78 for d in days)
    assert qm.bands(days, 5, 30) is None                       # fewer than 10 past sessions
    b = qm.bands(days, 15, 30)
    assert abs(b["sigma"] - 0.002 * 6 / 78) < 1e-9
    day, prev = days[15], days[14]
    assert abs(b["upper"] - max(day["open"], prev["close"]) * (1 + b["sigma"])) < 1e-9


def test_decide_entries_stops_and_buffer():
    b = {"close": 101.0, "upper": 100.5, "lower": 99.0, "vwap": 100.0, "sigma": 0.005}
    assert qm.decide(None, b, 0.02)[1] == "long"
    assert qm.decide(None, dict(b, close=100.51), 0.02)[1] is None           # touch, not a clear break
    assert qm.decide("long", dict(b, close=100.4), 0.02)[:2] == (True, None)  # under the band stop
    assert qm.decide("short", dict(b, close=98.0, vwap=98.5), 0.02)[:2] == (False, "short")
    flip = qm.decide("long", dict(b, close=98.5), 0.02)
    assert flip[0] is True and flip[1] == "short"


def test_costs():
    assert qm.fill("long", 100.0, True) == 100.01 and qm.fill("long", 100.0, False) == 99.99
    assert qm.fill("short", 100.0, True) == 99.99
    assert abs(qm.trade_pnl("long", 10, 100.0, 101.0) - (10 - 0.07)) < 1e-9
    assert abs(qm.trade_pnl("short", 10, 100.0, 101.0) - (-10 - 0.07)) < 1e-9


def test_live_replay_matches_backtest_and_is_flat_at_close(tmp_path):
    chart, last = _sessions(16, _rally)
    days = qm.parse_bars(chart)
    want = qm.backtest_day(days, 15, 0.02)
    assert want and want[0]["side"] == "long"
    bot = _bot()
    for k in range(1, 80):
        now = (dt.datetime.combine(last, dt.time(9, 30), qm.NY) + dt.timedelta(minutes=5 * k + 1)).astimezone(dt.timezone.utc)
        with contextlib.redirect_stdout(io.StringIO()):
            bot.main([], here=str(tmp_path), chart=chart, now=now)
    state = json.loads((tmp_path / "paper_account.json").read_text())
    assert state["open"] == []
    assert len(state["closed"]) == len(want)
    assert all(abs(r["pnl"] - t["pnl"]) < 1e-3 and r["side"] == t["side"] for r, t in zip(state["closed"], want))
    assert abs(state["cash"] - (500 + sum(t["pnl"] for t in want))) < 1e-3
    assert state["closed"][0]["ticker"] == "QQQ" and state["closed"][0]["cost"] == 25.0


def test_no_late_fills_and_gate(tmp_path, monkeypatch):
    chart, last = _sessions(16, _rally)
    bot = _bot()
    late = (dt.datetime.combine(last, dt.time(12, 0), qm.NY)).astimezone(dt.timezone.utc)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        bot.main([], here=str(tmp_path), chart=chart, now=late)
    rows = json.loads((tmp_path / "research.jsonl").read_text().splitlines()[-1])["checks"]
    assert [r["action"] for r in rows[:-1]] == ["missed"] * (len(rows) - 1)
    assert "no trade" in out.getvalue() or "BUY" in out.getvalue()
    monkeypatch.setenv("DESK_BLOCK_ENTRIES", "1")
    gated = tmp_path / "gated"
    for k in range(1, 40):
        now = (dt.datetime.combine(last, dt.time(9, 30), qm.NY) + dt.timedelta(minutes=5 * k + 1)).astimezone(dt.timezone.utc)
        with contextlib.redirect_stdout(io.StringIO()):
            bot.main([], here=str(gated), chart=chart, now=now)
    state = json.loads((gated / "paper_account.json").read_text())
    assert state["open"] == [] and state["closed"] == [] and state["cash"] == 500


def test_closed_day_and_failed_read(tmp_path):
    chart, last = _sessions(16)
    bot = _bot()
    sunday = dt.datetime(2026, 11, 15, 15, tzinfo=dt.timezone.utc)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert bot.main([], here=str(tmp_path), chart=chart, now=sunday) == 0
    assert "no QQQ session today" in out.getvalue() and "no trade" in out.getvalue()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert bot.main([], here=str(tmp_path), chart={}, now=sunday) == 0
    assert "no trade" in out.getvalue()


def test_registry_floor_and_desk_wiring():
    import desk_profit
    import new_towers
    import pimp_desk

    assert desk_profit.DEFAULT_VENUE_MIN_EDGE["equity_qqq"] == 0.02
    assert desk_profit.venue_min_edge("equity_qqq", {"venue_min_edge": {"equity_qqq": 0.0}}) == 0.02
    spec = next(s for s in new_towers.ACTIVE if s["id"] == "qqq-momentum")
    assert spec["venue"] == "equity_qqq" and not spec.get("research")
    assert pimp_desk._account_body("qqq-momentum")["cash"] == 500.0
    assert "qqq-momentum-paper/research.jsonl" in pimp_desk.SETTLEMENT_FILES
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("qqq-momentum")["ok"]
