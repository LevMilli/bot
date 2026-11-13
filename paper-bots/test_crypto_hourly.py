"""Crypto hourly tower (SOL/XRP/DOGE/BNB). Offline."""
import datetime as dt
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "crypto-hourly-paper"))

import hourly_model as hm  # noqa: E402

NOW = dt.datetime(2026, 11, 13, 15, 20, tzinfo=dt.timezone.utc)


def _bot():
    spec = importlib.util.spec_from_file_location("crypto_hourly_bot",
                                                  os.path.join(HERE, "crypto-hourly-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _candles(n, step, bar=300):
    # Coinbase order: newest first, [time, low, high, open, close, volume]
    rows, price = [], 100.0
    for i in range(n):
        price *= math.exp(step if i % 2 else -step)
        rows.append([1_700_000_000 + i * bar, price, price, price, price, 1])
    return list(reversed(rows))


def test_realized_vol_floor_cap_and_short_history():
    assert hm.realized_vol(_candles(10, 0.001)) is None
    assert hm.realized_vol(_candles(100, 0.0)) == hm.VOL_FLOOR
    assert hm.realized_vol(_candles(100, 0.2)) == hm.VOL_CAP
    mid = hm.realized_vol(_candles(100, 0.004))
    assert hm.VOL_FLOOR < mid < hm.VOL_CAP


def test_vol_blend_and_probabilities():
    assert hm.vol_for(30, 0.5, 1.0) == 0.5
    assert hm.vol_for(600, 0.5, 1.0) == 1.0
    assert abs(hm.vol_for(150, 0.5, 1.0) - 0.75) < 1e-9
    assert hm.vol_for(30, None, 0.8) == 0.8 and hm.vol_for(30, None, None) is None
    years = 60 * 60 / hm.YEAR_SEC
    up = hm.p_yes({"strike_type": "greater", "floor_strike": 100.0}, 100.0, 0.8, years)
    assert 0.45 < up < 0.51
    assert hm.p_yes({"strike_type": "greater", "floor_strike": 90.0}, 100.0, 0.8, years) == 0.99
    below = hm.p_yes({"strike_type": "less", "cap_strike": 100.0}, 100.0, 0.8, years)
    assert abs(up + below - 1.0) < 1e-9
    band = hm.p_yes({"strike_type": "between", "floor_strike": 99.0, "cap_strike": 101.0}, 100.0, 0.8, years)
    assert 0.0 < band < 1.0
    assert hm.p_yes({"strike_type": "odd"}, 100.0, 0.8, years) is None


def test_coin_quotes_window_and_groups():
    bot = _bot()

    def at(delta):
        return (NOW + delta).isoformat().replace("+00:00", "Z")

    base = {"event_ticker": "KXSOLD-26NOV1311", "yes_ask_dollars": "0.40", "no_ask_dollars": "0.62",
            "yes_bid_dollars": "0.38", "no_bid_dollars": "0.60", "strike_type": "greater", "floor_strike": 150.0}
    markets = [dict(base, ticker="A", close_time=at(dt.timedelta(minutes=40))),
               dict(base, ticker="B", close_time=at(dt.timedelta(hours=40))),    # past 30 hours
               dict(base, ticker="C", close_time=at(dt.timedelta(minutes=5)))]   # under 10 minutes
    rows = bot.coin_quotes("SOL", markets, 150.0, (0.6, 0.7), NOW)
    assert {r["ticker"] for r in rows} == {"A"}
    yes = next(r for r in rows if r["side"] == "yes")
    no = next(r for r in rows if r["side"] == "no")
    assert abs(yes["fair"] + no["fair"] - 1.0) < 1e-9
    assert yes["group"].endswith("up") and no["group"].endswith("down")
    assert "SOL" in yes["label"]


def test_dormant_series_is_noted(monkeypatch):
    bot = _bot()
    monkeypatch.setattr(bot.engine, "public_json",
                        lambda url, **kw: {"price": "150"} if "ticker" in url else _candles(100, 0.003))
    monkeypatch.setattr(bot.engine, "kalshi_open_markets", lambda series, pages=1: [])
    quotes, note = bot.model({}, NOW)
    assert quotes == []
    assert "no open markets" in note and "KXSOL" in note and "KXBNBD" in note
    assert bot.SPEC["floor"] == 0.05 and set(bot.COINS) == {"SOL", "XRP", "DOGE", "BNB"}
