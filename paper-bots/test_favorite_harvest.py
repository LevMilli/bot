"""Favorite harvest: horizon windows, pricing from the lab table, waits and wiring."""
from __future__ import annotations

import datetime as dt
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOWER = os.path.join(HERE, "favorite-harvest-paper")
for p in (HERE, TOWER):
    if p not in sys.path:
        sys.path.insert(0, p)

import calibration_lab as lab  # noqa: E402
import harvest_model as hm  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402

_spec = importlib.util.spec_from_file_location("favorite_harvest_bot", os.path.join(TOWER, "bot.py"))
bot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bot)

NOW = dt.datetime(2026, 11, 12, 18, 0, tzinfo=dt.timezone.utc)


def _cell(n, wins, price=0.91):
    lo, hi = lab.wilson(wins, n)
    return {"n": n, "wins": wins, "win_rate": wins / n, "avg_price": price, "avg_fee": 0.01,
            "wilson_lo": round(lo, 4), "wilson_hi": round(hi, 4), "edge_lo": round(lo - price - 0.01, 4)}


def _market(hours, yes_ask=0.90, yes_bid=0.89, ticker="KXHIGHNY-26NOV12-B60"):
    close = (NOW + dt.timedelta(hours=hours)).isoformat()
    return {"ticker": ticker, "event_ticker": ticker.rsplit("-", 1)[0], "close_time": close,
            "title": "NYC high 60-61", "yes_ask_dollars": str(yes_ask), "yes_bid_dollars": str(yes_bid),
            "no_ask_dollars": str(round(1 - yes_bid, 2)), "no_bid_dollars": str(round(1 - yes_ask, 2))}


def test_horizon_windows():
    assert hm.horizon_for(1.0) == 1 and hm.horizon_for(0.4) is None
    assert hm.horizon_for(3.5) == 3 and hm.horizon_for(4.5) is None
    assert hm.horizon_for(6.9) == 6 and hm.horizon_for(8) is None


def test_buys_only_when_cautious_fair_clears_floor():
    cfg = engine.locked_cfg(bot.SPEC, {})
    assert cfg["min_ask"] == 0.88 and cfg["max_ask"] == 0.94
    strong = {"weather": {"1": {"0.90-0.95": _cell(2000, 1990)}}}
    quotes = bot.quotes_for({"weather": [_market(1.0)]}, strong, NOW)
    yes = next(q for q in quotes if q["side"] == "yes")
    assert not any(q["side"] == "no" for q in quotes)  # 11c NO is not a favorite
    row = engine.decide(yes, cfg)
    assert row["action"] == "buy", row
    weak = {"weather": {"1": {"0.90-0.95": _cell(200, 184)}}}
    row = engine.decide(next(q for q in bot.quotes_for({"weather": [_market(1.0)]}, weak, NOW)), cfg)
    assert row["action"] == "skip" and "floor" in row["reason"]


def test_waits_on_small_or_missing_cells():
    cfg = engine.locked_cfg(bot.SPEC, {})
    small = {"weather": {"1": {"0.90-0.95": _cell(20, 20)}}}
    row = engine.decide(bot.quotes_for({"weather": [_market(1.0)]}, small, NOW)[0], cfg)
    assert row["action"] == "skip" and "waiting on calibration" in row["reason"]
    row = engine.decide(bot.quotes_for({"weather": [_market(1.0)]}, {}, NOW)[0], cfg)
    assert row["action"] == "skip" and "no cell" in row["reason"]
    assert bot.quotes_for({"weather": [_market(10.0)]}, small, NOW) == []


def test_model_waits_for_fresh_table():
    quotes, note = bot.model({}, NOW, read=lambda: {}, fetch=lambda s: [])
    assert quotes == [] and "has not run" in note
    old = {"updated": (NOW - dt.timedelta(hours=60)).isoformat(), "table": {}}
    quotes, note = bot.model({}, NOW, read=lambda: old, fetch=lambda s: [])
    assert quotes == [] and "old" in note
    fresh = {"updated": NOW.isoformat(), "table": {"gas": {"3": {"0.90-0.95": _cell(500, 499)}}}}
    seen = []

    def fetch(series):
        seen.append(series)
        return [_market(3.0, ticker="KXAAAGASW-26NOV16-3.10")] if series == "KXAAAGASW" else []

    quotes, note = bot.model({}, NOW, read=lambda: fresh, fetch=fetch)
    assert quotes and quotes[0]["fair"] > 0.97 and note == ""
    assert "KXBTCD" in seen and "KXINXU" in seen


def test_registry_and_desk_wiring():
    import desk_profit
    import pimp_desk

    assert desk_profit.BOT_VENUE["favorite-harvest"] == "kalshi_econ"
    assert desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_econ"] == 0.05
    spec = next(b for b in pimp_desk.BOTS if b["id"] == "favorite-harvest")
    assert spec["shadow_only"] and spec["kind"] == "shadow"
    assert pimp_desk._account_body("favorite-harvest")["cash"] == 500.0
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    res = new_tower.check_tower("favorite-harvest")
    assert res["ok"], res


def test_label_is_cut_at_a_word_and_says_the_side_once():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "fav_bot_label", os.path.join(os.path.dirname(os.path.abspath(__file__)), "favorite-harvest-paper", "bot.py"))
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    long = "Will the S&P 500 be between 7550 and 7574.9999 on Nov 12, 2026?"
    short = bot._short(long)
    assert short == "Will the S&P 500 be between 7550 and 7574.9999 on Nov 12..."
    assert bot._short("High in NYC on Nov 12?") == "High in NYC on Nov 12"
    assert not short.endswith(("NO", "YES"))
