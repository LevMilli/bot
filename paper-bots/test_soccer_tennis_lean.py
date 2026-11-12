"""Soccer & tennis lean tower. Offline."""
import datetime as dt
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "soccer-tennis-lean-paper"))

import match_model as mm  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 21, 6, tzinfo=UTC)


def _bot():
    spec = importlib.util.spec_from_file_location("st_bot", os.path.join(HERE, "soccer-tennis-lean-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pm(title, bid, ask, liq=20000, outcomes=None):
    return {"sportsMarketType": "moneyline", "groupItemTitle": title, "bestBid": bid, "bestAsk": ask,
            "liquidityNum": liq, "outcomes": json.dumps(outcomes or ["Yes", "No"])}


def _soccer_event(slug="epl-mac-ful-2026-11-21", start="2026-11-21T12:30:00Z", lines=None):
    return {"slug": slug, "startTime": start, "markets": lines or [
        _pm("Manchester City FC", 0.67, 0.68), _pm("Draw (Manchester City FC vs. Fulham FC)", 0.18, 0.19),
        _pm("Fulham FC", 0.13, 0.14)]}


def _k(ticker, who, ask="0.60"):
    return {"ticker": ticker, "event_ticker": ticker.rsplit("-", 1)[0], "yes_sub_title": who,
            "yes_ask_dollars": ask, "yes_bid_dollars": "0.10", "no_ask_dollars": "0.90", "no_bid_dollars": "0.40"}


KALSHI_EPL = [_k("KXEPLGAME-26NOV21MCIFUL-MCI", "Manchester City"), _k("KXEPLGAME-26NOV21MCIFUL-TIE", "Tie"),
              _k("KXEPLGAME-26NOV21MCIFUL-FUL", "Fulham")]


def test_names():
    assert mm.same("Brighton", "Brighton & Hove Albion FC")
    assert mm.same("Bayern Munich", "FC Bayern München")
    assert mm.same("M´gladbach", "Borussia Mönchengladbach")
    assert mm.same("Atletico", "Club Atlético de Madrid")
    assert mm.same("PSG", "Paris Saint-Germain FC")
    assert not mm.same("Manchester City", "Manchester United FC")
    assert not mm.same("Real Madrid", "Real Sociedad de Fútbol")
    assert mm.surname_match("Aleksandr Shevchenko", "Alexander Shevchenko")
    assert not mm.surname_match("Aleksandr Shevchenko", "Maria Shevchenko")
    assert not mm.surname_match("Taylor Fritz", "Holger Rune")


def test_soccer_pair_scales_to_one():
    pairs, unmatched = mm.pair("EPL", [_soccer_event()], KALSHI_EPL, NOW)
    assert unmatched == 0 and len(pairs) == 3
    fair = {m["yes_sub_title"]: p for m, p, _ in pairs}
    assert math.isclose(sum(fair.values()), 1.0)
    assert math.isclose(fair["Manchester City"], 0.675 / 1.0, abs_tol=0.01)
    assert fair["Tie"] < fair["Manchester City"]


def test_soccer_skips_props_wide_thin_started_and_ambiguous():
    prop = _soccer_event(slug="epl-mac-ful-2026-11-21-halftime-result")
    assert mm.pair("EPL", [prop], KALSHI_EPL, NOW) == ([], 0)
    wide = _soccer_event(lines=[_pm("Manchester City FC", 0.60, 0.70), _pm("Draw (x)", 0.18, 0.19),
                                _pm("Fulham FC", 0.13, 0.14)])
    assert mm.pair("EPL", [wide], KALSHI_EPL, NOW)[0] == []
    thin = _soccer_event(lines=[_pm("Manchester City FC", 0.67, 0.68, liq=100), _pm("Draw (x)", 0.18, 0.19),
                                _pm("Fulham FC", 0.13, 0.14)])
    assert mm.pair("EPL", [thin], KALSHI_EPL, NOW)[0] == []
    started = dt.datetime(2026, 11, 21, 12, 25, tzinfo=UTC)
    assert mm.pair("EPL", [_soccer_event()], KALSHI_EPL, started) == ([], 0)
    other_day = [dict(m, event_ticker="KXEPLGAME-26NOV28MCIFUL") for m in KALSHI_EPL]
    assert mm.pair("EPL", [_soccer_event()], other_day, NOW) == ([], 1)
    wrong_team = KALSHI_EPL[:2] + [_k("KXEPLGAME-26NOV21MCIFUL-CHE", "Chelsea")]
    assert mm.pair("EPL", [_soccer_event()], wrong_team, NOW) == ([], 1)


def test_tennis_pair():
    event = {"slug": "atp-fritz-rune-2026-11-21", "startTime": "2026-11-21T19:30:00Z",
             "markets": [_pm(None, 0.65, 0.66, outcomes=["Taylor Fritz", "Holger Rune"])]}
    kalshi = [_k("KXATPMATCH-26NOV21FRIRUN-RUN", "Holger Rune"), _k("KXATPMATCH-26NOV21FRIRUN-FRI", "Taylor Fritz")]
    pairs, _ = mm.pair("ATP", [event], kalshi, NOW)
    fair = {m["yes_sub_title"]: p for m, p, _ in pairs}
    assert math.isclose(fair["Taylor Fritz"], 0.655) and math.isclose(fair["Holger Rune"], 0.345)


def test_bot_quotes_and_url():
    bot = _bot()
    quotes, _ = bot.quotes_for("EPL", [_soccer_event()], KALSHI_EPL, NOW)
    assert len(quotes) == 6
    labels = {q["label"] for q in quotes}
    assert "EPL draw" in labels and "EPL Fulham to win" in labels
    url = bot.gamma_url(10365, "tennis", NOW)
    assert "series_id=10365" in url and "end_date_max=2026-12-01T06:00:00Z" in url


def test_registry_and_desk_wiring():
    import desk_profit
    import new_towers
    import pimp_desk

    assert desk_profit.BOT_VENUE["soccer-tennis-lean"] == "kalshi_sports"
    assert desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_sports"] == 0.06
    spec = next(b for b in pimp_desk.BOTS if b["id"] == "soccer-tennis-lean")
    assert spec["shadow_only"]
    assert pimp_desk._account_body("soccer-tennis-lean")["cash"] == 500.0
    assert "soccer-tennis-lean" in new_towers.BY_ID
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("soccer-tennis-lean")["ok"]
