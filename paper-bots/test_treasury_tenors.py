"""Treasury tenors tower (KXUST2A / KXUST5A / KXUST30A). Offline."""
import datetime as dt
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "treasury-tenors-paper"))

import ust_tenor_model as um  # noqa: E402

UTC = dt.timezone.utc
CSV = ('Date,"1 Mo","2 Yr","5 Yr","10 Yr","30 Yr"\n'
       + "".join(f"11/{d:02d}/2026,4.10,{4.80 + d / 100:.2f},{4.90 + (d % 3) / 100:.2f},5.10,{5.40 + (d % 2) / 50:.2f}\n"
                 for d in range(1, 29)))


def _bot():
    spec = importlib.util.spec_from_file_location("treasury_tenors_bot",
                                                  os.path.join(HERE, "treasury-tenors-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_parse_by_column():
    two = um.parse_treasury_csv(CSV, "2 Yr")
    five = um.parse_treasury_csv(CSV, "5 Yr")
    assert two["2026-11-05"] == 4.85 and five["2026-11-05"] == 4.92
    assert um.parse_treasury_csv(CSV)["2026-11-05"] == 5.10           # default stays the 10-year
    assert um.parse_treasury_csv(CSV, "7 Yr") == {}
    assert um.event_day("KXUST5A-26NOV20") == dt.date(2026, 11, 20)


def _chart(closes):
    bars = [{"tradeTime": d.replace("-", "") + "000000", "close": str(v)} for d, v in closes.items()]
    return {"barData": {"priceBars": bars}}


def test_history_one_treasury_file_for_all_tenors(tmp_path, monkeypatch):
    bot = _bot()
    monkeypatch.setattr(bot, "HERE", str(tmp_path))
    official = um.parse_treasury_csv(CSV, "5 Yr")
    calls = []

    def read(url):
        calls.append(url)
        if "treasury.gov" in url:
            return CSV
        if "cnbc" in url:
            return json.dumps(_chart({d: v - 0.01 for d, v in official.items()}))
        raise OSError("refused")      # Yahoo down: CNBC alone is enough

    now = dt.datetime(2026, 11, 29, 15, tzinfo=UTC)
    hist = bot._history(now, ["2Y", "5Y", "30Y"], read=read)
    assert set(hist) == {"2Y", "5Y", "30Y"}
    assert abs(hist["5Y"]["basis"]["cnbc"][0] - 0.01) < 1e-6 and "yahoo" not in hist["5Y"]["basis"]
    assert hist["2Y"]["source"] == "treasury.gov"
    assert sum("treasury.gov" in u for u in calls) == 2            # last year + this year, shared
    assert not any("FVX" in u or "TYX" in u for u in calls if "2Y" in u)
    again = bot._history(now + dt.timedelta(hours=1), ["5Y"], read=lambda u: (_ for _ in ()).throw(OSError()))
    assert again == hist                                            # cached for 6 hours


def _market(tenor_series, strike, day="26NOV20"):
    return {"ticker": f"{tenor_series}-{day}-T{strike}", "event_ticker": f"{tenor_series}-{day}",
            "strike_type": "greater", "floor_strike": strike, "yes_ask_dollars": "0.40",
            "no_ask_dollars": "0.62", "yes_bid_dollars": "0.38", "no_bid_dollars": "0.60"}


def test_model_settlement_day_only_and_notes():
    bot = _bot()
    settle = dt.datetime(2026, 11, 20, 17, tzinfo=UTC)               # 12:00 ET on the Friday
    lists = {"KXUST2A": [_market("KXUST2A", 4.80)], "KXUST5A": [_market("KXUST5A", 4.96)],
             "KXUST30A": []}
    hist = {t: {"sd_day": 0.06, "basis": {"cnbc": [0.0, 0.01]}} for t in ("2Y", "5Y")}
    live = lambda tenor, now: ("cnbc", {"2Y": 4.85, "5Y": 4.96}[tenor], 30.0)
    quotes, note = bot.model({}, settle, list_markets=lambda s: lists[s], live=live,
                             history=lambda now, tenors: hist)
    assert "no open markets: KXUST30A" in note
    assert {q["label"].split()[0] for q in quotes} == {"2Y", "5Y"}
    two_yes = next(q for q in quotes if q["label"].startswith("2Y") and q["side"] == "yes")
    assert two_yes["fair"] > 0.7 and "CNBC 2Y" in two_yes["why"]
    early = dt.datetime(2026, 11, 18, 17, tzinfo=UTC)                 # not the event day
    quotes, note = bot.model({}, early, list_markets=lambda s: lists[s], live=live,
                             history=lambda now, tenors: hist)
    assert quotes == [] and "settles today" in note
    stale = lambda tenor, now: ("cnbc", 4.85, 3600.0)
    quotes, note = bot.model({}, settle, list_markets=lambda s: lists[s], live=stale,
                             history=lambda now, tenors: hist)
    assert quotes == [] and "min old" in note
    night = dt.datetime(2026, 11, 20, 23, tzinfo=UTC)
    assert bot.model({}, night)[1].startswith("outside the settlement-day window")


def test_tenor_table():
    bot = _bot()
    assert bot.TENORS["2Y"]["yahoo"] is None                          # no Yahoo 2-year index
    assert bot.TENORS["5Y"]["fred"] == "DGS5" and bot.TENORS["30Y"]["series"] == "KXUST30A"
    assert bot.SPEC["floor"] == 0.05 and bot.SPEC["max_open"] == 3
