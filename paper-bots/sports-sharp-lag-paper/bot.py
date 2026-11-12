#!/usr/bin/env python3
"""Sports Sharp Lag — shadow paper tower.

Compares a sharp-book fair (fixture or injected quotes) to the Kalshi ask.
Buys only when lag edge after Kalshi fee clears the locked sports floor 0.06.

Paper only. Shadow only. Spends no desk cash. Never LIVE.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
LOCKED_FLOOR = 0.06
STAKE_USD = 25.0
STARTER_CASH = 500.0


def locked_cfg(raw: dict | None = None) -> dict:
    cfg = dict(raw or {})
    floor = float(cfg.get("venue_min_edge") or LOCKED_FLOOR)
    cfg["venue_min_edge"] = max(LOCKED_FLOOR, floor)
    cfg["paper_only"] = True
    cfg["live_orders"] = False
    cfg["shadow_only"] = True
    cfg["stake_usd"] = float(cfg.get("stake_usd") or STAKE_USD)
    cfg["starter_cash"] = float(cfg.get("starter_cash") or STARTER_CASH)
    cfg["max_open"] = int(cfg.get("max_open") or 1)
    return cfg


def kalshi_fee_per_contract(ask: float) -> float:
    """Same ceil(0.07·p·(1-p)) dollars per $1 contract as desk_roi_plan."""
    p = float(ask)
    if not (0.0 < p < 1.0) or not math.isfinite(p):
        return 0.0
    raw = 0.07 * p * (1.0 - p)
    return math.ceil(round(raw * 100, 6)) / 100.0


def lag_decision(quote: dict, cfg: dict | None = None) -> dict:
    """Fee-aware sharp→Kalshi lag decision for one quote row."""
    cfg = locked_cfg(cfg)
    fair = _num(quote.get("sharp_fair") if quote.get("sharp_fair") is not None else quote.get("fair"))
    ask = _num(quote.get("ask"))
    game = str(quote.get("game") or quote.get("ticker") or "game")
    row = {
        "game": game,
        "ticker": str(quote.get("ticker") or ""),
        "league": str(quote.get("league") or ""),
        "source": str(quote.get("source") or ""),
        "action": "skip",
        "reason": "",
        "sharp_fair": fair,
        "ask": ask,
        "fee": None,
        "edge": None,
        "floor": cfg["venue_min_edge"],
        "paper_only": True,
        "shadow_only": True,
    }
    if fair is None or ask is None:
        row["reason"] = "need sharp_fair + ask"
        return row
    if not (0.0 < ask < 1.0) or not (0.0 < fair < 1.0):
        row["reason"] = "fair/ask out of range"
        return row
    fee = kalshi_fee_per_contract(ask)
    edge = fair - ask - fee
    row["fee"] = round(fee, 4)
    row["edge"] = round(edge, 4)
    if edge + 1e-12 < float(cfg["venue_min_edge"]):
        row["reason"] = (
            f"lag edge {edge:.4f} < floor {cfg['venue_min_edge']:g} "
            f"(fair {fair:.3f} ask {ask:.3f} fee {fee:.4f})"
        )
        return row
    row["action"] = "buy"
    row["reason"] = (
        f"sharp lag clears floor: fair {fair:.3f} ask {ask:.3f} "
        f"fee {fee:.4f} edge {edge:.4f}"
    )
    return row


def load_quotes(tower: str) -> list[dict]:
    """Optional fixture file. Empty → waiting on sharp book (no invent)."""
    path = os.path.join(tower, "sharp_quotes.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        data = data.get("quotes") or data.get("rows") or []
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def quotes_from_matched(matched: list[dict]) -> list[dict]:
    """Build lag quote rows from ESPN fair + Kalshi asks. Skip incomplete legs."""
    out = []
    for row in matched or []:
        if not isinstance(row, dict):
            continue
        fair_home = _num(row.get("fair_home") if row.get("fair_home") is not None else row.get("sharp_fair_home"))
        home_ask = _num(row.get("home_ask"))
        away_ask = _num(row.get("away_ask"))
        game = str(row.get("game") or row.get("name") or "game")
        league = str(row.get("league") or "")
        if fair_home is None:
            continue
        if home_ask is not None and 0.0 < home_ask < 1.0:
            out.append({
                "game": f"{game} HOME",
                "sharp_fair": round(float(fair_home), 4),
                "ask": round(float(home_ask), 4),
                "side": "home",
                "league": league,
                "ticker": str(row.get("home_ticker") or ""),
                "source": str(row.get("source") or "espn_fair"),
            })
        if away_ask is not None and 0.0 < away_ask < 1.0:
            out.append({
                "game": f"{game} AWAY",
                "sharp_fair": round(1.0 - float(fair_home), 4),
                "ask": round(float(away_ask), 4),
                "side": "away",
                "league": league,
                "ticker": str(row.get("away_ticker") or ""),
                "source": str(row.get("source") or "espn_fair"),
            })
    return out


def write_sharp_quotes(tower: str, quotes: list[dict], *, note: str = "") -> str:
    path = os.path.join(tower, "sharp_quotes.json")
    payload = {
        "paper_only": True,
        "shadow_only": True,
        "fee_floors_locked": True,
        "floor": LOCKED_FLOOR,
        "note": note or "ESPN/de-vig fair vs Kalshi ask — never invent",
        "quotes": list(quotes or []),
    }
    _write_json(path, payload)
    return path


def harvest_from_matched(
    desk_root: str | None,
    matched: list[dict],
    *,
    note: str = "",
) -> dict:
    """Write sharp_quotes.json from matched fair/ask rows. No network. No invent."""
    desk_root = desk_root or DESK_ROOT
    tower = os.path.join(desk_root, "sports-sharp-lag-paper")
    os.makedirs(tower, exist_ok=True)
    quotes = quotes_from_matched(matched)
    path = write_sharp_quotes(
        tower,
        quotes,
        note=note or "harvested matched fair/ask rows",
    )
    return {
        "ok": True,
        "paper_only": True,
        "shadow_only": True,
        "fee_floors_locked": True,
        "path": path,
        "n": len(quotes),
        "matched_n": len(matched or []),
        "quotes": quotes,
        "note": "Incomplete fair/ask legs skipped — no invent",
    }


def empty_state(cfg: dict) -> dict:
    return {
        "cash": float(cfg["starter_cash"]),
        "open": [],
        "closed": [],
        "paper_only": True,
        "shadow_only": True,
        "live_orders": False,
        "checks": 0,
    }


def run_once(
    desk_root: str | None = None,
    cfg: dict | None = None,
    quotes: list | None = None,
    now: dt.datetime | None = None,
) -> int:
    desk_root = desk_root or DESK_ROOT
    tower = os.path.join(desk_root, "sports-sharp-lag-paper")
    os.makedirs(tower, exist_ok=True)
    cfg = locked_cfg(cfg or _read_json(os.path.join(tower, "config.json")) or {})
    now = now or dt.datetime.now(dt.timezone.utc)
    state = _read_json(os.path.join(tower, "paper_account.json")) or empty_state(cfg)
    state.setdefault("open", [])
    state.setdefault("closed", [])
    state["paper_only"] = True
    state["shadow_only"] = True
    state["live_orders"] = False
    feed = None
    if quotes is not None:
        rows = list(quotes)
    else:
        rows, feed = _live_or_file(tower, now)
    settled = settle_open(state, now)
    held = {str(p.get("kalshi_ticker") or "") for p in state.get("open") or []}
    decisions = [lag_decision(row, cfg) for row in rows]
    for decision in decisions:
        if decision.get("action") == "buy" and decision.get("ticker") in held:
            decision["action"] = "skip"
            decision["reason"] = "already holding this side"
    bought = None
    blocked = os.environ.get("DESK_BLOCK_ENTRIES") == "1"
    if blocked:
        for decision in decisions:
            if decision.get("action") == "buy":
                decision["action"] = "skip"
                decision["reason"] = "desk entry gate"
    open_n = len(state.get("open") or [])
    if open_n >= int(cfg["max_open"]):
        for decision in decisions:
            if decision.get("action") == "buy":
                decision["action"] = "skip"
                decision["reason"] = "max open"
    else:
        for decision in decisions:
            if decision.get("action") != "buy":
                continue
            cash = float(state.get("cash") or 0)
            stake = float(cfg["stake_usd"])
            if cash + 1e-9 < stake:
                decision["action"] = "skip"
                decision["reason"] = "shadow cash below ticket"
                continue
            per = float(decision.get("ask") or 0) + float(decision.get("fee") or 0)
            contracts = int(stake // per) if per > 0 else 0
            if contracts < 1:
                decision["action"] = "skip"
                decision["reason"] = "ticket buys no contract"
                continue
            cost = round(contracts * per, 2)
            state["cash"] = round(cash - cost, 4)
            state["open"].append({
                "ticker": decision.get("game"),
                "kalshi_ticker": decision.get("ticker"),
                "league": decision.get("league"),
                "source": decision.get("source"),
                "side": "buy",
                "contracts": contracts,
                "fee": decision.get("fee"),
                "cost": cost,
                "ask": decision.get("ask"),
                "sharp_fair": decision.get("sharp_fair"),
                "edge": decision.get("edge"),
                "opened": now.isoformat(timespec="seconds"),
                "paper_only": True,
                "shadow_only": True,
                "exit_plan": {
                    "kind": "model-flip+settle",
                    "fee_floors_locked": True,
                    "note": "shadow sharp-lag; staff settle backstop",
                },
            })
            bought = decision.get("game")
            break
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    _write_json(os.path.join(tower, "paper_account.json"), state)
    _append_research(tower, now, decisions)
    for row in settled:
        print(f"SETTLE: {row.get('ticker')} {row.get('result')} pnl {row.get('pnl'):+.2f}")
    if bought:
        print(f"SIGNAL: BUY {bought}")
        print(f"CARD: paper buy {bought} sharp lag")
    elif not decisions:
        note = (feed or {}).get("note") or "waiting on sharp book quotes"
        print(f"SIGNAL: SKIP {note}")
        print(f"CARD: {note} (no invent)")
        print("no trade")
    else:
        first = decisions[0]
        print(f"SIGNAL: SKIP {first.get('game')} {first.get('reason')}")
        print("CARD: " + str(first.get("reason") or "no fee-clear sharp lag"))
        print("no trade")
    return 0


def _live_or_file(tower: str, now: dt.datetime):
    """Live Pinnacle-vs-Kalshi quotes when ODDS_API_KEY is set, else the file."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    try:
        import odds_feed
    except Exception:  # noqa: BLE001
        return load_quotes(tower), None
    if not odds_feed.api_key():
        return load_quotes(tower), {"note": "waiting on ODDS_API_KEY (no sharp book wired)"}
    quotes, status = odds_feed.live_quotes(tower, now)
    try:
        write_sharp_quotes(tower, quotes, note=f"live {status.get('bookmaker')} vs Kalshi ask")
    except OSError:
        pass
    if not quotes and not status.get("note"):
        status["note"] = (
            f"no matched pre-game lines ({status.get('unmatched', 0)} unmatched, "
            f"leagues {','.join(status.get('leagues') or []) or 'none'})"
        )
    return quotes, status


def _kalshi_market(ticker: str) -> dict:
    if DESK_ROOT not in sys.path:
        sys.path.insert(0, DESK_ROOT)
    import public_http
    url = f"https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}"
    data = json.loads(public_http.read(url, timeout=10).decode("utf-8"))
    return data.get("market") or {}


def settle_open(state: dict, now: dt.datetime, fetch=None) -> list:
    """Close shadow rows whose Kalshi market has a result. $1 per contract on YES."""
    fetch = fetch or _kalshi_market
    closed = []
    keep = []
    for pos in state.get("open") or []:
        ticker = str(pos.get("kalshi_ticker") or "")
        if not ticker:
            keep.append(pos)
            continue
        try:
            market = fetch(ticker)
        except Exception:  # noqa: BLE001
            keep.append(pos)
            continue
        result = str(market.get("result") or "").lower()
        if result not in ("yes", "no"):
            keep.append(pos)
            continue
        contracts = int(pos.get("contracts") or 0)
        payout = float(contracts) if result == "yes" else 0.0
        cost = float(pos.get("cost") or 0)
        row = dict(pos)
        row.update({
            "result": result,
            "payout": round(payout, 2),
            "pnl": round(payout - cost, 2),
            "closed": now.isoformat(timespec="seconds"),
            "exit": "settled",
        })
        state["cash"] = round(float(state.get("cash") or 0) + payout, 4)
        state.setdefault("closed", []).append(row)
        closed.append(row)
    state["open"] = keep
    return closed


def _num(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def _read_json(path: str):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def _append_research(tower: str, now: dt.datetime, decisions: list) -> None:
    path = os.path.join(tower, "research.jsonl")
    rows = []
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as handle:
                rows = handle.readlines()[-1999:]
        except OSError:
            rows = []
    for decision in decisions:
        rows.append(json.dumps({
            "at": now.isoformat(timespec="seconds"),
            "game": decision.get("game"),
            "action": decision.get("action"),
            "reason": decision.get("reason"),
            "sharp_fair": decision.get("sharp_fair"),
            "ask": decision.get("ask"),
            "edge": decision.get("edge"),
            "paper_only": True,
        }) + "\n")
    if not decisions:
        rows.append(json.dumps({
            "at": now.isoformat(timespec="seconds"),
            "action": "skip",
            "reason": "waiting on sharp book",
            "paper_only": True,
        }) + "\n")
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.writelines(rows[-2000:])
    except OSError:
        return


def harvest_live(desk_root: str | None = None) -> dict:
    """Pull tip-soon ESPN fair + Kalshi asks via sports-gap helpers. Opt-in only.

    Skips any game missing fair or asks. Never invents quotes. Floor stays 0.06.
    """
    desk_root = desk_root or DESK_ROOT
    if desk_root not in sys.path:
        sys.path.insert(0, desk_root)
    gap_dir = os.path.join(desk_root, "sports-gap-paper")
    if gap_dir not in sys.path:
        sys.path.insert(0, gap_dir)
    try:
        import gap_bot
    except Exception as exc:
        return {
            "ok": False,
            "paper_only": True,
            "reason": f"gap_bot import failed: {exc.__class__.__name__}",
            "n": 0,
            "quotes": [],
        }
    matched = []
    skipped = []
    sports = getattr(gap_bot, "SPORTS", None) or {}
    if not isinstance(sports, dict):
        return {
            "ok": False,
            "paper_only": True,
            "reason": "gap_bot.SPORTS missing",
            "n": 0,
            "quotes": [],
        }
    for league, meta in sports.items():
        try:
            path, series = meta[0], meta[1]
            if hasattr(gap_bot, "espn_games"):
                games = gap_bot.espn_games(path)
            else:
                scoreboard = gap_bot.get(f"{gap_bot.ESPN}/{path}/scoreboard")
                games = []
                for ev in (scoreboard or {}).get("events") or []:
                    comps = ((ev.get("competitions") or [{}])[0])
                    state = str((comps.get("status") or {}).get("type", {}).get("state") or "")
                    g = {
                        "date": ev.get("date"),
                        "state": "in" if state == "in" else state,
                        "home": {},
                        "away": {},
                        "id": ev.get("id"),
                    }
                    for c in comps.get("competitors") or []:
                        if c.get("homeAway") == "home":
                            g["home"] = c
                        elif c.get("homeAway") == "away":
                            g["away"] = c
                    games.append(g)
            markets = gap_bot.kalshi_markets(series)
            for g in games:
                if not isinstance(g, dict) or not g.get("home") or not g.get("away"):
                    skipped.append("no teams")
                    continue
                state = str(g.get("state") or "")
                if state != "in" and not gap_bot.tip_within_minutes(g):
                    continue
                name = (
                    f"{(g['away'].get('team') or {}).get('abbreviation', '?')} @ "
                    f"{(g['home'].get('team') or {}).get('abbreviation', '?')}"
                )
                pair = gap_bot.match_event(g, markets)
                if not pair:
                    skipped.append("no Kalshi match")
                    continue
                eid = g.get("id") or g.get("event_id")
                try:
                    summ = gap_bot.espn_summary(path, eid) if eid else {}
                except Exception:
                    summ = {}
                fair = None
                if state != "in":
                    fair = gap_bot.espn_pregame_fair_home(summ or {})
                else:
                    try:
                        fair = gap_bot.espn_fair_home(summ or {}, g)
                    except Exception:
                        fair = gap_bot.espn_pregame_fair_home(summ or {})
                if fair is None:
                    skipped.append("no fair")
                    continue
                ha = gap_bot.px(pair["home"], "yes_ask_dollars")
                aa = gap_bot.px(pair["away"], "yes_ask_dollars")
                if ha is None or aa is None:
                    skipped.append("no ask")
                    continue
                matched.append({
                    "game": name,
                    "league": league,
                    "fair_home": fair,
                    "home_ask": ha,
                    "away_ask": aa,
                    "home_ticker": (pair["home"] or {}).get("ticker"),
                    "away_ticker": (pair["away"] or {}).get("ticker"),
                    "source": "espn_fair",
                })
        except Exception as exc:
            skipped.append(exc.__class__.__name__)
            continue
    out = harvest_from_matched(
        desk_root,
        matched,
        note="live ESPN fair + Kalshi ask harvest (tip-soon/live only)",
    )
    out["skipped_n"] = len(skipped)
    out["live_harvest"] = True
    return out


def main() -> int:
    if "--reset" in sys.argv:
        path = os.path.join(HERE, "paper_account.json")
        if os.path.isfile(path):
            os.remove(path)
        print("reset paper account")
        return 0
    if "--harvest" in sys.argv:
        out = harvest_live(DESK_ROOT)
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if out.get("ok") else 1
    return run_once()


if __name__ == "__main__":
    raise SystemExit(main())
