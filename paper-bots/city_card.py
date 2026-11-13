"""Plain-words city cards for APEX-CITY (plan steps 806-885, the city page).

Read only. This module looks at the snapshot rows the desk already built and
adds a ``card`` dict to each tower plus a ``city`` dict on the desk row. It
never changes a tower's entry, exit, sizing, edge, fills, caps, timers or
settlement math. It does not write any file.

Losses always count. Every settled row from today is in the counts and the
sums, wins and losses alike.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Iterable

# Results a practice (shadow) tower needs before its numbers count.
SHADOW_RESULTS_NEEDED = 50

# Districts on the city map (plan step 864). Plain signs (step 865).
DISTRICTS = ("vault", "sports", "crypto", "markets", "weather", "research")
DISTRICT_SIGNS = {
    "vault": "Vault district (desk towers)",
    "sports": "Sports district",
    "crypto": "Crypto district",
    "markets": "Markets district",
    "weather": "Weather district",
    "research": "Research district",
}

# Exit words that mean the tower sold before the market settled.
_EARLY_WORDS = (
    "sold", "bid", "take-profit", "take profit", "model-flip", "model flip", "flip",
    "trail", "stop", "gap-decay", "gap closed", "early",
)
_HELD_WORDS = ("settled", "settle", "expired", "held", "final", "result")

_LEARN_RE = re.compile(r"learning skip|paper bucket has \d+/\d+ hits|\(learn v2\)", re.I)


def _num(value) -> float | None:
    try:
        if value is None or value == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:  # NaN
        return None
    return out


def district_for(bot: dict, spec: dict | None = None) -> str:
    """Which district a tower stands in. Desk towers (they spend vault cash) are the vault."""
    spec = spec or {}
    bid = str(bot.get("id") or "")
    kind = str(spec.get("kind") or "").lower()
    cat = str(spec.get("category") or "").lower()
    if cat == "research" or bid in ("wall-street",):
        return "research"
    if not bot.get("shadow_only"):
        return "vault"
    if kind == "sports" or cat == "sports" or "sport" in bid or bid in ("point-spread", "game-total", "exclusive-set"):
        return "sports"
    if cat == "weather" or "weather" in bid:
        return "weather"
    if cat == "crypto" or kind in ("btc", "meme", "spot", "carry") or "15m" in bid or "btc" in bid or "crypto" in bid:
        return "crypto"
    return "markets"


def _is_early(row: dict) -> bool:
    words = " ".join(str(row.get(k) or "") for k in ("exit_reason", "exit", "result_reason")).lower()
    if any(w in words for w in _HELD_WORDS) and not any(w in words for w in ("sold", "bid")):
        return False
    return any(w in words for w in _EARLY_WORDS)


def _row_day(row: dict, ct_date) -> dt.date | None:
    for key in ("settled_at", "closed_at_iso", "when_iso", "closed_at", "when", "day"):
        raw = row.get(key)
        if not raw:
            continue
        day = ct_date(raw)
        if day is not None:
            return day
        parsed = _central_day(str(raw))
        if parsed is not None:
            return parsed
    return None


_CENTRAL = re.compile(
    r"^(January|February|March|April|May|June|July|August|September|October|November|December)"
    r" (\d{1,2}), (\d{4})"
)
_MONTHS = {m: i + 1 for i, m in enumerate((
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
))}


def _central_day(text: str) -> dt.date | None:
    """'November 13, 2026, 8:56 PM Central' is already a Central wall clock."""
    m = _CENTRAL.match(text.strip())
    if not m:
        return None
    try:
        return dt.date(int(m.group(3)), _MONTHS[m.group(1)], int(m.group(2)))
    except ValueError:
        return None


def _short(row: dict) -> str:
    what = row.get("what") or row.get("title") or row.get("team") or row.get("ticker") or row.get("game") or "trade"
    return str(what)[:80]


def today_stats(history: Iterable[dict], day: dt.date, ct_date) -> dict:
    """Today's settled results for one tower. Losses are counted and summed like wins."""
    wins = losses = flat = early = held = 0
    pnl = fees = 0.0
    early_pnl = held_pnl = 0.0
    best = worst = None
    for row in history or []:
        if not isinstance(row, dict):
            continue
        if _row_day(row, ct_date) != day:
            continue
        value = _num(row.get("pnl"))
        fee = _num(row.get("fee")) or 0.0
        fees += abs(fee)
        if value is None:
            continue
        pnl += value
        if value > 0:
            wins += 1
        elif value < 0:
            losses += 1
        else:
            flat += 1
        if _is_early(row):
            early += 1
            early_pnl += value
        else:
            held += 1
            held_pnl += value
        if best is None or value > best["pnl"]:
            best = {"what": _short(row), "pnl": round(value, 2)}
        if worst is None or value < worst["pnl"]:
            worst = {"what": _short(row), "pnl": round(value, 2)}
    settled = wins + losses + flat
    return {
        "settled": settled,
        "wins": wins,
        "losses": losses,
        "flat": flat,
        "pnl": round(pnl, 2),
        "fees": round(fees, 2),
        "early_sales": early,
        "early_pnl": round(early_pnl, 2),
        "held": held,
        "held_pnl": round(held_pnl, 2),
        # One trade today: it is the best if it made money, the worst if it lost.
        "best": best if settled > 1 or (best and best["pnl"] > 0) else None,
        "worst": worst if settled > 1 or (worst and worst["pnl"] < 0) else None,
    }


def _schedule(bot_id: str, auto: Iterable[dict]) -> tuple[int | None, list[str]]:
    every = None
    scans: list[str] = []
    for slot in auto or ():
        if slot.get("id") != bot_id:
            continue
        if "every_sec" in slot and every is None and slot.get("action") in ("run", None):
            try:
                every = int(slot["every_sec"])
            except (TypeError, ValueError):
                every = None
        elif slot.get("at_ct") and slot.get("action") == "run":
            scans.append(str(slot["at_ct"]))
    return every, sorted(set(scans))


def _parse_iso(text) -> dt.datetime | None:
    try:
        when = dt.datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return when


def error_line(bot: dict) -> str:
    """A plain error from the last check. Clears itself once a clean check runs."""
    if bot.get("read_error"):
        return "The tower's paper file could not be read."
    if bot.get("data_error"):
        return "The tower's data file looks broken."
    run = bot.get("last_run") if isinstance(bot.get("last_run"), dict) else None
    if not run:
        return ""
    if run.get("ok") or run.get("blocked"):
        return ""
    code = run.get("exit")
    if code in (None, ""):
        return "The last check did not finish (it timed out or stopped)."
    return f"The last check failed (exit code {code})."


def learning_skip_line(bot: dict) -> str:
    for key in ("skip", "why"):
        text = str(bot.get(key) or "")
        if _LEARN_RE.search(text):
            return text[:200]
    return ""


def why_no_trade(bot: dict) -> str:
    """Plain reason the tower did not buy on its last check. Empty when it is holding a trade."""
    if bot.get("present") is False:
        return "The tower is not on this checkout."
    if bot.get("paused"):
        return "Paused by staff."
    if (int(_num(bot.get("open_count")) or 0)) > 0:
        return ""
    for key in ("why", "skip", "idle_copy", "feed"):
        text = str(bot.get(key) or "").strip()
        if text:
            return text[:200]
    return "No buy on the last check. The tower did not say why."


def card_for(bot: dict, *, spec: dict | None, auto, saved_auto: dict, day: dt.date,
             now: dt.datetime, ct_date) -> dict:
    bid = str(bot.get("id") or "")
    every, scans = _schedule(bid, auto)
    next_in = None
    if every:
        prev = _parse_iso((saved_auto or {}).get(f"{bid}:run"))
        if prev is not None:
            next_in = max(0, int(round(every - (now - prev).total_seconds())))
    stats = today_stats(bot.get("history") or [], day, ct_date)
    life = bot.get("lifetime") if isinstance(bot.get("lifetime"), dict) else {}
    lt_trades = int(_num(life.get("trades")) or 0)
    settled_total = max(lt_trades, len(bot.get("history") or []))
    district = district_for(bot, spec)
    progress = None
    if bot.get("shadow_only") and district != "research" and bid != "wall-street":
        progress = {
            "have": settled_total,
            "need": SHADOW_RESULTS_NEEDED,
            "counts": settled_total >= SHADOW_RESULTS_NEEDED,
            # Even after 50 results a move to the desk still needs Levi's OK.
            "note": (
                f"{settled_total} of {SHADOW_RESULTS_NEEDED} results. Numbers count after {SHADOW_RESULTS_NEEDED}."
                if settled_total < SHADOW_RESULTS_NEEDED
                else f"{settled_total} results. Counts now. A move to the desk still needs Levi's OK."
            ),
        }
    return {
        "district": district,
        "every_sec": every,
        "scan_times": scans,
        "next_check_in_sec": next_in,
        "today": stats,
        "trades_today": stats["settled"] + int(_num(bot.get("open_count")) or 0),
        "settled_total": settled_total,
        "progress": progress,
        "why_no_trade": why_no_trade(bot),
        "learning_skip": learning_skip_line(bot),
        "error": error_line(bot),
        "floor": _num(bot.get("venue_min_edge")),
    }


def city_banner(desk: dict, cfg: dict, bots: list[dict]) -> dict:
    """Banner numbers for the top of the city. Real money is always off on this desk."""
    today = _num(desk.get("today")) or 0.0
    stop = _num(cfg.get("daily_loss_stop")) or 150.0
    max_open = int(_num(cfg.get("max_open_positions")) or 12)
    max_risk = _num(cfg.get("max_open_risk")) or 100.0
    life = desk.get("lifetime") if isinstance(desk.get("lifetime"), dict) else {}
    gate = str(desk.get("gate") or "")
    halted = bool(desk.get("paused_all")) or "daily loss stop is hit" in gate.lower()
    return {
        "real_money": "off",
        "today": round(today, 2),
        "lifetime_realized": _num(life.get("realized")),
        "lifetime_wins": int(_num(life.get("wins")) or 0),
        "lifetime_losses": int(_num(life.get("losses")) or 0),
        "stop": round(stop, 2),
        # Distance left before the desk stop fires. Wins do not widen it past the stop.
        "stop_left": round(max(0.0, stop + min(0.0, today)), 2),
        "open_count": int(_num(desk.get("open_count")) or 0),
        "max_open": max_open,
        "open_risk": round(_num(desk.get("open_risk")) or 0.0, 2),
        "max_open_risk": round(max_risk, 2),
        "halted": halted,
        "halt_reason": gate if halted else "",
        "gate": gate,
        "districts": [{"id": d, "sign": DISTRICT_SIGNS[d]} for d in DISTRICTS],
        "results_needed": SHADOW_RESULTS_NEEDED,
    }


def attach(public: list[dict], desk_row: dict, cfg: dict, *, specs: Iterable[dict], auto,
           saved_auto: dict, day: dt.date, now: dt.datetime, ct_date) -> None:
    by_id = {str(s.get("id")): s for s in specs or ()}
    for bot in public:
        bot["card"] = card_for(
            bot, spec=by_id.get(str(bot.get("id") or "")), auto=auto, saved_auto=saved_auto,
            day=day, now=now, ct_date=ct_date,
        )
    desk_row["city"] = city_banner(desk_row, cfg, public)
