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


def _busy_tape(ticker, now):
    return [{"yes_price_dollars": "0.30", "count_fp": "500"}, {"yes_price_dollars": "0.70", "count_fp": "500"}]


def _quote(ticker="KXSOL15M-W", side="yes", fair=0.70, ask=0.60, bid=0.55):
    return {"ticker": ticker, "event": ticker + "-E", "side": side, "fair": fair, "ask": ask, "bid": bid}


def _acct(tower):
    import json
    return json.load(open(os.path.join(tower, "paper_account.json")))


def test_buy_needs_real_kalshi_trading_at_our_price(tmp_path):
    bot = _bot()
    import kalshi_shadow_tower as engine
    tower = str(tmp_path / "t")
    quiet = lambda t, n: [{"yes_price_dollars": "0.65", "count_fp": "900"}]  # noqa: E731 - all above our 0.60
    engine.run_tower(bot.SPEC, tower, None, now=NOW, fetch=lambda t: {}, quotes=[_quote()], tape=quiet)
    assert _acct(tower)["open"] == []
    broken = lambda t, n: (_ for _ in ()).throw(OSError("down"))  # noqa: E731
    engine.run_tower(bot.SPEC, tower, None, now=NOW, fetch=lambda t: {}, quotes=[_quote()], tape=broken)
    assert _acct(tower)["open"] == []
    engine.run_tower(bot.SPEC, tower, None, now=NOW, fetch=lambda t: {}, quotes=[_quote()], tape=_busy_tape)
    pos = _acct(tower)["open"][0]
    assert pos["tape_volume"] == 500 and pos["contracts"] <= 500
    # "no" side reads the same tape flipped: yes 0.70 is no 0.30.
    assert engine.tape_volume(_busy_tape("", NOW), "no", 0.30) == 500


def test_one_buy_per_window_no_switching_sides(tmp_path):
    bot = _bot()
    import kalshi_shadow_tower as engine
    tower = str(tmp_path / "t")
    run = lambda q: engine.run_tower(bot.SPEC, tower, None, now=NOW, fetch=lambda t: {}, quotes=q,  # noqa: E731
                                     tape=_busy_tape)
    run([_quote()])
    assert len(_acct(tower)["open"]) == 1
    run([_quote(fair=0.40, bid=0.80)])            # model flip: sold at the bid
    acct = _acct(tower)
    assert acct["open"] == [] and acct["closed"][0]["exit"] == "model-flip"
    run([_quote(side="no", fair=0.80, ask=0.25)])  # other side, same window: blocked
    run([_quote(fair=0.90, ask=0.60)])             # same side again: blocked
    assert _acct(tower)["open"] == []
    run([_quote(ticker="KXSOL15M-NEXT")])          # next window is fine
    assert len(_acct(tower)["open"]) == 1


def test_fee_charged_once_per_order_like_kalshi():
    import kalshi_shadow_tower as engine
    # 40 contracts at 0.60: per-contract rounding 40 x 0.02 = 0.80; Kalshi 0.07*40*.6*.4 = 0.672 -> 0.68.
    assert engine.order_fee(40, 0.60) == 0.68
    c, f, cost = engine.size_order(25.0, 0.60, True)
    assert cost <= 25.0 and f == engine.order_fee(c, 0.60) and abs(cost - (c * 0.60 + f)) < 1e-9
    old = engine.size_order(25.0, 0.60, False)
    assert c >= old[0] and f < old[1]
    bot = _bot()
    assert bot.SPEC["fee_per_order"] and bot.SPEC["one_per_window"] and bot.SPEC["tape_check"]


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
        engine.run_tower(bot.SPEC, tower, None, now=NOW, fetch=lambda t: {}, quotes=quotes, tape=_busy_tape)
    import json
    acct = json.load(open(os.path.join(tower, "paper_account.json")))
    assert len(acct["open"]) == 2 and all(p["group"].startswith("coins up") for p in acct["open"])


def test_swing_multiplier_calibrated():
    bot = _bot()
    assert bot.SIGMA_MULT_DEFAULT == 1.0 and bot.SIGMA_MULT["KXUSDJPY15M"] == 1.3


def test_open_offsets_survive_redeploys():
    import pimp_desk
    assert "more-15m-paper/index_basis.json" in pimp_desk.SETTLEMENT_FILES
    assert "commodity-15m-paper/index_basis.json" in pimp_desk.SETTLEMENT_FILES
