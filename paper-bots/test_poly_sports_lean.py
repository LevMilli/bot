"""Poly sports lean tower. Offline."""
import datetime as dt
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "poly-sports-lean-paper"))

import lean_model as lean  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 12, 15, tzinfo=UTC)


def _bot():
    spec = importlib.util.spec_from_file_location("lean_bot", os.path.join(HERE, "poly-sports-lean-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _event(slug, start, bid=0.20, ask=0.21, liq=50000.0, outcomes=("Raptors", "76ers")):
    return {"slug": slug, "startTime": start, "markets": [
        {"sportsMarketType": "spreads", "outcomes": json.dumps(list(outcomes)), "bestBid": 0.5, "bestAsk": 0.51},
        {"sportsMarketType": "moneyline", "outcomes": json.dumps(list(outcomes)),
         "bestBid": bid, "bestAsk": ask, "liquidityNum": liq},
    ]}


def _kalshi(code, teams, asks=("0.12", "0.88")):
    ev = f"KXNBAGAME-{code}"
    return [{"ticker": f"{ev}-{t}", "event_ticker": ev, "yes_sub_title": t.title(),
             "yes_ask_dollars": a, "yes_bid_dollars": "0.10", "no_ask_dollars": "0.90", "no_bid_dollars": "0.86"}
            for t, a in zip(teams, asks)]


def test_event_key_uses_eastern_date_and_aliases():
    # Monday night NFL: slug says the 16th (UTC), Kalshi says the 15th (Eastern)
    ev = {"slug": "nfl-pit-cin-2026-11-16", "startTime": "2026-11-16T01:20:00Z"}
    assert lean.event_key("NFL", ev) == ("26NOV15PITCIN", ["PIT", "CIN"])
    ev = {"slug": "nfl-jax-ten-2026-11-15", "startTime": "2026-11-15T18:00:00Z"}
    assert lean.event_key("NFL", ev)[0] == "26NOV15JACTEN"
    ev = {"slug": "nhl-mon-bos-2026-11-12", "startTime": "2026-11-13T00:00:00Z"}
    assert lean.event_key("NHL", ev)[0] == "26NOV12MTLBOS"
    assert lean.event_key("NBA", {"slug": "nba-player-props-x", "startTime": "2026-11-13T00:00:00Z"}) is None


def test_moneyline_and_quality_filters():
    assert lean.moneyline(_event("x", "t")) == (0.205, 0.01, 50000.0)
    wide = _event("nba-tor-phi-2026-11-12", "2026-11-13T00:00:00Z", bid=0.15, ask=0.25)
    thin = _event("nba-tor-phi-2026-11-12", "2026-11-13T00:00:00Z", liq=500)
    k = _kalshi("26NOV12TORPHI", ("TOR", "PHI"))
    assert lean.pair("NBA", [wide], k, NOW)[0] == []
    assert lean.pair("NBA", [thin], k, NOW)[0] == []


def test_pair_maps_first_outcome_to_first_code():
    ev = _event("nba-tor-phi-2026-11-12", "2026-11-13T00:00:00Z")
    got, unmatched = lean.pair("NBA", [ev], _kalshi("26NOV12TORPHI", ("TOR", "PHI")), NOW)
    assert unmatched == 0
    fair = {m["ticker"].rsplit("-", 1)[1]: p for m, p, _ in got}
    assert fair["TOR"] == 0.205 and abs(fair["PHI"] - 0.795) < 1e-9


def test_pair_window_and_unmatched():
    k = _kalshi("26NOV12TORPHI", ("TOR", "PHI"))
    started = _event("nba-tor-phi-2026-11-12", "2026-11-12T15:02:00Z")
    far = _event("nba-tor-phi-2026-11-12", "2026-11-15T00:00:00Z")
    assert lean.pair("NBA", [started, far], k, NOW) == ([], 0)
    other = _event("nba-chi-cle-2026-11-12", "2026-11-13T00:00:00Z")
    assert lean.pair("NBA", [other], k, NOW) == ([], 1)


def test_quotes_for_buys_lagging_kalshi_side():
    import kalshi_shadow_tower as engine

    bot = _bot()
    ev = _event("nba-tor-phi-2026-11-12", "2026-11-13T00:00:00Z")
    quotes, _ = bot.quotes_for("NBA", [ev], _kalshi("26NOV12TORPHI", ("TOR", "PHI")), NOW)
    tor_yes = next(q for q in quotes if q["ticker"].endswith("TOR") and q["side"] == "yes")
    assert tor_yes["label"] == "NBA Tor to win" and tor_yes["ask"] == 0.12
    cfg = engine.locked_cfg(bot.SPEC)
    assert cfg["venue_min_edge"] == 0.06
    assert engine.decide(tor_yes, cfg)["action"] == "buy"   # 0.205 - 0.12 - fee 0.01 = 0.075
    phi_yes = next(q for q in quotes if q["ticker"].endswith("PHI") and q["side"] == "yes")
    assert engine.decide(phi_yes, cfg)["action"] == "skip"


def test_registry_and_desk_wiring():
    import desk_profit
    import new_towers
    import pimp_desk

    assert desk_profit.BOT_VENUE["poly-sports-lean"] == "kalshi_sports"
    assert desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_sports"] == 0.06
    spec = next(b for b in pimp_desk.BOTS if b["id"] == "poly-sports-lean")
    assert spec["shadow_only"]
    assert pimp_desk._account_body("poly-sports-lean")["cash"] == 500.0
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("poly-sports-lean")["ok"]
