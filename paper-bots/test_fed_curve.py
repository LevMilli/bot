"""Fed curve tower. Offline."""
import datetime as dt
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "fed-curve-paper"))

import curve_model as cm  # noqa: E402

UTC = dt.timezone.utc


def _bot():
    spec = importlib.util.spec_from_file_location("fed_curve_bot", os.path.join(HERE, "fed-curve-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_symbols_and_price():
    assert cm.zq_symbol(2026, 12) == "ZQZ26.CBT" and cm.zq_symbol(2027, 1) == "ZQF27.CBT"
    assert abs(cm.rate_from_price(95.93) - 4.07) < 1e-9
    assert cm.rate_from_price("x") is None and cm.rate_from_price(50) is None


def test_meeting_days_from_close_time():
    days = cm.meeting_days([{"close_time": "2026-12-09T18:59:00Z"}, {"close_time": "2027-01-27T18:59:00Z"}])
    assert days == {(2026, 12): 9, (2027, 1): 27}


def test_chain_matches_cme_method():
    avgs = {(2026, 11): 3.878, (2026, 12): 4.07, (2027, 1): 4.165, (2027, 2): 4.32}
    meet = {(2026, 12): 9, (2027, 1): 27}
    curve = cm.chain(avgs, meet, (2026, 11), 13)
    before, after = curve[(2026, 12)]
    assert before == 3.878
    assert abs(after - (4.07 * 31 - 3.878 * 9) / 22) < 1e-9
    # January's meeting is late; February has none, so February's average is the end.
    assert curve[(2027, 1)] == (after, 4.32)


def test_chain_needs_effr_when_meeting_is_this_month():
    avgs = {(2026, 12): 4.07, (2027, 1): 4.165}
    meet = {(2026, 12): 9}
    assert cm.chain(avgs, meet, (2026, 12), 2) == {}
    assert cm.chain(avgs, meet, (2026, 12), 2, effr_now=3.88)[(2026, 12)] == (3.88, 4.165)
    assert cm.chain({(2026, 11): 3.9}, meet, (2026, 11), 13) == {}   # December future missing


def test_odds_split_two_steps():
    p = cm.odds(3.878, 3.878 + 0.27)
    assert abs(p["hike25"] - 0.92) < 1e-9 and abs(p["hike50"] - 0.08) < 1e-9
    assert p["hold"] == cm.CLIP[0] and p["cut25"] == cm.CLIP[0]
    assert cm.odds(4.0, 4.0)["hold"] == cm.CLIP[1]


def _k(ev, out, ya, yb):
    return {"ticker": f"{ev}-{out}", "event_ticker": ev, "yes_ask_dollars": ya, "yes_bid_dollars": yb,
            "no_ask_dollars": round(1 - yb, 2), "no_bid_dollars": round(1 - ya, 2)}


def test_quotes_take_lower_read_and_gate():
    bot = _bot()
    assert bot.SPEC["floor"] == 0.05 and bot.SPEC["max_open"] == 2
    curve = {(2026, 12): (3.878, 4.148), (2027, 1): (4.148, 4.32), (2027, 3): (4.32, 4.32)}
    pm = {(2026, 12, "hike25"): {"fair": 0.885}, (2027, 1, "hike25"): {"fair": 0.30},
          (2027, 3, "hold"): {"fair": 0.95}}
    markets = [_k("KXFEDDECISION-26DEC", "H25", 0.80, 0.78), _k("KXFEDDECISION-27JAN", "H25", 0.59, 0.58),
               _k("KXFEDDECISION-27MAR", "H0", 0.90, 0.88), _k("KXFEDDECISION-27APR", "H0", 0.9, 0.88),
               _k("KXFEDDECISION-26DEC", "C25", 0.02, 0.01)]
    quotes = bot.quotes_for(markets, curve, pm)
    by = {(q["ticker"], q["side"]): q for q in quotes}
    dec = by[("KXFEDDECISION-26DEC-H25", "yes")]
    assert dec["fair"] == 0.885 and not dec.get("log_only")
    assert "differ" in by[("KXFEDDECISION-27JAN-H25", "yes")]["log_reason"]
    assert "too far" in by[("KXFEDDECISION-27MAR-H0", "yes")]["log_reason"]
    assert "Polymarket" in by[("KXFEDDECISION-26DEC-C25", "yes")]["log_reason"]
    assert not any(q["ticker"].startswith("KXFEDDECISION-27APR") for q in quotes)   # no futures


def test_reply_parsers():
    bot = _bot()
    now = dt.datetime(2026, 11, 13, 22, tzinfo=UTC)
    body = {"chart": {"result": [{"meta": {"regularMarketPrice": 95.93, "regularMarketTime": now.timestamp() - 60}}]}}
    rate, age = bot.future_rate(body, now)
    assert abs(rate - 4.07) < 1e-9 and age == 60
    assert bot.future_rate({}, now) is None
    assert bot.effr_rate({"refRates": [{"percentRate": 3.88}]}) == 3.88
