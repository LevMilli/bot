"""Nasdaq tower. Offline."""
import datetime as dt
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "nasdaq-paper"))

import nasdaq_model as nm  # noqa: E402

UTC = dt.timezone.utc
NOON = dt.datetime(2026, 11, 12, 17, tzinfo=UTC)       # 12:00 ET Thursday
CLOSE = dt.datetime(2026, 11, 12, 21, tzinfo=UTC)      # 16:00 ET


def _bot():
    spec = importlib.util.spec_from_file_location("nasdaq_bot", os.path.join(HERE, "nasdaq-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_minutes_left_regular_hours_only():
    assert nm.minutes_left(NOON, CLOSE) == 240
    assert nm.minutes_left(dt.datetime(2026, 11, 12, 13, tzinfo=UTC), CLOSE) is None   # 8:00 ET
    assert nm.minutes_left(dt.datetime(2026, 11, 12, 21, 30, tzinfo=UTC), CLOSE) is None
    assert nm.minutes_left(dt.datetime(2026, 11, 14, 17, tzinfo=UTC),
                           dt.datetime(2026, 11, 14, 21, tzinfo=UTC)) is None          # Saturday
    assert nm.minutes_left(NOON, CLOSE + dt.timedelta(days=1)) is None                 # tomorrow's event


def test_fair_kinds_add_up():
    lvl, vol, mins = 28400.0, 0.27, 240
    above = nm.fair_yes({"strike_type": "greater", "floor_strike": 28500}, lvl, vol, mins)
    below = nm.fair_yes({"strike_type": "less", "cap_strike": 28500}, lvl, vol, mins)
    assert math.isclose(above + below, 1.0, abs_tol=1e-9)
    rng = nm.fair_yes({"strike_type": "between", "floor_strike": 28300, "cap_strike": 28499.99}, lvl, vol, mins)
    assert 0.2 < rng < 0.5
    assert nm.fair_yes({"strike_type": "greater_or_equal", "floor_strike": 30000}, lvl, vol, mins) == 0.01
    assert nm.fair_yes({"strike_type": "weird"}, lvl, vol, mins) is None


def test_chart_meta():
    body = {"chart": {"result": [{"meta": {"regularMarketPrice": 28374.25, "regularMarketTime": 1794435359}}]}}
    assert nm.chart_meta(body) == (28374.25, 1794435359)
    assert nm.chart_meta({"chart": {"result": []}}) is None


def test_quotes_for_window_and_labels():
    bot = _bot()
    base = {"close_time": "2026-11-12T21:00:00Z", "yes_ask_dollars": "0.40", "yes_bid_dollars": "0.36",
            "no_ask_dollars": "0.64", "no_bid_dollars": "0.60"}
    markets = [
        dict(base, ticker="U-1", event_ticker="KXNASDAQ100U-26NOV12H1600", strike_type="greater_or_equal", floor_strike=28500),
        dict(base, ticker="R-1", event_ticker="KXNASDAQ100-26NOV12H1600", strike_type="between", floor_strike=28300, cap_strike=28499.99),
        dict(base, ticker="T-1", event_ticker="KXNASDAQ100-26NOV13H1600", strike_type="greater", floor_strike=28500,
             close_time="2026-11-13T21:00:00Z"),
    ]
    q = bot.quotes_for(markets, 28400.0, 0.27, NOON)
    assert {x["ticker"] for x in q} == {"U-1", "R-1"}
    assert any(x["label"] == "NDX Nov 12 above 28,500" for x in q)
    assert any(x["label"] == "NDX Nov 12 28,300-28,500" for x in q)
    late = dt.datetime(2026, 11, 12, 20, 55, tzinfo=UTC)
    assert bot.quotes_for(markets, 28400.0, 0.27, late) == []


def test_model_closed_and_stale(monkeypatch):
    bot = _bot()
    assert bot.model({}, dt.datetime(2026, 11, 12, 10, tzinfo=UTC)) == ([], "market closed")
    monkeypatch.setattr(bot, "_yahoo", lambda sym, now: (28400.0, 900) if "NDX" in sym else (27.0, 10))
    quotes, note = bot.model({}, NOON)
    assert quotes == [] and "min old" in note


def test_registry_and_desk_wiring():
    import desk_profit
    import new_towers
    import pimp_desk

    assert desk_profit.BOT_VENUE["nasdaq"] == "kalshi_inx"
    assert desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_inx"] == 0.02
    spec = next(b for b in pimp_desk.BOTS if b["id"] == "nasdaq")
    assert spec["shadow_only"]
    assert pimp_desk._account_body("nasdaq")["cash"] == 500.0
    assert "nasdaq" in new_towers.BY_ID
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("nasdaq")["ok"]


def test_reads_every_page_and_names_failures(monkeypatch):
    import urllib.error
    import kalshi_shadow_tower as engine
    pages = {"": {"markets": [{"ticker": "A"}], "cursor": "c1"}, "c1": {"markets": [{"ticker": "B"}], "cursor": ""}}
    monkeypatch.setattr(engine, "public_json", lambda url, **k: pages[url.split("cursor=")[1] if "cursor=" in url else ""])
    assert [m["ticker"] for m in engine.kalshi_open_markets("X", limit=1000, pages=5)] == ["A", "B"]
    assert [m["ticker"] for m in engine.kalshi_open_markets("X")] == ["A"]
    bot = _bot()
    open_at = dt.datetime(2026, 11, 12, 15, tzinfo=UTC)   # 10:00 ET Thursday

    def boom(sym, now):
        raise urllib.error.HTTPError("u", 429, "slow down", {}, None)
    monkeypatch.setattr(bot, "_yahoo", boom)
    assert bot.model({}, open_at) == ([], "Yahoo NDX quote HTTP 429; waiting")


def test_only_the_4pm_events_are_priced(monkeypatch):
    bot = _bot()
    import kalshi_shadow_tower as engine
    rows = [{"ticker": "A", "event_ticker": "KXNASDAQ100U-26NOV12H1000"},
            {"ticker": "B", "event_ticker": "KXNASDAQ100U-26NOV12H1600"}]
    monkeypatch.setattr(engine, "kalshi_open_markets", lambda series, **k: rows)
    monkeypatch.setattr(bot, "_yahoo", lambda sym, now: (28000.0, 5) if "NDX" in sym else (25.0, 5))
    seen = {}
    monkeypatch.setattr(bot, "quotes_for", lambda markets, *a: seen.setdefault("m", markets) and [])
    bot.model({}, dt.datetime(2026, 11, 12, 15, tzinfo=UTC))
    assert {m["ticker"] for m in seen["m"]} == {"B"}
