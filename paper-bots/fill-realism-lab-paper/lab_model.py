"""Fill-realism lab: grade every pretend fill against what really traded.

Research only. It buys nothing and changes no tower. For each tower buy it
reads Kalshi's public trades around the moment of the buy, once, and keeps:

* tape cover: did real trading at our price or better, inside the five
  minutes before our buy, cover our whole contract count? A buy that was not
  covered is one the More 15m tape check would have blocked (steps 205, 202-204).
* tape gap: our price minus the volume-weighted tape price in the same
  minute (219-221). Negative means our pretend fill beat real traders.
* early sales: was there real trading at or above our exit bid near the
  sale (239)?
* maker practice book: would a resting bid one cent under our ask have been
  filled by trades that went THROUGH it (228-237)? Kept apart from the taker
  numbers and never added to any tower.
* spot fills: Coinbase spot vs the next 1-minute candle open (245), QQQ vs the
  next 1-minute bar (246).
* no-fills per tower from the shadow research logs, by plain reason (252-253).

Pure logic here; every network read is passed in.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
if DESK_ROOT not in sys.path:
    sys.path.insert(0, DESK_ROOT)

import fill_realism as fr  # noqa: E402

MAX_READS = 40            # Kalshi trade reads per run (shared gateway)
MAX_SPOT_READS = 10       # Coinbase / Yahoo candle reads per run
MAX_GRADED = 4000         # graded rows kept
RESEARCH_TAIL_BYTES = 600_000
REVIEW_DAYS = 30


def _num(value):
    return fr._num(value)


def _iso(ts):
    return dt.datetime.fromtimestamp(float(ts), dt.timezone.utc).isoformat(timespec="seconds")


def row_key(bot: str, row: dict) -> str:
    return f"{bot}|{row.get('ticker')}|{row.get('side')}|{row.get('opened')}"


def kalshi_buys(bot: str, state: dict) -> list[dict]:
    """Every Kalshi buy on a tower's book, open or closed (losses included)."""
    out = []
    for group in ("open", "closed"):
        for row in (state or {}).get(group) or []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "")
            side = str(row.get("side") or "").lower()
            price = _num(row.get("ask") if row.get("ask") is not None else row.get("entry"))
            opened = fr._epoch(row.get("opened"))
            if not ticker.startswith("KX") or side not in ("yes", "no") or price is None or opened is None:
                continue
            out.append(dict(row, bot=bot, side=side, _price=price, _opened=opened, _group=group))
    return out


def spot_buys(bot: str, state: dict) -> list[dict]:
    out = []
    for group in ("open", "closed"):
        for row in (state or {}).get(group) or []:
            if not isinstance(row, dict):
                continue
            price = _num(row.get("entry_price") if row.get("entry_price") is not None else row.get("entry"))
            opened = fr._epoch(row.get("opened"))
            if price is None or opened is None or str(row.get("ticker") or "").startswith("KX"):
                continue
            out.append(dict(row, bot=bot, _price=price, _opened=opened, _group=group))
    return out


def grade_buy(row: dict, trades: list[dict]) -> dict:
    """One Kalshi buy against the public tape around it."""
    side, price, opened = row["side"], row["_price"], row["_opened"]
    contracts = int(row.get("contracts") or 0)
    cover = fr.tape_cover(trades, side, price, contracts,
                          window_start=opened - fr.SETTINGS["tape_lookback_sec"], decided_at=opened)
    gap = fr.tape_gap(side, price, trades, opened)
    maker_px = round(price - 0.01, 4)
    maker = fr.maker_fill(side, maker_px, contracts,
                          [t for t in trades if (fr.trade_time(t) or 0) <= opened + 300],
                          queue_ahead=float("inf"), placed_at=opened, cancel_after=opened + 300)
    out = {
        "bot": row["bot"], "ticker": row.get("ticker"), "side": side, "price": price,
        "contracts": contracts, "opened": row.get("opened"), "day": _iso(opened)[:10],
        "covered": cover["covered"], "tape_volume": cover["volume"],
        "tape_price": gap["tape_price"], "gap": gap["gap"],
        "fill_check": bool(row.get("fill_check")),
        "maker": {"price": maker_px, "filled": maker["filled"], "status": maker["status"]},
    }
    result = str(row.get("result") or "").lower()
    if row["_group"] == "closed":
        out["pnl"] = _num(row.get("pnl"))
        out["won"] = None if result not in ("yes", "no") else result == side
        exit_bid, closed = _num(row.get("exit_bid")), fr._epoch(row.get("closed"))
        if exit_bid is not None and closed is not None:
            sold = fr.tape_gap(side, exit_bid, trades, closed)
            # For a sale, a tape price below our bid means we sold better than real traders.
            out["sale_gap"] = None if sold["gap"] is None else round(-sold["gap"], 4)
    return out


def grade_spot(row: dict, next_open) -> dict:
    nxt = _num(next_open)
    gap = None if nxt is None or nxt <= 0 else round(row["_price"] / nxt - 1.0, 6)
    return {"bot": row["bot"], "ticker": row.get("ticker"), "price": row["_price"],
            "opened": row.get("opened"), "day": _iso(row["_opened"])[:10],
            "next_open": nxt, "gap_pct": None if gap is None else round(gap * 100, 4)}


def no_fills(root: str, towers, since: float) -> dict:
    """Fill-related skips per shadow tower from research.jsonl since ``since`` (252-253)."""
    out = {}
    for spec in towers or []:
        path = os.path.join(root, spec["folder"], "research.jsonl")
        try:
            size = os.path.getsize(path)
            with open(path, encoding="utf-8") as fh:
                if size > RESEARCH_TAIL_BYTES:
                    fh.seek(size - RESEARCH_TAIL_BYTES)
                    fh.readline()
                lines = fh.readlines()
        except OSError:
            continue
        counts: dict[str, int] = {}
        for line in lines:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if (fr._epoch(rec.get("at")) or 0) < since:
                continue
            for d in rec.get("decisions") or []:
                key = fr.classify_skip((d or {}).get("reason"))
                if key:
                    counts[key] = counts.get(key, 0) + 1
        if counts:
            out[spec["id"]] = {fr.NO_FILL_REASONS[k]: v for k, v in sorted(counts.items())}
    return out


def summarize(graded: dict, spot: dict, today: str) -> dict:
    """Per-tower numbers. Every buy counts, wins and losses alike."""
    towers: dict[str, dict] = {}
    for g in graded.values():
        t = towers.setdefault(g["bot"], {"buys": 0, "covered": 0, "blocked_today": 0, "gaps": [],
                                         "sale_gaps": [], "maker_tries": 0, "maker_filled": 0,
                                         "maker_won": 0, "maker_settled": 0, "taker_won": 0,
                                         "taker_settled": 0, "strict": 0})
        t["buys"] += 1
        t["covered"] += 1 if g["covered"] else 0
        if not g["covered"] and g["day"] == today:
            t["blocked_today"] += 1
        if g.get("gap") is not None:
            t["gaps"].append(g["gap"])
        if g.get("sale_gap") is not None:
            t["sale_gaps"].append(g["sale_gap"])
        t["strict"] += 1 if g.get("fill_check") else 0
        t["maker_tries"] += 1
        filled = (g.get("maker") or {}).get("filled", 0) >= max(1, int(g.get("contracts") or 0))
        t["maker_filled"] += 1 if filled else 0
        if g.get("won") is not None:
            t["taker_settled"] += 1
            t["taker_won"] += 1 if g["won"] else 0
            if filled:
                t["maker_settled"] += 1
                t["maker_won"] += 1 if g["won"] else 0
    out = {}
    for bot, t in sorted(towers.items()):
        gaps = t.pop("gaps")
        sale = t.pop("sale_gaps")
        row = {
            "buys": t["buys"],
            "tape_covered": t["covered"],
            "tape_blocked": t["buys"] - t["covered"],
            "tape_blocked_today": t["blocked_today"],
            "avg_gap_cents": None if not gaps else round(100 * sum(gaps) / len(gaps), 2),
            "gap_n": len(gaps),
            "beats_tape": fr.beats_tape(gaps),
            "avg_sale_gap_cents": None if not sale else round(100 * sum(sale) / len(sale), 2),
            "fill_quality": fr.fill_quality(gaps, [True] * t["covered"]
                                            + [False] * (t["buys"] - t["covered"])),
            "fill_delay": (f"{fr.SETTINGS['requote_seconds']:g}s re-check modelled"
                           if t["strict"] else "no delay modelled"),
            # Maker practice book: separate numbers, never mixed into the tower (236-237).
            "maker_book": {
                "tries": t["maker_tries"], "filled": t["maker_filled"],
                "fill_rate": round(t["maker_filled"] / t["maker_tries"], 3) if t["maker_tries"] else None,
                "filled_win_rate": (round(t["maker_won"] / t["maker_settled"], 3)
                                    if t["maker_settled"] else None),
                "taker_win_rate": (round(t["taker_won"] / t["taker_settled"], 3)
                                   if t["taker_settled"] else None),
            },
        }
        out[bot] = row
    spots: dict[str, dict] = {}
    for s in spot.values():
        if s.get("gap_pct") is None:
            continue
        b = spots.setdefault(s["bot"], {"n": 0, "sum": 0.0})
        b["n"] += 1
        b["sum"] += s["gap_pct"]
    for bot, b in spots.items():
        out.setdefault(bot, {})["spot_vs_next_open_pct"] = round(b["sum"] / b["n"], 4)
        out[bot]["spot_n"] = b["n"]
    return out


def run(states: dict, prior: dict, trades_fetch, now: dt.datetime, *, root: str | None = None,
        shadow_towers=(), candle_fetch=None, max_reads: int = MAX_READS) -> dict:
    """One lab pass. ``trades_fetch(ticker, min_ts, max_ts) -> [trade]``."""
    graded = dict((prior or {}).get("graded") or {})
    spot = dict((prior or {}).get("spot") or {})
    notes, reads, pending = [], 0, 0
    buys = [r for bot, st in sorted(states.items()) for r in kalshi_buys(bot, st)]
    live = {row_key(r["bot"], r) for r in buys}
    for row in sorted(buys, key=lambda r: -r["_opened"]):
        key = row_key(row["bot"], row)
        if key in graded:
            continue
        if reads >= max_reads:
            pending += 1
            continue
        reads += 1
        lo = int(row["_opened"] - fr.SETTINGS["tape_lookback_sec"] - 5)
        closed = fr._epoch(row.get("closed")) or row["_opened"]
        hi = int(max(row["_opened"] + 300, closed + 60))
        try:
            trades = trades_fetch(str(row["ticker"]), lo, hi) or []
        except Exception as exc:  # noqa: BLE001 - try again next run
            notes.append(f"{row['ticker']} tape read failed ({type(exc).__name__})")
            continue
        graded[key] = grade_buy(row, trades)
    spot_rows = [r for bot, st in sorted(states.items()) if bot in ("coinbase-spot", "qqq-momentum")
                 for r in spot_buys(bot, st)]
    live |= {row_key(r["bot"], r) for r in spot_rows}
    spot_reads = 0
    if candle_fetch is not None:
        for row in sorted(spot_rows, key=lambda r: -r["_opened"]):
            key = row_key(row["bot"], row)
            if key in spot or row["_opened"] > now.timestamp() - 120:
                continue
            if spot_reads >= MAX_SPOT_READS:
                pending += 1
                continue
            spot_reads += 1
            try:
                nxt = candle_fetch(row["bot"], str(row.get("ticker") or ""), row["_opened"])
            except Exception as exc:  # noqa: BLE001
                notes.append(f"{row['bot']} candle read failed ({type(exc).__name__})")
                continue
            spot[key] = grade_spot(row, nxt)
    # forget rows no longer on any book (account resets); keep the file small
    graded = {k: v for k, v in graded.items() if k in live}
    if len(graded) > MAX_GRADED:
        graded = dict(sorted(graded.items(), key=lambda kv: kv[1].get("opened") or "")[-MAX_GRADED:])
    spot = {k: v for k, v in spot.items() if k in live}
    today = now.date().isoformat()
    towers = summarize(graded, spot, today)
    sample = fr.daily_sample([g for g in graded.values() if g["day"] <= today], today)
    reviewed = (prior or {}).get("reviewed") or today
    try:
        review_due = (now.date() - dt.date.fromisoformat(reviewed)).days > REVIEW_DAYS
    except ValueError:
        review_due = True
    since = now.timestamp() - 86400
    return {
        "at": now.isoformat(timespec="seconds"), "paper_only": True, "research": True,
        "settings": dict(fr.SETTINGS), "flags": fr.flags_state(),
        "graded": graded, "spot": spot, "towers": towers,
        "flagged_beats_tape": sorted(b for b, t in towers.items() if t.get("beats_tape")),
        "spot_check": [{k: s.get(k) for k in ("bot", "ticker", "side", "price", "opened", "tape_price",
                                               "gap", "covered")} for s in sample],
        "no_fills_24h": no_fills(root, shadow_towers, since) if root else {},
        "reads": reads, "spot_reads": spot_reads, "pending": pending, "notes": notes[:10],
        "reviewed": reviewed, "review_due": review_due,
        "fee_review_due": fr.fee_review_due(now.date()),
    }


def report_lines(body: dict) -> list[str]:
    """Plain lines for the evening or weekly report (206, 243, 253, 254). Not wired in."""
    towers = body.get("towers") or {}
    lines = ["Fill realism (pretend fills checked against real Kalshi trading):"]
    for bot, t in towers.items():
        if not t.get("buys"):
            continue
        gap = t.get("avg_gap_cents")
        lines.append(
            f"- {bot}: {t['buys']} buys; {t['tape_blocked']} had no real trading at our price "
            f"({t['tape_blocked_today']} today); average gap to tape "
            f"{'n/a' if gap is None else f'{gap:+.2f} cents'}; fill quality {t.get('fill_quality')}"
            + ("; FLAG: fills beat the tape" if t.get("beats_tape") else ""))
    for bot, counts in (body.get("no_fills_24h") or {}).items():
        lines.append(f"- {bot} no-fills in 24h: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    sample = body.get("spot_check") or []
    if sample:
        lines.append(f"Spot check: {len(sample)} random fills listed for a manual look today.")
    if body.get("review_due"):
        lines.append("Monthly fill-realism review is due.")
    if body.get("fee_review_due"):
        lines.append("Monthly fee schedule check is due.")
    return lines


def card(body: dict) -> str:
    towers = body.get("towers") or {}
    buys = sum(t.get("buys") or 0 for t in towers.values())
    blocked = sum(t.get("tape_blocked") or 0 for t in towers.values())
    flagged = body.get("flagged_beats_tape") or []
    head = f"{buys} Kalshi buys checked against the tape: {blocked} had no real trading at our price"
    tail = f"; fills beat the tape at {', '.join(flagged)}" if flagged else "; no tower beats the tape"
    more = f"; {body.get('pending')} waiting" if body.get("pending") else ""
    return head + tail + more
