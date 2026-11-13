#!/usr/bin/env python3
"""Sports gap + Polymarket: shadow twin of the sports gap tower with a second opinion.

Idea B11. Same ESPN read and lane rules as sports gap (``espn_gap_model.py``),
but a Kalshi side is bought only when ESPN's chance AND Polymarket's live
moneyline mid for the same game both say Kalshi is behind:

* fair = the lower of the two chances for that side, so both must clear
  ask + Kalshi fee + the locked sports floor 0.06 on their own;
* if ESPN and Polymarket differ by more than 0.15 the row is logged, not bought;
* Polymarket spread must be 4 cents or less and liquidity at least $5k.

Leagues: NBA, NFL, NHL (Polymarket game slugs carry the same team codes as
Kalshi). Live games and the 3 hours before start.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 4 open, one
per game. Exits: model flip at the bid, settle backstop. The sports gap tower
itself is not changed.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE, os.path.join(DESK_ROOT, "ncaab-gap-paper"),
             os.path.join(DESK_ROOT, "poly-sports-lean-paper")):
    if path not in sys.path:
        sys.path.insert(0, path)

import kalshi_shadow_tower as engine  # noqa: E402
import espn_gap_model as gm  # noqa: E402
import lean_model as lean  # noqa: E402 - read-only reuse of the slug matcher

SPEC = {"id": "sports-gap-poly", "name": "Sports gap + Polymarket", "floor": 0.06, "max_open": 4,
        "max_edge": 0.15, "max_ask": 0.92}
# league: (ESPN path, Kalshi series, Polymarket series id)
LEAGUES = {
    "NBA": ("basketball/nba", "KXNBAGAME", lean.LEAGUES["NBA"][0]),
    "NFL": ("football/nfl", "KXNFLGAME", lean.LEAGUES["NFL"][0]),
    "NHL": ("hockey/nhl", "KXNHLGAME", lean.LEAGUES["NHL"][0]),
}
GAMMA = "https://gamma-api.polymarket.com/events?series_id={sid}&active=true&closed=false&limit=500"
UA = {"User-Agent": "Mozilla/5.0 (paper)"}  # ESPN refuses longer bot names (HTTP 403)
PM_MAX_SPREAD = 0.04
PM_MIN_LIQUIDITY = 5_000.0
MAX_DISAGREE = 0.15


def poly_by_code(league: str, events: list[dict]) -> dict:
    """{Kalshi event code: {team code: (chance, spread, liquidity, slug)}} from Polymarket games."""
    out = {}
    for event in events or []:
        key = lean.event_key(league, event)
        line = lean.moneyline(event)
        if key is None or line is None:
            continue
        code, codes = key
        mid, wide, liq = line
        out[code] = {codes[0]: (mid, wide, liq, event.get("slug")),
                     codes[1]: (round(1.0 - mid, 4), wide, liq, event.get("slug"))}
    return out


def quotes_for_game(league: str, game: dict, pair: dict, espn_home: float, source: str,
                    poly: dict, floor: float) -> tuple[list[dict], str]:
    """Quote rows for one matched game, or ([], why not)."""
    code = str(pair["home"].get("event_ticker") or "").split("-", 1)[-1]
    pm = poly.get(code)
    if not pm:
        return [], "no Polymarket game"
    out = []
    for where, espn_p in (("home", espn_home), ("away", 1.0 - espn_home)):
        market = pair[where]
        team_code = str(market.get("ticker") or "").rsplit("-", 1)[-1]
        if team_code not in pm:
            return [], "Polymarket team codes differ"
        poly_p, wide, liq, slug = pm[team_code]
        team = gm.label_team(game, where)
        k_wide = gm.spread(market)
        gap = abs(espn_p - poly_p)
        why = (f"{source} {espn_p:.3f}, Polymarket {slug} {poly_p:.3f} (spread {wide:.2f}, "
               f"liquidity ${liq:,.0f}); {game.get('detail') or game.get('state')}")
        for side in engine.sides(market):
            yes = side["side"] == "yes"
            e_side, p_side = (espn_p, poly_p) if yes else (1.0 - espn_p, 1.0 - poly_p)
            side["fair"] = round(min(e_side, p_side), 4)
            side["espn_fair"], side["poly_fair"] = round(e_side, 4), round(p_side, 4)
            side["label"] = f"{league} {team} {'to win' if yes else 'not to win'}"
            side["why"] = why
            reason = ""
            if wide > PM_MAX_SPREAD + 1e-9 or liq < PM_MIN_LIQUIDITY:
                reason = f"Polymarket book too thin (spread {wide:.2f}, liquidity ${liq:,.0f}); logged"
            elif gap > MAX_DISAGREE + 1e-9:
                reason = f"ESPN and Polymarket disagree by {gap:.2f}; logged, not bought"
            elif k_wide is None or k_wide > gm.MAX_SPREAD + 1e-9:
                reason = "Kalshi spread over 5 cents (sports gap spread rule); logged"
            else:
                reason = gm.lane_gate(side, floor) or ""
            if reason:
                side["log_only"], side["log_reason"] = True, reason
            out.append(side)
    return out, ""


def league_quotes(league: str, now: dt.datetime, floor: float, *, scoreboard=None, markets=None,
                  events=None, summary=None) -> tuple[list[dict], str]:
    path, series, sid = LEAGUES[league]
    board = scoreboard if scoreboard is not None else engine.public_json(gm.scoreboard_url(path), headers=UA)
    games = [g for g in gm.parse_games(board) if gm.in_window(g, now)]
    if not games:
        return [], ""
    rows = markets if markets is not None else engine.kalshi_open_markets(series, limit=1000, pages=2)
    pm_events = events if events is not None else engine.public_json(GAMMA.format(sid=sid), timeout=30)
    poly = poly_by_code(league, pm_events or [])
    read = summary or (lambda eid: engine.public_json(gm.summary_url(path, eid), headers=UA))
    quotes, skipped = [], 0
    for game in gm.priority(games, now):
        pair = gm.match_event(game, rows)
        if pair is None:
            skipped += 1
            continue
        code = str(pair["home"].get("event_ticker") or "").split("-", 1)[-1]
        if code not in poly:
            skipped += 1
            continue
        try:
            got = gm.home_fair(read(game["id"]), game, now)
        except Exception:  # noqa: BLE001 - one game's read failing skips that game
            got = None
        if got is None:
            skipped += 1
            continue
        rows_out, why = quotes_for_game(league, game, pair, got[0], got[1], poly, floor)
        skipped += 1 if why else 0
        quotes.extend(rows_out)
    return quotes, f"{league} {len(games)} in window, {skipped} without both reads"


def model(cfg: dict, now: dt.datetime):
    quotes, notes = [], []
    for league in LEAGUES:
        try:
            got, note = league_quotes(league, now, cfg["venue_min_edge"])
        except Exception as exc:  # noqa: BLE001 - one league failing skips that league
            got, note = [], f"{league} skipped ({type(exc).__name__})"
        quotes.extend(got)
        if note:
            notes.append(note)
    note = "; ".join(notes) or "no live or start-soon game"
    return quotes, note


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
