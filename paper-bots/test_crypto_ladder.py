"""Crypto ladder tower. Offline."""
import datetime as dt
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "crypto-ladder-paper"))

import ladder_model as lm  # noqa: E402

NOW = dt.datetime(2026, 11, 12, 10, tzinfo=dt.timezone.utc)
CLOSE = dt.datetime(2026, 11, 12, 22, tzinfo=dt.timezone.utc)


def _bot():
    spec = importlib.util.spec_from_file_location("ladder_bot", os.path.join(HERE, "crypto-ladder-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _summary(day="13NOV26", under=73300.0, ivs=None):
    ivs = ivs or {70000: 45.0, 72000: 38.0, 73000: 35.0, 74000: 34.0, 76000: 36.0}
    rows = []
    for k, iv in ivs.items():
        cp = "C" if k >= under else "P"
        rows.append({"instrument_name": f"BTC-{day}-{k}-{cp}", "mark_iv": iv, "underlying_price": under})
    rows.append({"instrument_name": f"BTC-{day}-70000-C", "mark_iv": 99.0, "underlying_price": under})  # ITM call: ignored
    rows.append({"instrument_name": "BTC-PERPETUAL", "mark_iv": 1, "underlying_price": under})
    return rows


def test_parse_instrument_and_smiles():
    coin, exp, k, cp = lm.parse_instrument("BTC-13NOV26-84000-P")
    assert (coin, exp, k, cp) == ("BTC", dt.datetime(2026, 11, 13, 8, tzinfo=dt.timezone.utc), 84000.0, "P")
    assert lm.parse_instrument("BTC-PERPETUAL") is None
    sm = lm.smiles(_summary())
    pts = dict(sm[dt.datetime(2026, 11, 13, 8, tzinfo=dt.timezone.utc)]["points"])
    assert pts[70000.0] == 0.45  # the OTM put, not the ITM call
    assert lm.iv_at(sorted(pts.items()), 73500) == 0.345


def test_vol_blends_expiries_by_total_variance():
    sm = lm.smiles(_summary("12NOV26", ivs={72000: 30, 73000: 30, 74000: 30}) + _summary("13NOV26", ivs={72000: 50, 73000: 50, 74000: 50}))
    close = dt.datetime(2026, 11, 12, 20, tzinfo=dt.timezone.utc)
    now = dt.datetime(2026, 11, 12, 6, tzinfo=dt.timezone.utc)
    v = lm.vol_for(sm, close, 73000, now)
    assert 0.30 < v < 0.50
    t0, t1, tc = 2.0, 26.0, 14.0
    w = (tc - t0) / (t1 - t0)
    assert math.isclose(v, math.sqrt(((1 - w) * 0.09 * t0 + w * 0.25 * t1) / tc), rel_tol=1e-9)
    assert lm.vol_for({}, close, 73000, now) is None


def test_p_above_sane():
    years = 12 * 3600 / lm.YEAR_SEC
    assert math.isclose(lm.p_above(73300, 73300, 0.35, years), 0.5, abs_tol=0.01)
    assert lm.p_above(73300, 74000, 0.34, years) < 0.3
    assert lm.p_above(73300, 90000, 0.34, years) == 0.01
    assert lm.p_above(73300, 60000, 0.34, years) == 0.99


def _m(ticker, kind, strike, close=CLOSE, **book):
    m = {"ticker": ticker, "event_ticker": "KXBTCD-26NOV1217", "strike_type": kind,
         "close_time": close.isoformat().replace("+00:00", "Z"),
         "yes_ask_dollars": "0.30", "yes_bid_dollars": "0.25", "no_ask_dollars": "0.75", "no_bid_dollars": "0.70"}
    m["floor_strike" if kind == "greater" else "cap_strike"] = strike
    m.update(book)
    return m


def test_coin_quotes_windows_and_spot_gap():
    bot = _bot()
    sm = lm.smiles(_summary())
    markets = [_m("A", "greater", 74000), _m("B", "less", 72000),
               _m("C", "greater", 74000, close=NOW + dt.timedelta(minutes=5)),
               _m("D", "greater", 74000, close=NOW + dt.timedelta(hours=40)),
               _m("E", "between", 74000)]
    q = bot.coin_quotes("BTC", markets, 73300.0, sm, NOW)
    assert {x["ticker"] for x in q} == {"A", "B"}
    a_yes = next(x for x in q if x["ticker"] == "A" and x["side"] == "yes")
    b_yes = next(x for x in q if x["ticker"] == "B" and x["side"] == "yes")
    assert a_yes["fair"] < 0.35 and b_yes["fair"] < 0.25
    assert "Deribit vol" in a_yes["why"]
    assert bot.coin_quotes("BTC", markets, 75000.0, sm, NOW) == []  # 2.3% spot gap -> skip


def test_registry_and_desk_wiring():
    import desk_profit
    import new_towers
    import pimp_desk

    assert desk_profit.BOT_VENUE["crypto-ladder"] == "kalshi_btc15m"
    assert desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"] == 0.05
    spec = next(b for b in pimp_desk.BOTS if b["id"] == "crypto-ladder")
    assert spec["shadow_only"]
    assert any(s["id"] == "crypto-ladder" and s["every_sec"] == 300 for s in pimp_desk.AUTO)
    assert "crypto-ladder" in new_towers.BY_ID
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("crypto-ladder")["ok"]


def test_bare_desk_account_gets_starter_cash(tmp_path, capsys):
    import json
    import kalshi_shadow_tower as engine
    import pimp_desk

    body = pimp_desk._account_body("crypto-ladder")
    assert body["cash"] == 500.0 and body["shadow_only"] and not body["live_orders"]
    (tmp_path / "paper_account.json").write_text(json.dumps({"paper_only": True}))
    spec = {"id": "t", "name": "T", "floor": 0.05, "max_open": 2}
    quotes = [{"ticker": "A-1", "event": "A", "side": "yes", "fair": 0.70, "ask": 0.50, "bid": 0.48, "label": "A1"}]
    engine.run_tower(spec, str(tmp_path), None, now=NOW, fetch=lambda t: {}, quotes=quotes)
    assert "SIGNAL: BUY A1 YES" in capsys.readouterr().out
    state = json.loads((tmp_path / "paper_account.json").read_text())
    assert len(state["open"]) == 1 and state["cash"] < 500
