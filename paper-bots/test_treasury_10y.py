"""10-year Treasury tower. Offline."""
import datetime as dt
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "treasury-10y-paper"))

import ust_model as um  # noqa: E402

UTC = dt.timezone.utc
DAY = dt.date(2026, 11, 13)
AT_11ET = dt.datetime(2026, 11, 13, 16, tzinfo=UTC)
HIST = {"sd_day": 0.05, "basis_mean": 0.0, "basis_sd": 0.008}


def _bot():
    spec = importlib.util.spec_from_file_location("ust_bot", os.path.join(HERE, "treasury-10y-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_parse_csv_sd_and_basis():
    rows = ["Date,\"1 Mo\",\"10 Yr\""]
    cmt = {}
    for i in range(40):
        d = dt.date(2026, 9, 1) + dt.timedelta(days=i)
        y = 4.80 + (0.05 if i % 2 else 0.0)
        rows.append(f"{d.month:02d}/{d.day:02d}/{d.year},4.0,{y:.2f}")
        cmt[d.isoformat()] = y
    parsed = um.parse_treasury_csv("\n".join(rows))
    assert parsed == {k: round(v, 2) for k, v in cmt.items()}
    assert math.isclose(um.daily_sd(parsed), 0.05, abs_tol=1e-3)
    tnx = {k: v - 0.01 for k, v in parsed.items()}
    mean, sd = um.basis(parsed, tnx)
    assert math.isclose(mean, 0.01, abs_tol=1e-9) and sd == um.BASIS_SD_FLOOR
    assert um.daily_sd({"2026-01-01": 4.0}) is None


def test_window_is_settlement_day_only():
    assert um.minutes_left(AT_11ET, DAY) == 270
    assert um.minutes_left(dt.datetime(2026, 11, 13, 13, tzinfo=UTC), DAY) is None   # 8:00 ET
    assert um.minutes_left(dt.datetime(2026, 11, 13, 21, tzinfo=UTC), DAY) is None   # 16:00 ET
    assert um.minutes_left(AT_11ET, dt.date(2026, 11, 16)) is None                  # other day
    assert um.event_day("KXUST10A-26NOV13") == DAY
    assert um.event_day("bad") is None


def test_rounding_and_sides_add_up():
    at = um.p_above(5.000, 5.00, 0.05, 0.0, 0.0, 0.008)
    assert at < 0.5            # 5.00 printed is not "above 5.00"
    hi = um.fair_yes({"strike_type": "greater", "floor_strike": 4.90}, 5.0, 0.05, 270, 0.0, 0.008)
    lo = um.fair_yes({"strike_type": "greater", "floor_strike": 5.10}, 5.0, 0.05, 270, 0.0, 0.008)
    assert hi > 0.9 and lo < 0.1
    below = um.fair_yes({"strike_type": "less", "cap_strike": 4.95}, 5.0, 0.05, 270, 0.0, 0.008)
    above = um.fair_yes({"strike_type": "greater", "floor_strike": 4.94}, 5.0, 0.05, 270, 0.0, 0.008)
    assert math.isclose(below + above, 1.0, abs_tol=1e-9)
    assert um.fair_yes({"strike_type": "between"}, 5.0, 0.05, 270, 0.0, 0.008) is None


def test_quotes_for_labels_and_window():
    bot = _bot()
    base = {"event_ticker": "KXUST10A-26NOV13", "strike_type": "greater", "yes_ask_dollars": "0.86",
            "yes_bid_dollars": "0.70", "no_ask_dollars": "0.30", "no_bid_dollars": "0.14"}
    markets = [dict(base, ticker="KXUST10A-26NOV13-T4.92", floor_strike=4.92),
               dict(base, ticker="KXUST10A-26NOV16-T4.92", event_ticker="KXUST10A-26NOV16", floor_strike=4.92)]
    q = bot.quotes_for(markets, 5.0, HIST, AT_11ET)
    assert {x["ticker"] for x in q} == {"KXUST10A-26NOV13-T4.92"}
    assert q[0]["label"] == "10Y Nov 13 above 4.92%"
    assert math.isclose(q[0]["fair"] + q[1]["fair"], 1.0)
    late = dt.datetime(2026, 11, 13, 20, 20, tzinfo=UTC)     # 15:20 ET: under 15 min
    assert bot.quotes_for(markets, 5.0, HIST, late) == []


def test_model_skips_outside_window_and_stale(monkeypatch):
    bot = _bot()
    quotes, note = bot.model({}, dt.datetime(2026, 11, 14, 16, tzinfo=UTC))   # Saturday
    assert quotes == [] and "window" in note
    monkeypatch.setattr(bot, "_live_tnx", lambda now: (5.0, 3600))
    quotes, note = bot.model({}, AT_11ET)
    assert quotes == [] and "min old" in note


def test_registry_and_desk_wiring():
    import desk_profit
    import new_towers
    import pimp_desk

    assert desk_profit.BOT_VENUE["treasury-10y"] == "kalshi_econ"
    assert desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_econ"] == 0.05
    spec = next(b for b in pimp_desk.BOTS if b["id"] == "treasury-10y")
    assert spec["shadow_only"]
    assert pimp_desk._account_body("treasury-10y")["cash"] == 500.0
    assert "treasury-10y-paper/ust_daily.json" in pimp_desk.SETTLEMENT_FILES
    assert "treasury-10y" in new_towers.BY_ID
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("treasury-10y")["ok"]
