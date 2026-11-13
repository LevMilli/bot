"""Desk report card: one read-only summary of the paper desk for the evening report.

Plan steps 886-925 (Reports and communication). This module only reads tower
views and paper state files. It never buys, sells, sizes, or changes a setting.

What it builds (``report_card``):

- a three-sentence plain summary at the top (step 889)
- each tower's trades, wins, losses, fees and profit today (890)
- early sales vs held-to-the-end results for each 15-minute tower (891)
- fees saved by charging Kalshi's fee once per order (892)
- 50-results progress for every practice (shadow) tower (894)
- the biggest win and the biggest loss, with plain reasons (895)
- errors seen today, in plain words (896)
- a "nothing happened" line with the reason when a tower is quiet (907)
- a number check: tower totals must add up to the desk total, losses included (888, 908, 909)
- the desk stop and open-risk status (914)
- a "questions for Levi" list when a decision is needed (917)
- a health word for every tower: running, paused, error, blocked, idle, research or missing (924)
- a short glossary (923)

``markdown(card)`` turns the card into short, phone-friendly lines (906, 922).
The desk timer logs ``desk report {json}`` every 30 minutes so the evening
report can read the last card of the day from the logs.

Losses always count. Nothing is filtered out of a total.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import sys
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
RESULTS_NEEDED = 50
FIFTEEN_MIN_TOWERS = ("btc15m", "commodity-15m", "more-15m")
CHECK_TOLERANCE = 0.02  # dollars; rounding on many small trades

GLOSSARY = (
    ("Edge", "How much better our fair price is than Kalshi's price, after the fee."),
    ("Floor", "The smallest edge a tower may buy at. Floors are locked and never go lower."),
    ("Fill", "The price a paper buy or sale is booked at."),
    ("Settle", "When the market ends and Kalshi pays $1 per contract on the winning side."),
    ("Early sale", "Selling before the end because the price moved our way."),
    ("Practice tower", "A shadow tower. It spends no desk cash and counts only after 50 settled results."),
)

_CENTRAL = re.compile(
    r"^(January|February|March|April|May|June|July|August|September|October|November|December)"
    r" (\d{1,2}), (\d{4}), (\d{1,2}):(\d{2}) (AM|PM) Central$"
)
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December")


def _num(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def ct_date(text) -> dt.date | None:
    """Central-time date of a stored timestamp (ISO, epoch, or 'Month D, YYYY, H:MM PM Central')."""
    raw = str(text or "").strip()
    if not raw:
        return None
    m = _CENTRAL.match(raw)
    if m:
        return dt.date(int(m.group(3)), _MONTHS.index(m.group(1)) + 1, int(m.group(2)))
    if len(raw) == 10:
        try:
            return dt.date.fromisoformat(raw)
        except ValueError:
            return None
    try:
        when = dt.datetime.fromtimestamp(float(raw), dt.timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        try:
            when = dt.datetime.fromisoformat(raw.replace(" UTC", "+00:00").replace("Z", "+00:00"))
        except ValueError:
            return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return when.astimezone(CT).date()


def _fee_each(price: float) -> float:
    """Old way: Kalshi fee per contract, rounded up to the cent on every contract."""
    p = float(price)
    if not (0.0 < p < 1.0):
        return 0.0
    return math.ceil(round(0.07 * p * (1.0 - p) * 100, 6)) / 100.0


def _fee_once(contracts: int, price: float) -> float:
    """New way: 0.07 x C x P x (1 - P), rounded up once to the cent for the whole order."""
    p, c = float(price), int(contracts)
    if c < 1 or not (0.0 < p < 1.0):
        return 0.0
    return math.ceil(round(0.07 * c * p * (1.0 - p) * 100, 6)) / 100.0


def trade_fees(row: dict) -> dict:
    """Fees on one closed trade: charged, the old per-contract way, and whether it is known.

    Only trades that stored ``order_fee`` (fee once per order, from Nov 13, 2026) count toward
    "fees saved". Older trades report their stored fee as charged when contracts are known.
    """
    contracts = int(_num(row.get("contracts")) or 0)
    ask = _num(row.get("ask") if row.get("ask") is not None else row.get("entry_price"))
    exit_bid = _num(row.get("exit_bid"))
    sold_early = exit_bid is not None and not str(row.get("exit") or "").startswith("settled")
    order_fee = _num(row.get("order_fee"))
    if order_fee is not None and contracts and ask is not None:
        charged = order_fee
        old = contracts * _fee_each(ask)
        if sold_early:
            charged += _fee_once(contracts, exit_bid)
            old += contracts * _fee_each(exit_bid)
        return {"charged": round(charged, 2), "old_way": round(old, 2), "per_order": True, "known": True}
    each = _num(row.get("fee"))
    if each is not None and contracts:
        charged = contracts * each
        exit_fee = _num(row.get("exit_fee"))
        if sold_early:
            charged += contracts * (exit_fee if exit_fee is not None else _fee_each(exit_bid))
        return {"charged": round(charged, 2), "old_way": round(charged, 2), "per_order": False, "known": True}
    return {"charged": 0.0, "old_way": 0.0, "per_order": False, "known": False}


def _is_held(row: dict) -> bool:
    return str(row.get("exit") or row.get("exit_reason") or "").strip().lower().startswith("settle")


def _reason(row: dict) -> str:
    label = str(row.get("label") or row.get("team") or row.get("ticker") or row.get("title") or "a contract").strip()
    side = str(row.get("side") or "").upper()
    how = "held to the end" if _is_held(row) else f"sold early ({row.get('exit') or row.get('exit_reason') or 'exit'})"
    why = str(row.get("why") or "").strip()
    text = f"{side} {label}, {how}".strip()
    if why and not why.lower().startswith(("paper win", "paper loss")):
        text += f". Bought because: {why[:120]}"
    return text


def health_word(view: dict, research: bool = False) -> str:
    if view.get("present") is False:
        return "missing"
    if research:
        return "research"
    if view.get("paused"):
        return "paused"
    status = str(view.get("status") or "")
    if status == "error" or view.get("read_error"):
        return "error"
    if status == "blocked":
        return "blocked"
    if status == "running":
        return "running"
    return "idle"


def quiet_line(view: dict) -> str:
    """Plain 'nothing happened' line with the reason (step 907)."""
    why = str(view.get("skip") or view.get("why") or view.get("idle_copy") or "").strip()
    if view.get("paused"):
        why = "It is paused."
    if not why:
        why = "No buy cleared its rules today."
    return f"No trades today. {why[:160]}"


def tower_card(view: dict, closed_today: list, research: bool = False, settled_all: int | None = None) -> dict:
    """One tower's day. ``closed_today`` are raw closed rows from today (Central day)."""
    rows = [r for r in closed_today if isinstance(r, dict)]
    pnls = [_num(r.get("pnl") if r.get("pnl") is not None else r.get("pnl_usd")) for r in rows]
    known = [p for p in pnls if p is not None]
    fees = [trade_fees(r) for r in rows]
    card = {
        "id": view.get("id"),
        "name": view.get("name") or view.get("id"),
        "shadow_only": bool(view.get("shadow_only")),
        "health": health_word(view, research),
        "trades": len(rows),
        "wins": sum(1 for p in known if p > 0),
        "losses": sum(1 for p in known if p < 0),
        "flat": sum(1 for p in known if p == 0),
        "unknown_result": len(pnls) - len(known),
        "profit": round(sum(known), 2),
        "desk_today": round(_num(view.get("today")) or 0.0, 2),
        "fees": round(sum(f["charged"] for f in fees), 2),
        "fees_unknown": sum(1 for f in fees if not f["known"]),
        "open": int(view.get("open_count") or 0),
        "open_risk": round(_num(view.get("open_risk")) or 0.0, 2),
    }
    per_order = [f for f in fees if f["per_order"]]
    if per_order:
        card["fee_once"] = {
            "trades": len(per_order),
            "charged": round(sum(f["charged"] for f in per_order), 2),
            "old_way": round(sum(f["old_way"] for f in per_order), 2),
            "saved": round(sum(f["old_way"] - f["charged"] for f in per_order), 2),
        }
    if view.get("id") in FIFTEEN_MIN_TOWERS:
        split = {}
        for name, keep in (("held", True), ("sold_early", False)):
            part = [p for r, p in zip(rows, pnls) if p is not None and _is_held(r) == keep]
            split[name] = {"n": len(part), "wins": sum(1 for p in part if p > 0),
                           "losses": sum(1 for p in part if p < 0), "profit": round(sum(part), 2)}
        card["exits"] = split
    if card["shadow_only"] and not research:
        n = int(settled_all if settled_all is not None else 0)
        card["practice"] = {"settled": n, "needed": RESULTS_NEEDED, "counts": n >= RESULTS_NEEDED,
                            "left": max(0, RESULTS_NEEDED - n)}
    if not rows and not research:
        card["quiet"] = quiet_line(view)
    problem = str(view.get("read_error") or view.get("data_error") or "").strip()
    run = view.get("last_run") or {}
    if not problem and run.get("ok") is False:
        problem = str(run.get("error") or run.get("summary") or "The last check did not finish.").strip()
    if problem:
        card["error"] = problem[:200]
    best = worst = None
    for r, p in zip(rows, pnls):
        if p is None:
            continue
        if p > 0 and (best is None or p > best[1]):
            best = (r, p)
        if p < 0 and (worst is None or p < worst[1]):
            worst = (r, p)
    card["_best"] = None if best is None else {"bot": card["id"], "pnl": round(best[1], 2), "why": _reason(best[0])}
    card["_worst"] = None if worst is None else {"bot": card["id"], "pnl": round(worst[1], 2), "why": _reason(worst[0])}
    return card


def check_numbers(cards: list, desk_today: float) -> list:
    """Problems that should stop a report from being sent as-is (steps 908, 909).

    1. Each tower's closed trades must add up to the tower's own today number.
    2. Desk towers (not shadow) must add up to the desk's today number.
    """
    problems = []
    for c in cards:
        if c.get("unknown_result"):
            problems.append(f"{c['name']}: {c['unknown_result']} closed trade(s) have no stored result.")
        if c.get("checked") and abs(c["profit"] - c["desk_today"]) > CHECK_TOLERANCE:
            problems.append(f"{c['name']}: trades add up to ${c['profit']:.2f} but the tower shows "
                            f"${c['desk_today']:.2f} today.")
    desk_sum = round(sum(c["desk_today"] for c in cards if not c.get("shadow_only")), 2)
    if abs(desk_sum - round(desk_today, 2)) > CHECK_TOLERANCE:
        problems.append(f"Desk towers add up to ${desk_sum:.2f} but the desk shows ${desk_today:.2f} today.")
    return problems


def _money(x: float) -> str:
    return f"-${abs(x):,.2f}" if x < 0 else f"+${x:,.2f}"


def summary_sentences(card: dict) -> list:
    """Three plain sentences for the top of the report (step 889)."""
    towers = card["towers"]
    trading = [t for t in towers if t["trades"]]
    desk = [t for t in towers if not t["shadow_only"]]
    shadow = [t for t in towers if t["shadow_only"] and t["trades"]]
    wins = sum(t["wins"] for t in trading)
    losses = sum(t["losses"] for t in trading)
    first = (f"The desk towers made {_money(card['desk_today'])} today and the practice towers made "
             f"{_money(round(sum(t['profit'] for t in shadow), 2))}, losses included.")
    if trading:
        top = max(trading, key=lambda t: t["profit"])
        low = min(trading, key=lambda t: t["profit"])
        second = (f"{len(trading)} towers traded {sum(t['trades'] for t in trading)} times "
                  f"({wins} wins, {losses} losses); {top['name']} did best ({_money(top['profit'])}) and "
                  f"{low['name']} did worst ({_money(low['profit'])}).")
    else:
        second = "No tower closed a trade today."
    errors = [t for t in towers if t["health"] == "error"]
    stop = card["stop"]
    if card["checks"]:
        third = f"The number check found {len(card['checks'])} problem(s), so read the totals with care."
    elif errors:
        third = f"{len(errors)} tower(s) had errors: " + ", ".join(t["name"] for t in errors[:4]) + "."
    elif stop["blocked"]:
        third = "New desk buys are stopped right now: " + stop["reason"]
    else:
        third = (f"No errors, the numbers add up, and {len(desk)} desk towers have "
                 f"${stop['open_risk']:.2f} of ${stop['max_open_risk']:.0f} at risk.")
    return [first, second, third]


def report_card(views: list, closed_by_bot: dict, gate: str, cfg: dict, *, research_ids=(),
                settled_by_bot: dict | None = None, checked_ids=(), now: dt.datetime | None = None,
                city_url: str = "") -> dict:
    """Build the desk report card from tower views plus today's raw closed rows per tower."""
    now = (now or dt.datetime.now(CT)).astimezone(CT)
    settled_by_bot = settled_by_bot or {}
    research_ids = set(research_ids)
    cards = []
    for view in views:
        bot = str(view.get("id") or "")
        c = tower_card(view, closed_by_bot.get(bot) or [], research=bot in research_ids,
                       settled_all=settled_by_bot.get(bot))
        if bot in checked_ids:
            c["checked"] = True
        cards.append(c)
    live = [c for c in cards if not c["shadow_only"]]
    desk_today = round(sum(_num(v.get("today")) or 0.0 for v in views if not v.get("shadow_only")), 2)
    open_risk = round(sum(c["open_risk"] for c in live), 2)
    bests = [c.pop("_best") for c in cards]
    worsts = [c.pop("_worst") for c in cards]
    bests = [b for b in bests if b]
    worsts = [w for w in worsts if w]
    fee_rows = [c["fee_once"] for c in cards if c.get("fee_once")]
    card = {
        "paper_only": True,
        "day": now.date().isoformat(),
        "at_ct": now.strftime("%I:%M %p CT").lstrip("0"),
        "desk_today": desk_today,
        "towers": cards,
        "stop": {
            "blocked": bool(gate),
            "reason": str(gate or ""),
            "open": int(sum(c["open"] for c in live)),
            "max_open": int(cfg.get("max_open_positions") or 12),
            "open_risk": open_risk,
            "max_open_risk": float(cfg.get("max_open_risk") or 100.0),
            "daily_loss_stop": float(cfg.get("daily_loss_stop") or 150.0),
            "loss_room": round(float(cfg.get("daily_loss_stop") or 150.0) + min(0.0, desk_today), 2),
        },
        "biggest_win": max(bests, key=lambda b: b["pnl"]) if bests else None,
        "biggest_loss": min(worsts, key=lambda w: w["pnl"]) if worsts else None,
        "fee_once": {
            "trades": sum(f["trades"] for f in fee_rows),
            "charged": round(sum(f["charged"] for f in fee_rows), 2),
            "old_way": round(sum(f["old_way"] for f in fee_rows), 2),
            "saved": round(sum(f["saved"] for f in fee_rows), 2),
        },
        "errors": [f"{c['name']}: {c['error']}" for c in cards if c.get("error")],
        "health": {c["id"]: c["health"] for c in cards},
        "city_url": city_url,
    }
    card["checks"] = check_numbers(cards, desk_today)
    card["send_ok"] = not card["checks"]
    questions = []
    for c in cards:
        p = c.get("practice") or {}
        if p.get("counts"):
            questions.append(f"{c['name']} has {p['settled']} settled results. Promote it, keep it practicing, "
                             "or retire it? (Needs your OK.)")
    if card["checks"]:
        questions.append("The numbers did not add up. Hold the report until it is checked?")
    card["questions"] = questions
    card["summary"] = summary_sentences(card)
    return card


def log_line(card: dict) -> str:
    """Compact line for the desk log: ``desk report {json}``."""
    slim = dict(card)
    slim["towers"] = [{k: v for k, v in t.items() if k != "quiet" or t.get("health") != "missing"}
                      for t in card["towers"] if t["trades"] or t["open"] or t.get("error") or not t["shadow_only"]
                      or (t.get("practice") or {}).get("settled")]
    slim["quiet_count"] = sum(1 for t in card["towers"] if not t["trades"])
    return "desk report " + json.dumps(slim, sort_keys=True, separators=(",", ":"))


def markdown(card: dict) -> str:
    """Short, phone-friendly report text. Plain words, no tables wider than four columns."""
    out = [f"# Desk report, {card['day']} ({card['at_ct']})", "", "Pretend money only.", ""]
    out += [" ".join(card["summary"]), ""]
    stop = card["stop"]
    out += ["## Desk status",
            f"- Open bets: {stop['open']} of {stop['max_open']}",
            f"- Open risk: ${stop['open_risk']:.2f} of ${stop['max_open_risk']:.0f}",
            f"- Today: {_money(card['desk_today'])} (stop at -${stop['daily_loss_stop']:.0f})",
            f"- New buys: {'stopped. ' + stop['reason'] if stop['blocked'] else 'allowed'}", ""]
    out += ["## Towers", "", "| Tower | Health | W-L | Profit |", "| --- | --- | --- | --- |"]
    for t in card["towers"]:
        if t["trades"] or t["open"] or not t["shadow_only"] or t["health"] == "error":
            out.append(f"| {t['name']} | {t['health']} | {t['wins']}-{t['losses']} | {_money(t['profit'])} |")
    out.append("")
    for t in card["towers"]:
        if t.get("exits"):
            e = t["exits"]
            out.append(f"- {t['name']}: held {e['held']['n']} ({_money(e['held']['profit'])}), "
                       f"sold early {e['sold_early']['n']} ({_money(e['sold_early']['profit'])})")
    fee = card["fee_once"]
    if fee["trades"]:
        out += ["", "## Fee once per order",
                f"{fee['trades']} trades paid ${fee['charged']:.2f}. The old way would have been "
                f"${fee['old_way']:.2f}, so it saved ${fee['saved']:.2f}."]
    out += ["", "## Biggest win and loss"]
    for label, row in (("Win", card["biggest_win"]), ("Loss", card["biggest_loss"])):
        out.append(f"- {label}: none" if not row else f"- {label}: {_money(row['pnl'])}, {row['bot']}. {row['why']}")
    practice = [t for t in card["towers"] if t.get("practice")]
    if practice:
        out += ["", "## Practice towers (50 results to count)"]
        started = [t for t in practice if t["practice"]["settled"]]
        for t in sorted(started, key=lambda t: -t["practice"]["settled"]):
            p = t["practice"]
            out.append(f"- {t['name']}: {p['settled']} of {p['needed']}" + (" (counts now; needs Levi's OK)" if p["counts"] else ""))
        if len(practice) > len(started):
            out.append(f"- {len(practice) - len(started)} more have no settled results yet.")
    quiet = [t for t in card["towers"] if t.get("quiet") and t["health"] != "missing"]
    if quiet:
        out += ["", "## Quiet towers"]
        out += [f"- {t['name']}: {t['quiet']}" for t in quiet if not t["shadow_only"] or t["open"]]
        rest = [t for t in quiet if t["shadow_only"] and not t["open"]]
        if rest:
            out.append(f"- {len(rest)} practice towers made no trades today.")
    out += ["", "## Errors"]
    out += [f"- {e}" for e in card["errors"]] or ["- None today."]
    if card["checks"]:
        out += ["", "## Number check failed"] + [f"- {p}" for p in card["checks"]]
    if card["questions"]:
        out += ["", "## Questions for Levi"] + [f"- {q}" for q in card["questions"]]
    if card.get("city_url"):
        out += ["", f"City page: {card['city_url']}"]
    out += ["", "## Words"] + [f"- {w}: {d}" for w, d in GLOSSARY]
    return "\n".join(out) + "\n"


def wilson_low(wins: int, n: int, z: float = 1.645) -> float | None:
    """Cautious lower bound on the win rate (Wilson, about 95% one-sided). None with no results."""
    if n <= 0:
        return None
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round(max(0.0, (centre - spread) / denom), 4)


def period_card(views: list, rows_by_bot: dict, first_day: dt.date, last_day: dt.date) -> dict:
    """Week or month totals per tower (steps 900-902). Losses included; ranked by profit."""
    towers = []
    for view in views:
        bot = str(view.get("id") or "")
        rows = [r for r in rows_by_bot.get(bot) or [] if isinstance(r, dict)]
        pnls = [p for p in (_num(r.get("pnl") if r.get("pnl") is not None else r.get("pnl_usd")) for r in rows)
                if p is not None]
        if not pnls and not rows:
            continue
        wins = sum(1 for p in pnls if p > 0)
        cost = sum(_num(r.get("cost") if r.get("cost") is not None else r.get("cost_usd")) or 0.0 for r in rows)
        towers.append({
            "id": bot, "name": view.get("name") or bot, "shadow_only": bool(view.get("shadow_only")),
            "trades": len(rows), "wins": wins, "losses": sum(1 for p in pnls if p < 0),
            "profit": round(sum(pnls), 2),
            "fees": round(sum(trade_fees(r)["charged"] for r in rows), 2),
            "win_rate": round(wins / len(pnls), 4) if pnls else None,
            "win_rate_low": wilson_low(wins, len(pnls)),
            "avg_cost": round(cost / len(rows), 2) if rows else None,
        })
    towers.sort(key=lambda t: -t["profit"])
    for rank, t in enumerate(towers, 1):
        t["rank"] = rank
    desk = [t for t in towers if not t["shadow_only"]]
    return {
        "paper_only": True,
        "from": first_day.isoformat(),
        "to": last_day.isoformat(),
        "desk_profit": round(sum(t["profit"] for t in desk), 2),
        "practice_profit": round(sum(t["profit"] for t in towers if t["shadow_only"]), 2),
        "trades": sum(t["trades"] for t in towers),
        "towers": towers,
    }


def period_markdown(card: dict, title: str = "Week") -> str:
    out = [f"# {title} report, {card['from']} to {card['to']}", "", "Pretend money only. Losses included.", "",
           f"Desk towers: {_money(card['desk_profit'])}. Practice towers: {_money(card['practice_profit'])}. "
           f"{card['trades']} trades.", "",
           "| # | Tower | W-L | Profit | Win rate (low) |", "| --- | --- | --- | --- | --- |"]
    for t in card["towers"]:
        rate = "n/a" if t["win_rate"] is None else f"{t['win_rate'] * 100:.0f}% ({t['win_rate_low'] * 100:.0f}%)"
        out.append(f"| {t['rank']} | {t['name']} | {t['wins']}-{t['losses']} | {_money(t['profit'])} | {rate} |")
    out += ["", "Win rate (low) is the cautious lower bound: the real rate is very likely at least this high."]
    return "\n".join(out) + "\n"


if __name__ == "__main__":  # python3 desk_report.py [root] [--json] [--week | --month]
    import pimp_desk

    root = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    if "--week" in sys.argv or "--month" in sys.argv:
        week = "--week" in sys.argv
        built = pimp_desk.desk_period_card(root, days=7 if week else 30)
        print(json.dumps(built, indent=2) if "--json" in sys.argv else period_markdown(built, "Week" if week else "Month"))
    else:
        built = pimp_desk.desk_report_card(root)
        print(json.dumps(built, indent=2) if "--json" in sys.argv else markdown(built))
