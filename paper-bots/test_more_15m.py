"""More 15m tower. Offline."""
import datetime as dt
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 12, 20, 36, tzinfo=UTC)


def _bot():
    spec = importlib.util.spec_from_file_location("more15_bot", os.path.join(HERE, "more-15m-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _market(series, strike, close, yes_ask=0.5, no_ask=0.5):
    return {"ticker": f"{series}-T", "event_ticker": f"{series}-E", "floor_strike": strike,
            "close_time": close.isoformat().replace("+00:00", "Z"),
            "yes_ask_dollars": str(yes_ask), "no_ask_dollars": str(no_ask),
            "yes_bid_dollars": "0.4", "no_bid_dollars": "0.4"}


def test_fair_tracks_distance_from_open(tmp_path, monkeypatch):
    bot = _bot()
    monkeypatch.setattr(bot, "HERE", str(tmp_path))
    close = NOW + dt.timedelta(minutes=9)
    up = bot.window_quotes("KXSOL15M", [_market("KXSOL15M", 100.0, close)], 100.3, 0.001, NOW)
    flat = bot.window_quotes("KXSOL15M", [_market("KXSOL15M", 100.0, close)], 100.0, 0.001, NOW)
    yes_up = next(q for q in up if q["side"] == "yes")
    assert 0.8 < yes_up["fair"] < 0.95 and not yes_up.get("log_only")
    assert abs(next(q for q in flat if q["side"] == "yes")["fair"] - 0.5) < 1e-9
    assert abs(sum(q["fair"] for q in up) - 1.0) < 1e-9


def test_buy_window_and_fx_offset_learning(tmp_path, monkeypatch):
    bot = _bot()
    monkeypatch.setattr(bot, "HERE", str(tmp_path))
    late = bot.window_quotes("KXSOL15M", [_market("KXSOL15M", 100.0, NOW + dt.timedelta(minutes=2))], 100, 0.001, NOW)
    assert all(q.get("log_only") for q in late)
    # FX: logs only until three window opens have been seen.
    for i in range(3):
        start = NOW + dt.timedelta(minutes=15 * i)
        mk = _market("KXEURUSD15M", 1.1050, start + dt.timedelta(minutes=14))
        mk["ticker"] = f"KXEURUSD15M-{i}"
        rows = bot.window_quotes("KXEURUSD15M", [mk], 1.1055, 0.0001, start)
        assert all(q.get("log_only") for q in rows) == (i < 2)
    level, ready = bot.anchor("KXEURUSD15M", 1.1055, mk, start + dt.timedelta(minutes=14), start)
    assert ready and abs(level - 1.1050) < 1e-6   # offset learned onto Kalshi's print


def test_engine_buys_clear_edge_only(tmp_path, monkeypatch):
    bot = _bot()
    import kalshi_shadow_tower as engine
    cfg = engine.locked_cfg(bot.SPEC, {"venue_min_edge": 0.01})
    assert cfg["venue_min_edge"] == 0.05 and cfg["max_open"] == 4
    row = engine.decide({"ticker": "T", "side": "yes", "fair": 0.70, "ask": 0.60}, cfg)
    assert row["action"] == "buy"
    row = engine.decide({"ticker": "T", "side": "yes", "fair": 0.63, "ask": 0.60}, cfg)
    assert row["action"] == "skip"


def test_registry_and_desk_wiring():
    import desk_profit
    import new_towers
    import pimp_desk

    assert desk_profit.BOT_VENUE["more-15m"] == "kalshi_btc15m"
    spec = next(b for b in pimp_desk.BOTS if b["id"] == "more-15m")
    assert spec["shadow_only"]
    assert any(s["id"] == "more-15m" and s["every_sec"] == 60 for s in pimp_desk.AUTO)
    assert pimp_desk._account_body("more-15m")["cash"] == 500.0
    assert "more-15m" in new_towers.BY_ID
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("more-15m")["ok"]


def test_same_direction_cap(tmp_path, monkeypatch):
    bot = _bot()
    import kalshi_shadow_tower as engine
    monkeypatch.setattr(bot, "HERE", str(tmp_path))
    close = NOW + dt.timedelta(minutes=9)
    quotes = []
    for s in ("KXSOL15M", "KXXRP15M", "KXDOGE15M"):
        m = _market(s, 100.0, close, yes_ask=0.75, no_ask=0.27)
        m["ticker"], m["event_ticker"] = f"{s}-W", f"{s}-E"
        quotes += bot.window_quotes(s, [m], 100.3, 0.001, NOW)   # fair up ~0.87 vs ask 0.40
    assert {q["group"] for q in quotes if q["side"] == "yes"} == {f"coins up {close.strftime('%H:%M')}"}
    tower = str(tmp_path / "t")
    for _ in range(3):
        engine.run_tower(bot.SPEC, tower, None, now=NOW, fetch=lambda t: {}, quotes=quotes)
    import json
    acct = json.load(open(os.path.join(tower, "paper_account.json")))
    assert len(acct["open"]) == 2 and all(p["group"].startswith("coins up") for p in acct["open"])


def test_swing_multiplier_calibrated():
    bot = _bot()
    assert bot.SIGMA_MULT_DEFAULT == 1.0 and bot.SIGMA_MULT["KXUSDJPY15M"] == 1.3
