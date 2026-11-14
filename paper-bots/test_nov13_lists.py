"""New markets are recorded and graded; weather high has more time (Nov 13). Offline."""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "market-snapshots-paper"))


def _load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _source(rel):
    return open(os.path.join(HERE, rel)).read()


def test_snapshots_cover_every_new_tower_series_once():
    import snapshot_model as sm
    assert len(sm.SERIES) == len(set(sm.SERIES)) == 100
    for group in (sm.CRYPTO_HOURLY, sm.WEATHER_LOWS, sm.WEATHER_CITY_HIGHS, sm.MONTHLY_PRECIP, sm.GAS_MONTHLY):
        assert set(group) <= set(sm.SERIES)


def test_calibration_has_the_new_families_and_room_for_them():
    import calibration_lab as lab
    for fam in ("weather_low", "weather_cities", "precip_monthly", "gas_monthly", "crypto_hourly"):
        assert lab.FAMILIES[fam]
    assert lab.MAX_BATCHES >= lab.FAMILY_BATCHES * len(lab.FAMILIES)
    every = [s for members in lab.FAMILIES.values() for s in members]
    assert len(every) == len(set(every))


def test_lists_match_the_towers_that_trade_them():
    import calibration_lab as lab
    import snapshot_model as sm
    assert sm.WEATHER_LOWS == lab.WEATHER_LOWS and sm.MONTHLY_PRECIP == lab.MONTHLY_PRECIP
    src = _source("weather_extra.py")
    for s in sm.WEATHER_LOWS + sm.WEATHER_CITY_HIGHS:
        code = s.replace("KXLOWT", "").replace("KXHIGHT", "")
        assert f'"{code}"' in src, s
    precip = _source("monthly-precip-paper/bot.py")
    assert all(f'"{s}"' in precip for s in sm.MONTHLY_PRECIP)
    crypto = _source("crypto-hourly-paper/bot.py")
    assert all(f'"{s}"' in crypto for s in sm.CRYPTO_HOURLY)
    assert '"KXAAAGASM"' in _source("gas-monthly-paper/bot.py")


def test_weather_high_time_limit_raised_but_under_its_pace():
    import new_towers
    row = next(t for t in new_towers.TOWERS if t["id"] == "weather-high")
    assert row["timeout"] == 150 and row["timeout"] < row["every_sec"]
