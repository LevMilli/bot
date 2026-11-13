"""Weather low and Weather cities towers (shared weather_extra.py). Offline."""
import datetime as dt
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import weather_extra as wx  # noqa: E402

UTC = dt.timezone.utc


def _bot(folder, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, folder, "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _obs(when, c, raw=""):
    return {"properties": {"timestamp": when.isoformat(), "temperature": {"value": c}, "rawMessage": raw}}


def test_whole_degree_readings_only_bound_the_extreme():
    start = dt.datetime(2026, 11, 13, 8, tzinfo=UTC)
    end = start + dt.timedelta(days=1)
    obs = [_obs(start + dt.timedelta(hours=2), 13.3, "KLAS 131056Z 13/02 RMK AO2 T01330022"),
           _obs(start + dt.timedelta(hours=2, minutes=35), 13),   # 5-minute report, whole degrees C
           _obs(start - dt.timedelta(hours=1), 5.0, "T00500000")]  # before the climate day: ignored
    low = wx.observed_min_f(obs, start, end)
    assert abs(low - 55.94) < 0.01            # exact 13.3C beats 13C + 0.5C (56.3F)
    only_coarse = [_obs(start + dt.timedelta(hours=3), 4)]
    assert abs(wx.observed_min_f(only_coarse, start, end) - 40.1) < 0.01   # 4.5C upper bound
    assert abs(wx.observed_max_f(only_coarse, start, end) - 38.3) < 0.01   # 3.5C lower bound
    assert wx.observed_min_f([], start, end) is None


def test_low_draws_and_night_low_anchor():
    periods = [{"isDaytime": False, "endTime": "2026-11-14T06:00:00-05:00", "temperature": 34,
                "temperatureUnit": "F"}]
    assert wx.nws_night_low(periods, dt.date(2026, 11, 14)) == 34
    assert wx.nws_night_low(periods, dt.date(2026, 11, 15)) is None
    assert wx.anchor_shift_low([30.0, 31.0, 32.0], 40) == 4.0
    assert wx.anchor_shift_low([30.0, 31.0, 32.0], None) == 0.0
    draws = wx.draws_low(40.0, [45.0, 46.0], 1.0, "seed")
    assert draws and max(draws) <= 40
    assert wx.draws_low(None, [], 1.0, "x") == []


def _market(ticker, lo, hi, kind):
    row = {"ticker": ticker, "event_ticker": "KXLOWTNYC-26NOV14", "yes_ask_dollars": "0.30",
           "no_ask_dollars": "0.72", "yes_bid_dollars": "0.28", "no_bid_dollars": "0.70",
           "strike_type": kind}
    if lo is not None:
        row["floor_strike"] = lo
    if hi is not None:
        row["cap_strike"] = hi
    return row


def test_run_cities_logs_before_lock_and_notes_dormant():
    now = dt.datetime(2026, 11, 14, 10, tzinfo=UTC)      # 05:00 EST: before the 10:00 lock
    times = [(dt.datetime(2026, 11, 14, 5, tzinfo=UTC) + dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M")
             for h in range(30)]
    hourly = {"time": times, "temperature_2m": [40.0] * 30, "temperature_2m_member01": [38.0] * 30}
    markets = {"KXLOWTNYC": [_market("KXLOWTNYC-26NOV14-B38.5", 38, 39, "between")], "KXLOWTCHI": []}
    quotes, note = wx.run_cities(
        "/nonexistent", "low", {"KXLOWTNYC": "NYC", "KXLOWTCHI": "CHI"}, now, 10,
        list_markets=lambda s: markets[s], get_ensemble=lambda c, city: hourly,
        get_periods=lambda c, city: [], get_obs=lambda station, start: [])
    assert "no open markets: KXLOWTCHI" in note
    assert len(quotes) == 2 and all(q["log_only"] for q in quotes)
    yes = next(q for q in quotes if q["side"] == "yes")
    assert 0.0 < yes["fair"] < 1.0 and "low" in yes["label"]


def test_series_maps_and_specs():
    assert len(wx.LOW_SERIES) == 24 and len(wx.HIGH_SERIES) == 17
    assert all(code in wx.STATIONS for code in list(wx.LOW_SERIES.values()) + list(wx.HIGH_SERIES.values()))
    # The high twin only covers cities Weather high does not already trade.
    assert not {"KXHIGHNY", "KXHIGHCHI", "KXHIGHMIA"} & set(wx.HIGH_SERIES)
    low = _bot("weather-low-paper", "weather_low_bot")
    cities = _bot("weather-cities-paper", "weather_cities_bot")
    assert low.SPEC["floor"] == 0.05 and cities.SPEC["floor"] == 0.05
    assert low.LOCK_HOUR_LST == 10 and cities.LOCK_HOUR_LST == 15
