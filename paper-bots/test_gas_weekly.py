"""Gas weekly tower. Offline."""
import datetime as dt
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "gas-weekly-paper"))

import gas_model as gm  # noqa: E402

HTML = """<p class="price-text">Price as of 11/12/26</p>
<table><tbody>
<tr><td>Current Avg.</td><td>$3.9081</td><td>$4.4100</td><td>$4.8000</td><td>$4.9000</td></tr>
<tr><td>Yesterday Avg.</td><td>$3.9429</td><td>$4.4400</td><td>$4.8</td><td>$4.9</td></tr>
<tr><td>Week Ago Avg.</td><td>$4.1003</td><td>$4.6</td><td>$5</td><td>$5.1</td></tr>
</tbody></table>"""


def _bot():
    spec = importlib.util.spec_from_file_location("gas_bot", os.path.join(HERE, "gas-weekly-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_parse_aaa_reads_regular_column_and_date():
    r = gm.parse_aaa(HTML)
    assert r == {"as_of": "2026-11-12", "current": 3.9081, "yesterday": 3.9429, "week_ago": 4.1003}
    assert gm.parse_aaa("<html>changed layout</html>") is None
    assert gm.parse_aaa(HTML.replace("$3.9081", "$39.081")) is None


def test_event_day():
    assert gm.event_day("KXAAAGASW-26NOV16") == dt.date(2026, 11, 16)
    assert gm.event_day("KXAAAGASW-bad") is None


def test_forecast_fades_momentum_and_widens():
    r = gm.parse_aaa(HTML)
    p = gm.fit({})
    assert p["phi"] == 0.9 and not p["fitted"]
    one = gm.forecast(r, dt.date(2026, 11, 13), p)
    four = gm.forecast(r, dt.date(2026, 11, 16), p)
    assert one["mean"] < 3.9081 and four["mean"] < one["mean"]
    assert four["sd"] > one["sd"]
    # fading: four days of drift is less than 4x the first day's
    assert abs(four["drift"]) < 4 * abs(one["drift"])
    assert gm.forecast(r, dt.date(2026, 11, 11), p) is None
    assert gm.forecast(r, dt.date(2026, 11, 12), p)["mean"] == 3.9081


def test_p_greater_monotone_and_bounded():
    fc = {"mean": 3.81, "sd": 0.03}
    ps = [gm.p_greater(k, fc) for k in (3.70, 3.78, 3.80, 3.82, 3.90)]
    assert ps == sorted(ps, reverse=True)
    assert 0.01 <= ps[-1] and ps[0] <= 0.99


def test_fit_uses_own_history_with_bounds():
    start = dt.date(2026, 10, 1)
    price, move, hist = 4.0, -0.02, {}
    for i in range(30):
        hist[(start + dt.timedelta(days=i)).isoformat()] = round(price, 4)
        price += move
        move *= 0.7
    p = gm.fit(hist)
    assert p["fitted"] and 0.6 < p["phi"] < 0.8 and p["noise"] == 0.003
    gap = dict(list(hist.items())[:10])
    assert not gm.fit(gap)["fitted"]


def _markets():
    base = {"event_ticker": "KXAAAGASW-26NOV16", "strike_type": "greater", "status": "active"}
    return [
        dict(base, ticker="KXAAAGASW-26NOV16-3.80", floor_strike=3.80, yes_ask_dollars="0.44",
             yes_bid_dollars="0.41", no_ask_dollars="0.59", no_bid_dollars="0.56"),
        dict(base, ticker="KXAAAGASW-26NOV16-X", strike_type="between", floor_strike=3.8),
    ]


def test_quotes_log_only_while_learning_far_from_settle():
    bot = _bot()
    r = gm.parse_aaa(HTML)
    q = bot.quotes_for(_markets(), r, gm.fit({}))
    assert len(q) == 2 and all(x["log_only"] for x in q)
    yes = next(x for x in q if x["side"] == "yes")
    assert abs(yes["fair"] + next(x for x in q if x["side"] == "no")["fair"] - 1) < 1e-9
    assert "learning momentum" in yes["log_reason"]
    near = dict(r, as_of="2026-11-15")
    assert not any(x.get("log_only") for x in bot.quotes_for(_markets(), near, gm.fit({})))
    fitted = {"phi": 0.8, "noise": 0.008, "n": 25, "fitted": True}
    assert not any(x.get("log_only") for x in bot.quotes_for(_markets(), r, fitted))


def test_aaa_cache_and_history(tmp_path, monkeypatch):
    bot = _bot()
    monkeypatch.setattr(bot, "HERE", str(tmp_path))
    calls = []
    fetch = lambda: calls.append(1) or HTML  # noqa: E731
    now = dt.datetime(2026, 11, 12, 15, tzinfo=dt.timezone.utc)
    assert bot._aaa_reading(now, fetch)["current"] == 3.9081
    assert bot._aaa_reading(now + dt.timedelta(minutes=30), fetch)["current"] == 3.9081
    assert len(calls) == 1
    bot._aaa_reading(now + dt.timedelta(hours=2), fetch)
    assert len(calls) == 2
    hist = json.loads((tmp_path / "aaa_history.json").read_text())
    assert hist == {"2026-11-11": 3.9429, "2026-11-12": 3.9081}
    assert bot._aaa_reading(now + dt.timedelta(hours=4), lambda: "broken") is None


def test_registry_and_desk_wiring():
    import desk_profit
    import new_towers
    import pimp_desk

    assert desk_profit.BOT_VENUE["gas-weekly"] == "kalshi_econ"
    spec = next(b for b in pimp_desk.BOTS if b["id"] == "gas-weekly")
    assert spec["shadow_only"] and "gas-weekly" not in (pimp_desk.DEFAULTS.get("tower_risk_budgets") or {})
    assert any(s["id"] == "gas-weekly" and s["every_sec"] == 900 for s in pimp_desk.AUTO)
    assert "gas-weekly" in new_towers.BY_ID
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("gas-weekly")["ok"]
