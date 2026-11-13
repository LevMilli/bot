"""ESPN win chance vs Kalshi game winners. Pure logic, no network.

Shared by two shadow towers:

* ``ncaab-gap`` (this folder): the sports gap rules on men's college basketball.
* ``sports-gap-poly``: the same ESPN read, plus Polymarket as a second opinion.

The rules copy the sports gap tower's lane rules so the twins are comparable:

* Fair = ESPN's live win probability during the game; before the game (only in
  the last 3 hours before tip) ESPN's pick-center moneylines with the vig removed.
* Accurate lane: fair at least 0.80. Speed lane: fair 0.72 to 0.80, and then the
  edge must clear the floor by 2 more cents. Below 0.72 is logged, never bought.
* A Kalshi market with a spread over 5 cents is logged, never bought.

Nothing here changes the sports gap tower; this file only reads public data.
"""
from __future__ import annotations

import datetime as dt
import math
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ESPN = "https://site.api.espn.com/apis/site/v2/sports"
PREGAME_WINDOW_MIN = 180
MIN_FAIR_ACCURATE = 0.80
MIN_FAIR_SPEED = 0.72
SPEED_EXTRA_EDGE = 0.02
MAX_SPREAD = 0.05
MAX_SUMMARIES = 25
ALIAS = {"WSH": "WAS", "GS": "GSW", "UTAH": "UTA", "SA": "SAS", "NO": "NOP", "NY": "NYK"}


def scoreboard_url(path: str) -> str:
    url = f"{ESPN}/{path}/scoreboard"
    if "mens-college-basketball" in path:
        url += "?groups=50&limit=400"     # every Division I game, not just the top 25
    elif "college-football" in path:
        url += "?groups=80&limit=300"
    return url


def summary_url(path: str, event_id: str) -> str:
    return f"{ESPN}/{path}/summary?event={event_id}"


def fee(price: float) -> float:
    p = float(price)
    if not 0.0 < p < 1.0:
        return 0.0
    return math.ceil(round(0.07 * p * (1.0 - p) * 100, 6)) / 100.0


def _when(raw):
    try:
        when = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=dt.timezone.utc)


def parse_games(body: dict) -> list[dict]:
    out = []
    for event in (body or {}).get("events") or []:
        try:
            comp = event["competitions"][0]
            teams = {t["homeAway"]: t for t in comp["competitors"]}
            out.append({"id": str(event["id"]), "date": _when(event.get("date")),
                        "state": event["status"]["type"]["state"],
                        "detail": event["status"]["type"].get("shortDetail") or "",
                        "home": teams["home"], "away": teams["away"]})
        except (KeyError, IndexError, TypeError):
            continue
    return [g for g in out if g["date"] is not None]


def minutes_to_tip(game: dict, now: dt.datetime):
    return (game["date"] - now).total_seconds() / 60.0 if game.get("date") else None


def in_window(game: dict, now: dt.datetime) -> bool:
    """Live, or tip within the next 3 hours."""
    if game.get("state") == "in":
        return True
    eta = minutes_to_tip(game, now)
    return game.get("state") == "pre" and eta is not None and 0 < eta <= PREGAME_WINDOW_MIN


def norm(text) -> str:
    s = str(text or "").lower().replace(".", "").replace("&", "and").strip()
    s = s.replace(" st", " state") if s.endswith(" st") else s
    return " ".join(s.split())


def team_matches(market: dict, team: dict) -> bool:
    t = team.get("team") or {}
    code = str(market.get("ticker") or "").rsplit("-", 1)[-1]
    abbr = str(t.get("abbreviation") or "")
    if abbr and (code == abbr or code == ALIAS.get(abbr)):
        return True
    sub = norm(market.get("yes_sub_title"))
    names = {norm(t.get("location")), norm(t.get("displayName")), norm(t.get("shortDisplayName"))}
    names.discard("")
    return bool(sub) and sub in names


def match_event(game: dict, markets: list[dict]):
    """{'home': market, 'away': market} for this ESPN game, or None (must be exactly one event)."""
    day = game["date"].astimezone(ET).strftime("%y%b%d").upper()
    by_event: dict = {}
    for m in markets or []:
        ev = str(m.get("event_ticker") or "")
        part = ev.split("-", 1)[1] if "-" in ev else ""
        if part[:7] == day:
            by_event.setdefault(ev, []).append(m)
    hits = []
    for rows in by_event.values():
        if len(rows) != 2:
            continue
        home = [m for m in rows if team_matches(m, game["home"])]
        away = [m for m in rows if team_matches(m, game["away"])]
        if len(home) == 1 and len(away) == 1 and home[0] is not away[0]:
            hits.append({"home": home[0], "away": away[0]})
    return hits[0] if len(hits) == 1 else None


def _num(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def spread(market: dict):
    bid, ask = _num(market.get("yes_bid_dollars")), _num(market.get("yes_ask_dollars"))
    if bid is None or ask is None:
        return None
    return round(ask - bid, 4)


def liquid(pair: dict) -> bool:
    """At least one of the two Kalshi markets has a spread of 5 cents or less."""
    return any((spread(m) is not None and spread(m) <= MAX_SPREAD + 1e-9) for m in pair.values())


def ml_to_prob(ml) -> float:
    ml = float(ml)
    return 100.0 / (ml + 100.0) if ml > 0 else -ml / (-ml + 100.0)


def pregame_home(summary: dict):
    """Vig-free home chance from ESPN pick-center moneylines."""
    try:
        pc = (summary.get("pickcenter") or [])[0]
        ph = ml_to_prob(pc["homeTeamOdds"]["moneyLine"])
        pa = ml_to_prob(pc["awayTeamOdds"]["moneyLine"])
    except (IndexError, KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    return ph / (ph + pa) if ph + pa > 0 else None


def live_home(summary: dict):
    wp = (summary or {}).get("winprobability") or []
    if not wp:
        return None
    return _num(wp[-1].get("homeWinPercentage"))


def home_fair(summary: dict, game: dict, now: dt.datetime):
    """(home chance, source) or None. Live WP in game; pick-center only in the 3 hours before tip."""
    if game.get("state") == "in":
        p = live_home(summary)
        return (p, "ESPN live win chance") if p is not None and 0.0 < p < 1.0 else None
    if in_window(game, now):
        p = pregame_home(summary)
        return (p, "ESPN pick-center moneyline") if p is not None and 0.0 < p < 1.0 else None
    return None


def lane_gate(side: dict, floor: float):
    """None when the sports-gap lane rules allow a buy; else the log-only reason."""
    fair, ask = _num(side.get("fair")), _num(side.get("ask"))
    if fair is None or ask is None:
        return None
    if fair + 1e-12 < MIN_FAIR_SPEED:
        return f"fair {fair:.2f} under the 0.72 lane floor (sports gap rule); logged"
    if fair + 1e-12 < MIN_FAIR_ACCURATE:
        edge = fair - ask - fee(ask)
        need = float(floor) + SPEED_EXTRA_EDGE
        if edge + 1e-12 < need:
            return f"speed lane (fair {fair:.2f}) needs edge {need:.2f}; has {edge:.3f}"
    return None


def priority(games: list[dict], now: dt.datetime) -> list[dict]:
    """Live games first, then the soonest tips. Capped at MAX_SUMMARIES reads."""
    live = [g for g in games if g.get("state") == "in"]
    soon = sorted((g for g in games if g.get("state") == "pre"), key=lambda g: g["date"])
    return (live + soon)[:MAX_SUMMARIES]


def label_team(game: dict, where: str) -> str:
    t = game[where].get("team") or {}
    return str(t.get("shortDisplayName") or t.get("abbreviation") or where)
