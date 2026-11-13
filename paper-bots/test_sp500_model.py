"""S&P model tower. Offline."""
import datetime as dt
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
UTC = dt.timezone.utc
NOON = dt.datetime(2026, 11, 12, 17, tzinfo=UTC)   # 12:00 ET Thursday


def _bot():
    spec = importlib.util.spec_from_file_location("sp500_bot", os.path.join(HERE, "sp500-model-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _m(kind, lo=None, hi=None, ya=0.5, yb=0.48, ev="KXINXU-26NOV12H1600"):
    return {"ticker": f"{ev}-T{lo or hi}", "event_ticker": ev, "strike_type": kind, "floor_strike": lo,
            "cap_strike": hi, "close_time": "2026-11-12T21:00:00Z", "yes_ask_dollars": ya, "yes_bid_dollars": yb,
            "no_ask_dollars": round(1 - yb, 2), "no_bid_dollars": round(1 - ya, 2)}


def test_spec_and_vault_band():
    bot = _bot()
    assert bot.SPEC["floor"] == 0.02 and bot.SPEC["max_open"] == 2
    assert bot.in_vault_band(0.85) and bot.in_vault_band(0.80) and not bot.in_vault_band(0.91)


def test_quotes_price_strikes_and_tag_band():
    bot = _bot()
    quotes = bot.quotes_for([_m("greater", lo=7400, ya=0.86, yb=0.84)], 7560.0, 0.18, NOON)
    yes = next(q for q in quotes if q["side"] == "yes")
    no = next(q for q in quotes if q["side"] == "no")
    assert 0.9 < yes["fair"] < 1.0 and abs(yes["fair"] + no["fair"] - 1) < 1e-9
    assert "vault band" in yes["why"] and "vault band" not in no["why"]
    assert yes["label"].startswith("SPX Nov 12 above 7,400")


def test_cnbc_parse_and_closed_market():
    bot = _bot()
    body = {"FormattedQuoteResult": {"FormattedQuote": [
        {"symbol": ".SPX", "last": "7,561.67", "last_time": "2026-11-12T11:58:00.000-0500"},
        {"symbol": ".VIX", "last": "19.30", "last_time": "2026-11-12T11:58:00.000-0500"}]}}
    got = bot._cnbc(body, NOON)
    assert got["SPX"][0] == 7561.67 and got["SPX"][1] == 120 and got["VIX"][0] == 19.3
    assert bot.model({}, dt.datetime(2026, 11, 14, 17, tzinfo=UTC)) == ([], "market closed")


def test_model_offline_filters_to_4pm_events(monkeypatch):
    bot = _bot()
    body = {"FormattedQuoteResult": {"FormattedQuote": [
        {"symbol": ".SPX", "last": "7,560", "last_time": "2026-11-12T11:59:00.000-0500"},
        {"symbol": ".VIX", "last": "18", "last_time": "2026-11-12T11:59:00.000-0500"}]}}
    monkeypatch.setattr(bot.engine, "public_json", lambda url, **k: body)
    rows = {"KXINXU": [_m("greater", lo=7500), _m("greater", lo=7500, ev="KXINXU-26NOV12H1200")],
            "KXINX": [_m("between", lo=7550, hi=7574.99, ev="KXINX-26NOV12H1600")]}
    monkeypatch.setattr(bot.engine, "kalshi_open_markets", lambda s, **k: rows[s])
    quotes, note = bot.model({}, NOON)
    assert note == "" and len(quotes) == 4
    assert all(q["event"].endswith("H1600") for q in quotes)
