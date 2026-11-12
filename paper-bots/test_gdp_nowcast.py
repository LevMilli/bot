"""GDP nowcast tower. Offline."""
import datetime as dt
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "gdp-nowcast-paper"))

import gdp_model as gm  # noqa: E402

UTC = dt.timezone.utc
TABLE = [(13, 0.9, 0.0), (45, 1.0, 0.2), (9999, 1.6, 0.8)]


def _bot():
    spec = importlib.util.spec_from_file_location("gdp_bot", os.path.join(HERE, "gdp-nowcast-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _arch(quarter, gdp, actual, days):
    row = [None] * 34
    row[1], row[27], row[31], row[33] = quarter, gdp, actual, days
    return tuple(row)


def test_error_table_buckets_and_skips_2020():
    q = dt.datetime(2024, 3, 31)
    rows = [_arch(q, 4.0, 2.0, d) for d in (1, 15, 29, 43)]
    rows += [_arch(q, 2.0, 2.0, d) for d in (2, 16, 30, 44)]
    rows.append(_arch(dt.datetime(2020, 6, 30), 30.0, 0.0, 5))       # COVID quarter ignored
    rows.append(_arch(q, "#N/A", 2.0, 5))
    table = gm.error_table(rows)
    assert [t[0] for t in table] == [13, 27, 41, 55]
    assert all(math.isclose(t[1], math.sqrt(2.0), abs_tol=1e-3) and t[2] == 1.0 for t in table)
    assert gm.error_table(rows[:2]) == []


def test_current_reads_latest_row_and_quarter():
    rows = [(dt.datetime(2026, 10, 29), "Initial GDPNow 26:Q4 forecast", 3.22),
            (dt.datetime(2026, 11, 9), "Retail sales", 3.48), (None, None, None)]
    assert gm.current(rows) == {"quarter": "2026Q4", "value": 3.48, "asof": "2026-11-09"}
    assert gm.current([(None, None, None)]) is None


def test_release_dates_map_to_quarters():
    assert gm.event_release("KXGDP-27JAN28") == dt.date(2027, 1, 28)
    assert gm.release_quarter(dt.date(2027, 1, 28)) == "2026Q4"
    assert gm.release_quarter(dt.date(2027, 4, 29)) == "2027Q1"
    assert gm.release_quarter(dt.date(2027, 7, 29)) == "2027Q2"
    assert gm.release_quarter(dt.date(2026, 10, 29)) == "2026Q3"
    assert gm.event_release("KXGDP-27XYZ28") is None


def test_rounding_bias_and_error_lookup():
    assert math.isclose(gm.p_above(3.0, 3.05, 1.0), 0.5)
    assert gm.p_above(3.0, 3.05, 1.0, bias=0.5) < 0.5
    assert gm.error_for(TABLE, 10) == (0.9, 0.0)
    assert gm.error_for(TABLE, 77) == (1.6, 0.8)
    assert gm.error_for([], 5)[0] == gm.DEFAULT_ERROR[0][1]


def _market(strike, event="KXGDP-27JAN28", close="2027-01-28T13:29:00Z"):
    return {"ticker": f"{event}-T{strike}", "event_ticker": event, "strike_type": "greater",
            "floor_strike": strike, "close_time": close, "yes_ask_dollars": "0.40",
            "yes_bid_dollars": "0.30", "no_ask_dollars": "0.70", "no_bid_dollars": "0.60"}


def test_quotes_window_quarter_and_log_only():
    bot = _bot()
    cast = {"now": {"quarter": "2026Q4", "value": 3.5, "asof": "2027-01-10"}, "table": TABLE}
    markets = [_market(3.0), _market(3.0, "KXGDP-27APR29", "2027-04-29T12:29:00Z")]
    near = dt.datetime(2027, 1, 12, 15, tzinfo=UTC)
    q = bot.quotes_for(markets, cast, near)
    assert {x["event"] for x in q} == {"KXGDP-27JAN28"} and not any(x.get("log_only") for x in q)
    assert q[0]["label"] == "GDP 2026Q4 above 3.0%"
    assert math.isclose(q[0]["fair"] + q[1]["fair"], 1.0)
    far_cast = dict(cast, now=dict(cast["now"], asof="2026-11-09"))
    far = bot.quotes_for(markets, far_cast, dt.datetime(2026, 11, 12, 15, tzinfo=UTC))
    assert far and all(x["log_only"] for x in far)
    assert bot.quotes_for(markets, cast, dt.datetime(2027, 1, 25, tzinfo=UTC)) == []      # 15 days stale
    late = dt.datetime(2027, 1, 28, 12, 0, tzinfo=UTC)
    fresh = dict(cast, now=dict(cast["now"], asof="2027-01-27"))
    assert bot.quotes_for(markets, fresh, late) == []


def test_cache(tmp_path, monkeypatch):
    bot = _bot()
    monkeypatch.setattr(bot, "HERE", str(tmp_path))
    calls = []

    def read(url):
        calls.append(url)
        return b""

    parse = lambda blob: {"now": {"quarter": "2026Q4", "value": 3.0, "asof": "2026-11-09"}, "table": TABLE}  # noqa: E731
    now = dt.datetime(2026, 11, 12, tzinfo=UTC)
    assert bot._gdpnow(now, read=read, parse=parse)["now"]["value"] == 3.0
    bot._gdpnow(now + dt.timedelta(hours=1), read=read, parse=parse)
    assert len(calls) == 1
    bot._gdpnow(now + dt.timedelta(hours=9), read=read, parse=parse)
    assert len(calls) == 2


def test_registry_and_desk_wiring():
    import desk_profit
    import new_towers
    import pimp_desk

    assert desk_profit.BOT_VENUE["gdp-nowcast"] == "kalshi_econ"
    spec = next(b for b in pimp_desk.BOTS if b["id"] == "gdp-nowcast")
    assert spec["shadow_only"]
    assert pimp_desk._account_body("gdp-nowcast")["cash"] == 500.0
    assert "gdp-nowcast-paper/gdpnow_cache.json" in pimp_desk.SETTLEMENT_FILES
    assert "gdp-nowcast" in new_towers.BY_ID
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("gdp-nowcast")["ok"]
