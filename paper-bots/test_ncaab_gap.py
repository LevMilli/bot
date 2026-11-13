"""NCAAB gap and Sports gap + Polymarket towers. Offline."""
import datetime as dt
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "ncaab-gap-paper"))

import espn_gap_model as gm  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 14, 0, 0, tzinfo=UTC)   # 19:00 ET Nov 13


def _load(folder, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, folder, "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _team(where, abbr, loc, name):
    return {"homeAway": where, "team": {"abbreviation": abbr, "location": loc, "displayName": f"{loc} {name}",
                                        "shortDisplayName": loc}}


def _board(state="in", tip=NOW - dt.timedelta(minutes=30)):
    return {"events": [{"id": "401", "date": tip.strftime("%Y-%m-%dT%H:%MZ"),
                        "status": {"type": {"state": state, "shortDetail": "2nd half"}},
                        "competitions": [{"competitors": [_team("home", "DUKE", "Duke", "Blue Devils"),
                                                          _team("away", "UNC", "North Carolina", "Tar Heels")]}]}]}


def _mk(code, sub, yb, ya, ev="KXNCAAMBGAME-26NOV13UNCDUKE"):
    return {"ticker": f"{ev}-{code}", "event_ticker": ev, "yes_sub_title": sub,
            "yes_bid_dollars": yb, "yes_ask_dollars": ya,
            "no_bid_dollars": round(1 - ya, 2), "no_ask_dollars": round(1 - yb, 2)}


def test_scoreboard_reads_all_division_one():
    assert "groups=50" in gm.scoreboard_url("basketball/mens-college-basketball")
    assert "?" not in gm.scoreboard_url("basketball/nba")


def test_window_match_and_spread():
    game = gm.parse_games(_board())[0]
    assert gm.in_window(game, NOW)
    pre = gm.parse_games(_board("pre", NOW + dt.timedelta(hours=4)))[0]
    assert not gm.in_window(pre, NOW)
    markets = [_mk("DUKE", "Duke", 0.80, 0.82), _mk("UNC", "North Carolina", 0.18, 0.20)]
    pair = gm.match_event(game, markets)
    assert pair["home"]["ticker"].endswith("DUKE") and pair["away"]["ticker"].endswith("UNC")
    assert gm.liquid(pair)
    # A different date never matches.
    assert gm.match_event(game, [_mk("DUKE", "Duke", 0.8, 0.82, "KXNCAAMBGAME-26NOV14UNCDUKE"),
                                 _mk("UNC", "North Carolina", 0.18, 0.2, "KXNCAAMBGAME-26NOV14UNCDUKE")]) is None


def test_fair_sources_and_lane_gate():
    game = gm.parse_games(_board())[0]
    assert gm.home_fair({"winprobability": [{"homeWinPercentage": 0.91}]}, game, NOW) == (0.91, "ESPN live win chance")
    pre = gm.parse_games(_board("pre", NOW + dt.timedelta(hours=1)))[0]
    p, src = gm.home_fair({"pickcenter": [{"homeTeamOdds": {"moneyLine": -400},
                                           "awayTeamOdds": {"moneyLine": 300}}]}, pre, NOW)
    assert src.startswith("ESPN pick-center") and 0.75 < p < 0.80
    assert "lane floor" in gm.lane_gate({"fair": 0.70, "ask": 0.50}, 0.06)
    assert "speed lane" in gm.lane_gate({"fair": 0.76, "ask": 0.70}, 0.06)
    assert gm.lane_gate({"fair": 0.90, "ask": 0.80}, 0.06) is None


def test_ncaab_model_offline_and_floor_locked():
    bot = _load("ncaab-gap-paper", "ncaab_gap_bot")
    assert bot.SPEC["floor"] == 0.06 and bot.SPEC["max_open"] == 6
    markets = [_mk("DUKE", "Duke", 0.80, 0.82), _mk("UNC", "North Carolina", 0.18, 0.20)]
    quotes, note = bot.model({"venue_min_edge": 0.06}, NOW, scoreboard=_board(), markets=markets,
                             summary=lambda eid: {"winprobability": [{"homeWinPercentage": 0.92}]})
    assert len(quotes) == 4 and "1 matched" in note
    duke_yes = next(q for q in quotes if q["ticker"].endswith("DUKE") and q["side"] == "yes")
    assert duke_yes["fair"] == 0.92 and not duke_yes.get("log_only")
    unc_yes = next(q for q in quotes if q["ticker"].endswith("UNC") and q["side"] == "yes")
    assert unc_yes["log_only"]   # fair 0.08 is under the lane floor


def test_sports_gap_poly_needs_both_reads():
    bot = _load("sports-gap-poly-paper", "sports_gap_poly_bot")
    assert bot.SPEC["floor"] == 0.06
    game = gm.parse_games(_board())[0]
    ev = "KXNBAGAME-26NOV13UNCDUKE"
    pair = {"home": _mk("DUKE", "Duke", 0.80, 0.82, ev), "away": _mk("UNC", "North Carolina", 0.18, 0.20, ev)}
    code = ev.split("-", 1)[1]
    poly = {code: {"DUKE": (0.90, 0.01, 50_000.0, "s"), "UNC": (0.10, 0.01, 50_000.0, "s")}}
    rows, why = bot.quotes_for_game("NBA", game, pair, 0.93, "ESPN", poly, 0.06)
    assert not why
    duke_yes = next(q for q in rows if q["ticker"].endswith("DUKE") and q["side"] == "yes")
    assert duke_yes["fair"] == 0.90 and not duke_yes.get("log_only")   # lower of the two
    assert bot.quotes_for_game("NBA", game, pair, 0.93, "ESPN", {}, 0.06) == ([], "no Polymarket game")
    far = {code: {"DUKE": (0.70, 0.01, 50_000.0, "s"), "UNC": (0.30, 0.01, 50_000.0, "s")}}
    rows, _ = bot.quotes_for_game("NBA", game, pair, 0.93, "ESPN", far, 0.06)
    assert all(q["log_only"] and "disagree" in q["log_reason"] for q in rows)
    thin = {code: {"DUKE": (0.90, 0.06, 50_000.0, "s"), "UNC": (0.10, 0.06, 50_000.0, "s")}}
    rows, _ = bot.quotes_for_game("NBA", game, pair, 0.93, "ESPN", thin, 0.06)
    assert all(q["log_only"] and "thin" in q["log_reason"] for q in rows)
