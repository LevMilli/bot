#!/usr/bin/env python3
"""NCAAB gap: shadow paper tower for Kalshi men's college basketball game winners.

Idea B10. The sports gap rules on a league the sports gap tower does not read:
ESPN's live win chance (or, in the 3 hours before tip, ESPN's pick-center
moneylines) is the fair price, and a Kalshi side is bought only when it lags
that fair by the locked sports floor of 0.06 after the Kalshi fee
(``espn_gap_model.py``).

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 6 open, one
per game. Kalshi spread over 5 cents: logged, never bought (most small-school
books). Edge over 0.20: logged, never bought.
Exits: model flip at the bid, settle backstop.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import kalshi_shadow_tower as engine  # noqa: E402
import espn_gap_model as gm  # noqa: E402

SPEC = {"id": "ncaab-gap", "name": "NCAAB gap", "floor": 0.06, "max_open": 6, "max_edge": 0.20,
        "max_ask": 0.92}
PATH = "basketball/mens-college-basketball"
SERIES = "KXNCAAMBGAME"
UA = {"User-Agent": "Mozilla/5.0 (paper)"}  # ESPN refuses longer bot names (HTTP 403)


def quotes_for_game(game: dict, pair: dict, fair_home: float, source: str, floor: float,
                    league: str = "NCAAB") -> list[dict]:
    out = []
    for where, p_yes in (("home", fair_home), ("away", 1.0 - fair_home)):
        market = pair[where]
        team = gm.label_team(game, where)
        wide = gm.spread(market)
        why = (f"{source} {team} {p_yes:.3f} ({game.get('detail') or game.get('state')}); "
               f"Kalshi spread {wide if wide is not None else 'n/a'}")
        for side in engine.sides(market):
            side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
            side["label"] = f"{league} {team} {'to win' if side['side'] == 'yes' else 'not to win'}"
            side["why"] = why
            if wide is None or wide > gm.MAX_SPREAD + 1e-9:
                side["log_only"] = True
                side["log_reason"] = "Kalshi spread over 5 cents (sports gap spread rule); logged"
            else:
                gate = gm.lane_gate(side, floor)
                if gate:
                    side["log_only"], side["log_reason"] = True, gate
            out.append(side)
    return out


def model(cfg: dict, now: dt.datetime, *, scoreboard=None, markets=None, summary=None):
    board = scoreboard if scoreboard is not None else engine.public_json(gm.scoreboard_url(PATH), headers=UA)
    games = [g for g in gm.parse_games(board) if gm.in_window(g, now)]
    if not games:
        return [], "no live or tip-soon college game"
    rows = markets if markets is not None else engine.kalshi_open_markets(SERIES, limit=1000, pages=3)
    matched, unmatched, thin = [], 0, 0
    for game in games:
        pair = gm.match_event(game, rows)
        if pair is None:
            unmatched += 1
        elif not gm.liquid(pair):
            thin += 1
        else:
            matched.append((game, pair))
    order = {id(g): i for i, g in enumerate(gm.priority([g for g, _ in matched], now))}
    quotes, misses = [], 0
    read = summary or (lambda eid: engine.public_json(gm.summary_url(PATH, eid), headers=UA))
    for game, pair in sorted((m for m in matched if id(m[0]) in order), key=lambda m: order[id(m[0])]):
        try:
            got = gm.home_fair(read(game["id"]), game, now)
        except Exception:  # noqa: BLE001 - one game's read failing skips that game
            got = None
        if got is None:
            misses += 1
            continue
        quotes.extend(quotes_for_game(game, pair, got[0], got[1], cfg["venue_min_edge"]))
    note = (f"{len(games)} games in window, {len(matched)} matched with a tight book, "
            f"{thin} wide books skipped, {unmatched} not on Kalshi, {misses} without an ESPN chance")
    return quotes, note


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
