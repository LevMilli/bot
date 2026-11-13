"""Monthly rain and snow tower (KXRAIN*M, KX*SNOWM). Offline."""
import datetime as dt
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "monthly-precip-paper"))

import precip_model as pm  # noqa: E402

UTC = dt.timezone.utc


def _bot():
    spec = importlib.util.spec_from_file_location("monthly_precip_bot",
                                                  os.path.join(HERE, "monthly-precip-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_event_month_and_days():
    assert pm.event_month("KXRAINNYCM-26NOV") == (2026, 11)
    assert pm.event_month("KXBOSSNOWM-26DEC") == (2026, 12)
    assert pm.event_month("KXRAINNYCM-bad") is None
    assert pm.month_days(2026, 2) == (dt.date(2026, 2, 1), dt.date(2026, 2, 28))


def test_month_to_date_skips_preview_reports_and_trace():
    rows = [
        {"valid": "2026-10-31", "product": "202611010600-KOKX-CDUS41-CLINYC", "precip_month": 4.0, "snow_month": 0},
        {"valid": "2026-11-11", "product": "202611120600-KOKX-CDUS41-CLINYC", "precip_month": 2.31, "snow_month": "T"},
        {"valid": "2026-11-12", "product": "202611130600-KOKX-CDUS41-CLINYC", "precip_month": 2.57, "snow_month": "T"},
        # Afternoon preview for the 13th, written before the day ended: not complete.
        {"valid": "2026-11-13", "product": "202611132133-KOKX-CDUS41-CLINYC", "precip_month": 2.83, "snow_month": 0},
        {"valid": "2026-11-10", "product": "202611110600-KOKX-CDUS41-CLINYC", "precip_month": "M", "snow_month": 0},
    ]
    assert pm.month_to_date(rows, 2026, 11, "rain", -5) == (2.57, dt.date(2026, 11, 12))
    assert pm.month_to_date(rows, 2026, 11, "snow", -5) == (0.0, dt.date(2026, 11, 12))
    assert pm.month_to_date(rows, 2026, 12, "snow", -5) == (0.0, dt.date(2026, 11, 30))


def _hourly(first, hours, per_hour, members=3, stop_early=None):
    times = [(first + dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(hours)]
    out = {"time": times}
    for m in range(members):
        key = "precipitation_ncep_gefs025" if m == 0 else f"precipitation_member{m:02d}_ncep_gefs025"
        vals = [per_hour] * hours
        if stop_early and m == 0:
            vals = vals[:-stop_early] + [None] * stop_early
        out[key] = vals
    out["precipitation_probability"] = [1] * hours  # never counted
    return out


def test_daily_sums_use_local_standard_days_and_coverage():
    first = dt.datetime(2026, 11, 28, 5, tzinfo=UTC)          # 00:00 EST Nov 28
    hourly = _hourly(first, 4 * 24, 0.01, members=3, stop_early=30)
    sums = pm.daily_sums(hourly, "precipitation", -5)
    assert len(sums) == 3
    full = sums["precipitation_member01_ncep_gefs025"]["days"]
    # The amount stamped 00:00 EST is for the hour before, so it belongs to the day before.
    assert abs(full["2026-11-27"] - 0.01) < 1e-9 and abs(full["2026-11-28"] - 0.24) < 1e-9
    rest = pm.member_rest(sums, dt.date(2026, 11, 28), dt.date(2026, 11, 30), -5)
    assert len(rest) == 2                                    # the short run is dropped
    assert all(abs(r - 0.72) < 1e-9 for r in rest)           # three whole days


def test_draws_and_probability():
    samples = pm.draws(2.0, [0.5] * 30, "rain", 5, "seed")
    assert len(samples) == 30 * pm.DRAWS_PER_MEMBER
    assert min(samples) >= 2.0
    assert pm.p_greater(samples, 1.0) == 0.99                 # already past the line
    p3 = pm.p_greater(samples, 3.0)
    assert 0.01 <= p3 < 0.2
    assert pm.p_greater([], 3.0) is None
    assert pm.draws(1.0, [0.0] * 30, "snow", 0, "x") == [1.0] * (30 * pm.DRAWS_PER_MEMBER)


def _market(ticker, strike, event="KXRAINNYCM-26NOV"):
    return {"ticker": ticker, "event_ticker": event, "strike_type": "greater", "floor_strike": strike,
            "yes_ask_dollars": "0.40", "no_ask_dollars": "0.62", "yes_bid_dollars": "0.38",
            "no_bid_dollars": "0.60"}


def _cli(code, year):
    return [{"valid": "2026-11-20", "product": "202611210600-KOKX-CDUS41-CLINYC", "precip_month": 2.5,
             "snow_month": 0}]


def _runs(n, amount, last="2026-12-02T00:00:00+00:00"):
    days = {f"2026-11-{d:02d}": amount for d in range(21, 31)}
    return {f"m{i}": {"days": days, "last": last} for i in range(n)}


def test_series_quotes_buy_window_and_short_forecast():
    bot = _bot()
    now = dt.datetime(2026, 11, 21, 18, tzinfo=UTC)
    markets = [_market("A", 3.0), _market("B", 5.0)]
    quotes, note = bot.series_quotes("KXRAINNYCM", markets, now, cli=_cli, members=lambda c, k: _runs(30, 0.1))
    assert note == "" and len(quotes) == 4
    assert not any(q.get("log_only") for q in quotes)          # 10 days left
    a_yes = next(q for q in quotes if q["ticker"] == "A" and q["side"] == "yes")
    b_yes = next(q for q in quotes if q["ticker"] == "B" and q["side"] == "yes")
    assert a_yes["fair"] > 0.5 > b_yes["fair"]
    assert "through 2026-11-20" in a_yes["why"] and "Nov rain" in a_yes["label"]
    short = lambda c, k: _runs(30, 0.1, last="2026-11-28T00:00:00+00:00")
    quotes, note = bot.series_quotes("KXRAINNYCM", markets, now, cli=_cli, members=short)
    assert quotes == [] and "does not reach Nov 30" in note
    early = dt.datetime(2026, 11, 1, 18, tzinfo=UTC)
    quotes, note = bot.series_quotes("KXRAINNYCM", markets, early, cli=lambda c, y: [],
                                     members=lambda c, k: (_ for _ in ()).throw(AssertionError("no fetch")))
    assert quotes == [] and "does not reach Nov 30" in note


def test_log_only_more_than_14_days_left():
    bot = _bot()
    now = dt.datetime(2026, 11, 15, 18, tzinfo=UTC)   # report two days behind: 18 days still to add
    days = {f"2026-11-{d:02d}": 0.1 for d in range(13, 31)}
    runs = {f"m{i}": {"days": days, "last": "2026-12-02T00:00:00+00:00"} for i in range(25)}
    cli = lambda c, y: [{"valid": "2026-11-12", "product": "202611130600-X-CLINYC", "precip_month": 2.0}]
    quotes, _ = bot.series_quotes("KXRAINNYCM", [_market("A", 3.0)], now, cli=cli, members=lambda c, k: runs)
    assert quotes and all(q["log_only"] and "18 days left" in q["log_reason"] for q in quotes)


def test_model_notes_dormant_and_maps():
    bot = _bot()
    now = dt.datetime(2026, 11, 21, 18, tzinfo=UTC)
    quotes, note = bot.model({}, now, list_markets=lambda s: [], cli=_cli, members=lambda c, k: {})
    assert quotes == [] and "no open markets: KXRAINNYCM" in note and "no open markets: KXMSPSNOWM" in note
    assert sum(1 for _, kind in bot.SERIES.values() if kind == "rain") == 18
    assert sum(1 for _, kind in bot.SERIES.values() if kind == "snow") == 9
    assert all(code in bot.STATIONS for code, _ in bot.SERIES.values())
    assert bot.SERIES["KXRAINCHIM"][0] == "ORD" and bot.SPEC["floor"] == 0.05
