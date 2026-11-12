"""Weather high tower + shared shadow engine. Offline."""
import datetime as dt
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "weather-high-paper"))

import kalshi_shadow_tower as engine  # noqa: E402
import weather_model as wm  # noqa: E402

SPEC = {"id": "t", "name": "Test tower", "floor": 0.05, "max_open": 2}


# ------------------------------------------------------------------ engine
def test_fee_matches_kalshi_table():
    assert engine.fee(0.50) == 0.02
    assert engine.fee(0.10) == 0.01
    assert engine.fee(0.0) == 0.0


def test_floor_cannot_be_lowered_in_config():
    cfg = engine.locked_cfg(SPEC, {"venue_min_edge": 0.01, "live_orders": True})
    assert cfg["venue_min_edge"] == 0.05 and cfg["live_orders"] is False and cfg["paper_only"]


def test_decide_needs_edge_after_fee():
    cfg = engine.locked_cfg(SPEC)
    assert engine.decide({"fair": 0.56, "ask": 0.50}, cfg)["action"] == "skip"   # 0.06 - 0.02 fee
    assert engine.decide({"fair": 0.58, "ask": 0.50}, cfg)["action"] == "buy"    # 0.08 - 0.02
    assert engine.decide({"fair": 0.99, "ask": 0.97}, cfg)["reason"].startswith("ask")
    row = engine.decide({"fair": 0.9, "ask": 0.5, "log_only": True, "log_reason": "morning"}, cfg)
    assert row["action"] == "skip" and row["reason"] == "morning" and row["edge"] == 0.38


def test_trust_cap_logs_but_does_not_buy():
    cfg = engine.locked_cfg(dict(SPEC, max_edge=0.25))
    row = engine.decide({"fair": 0.9, "ask": 0.5}, cfg)
    assert row["action"] == "skip" and "trust cap" in row["reason"]


def _quotes():
    return [
        {"ticker": "A-1", "event": "A", "side": "yes", "fair": 0.70, "ask": 0.50, "bid": 0.48, "label": "A1"},
        {"ticker": "A-2", "event": "A", "side": "yes", "fair": 0.65, "ask": 0.50, "bid": 0.48, "label": "A2"},
        {"ticker": "B-1", "event": "B", "side": "no", "fair": 0.40, "ask": 0.30, "bid": 0.28, "label": "B1"},
    ]


def _state(tmp_path):
    return json.loads((tmp_path / "paper_account.json").read_text())


def test_run_buys_best_one_per_check_one_per_event(tmp_path, capsys):
    now = dt.datetime(2026, 11, 12, 21, tzinfo=dt.timezone.utc)
    fetch = lambda t: {}  # noqa: E731 - nothing settled
    engine.run_tower(SPEC, str(tmp_path), None, now=now, fetch=fetch, quotes=_quotes())
    assert "SIGNAL: BUY A1 YES" in capsys.readouterr().out
    pos = _state(tmp_path)["open"][0]
    assert pos["ticker"] == "A-1"
    assert pos["contracts"] == 48 and pos["cost"] == 24.96  # $25 / (0.50 + 0.02 fee)
    engine.run_tower(SPEC, str(tmp_path), None, now=now, fetch=fetch, quotes=_quotes())
    assert [p["ticker"] for p in _state(tmp_path)["open"]] == ["A-1", "B-1"]  # A-2: same event
    engine.run_tower(SPEC, str(tmp_path), None, now=now, fetch=fetch, quotes=_quotes())
    assert len(_state(tmp_path)["open"]) == 2
    rows = (tmp_path / "research.jsonl").read_text().splitlines()
    assert len(rows) == 3 and json.loads(rows[0])["decisions"][0]["ticker"] == "A-1"


def test_desk_gate_blocks_buys(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("DESK_BLOCK_ENTRIES", "1")
    engine.run_tower(SPEC, str(tmp_path), None, fetch=lambda t: {}, quotes=_quotes())
    assert "desk entry gate" in capsys.readouterr().out
    assert _state(tmp_path)["open"] == []


def test_settle_and_model_flip(tmp_path, capsys):
    now = dt.datetime(2026, 11, 12, 21, tzinfo=dt.timezone.utc)
    engine.run_tower(SPEC, str(tmp_path), None, now=now, fetch=lambda t: {}, quotes=_quotes()[:1])
    engine.run_tower(SPEC, str(tmp_path), None, now=now, fetch=lambda t: {}, quotes=_quotes()[2:])
    # B-1 model flips: bid 0.80 - fee 0.02 beats fair 0.40. A-1 settles YES.
    flip = [{"ticker": "B-1", "event": "B", "side": "no", "fair": 0.40, "ask": 0.82, "bid": 0.80, "label": "B1"}]
    fetch = lambda t: {"result": "yes"} if t == "A-1" else {}  # noqa: E731
    engine.run_tower(SPEC, str(tmp_path), None, now=now, fetch=fetch, quotes=flip)
    out = capsys.readouterr().out
    assert "SETTLE: A1 YES yes pnl +23.04" in out
    assert "EXIT: model-flip B1 NO at 0.80" in out
    state = _state(tmp_path)
    assert state["open"] == [] and {r["exit"] for r in state["closed"]} == {"settled", "model-flip"}


def test_failed_model_read_is_a_skip(tmp_path, capsys):
    def broken(cfg, now):
        raise TimeoutError("slow")
    assert engine.run_tower(SPEC, str(tmp_path), broken, fetch=lambda t: {}) == 0
    out = capsys.readouterr().out
    assert "read failed (TimeoutError)" in out and "no trade" in out


# ------------------------------------------------------------------ weather model
def test_event_day_and_brackets():
    assert wm.event_day("KXHIGHNY-26NOV12") == dt.date(2026, 11, 12)
    assert wm.event_day("junk") is None
    assert wm.bracket({"strike_type": "between", "floor_strike": 59, "cap_strike": 60}) == (59, 60)
    assert wm.bracket({"strike_type": "less", "cap_strike": 59}) == (None, 58)
    assert wm.bracket({"strike_type": "greater", "floor_strike": 66}) == (67, None)
    assert wm.bracket({"strike_type": "custom"}) is None


def test_climate_day_is_local_standard_time():
    start, end = wm.climate_window(dt.date(2026, 7, 4), "America/New_York")
    assert start == dt.datetime(2026, 7, 4, 5, tzinfo=dt.timezone.utc)  # 1 a.m. EDT
    start, end = wm.climate_window(dt.date(2026, 11, 12), "America/Chicago")
    assert start == dt.datetime(2026, 11, 12, 6, tzinfo=dt.timezone.utc)
    assert end - start == dt.timedelta(days=1)


def test_observed_max_and_member_rest():
    start = dt.datetime(2026, 11, 12, 5, tzinfo=dt.timezone.utc)
    end = start + dt.timedelta(days=1)
    obs = [
        {"properties": {"timestamp": "2026-11-12T18:51:00+00:00", "temperature": {"value": 15.0}}},
        {"properties": {"timestamp": "2026-11-12T19:51:00+00:00", "temperature": {"value": None}}},
        {"properties": {"timestamp": "2026-11-11T19:51:00+00:00", "temperature": {"value": 30.0}}},
    ]
    assert wm.observed_max_f(obs, start, end) == 59.0
    hourly = {"time": ["2026-11-12T18:00", "2026-11-12T20:00", "2026-11-13T06:00"],
              "temperature_2m": [55.0, 61.0, 70.0], "temperature_2m_member01": [54.0, 58.0, None]}
    now = dt.datetime(2026, 11, 12, 19, tzinfo=dt.timezone.utc)
    assert sorted(wm.member_rest_max(hourly, start, end, now)) == [58.0, 61.0]


def test_late_day_lock_is_confident_and_never_certain():
    samples = wm.draws(62.0, [], 0.8, "x")  # day over: only the recorded high
    assert wm.prob_in(samples, 61, 62) > 0.5
    assert wm.prob_in(samples, None, 58) == 0.01  # floor, never zero
    assert wm.prob_in([], 1, 2) is None


def test_nws_anchor():
    periods = [{"isDaytime": False, "startTime": "2026-11-12T06:00:00-05:00", "temperature": 50},
               {"isDaytime": True, "startTime": "2026-11-12T06:00:00-05:00", "temperature": 59,
                "temperatureUnit": "F"}]
    assert wm.nws_day_high(periods, dt.date(2026, 11, 12)) == 59.0
    assert wm.nws_day_high(periods, dt.date(2026, 11, 13)) is None
    assert wm.anchor_shift([57.0, 58.0, 59.0], 59.0) == 1.0
    assert wm.anchor_shift([40.0], 59.0) == 4.0  # capped
    assert wm.anchor_shift([], 59.0) == 0.0


def _weather_bot():
    spec = importlib.util.spec_from_file_location(
        "weather_high_bot", os.path.join(HERE, "weather-high-paper", "bot.py"))
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    return bot


def test_city_quotes_log_only_before_lock_and_buyable_after():
    bot = _weather_bot()
    city = wm.CITIES["KXHIGHNY"]
    markets = [{"ticker": "KXHIGHNY-26NOV12-B59.5", "event_ticker": "KXHIGHNY-26NOV12",
                "strike_type": "between", "floor_strike": 59, "cap_strike": 60,
                "yes_ask_dollars": "0.40", "yes_bid_dollars": "0.38",
                "no_ask_dollars": "0.62", "no_bid_dollars": "0.60"}]
    hourly = {"time": [f"2026-11-12T{h:02d}:00" for h in range(5, 24)],
              "temperature_2m": [55.0 + (h > 15) * 4 for h in range(5, 24)]}
    obs = [{"properties": {"timestamp": "2026-11-12T19:51:00+00:00", "temperature": {"value": 15.2}}}]
    morning = dt.datetime(2026, 11, 12, 14, tzinfo=dt.timezone.utc)   # 9 a.m. EST
    rows = bot.city_quotes("KXHIGHNY", city, morning, markets=markets, obs=obs, hourly=hourly, periods=[])
    assert rows and all(r.get("log_only") for r in rows)
    late = dt.datetime(2026, 11, 12, 21, 30, tzinfo=dt.timezone.utc)  # 4:30 p.m. EST
    rows = bot.city_quotes("KXHIGHNY", city, late, markets=markets, obs=obs, hourly=hourly, periods=[])
    yes = next(r for r in rows if r["side"] == "yes")
    assert not yes.get("log_only") and yes["fair"] > 0.5 and "high so far 59.4F" in yes["why"]


def test_registry_and_desk_wiring():
    import desk_profit
    import new_towers
    import pimp_desk

    assert desk_profit.BOT_VENUE["weather-high"] == "kalshi_econ"
    assert desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_econ"] == 0.05
    spec = next(b for b in pimp_desk.BOTS if b["id"] == "weather-high")
    assert spec["shadow_only"] and "weather-high" not in (pimp_desk.DEFAULTS.get("tower_risk_budgets") or {})
    assert pimp_desk.BOT_PLANS["weather-high"]["exit_quality"] == "partial"
    assert any(s["id"] == "weather-high" and s["every_sec"] == 300 for s in pimp_desk.AUTO)
    assert "weather-high" in new_towers.BY_ID
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("weather-high")["ok"]
