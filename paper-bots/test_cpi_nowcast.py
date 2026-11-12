"""CPI nowcast tower. Offline."""
import datetime as dt
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "cpi-nowcast-paper"))

import cpi_model as cm  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 12, 18, tzinfo=UTC)


def _bot():
    spec = importlib.util.spec_from_file_location("cpi_bot", os.path.join(HERE, "cpi-nowcast-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _chart(month, values, asof="2026-11-10 00:00"):
    return {"chart": {"subcaption": month, "_comment": asof},
            "dataset": [{"seriesname": name, "data": [{"value": v} for v in vals]}
                        for name, vals in values.items()]}


CHARTS = [
    _chart("2026-10", {"CPI Inflation": ["0.2", "0.24"], "Actual CPI Inflation": ["", "0.35"]}),
    _chart("2026-11", {"CPI Inflation": ["0.1", "0.135", ""], "Core CPI Inflation": ["0.21", "", ""]}),
]


def test_latest_nowcasts_takes_last_nonempty():
    rows = cm.latest_nowcasts(CHARTS)
    assert rows["2026-11"]["CPI Inflation"] == 0.135
    assert rows["2026-11"]["Core CPI Inflation"] == 0.21
    assert rows["2026-11"]["_asof"] == "2026-11-10"
    assert rows["2026-10"]["Actual CPI Inflation"] == 0.35
    assert cm.latest_nowcasts([{"chart": {"subcaption": "bad"}}]) == {}


def test_event_month_and_business_days():
    assert cm.event_month("KXCPI-26NOV") == "2026-11"
    assert cm.event_month("KXCPICOREYOY-27JAN") == "2027-01"
    assert cm.event_month("KXCPI-26XYZ") is None
    assert cm.business_days(dt.date(2026, 11, 13), dt.date(2026, 11, 16)) == 1   # Fri -> Mon
    assert cm.error_for("KXCPI", 3)[0] == 0.112 * cm.SAFETY
    assert cm.error_for("KXCPI", 40)[0] == 0.198 * cm.SAFETY


def test_rounding_and_sides():
    # nowcast exactly 0.25 with no bias: "above 0.2" (needs >= 0.25) is a coin flip
    assert math.isclose(cm.p_above(0.2, 0.25, 0.1, 0.0), 0.5)
    assert cm.p_above(0.0, 0.3, 0.1, 0.0) > 0.99
    assert cm.p_above(0.5, 0.1, 0.1, 0.0) < 0.001
    # a positive bias (nowcast runs high) lowers P(above)
    assert cm.p_above(0.2, 0.25, 0.1, 0.02) < 0.5
    assert cm.fair_yes({"strike_type": "less", "floor_strike": 0.2}, 0.2, 0.1, 0) is None


def _market(ticker, strike, close="2026-12-10T13:29:00Z"):
    return {"ticker": ticker, "event_ticker": ticker.rsplit("-", 1)[0], "strike_type": "greater",
            "floor_strike": strike, "close_time": close, "yes_ask_dollars": "0.40",
            "yes_bid_dollars": "0.30", "no_ask_dollars": "0.70", "no_bid_dollars": "0.60"}


def test_quotes_only_for_fresh_matching_month():
    bot = _bot()
    casts = {"month": cm.latest_nowcasts(CHARTS)}
    markets = [_market("KXCPI-26NOV-T0.1", 0.1), _market("KXCPI-26DEC-T0.1", 0.1, "2027-01-13T13:29:00Z")]
    q = bot.quotes_for("KXCPI", markets, casts, NOW)
    assert {x["ticker"] for x in q} == {"KXCPI-26NOV-T0.1"}
    assert q[0]["label"] == "CPI MoM Nov above 0.1%"
    assert math.isclose(q[0]["fair"] + q[1]["fair"], 1.0)
    stale = NOW + dt.timedelta(days=6)
    assert bot.quotes_for("KXCPI", markets, casts, stale) == []
    late = dt.datetime(2026, 12, 10, 12, 0, tzinfo=UTC)            # 89 min before release
    fresh = {"month": cm.latest_nowcasts([_chart("2026-11", {"CPI Inflation": ["0.1"]}, "2026-12-09 00:00")])}
    assert bot.quotes_for("KXCPI", markets, fresh, late) == []


def test_cache_refresh_keeps_last_months(tmp_path, monkeypatch):
    bot = _bot()
    monkeypatch.setattr(bot, "HERE", str(tmp_path))
    charts = [_chart(f"2026-{m}", {"CPI Inflation": ["0.2"]}) for m in range(1, 12)]
    calls = []

    def read(url):
        calls.append(url)
        return json.dumps(charts)

    out = bot._nowcasts(NOW, read=read)
    assert sorted(out["month"]) == ["2026-09", "2026-10", "2026-11"] and len(calls) == 2
    bot._nowcasts(NOW + dt.timedelta(hours=1), read=read)
    assert len(calls) == 2                     # cached
    bot._nowcasts(NOW + dt.timedelta(hours=7), read=read)
    assert len(calls) == 4


def test_registry_and_desk_wiring():
    import desk_profit
    import new_towers
    import pimp_desk

    assert desk_profit.BOT_VENUE["cpi-nowcast"] == "kalshi_econ"
    assert desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_econ"] == 0.05
    spec = next(b for b in pimp_desk.BOTS if b["id"] == "cpi-nowcast")
    assert spec["shadow_only"]
    assert pimp_desk._account_body("cpi-nowcast")["cash"] == 500.0
    assert "cpi-nowcast-paper/nowcast_cache.json" in pimp_desk.SETTLEMENT_FILES
    assert "cpi-nowcast" in new_towers.BY_ID
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("cpi-nowcast")["ok"]
