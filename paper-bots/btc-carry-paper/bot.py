#!/usr/bin/env python3
"""BTC spot-long / perpetual-short carry. Paper shadow. Held. Unlevered.

Long BTC spot, short the BTCUSDT perpetual, same notional, leverage 1.
The round trip is 0.30% (spot taker 0.10% and perp taker 0.05%, each side).
It is paid when the hold opens, and again only if a person later closes it.
It is not paid every month. A red funding month is a mark, not a flip.

Public archive only: data.binance.vision fundingRate and 8h premiumIndexKlines.
No key. No order. No desk cash.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import math
import os
import statistics
import sys
import urllib.error
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)

SPOT_TAKER = 0.001
PERP_TAKER = 0.0005
ROUND_TRIP = 2.0 * (SPOT_TAKER + PERP_TAKER)  # 0.0030
ENTRY_FEE_RATE = SPOT_TAKER + PERP_TAKER  # paid once, on the open
EXIT_FEE_RATE = SPOT_TAKER + PERP_TAKER  # reserved; not charged on a month mark
# Research haircut: charging the 0.30% round trip once a year is ~0.03% a month.
# Used only to score the pass-bar median. Not taken from cash each month.
MONTHLY_HAIRCUT = 0.0003
NOTIONAL = 500.0
VENUE_FLOOR = 0.02  # registry lock. Not a monthly hurdle. Not the btc15m 0.05 floor.

FLAT_CARD = "flat - BTC spot long / perp short not open; 0.30% round trip unpaid"
HOLD_CARD = "holding unlevered BTC spot long / perp short; red month is a mark, not a flip"
HOLD_EXIT = "hold — red month is a mark"
HOLD_SENTENCE = "hold, not a sell"


def densified_hold_card(state: dict) -> str:
    """HUD densify: the open IS the trade. Realized stays $0 until a month seals."""
    pos = (state.get("open") or [None])[0]
    if not isinstance(pos, dict):
        return HOLD_CARD
    opened = str(pos.get("opened") or "")
    day = opened[:10] if opened else "?"
    fee = float(pos.get("entry_fee") or 0.0)
    fund = float(pos.get("funding_pnl") or 0.0)
    basis = float(pos.get("basis_pnl") or 0.0)
    return (
        f"{HOLD_CARD}; open 1 since {day}; "
        f"RT fee ${fee:.2f} paid once; funding {fund:+.4f} basis {basis:+.4f}"
    )


def densified_flat_card(*, error: str = "") -> str:
    """HUD densify: flat means waiting on marks, not a missed fill."""
    err = str(error or "").strip()
    if err:
        return f"{FLAT_CARD}; marks {err}"
    return (
        f"{FLAT_CARD}; opens once when public funding + premium marks exist, then holds"
    )

VISION = "https://data.binance.vision/data/futures/um"
UA = {"User-Agent": "btc-carry-paper/1.0 (paper-only; public archive)"}
KEY_ENV = ("BINANCE_API_KEY", "BINANCE_API_SECRET", "BINANCE_SECRET_KEY")

# January–October 2026 carry, funding plus premium change, before the haircut.
# Source: the tower research note. This list is the published study, not the sleeve.
BTC_2026_GROSS = (
    0.0046, -0.0007, -0.0009, -0.0015, 0.0025,
    0.0022, 0.0058, 0.0061, 0.0044, 0.0041,
)
# Same panel for ETH/SOL. ETH is the same factor as BTC — observe twin only,
# never a second tower or desk risk share. SOL mean is red → reject.
ETH_2026_GROSS = (
    0.0041, -0.0030, -0.0011, -0.0012, 0.0030,
    0.0007, 0.0035, 0.0047, 0.0042, 0.0028,
)
SOL_2026_GROSS = (
    0.0020, -0.0102, -0.0053, 0.0001, 0.0005,
    -0.0037, 0.0019, 0.0039, 0.0027, 0.0038,
)


def load_config(path: str | None = None) -> dict:
    path = path or os.path.join(HERE, "config.json")
    with open(path, encoding="utf-8") as handle:
        cfg = json.load(handle)
    if cfg.get("paper_only") is not True or cfg.get("live_orders") is True:
        raise RuntimeError("config must be paper_only with live_orders false")
    return cfg


def locked_cfg(cfg: dict | None = None) -> dict:
    """Force the Binance schedule and 1x. Never the Coinbase 0.90% taker."""
    raw = dict(cfg or {})
    raw["spot_taker"] = SPOT_TAKER
    raw["perp_taker"] = PERP_TAKER
    raw["round_trip"] = ROUND_TRIP
    raw["notional_usd"] = NOTIONAL
    raw["leverage"] = 1
    raw["starter_cash"] = NOTIONAL
    raw["symbol"] = "BTCUSDT"
    raw["venue"] = "binance_btc_carry"
    floor = VENUE_FLOOR
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_profit
        floor = max(floor, float(desk_profit.DEFAULT_VENUE_MIN_EDGE["binance_btc_carry"]))
    except Exception:
        floor = VENUE_FLOOR
    raw["venue_min_edge"] = floor
    raw["paper_only"] = True
    raw["live_orders"] = False
    raw["shadow_only"] = True
    return raw


def score_months(gross: list[float] | tuple[float, ...]) -> dict:
    """Held median uses the 0.03% haircut. A monthly flip pays the full 0.30%."""
    rows = [float(g) for g in gross]
    if not rows:
        return {
            "n": 0,
            "held_median": None,
            "held_mean": None,
            "flip_mean": None,
            "pass": False,
            "flip_reject": True,
        }
    held = [g - MONTHLY_HAIRCUT for g in rows]
    flipped = [g - ROUND_TRIP for g in rows]
    held_median = statistics.median(held)
    flip_mean = sum(flipped) / len(flipped)
    return {
        "n": len(rows),
        "held_median": held_median,
        "held_mean": sum(held) / len(held),
        "flip_mean": flip_mean,
        "pass": held_median > 0,
        "flip_reject": flip_mean <= 0,
    }


def twin_research_card() -> dict:
    """ETH observe twin + SOL reject. Same fee schedule. No second tower."""
    btc = score_months(BTC_2026_GROSS)
    eth = score_months(ETH_2026_GROSS)
    sol = score_months(SOL_2026_GROSS)
    return {
        "paper_only": True,
        "observe_only": True,
        "fee_floors_locked": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "window": "2026-01..2026-10",
        "round_trip": ROUND_TRIP,
        "monthly_haircut": MONTHLY_HAIRCUT,
        "btc": {
            "symbol": "BTCUSDT",
            "role": "live_shadow_sleeve",
            "held_median": btc["held_median"],
            "held_mean": btc["held_mean"],
            "flip_mean": btc["flip_mean"],
            "pass": btc["pass"],
            "flip_reject": btc["flip_reject"],
            "second_tower": False,
        },
        "eth": {
            "symbol": "ETHUSDT",
            "role": "observe_twin_same_factor",
            "held_median": eth["held_median"],
            "held_mean": eth["held_mean"],
            "flip_mean": eth["flip_mean"],
            "pass": eth["pass"],
            "flip_reject": eth["flip_reject"],
            # Research: same factor as BTC — a line inside the sleeve, not a folder.
            "second_tower": False,
            "opens_desk_cash": False,
            "note": "Observe twin only. Do not open a second carry tower.",
        },
        "sol": {
            "symbol": "SOLUSDT",
            "role": "reject_mean_red",
            "held_median": sol["held_median"],
            "held_mean": sol["held_mean"],
            "flip_mean": sol["flip_mean"],
            "pass": False,
            "flip_reject": True,
            "second_tower": False,
            "opens_desk_cash": False,
            "note": "2026 held mean red after haircut — reject as sleeve or twin.",
        },
        "note": (
            "Funding-carry twins from the published 2026 archive panel. "
            "Only BTC opens the shadow sleeve. ETH is observe-only. SOL is reject. "
            "Never invent marks. Never LIVE."
        ),
    }


def research_card(cfg: dict | None = None) -> dict:
    cfg = locked_cfg(cfg)
    study = score_months(BTC_2026_GROSS)
    return {
        "paper_only": True,
        "live_orders": False,
        "shadow_only": True,
        "venue": cfg["venue"],
        "symbol": cfg["symbol"],
        "spot_taker": cfg["spot_taker"],
        "perp_taker": cfg["perp_taker"],
        "round_trip": cfg["round_trip"],
        "notional_usd": cfg["notional_usd"],
        "leverage": cfg["leverage"],
        "flat_card": FLAT_CARD,
        "hold_card": HOLD_CARD,
        "pass_bar": (
            "After-fee monthly median stays positive. "
            "Flipping every month is a reject."
        ),
        "archive_study_2026": {
            "window": "2026-01..2026-10",
            "held_median": study["held_median"],
            "flip_mean": study["flip_mean"],
            "note": "Published archive sample. Not this sleeve's own pnl.",
        },
        "twins": twin_research_card(),
        "auto_promote": False,
    }


def archive_urls(now: dt.datetime, symbol: str = "BTCUSDT") -> list[tuple[str, str]]:
    """Public vision files only. The fapi host is not used."""
    sym = str(symbol or "BTCUSDT").upper()
    if sym not in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        sym = "BTCUSDT"
    months = []
    cursor = now.astimezone(dt.timezone.utc).date().replace(day=1)
    for _ in range(2):
        months.append(cursor.strftime("%Y-%m"))
        cursor = (cursor - dt.timedelta(days=1)).replace(day=1)
    urls: list[tuple[str, str]] = []
    for ym in months:
        urls.append((
            "funding",
            f"{VISION}/monthly/fundingRate/{sym}/{sym}-fundingRate-{ym}.zip",
        ))
        urls.append((
            "premium",
            f"{VISION}/monthly/premiumIndexKlines/{sym}/8h/{sym}-8h-{ym}.zip",
        ))
    day = now.astimezone(dt.timezone.utc).date()
    for delta in (1, 2):
        stamp = (day - dt.timedelta(days=delta)).isoformat()
        urls.append((
            "funding",
            f"{VISION}/daily/fundingRate/{sym}/{sym}-fundingRate-{stamp}.zip",
        ))
    # Daily funding zips are not on the archive. Daily 8h premium klines are.
    # They mark basis on the open hold. They do not open another leg.
    for delta in range(1, 11):
        stamp = (day - dt.timedelta(days=delta)).isoformat()
        urls.append((
            "premium",
            f"{VISION}/daily/premiumIndexKlines/{sym}/8h/{sym}-8h-{stamp}.zip",
        ))
    return urls


def parse_funding_csv(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("calc_time"):
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        when = _parse_time(parts[0])
        rate = _num(parts[-1])
        if when is None or rate is None:
            continue
        rows.append({"time": when.isoformat(timespec="seconds"), "rate": rate})
    rows.sort(key=lambda row: row["time"])
    return rows


def parse_premium_csv(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("open_time"):
            continue
        parts = line.split(",")
        if len(parts) < 5:
            continue
        when = _parse_time(parts[0])
        close = _num(parts[4])
        if when is None or close is None:
            continue
        rows.append({"time": when.isoformat(timespec="seconds"), "close": close})
    rows.sort(key=lambda row: row["time"])
    return rows


def _csv_from_zip(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not names:
            return ""
        return archive.read(names[0]).decode("utf-8", errors="replace")


def fetch_marks(
    now: dt.datetime | None = None,
    opener=None,
    *,
    symbol: str = "BTCUSDT",
) -> dict:
    """Read the public archive. A missing file is skipped. No fapi call."""
    now = now or dt.datetime.now(dt.timezone.utc)
    opener = opener or _urlopen
    sym = str(symbol or "BTCUSDT").upper()
    funding: list[dict] = []
    premium: list[dict] = []
    errors: list[str] = []
    for kind, url in archive_urls(now, symbol=sym):
        if "fapi.binance.com" in url:
            errors.append("refusing fapi host")
            continue
        try:
            blob = opener(url)
        except Exception as exc:
            errors.append(exc.__class__.__name__)
            continue
        if not blob:
            continue
        text = _csv_from_zip(blob) if blob[:2] == b"PK" else blob.decode("utf-8", errors="replace")
        if kind == "funding":
            funding.extend(parse_funding_csv(text))
        else:
            premium.extend(parse_premium_csv(text))
    funding = _dedupe_rows(funding)
    premium = _dedupe_rows(premium)
    return {
        "symbol": sym,
        "funding": funding,
        "premium": premium,
        "observe_only": sym != "BTCUSDT",
        "opens_desk_cash": sym == "BTCUSDT",
        "error": "" if funding or premium else (errors[0] if errors else "no archive rows"),
    }


def _public_print(value, *, spot=None):
    """A funding rate or a premium close. A Coinbase dollar price is not one."""
    n = _num(value)
    if n is None:
        return None
    spot_n = _num(spot)
    if spot_n is not None and abs(n - spot_n) <= 1e-9:
        return None
    if abs(n) >= 1.0:
        return None
    return n


def scan_marks(marks, *, coinbase_price=None, key_set=False) -> dict:
    """Read the public funding print and the public premium. No key.

    A missing archive is a data skip. A Coinbase spot price does not fill
    either print. This does not open and does not sell.
    """
    book = marks if isinstance(marks, dict) else {}
    blank = {
        "funding": [],
        "premium": [],
        "data_skip": True,
        "opened": False,
        "sold": False,
        "borrowed_spot": False,
        "paper_only": True,
    }
    if key_set:
        return {**blank, "reason": "data key is set"}
    spot = coinbase_price
    if spot is None:
        for key in ("coinbase", "coinbase_price", "spot", "btc_usd", "eth_usd"):
            if key in book:
                spot = book.get(key)
                break
    funding = []
    for row in book.get("funding") or []:
        if not isinstance(row, dict):
            continue
        rate = _public_print(row.get("rate"), spot=spot)
        when = str(row.get("time") or "").strip()
        if rate is None or not when:
            continue
        funding.append({"time": when, "rate": rate})
    premium = []
    for row in book.get("premium") or []:
        if not isinstance(row, dict):
            continue
        close = _public_print(row.get("close"), spot=spot)
        when = str(row.get("time") or "").strip()
        if close is None or not when:
            continue
        premium.append({"time": when, "close": close})
    if not funding or not premium:
        if not funding and not premium:
            detail = str(book.get("error") or "").strip() or "no archive rows"
        elif not funding:
            detail = "funding archive missing"
        else:
            detail = "premium archive missing"
        return {**blank, "funding": funding, "premium": premium, "reason": "data " + detail}
    return {
        "funding": funding,
        "premium": premium,
        "data_skip": False,
        "reason": "funding and premium read",
        "opened": False,
        "sold": False,
        "borrowed_spot": False,
        "paper_only": True,
    }


def floor_stays(edge=None, paid=None) -> float:
    """0.02 stays. A month that paid does not cut it."""
    _num(paid)
    n = _num(edge)
    if n is None or n < VENUE_FLOOR:
        return VENUE_FLOOR
    return n


def decide_hold(state, marks, *, floor=None, paid=None, block_entries=False) -> dict:
    """Open once, when both marks exist and the sleeve is flat.

    A red month does not add a second leg. A paid month does not cut 0.02.
    This does not open and does not sell.
    """
    book = state if isinstance(state, dict) else {}
    opens = [row for row in (book.get("open") or []) if isinstance(row, dict)]
    locked = floor_stays(VENUE_FLOOR if floor is None else floor, paid=paid)
    base = {
        "floor": locked,
        "opened": False,
        "sold": False,
        "second_leg": False,
        "paper_only": True,
        "legs": len(opens),
    }
    quote = marks if isinstance(marks, dict) else {}
    symbol = str(quote.get("symbol") or "BTCUSDT").upper()
    if quote.get("observe_only") or symbol != "BTCUSDT":
        return {**base, "action": "flat", "reason": "observe twin, not a second tower"}
    if block_entries and not opens:
        return {**base, "action": "flat", "reason": "desk entry gate"}
    scanned = scan_marks(quote)
    if opens:
        return {**base, "action": "hold", "reason": "red month is not a second leg"}
    if scanned["data_skip"]:
        return {**base, "action": "flat", "reason": scanned["reason"]}
    return {**base, "action": "open", "reason": "hold rule, once"}


def observe_twin_marks(
    now: dt.datetime | None = None,
    opener=None,
) -> dict:
    """Fetch ETH (+ optional SOL) archive marks for observe only. Never opens cash."""
    now = now or dt.datetime.now(dt.timezone.utc)
    eth = fetch_marks(now, opener=opener, symbol="ETHUSDT")
    sol = fetch_marks(now, opener=opener, symbol="SOLUSDT")
    return {
        "paper_only": True,
        "observe_only": True,
        "fee_floors_locked": True,
        "auto_promote": False,
        "live_orders_enabled": False,
        "opens_desk_cash": False,
        "second_tower": False,
        "eth": eth,
        "sol": sol,
        "research": twin_research_card(),
        "note": (
            "ETH/SOL archive marks are observe-only twins. "
            "Only BTCUSDT may open the shadow sleeve."
        ),
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
        "entry_fees": 0,
        "pass_bar": {"n": 0, "held_median": None, "flip_mean": None, "pass": False},
    }


def write_open_intent(path, *, fill_id, notional, exit_fee, premium):
    """The crash intent. The $500 pair and the reserved exit fee are required."""
    notional_n = _num(notional)
    fee_n = _num(exit_fee)
    prem = _public_print(premium)
    reserved = round(NOTIONAL * EXIT_FEE_RATE, 4)
    if (
        not path
        or notional_n is None
        or abs(notional_n - NOTIONAL) > 1e-9
        or fee_n is None
        or abs(fee_n - reserved) > 1e-9
        or prem is None
        or not str(fill_id or "").strip()
    ):
        raise ValueError("open intent needs the $500 pair and the reserved exit fee")
    payload = {
        "tower": "btc-carry",
        "fill_id": str(fill_id).strip(),
        "symbol": "BTCUSDT",
        "notional": NOTIONAL,
        "leverage": 1,
        "exit_fee_reserved": reserved,
        "exit_name": HOLD_EXIT,
        "premium": prem,
        "paper_only": True,
        "status": "intent",
    }
    _write_json(path, payload)
    return payload


def reconcile_open_intent(state, path) -> str:
    """Match an intent to the book. Never create a pair or a premium."""
    if not path or not os.path.exists(path):
        return "none"
    try:
        with open(path, encoding="utf-8") as handle:
            intent = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return "none"
    if not isinstance(intent, dict):
        return "none"
    fid = str(intent.get("fill_id") or "")
    book = state if isinstance(state, dict) else {}
    opens = [row for row in book.get("open") or [] if isinstance(row, dict)]
    if fid and any(str(row.get("fill_id") or "") == fid for row in opens):
        status = "open"
    else:
        status = "abandoned"
    intent["status"] = status
    intent["paper_only"] = True
    intent["exit_name"] = HOLD_EXIT
    intent["leverage"] = 1
    intent["notional"] = NOTIONAL
    _write_json(path, intent)
    return status


def place_open(state, decision, marks, *, intent_path, now) -> dict:
    """Write the hold intent before cash. One unlevered pair.

    A restart that already has the pair buys nothing. A refused decision
    does not invent a position. The reserved exit fee is not spent.
    """
    book = state if isinstance(state, dict) else {}
    cash_before = _num(book.get("cash"))
    if cash_before is None:
        cash_before = NOTIONAL

    def refuse(reason):
        return {
            "bought": False,
            "reason": reason,
            "fill": False,
            "leverage": 1,
            "sold": False,
            "paper_only": True,
            "cash": cash_before,
        }

    opens = [row for row in (book.get("open") or []) if isinstance(row, dict)]
    if opens:
        return refuse("one pair")
    if not isinstance(decision, dict) or decision.get("action") != "open":
        return refuse(str((decision or {}).get("reason") or "hold rule not met"))
    floor = _num(decision.get("floor"))
    if floor is None or floor + 1e-12 < VENUE_FLOOR:
        return refuse("floor stays 0.02")
    scanned = scan_marks(marks if isinstance(marks, dict) else {})
    if scanned["data_skip"] or not scanned["funding"] or not scanned["premium"]:
        return refuse(str(scanned.get("reason") or "data no archive rows"))
    when = now if isinstance(now, dt.datetime) else _parse_time(now)
    if when is None:
        return refuse("missing clock")
    when = _as_utc(when)
    entry = _latest_at_or_before(scanned["premium"], when) or scanned["premium"][-1]
    premium = _public_print(entry.get("close"))
    if premium is None:
        return refuse("missing premium")
    entry_fee = round(NOTIONAL * ENTRY_FEE_RATE, 4)
    exit_fee = round(NOTIONAL * EXIT_FEE_RATE, 4)
    if cash_before + 1e-9 < entry_fee:
        return refuse("shadow cash below the open fee")
    fill_id = f"btc-carry|{when.isoformat(timespec='seconds')}"
    try:
        write_open_intent(
            intent_path,
            fill_id=fill_id,
            notional=NOTIONAL,
            exit_fee=exit_fee,
            premium=premium,
        )
    except (TypeError, ValueError, OSError):
        return refuse("open intent needs the $500 pair and the reserved exit fee")
    book["cash"] = round(cash_before - entry_fee, 4)
    book["entry_fees"] = int(book.get("entry_fees") or 0) + 1
    book.setdefault("open", []).append({
        "ticker": "BTCUSDT",
        "team": "BTC carry",
        "side": "long spot / short perp",
        "contracts": 1,
        "cost": NOTIONAL,
        "notional": NOTIONAL,
        "leverage": 1,
        "entry_fee": entry_fee,
        "exit_fee_reserved": exit_fee,
        "exit_name": HOLD_EXIT,
        "funding_pnl": 0.0,
        "basis_pnl": 0.0,
        "premium": premium,
        "premium_time": entry.get("time"),
        "opened": when.isoformat(timespec="seconds"),
        "applied": [],
        "months": {},
        "sealed": [],
        "why": "held unlevered carry; round trip is not paid every month",
        "price_source": "https://data.binance.vision/",
        "price_at": entry.get("time"),
        "paper_only": True,
        "shadow_only": True,
        "fill_id": fill_id,
        "exit_plan": _exit_plan(),
    })
    return {
        "bought": True,
        "fill_id": fill_id,
        "exit_name": HOLD_EXIT,
        "notional": NOTIONAL,
        "leverage": 1,
        "exit_fee_reserved": exit_fee,
        "sold": False,
        "cash": book["cash"],
    }


def watch_pair(state, marks, now) -> dict:
    """Mark the open pair at the real premium. A red month is a month-mark.

    The pair stays open. A missing premium is not replaced, and a Coinbase
    spot price is not the mark. This does not sell.
    """
    book = state if isinstance(state, dict) else {}
    opens = [row for row in book.get("open") or [] if isinstance(row, dict)]
    if not opens:
        book["watch"] = "flat"
        return {"flat": True, "sold": False, "month_mark": False, "open": 0}
    pos = opens[0]
    scanned = scan_marks(marks if isinstance(marks, dict) else {})
    prior = _public_print(pos.get("last_mark"))
    if prior is None:
        prior = _public_print(pos.get("premium"))
    marked = None
    stamp = None
    for row in scanned["premium"]:
        close = _public_print(row.get("close"))
        when_row = str(row.get("time") or "")
        if close is None or not when_row:
            continue
        if stamp is None or when_row >= stamp:
            marked = close
            stamp = when_row
    stored_time = str(pos.get("premium_time") or "")
    if marked is not None and (not stored_time or (stamp and stamp >= stored_time)):
        pos["last_mark"] = marked
        pos["premium"] = marked
        pos["premium_time"] = stamp
    elif prior is not None:
        pos["last_mark"] = prior
    when = now if isinstance(now, dt.datetime) else _parse_time(now)
    if when is None:
        when = dt.datetime.now(dt.timezone.utc)
    before = len(book.get("closed") or [])
    _seal_finished_months(book, pos, _as_utc(when))
    book["open"] = [pos]
    book["watch"] = "marked"
    return {
        "flat": False,
        "sold": False,
        "month_mark": len(book.get("closed") or []) > before,
        "open": 1,
        "last_mark": pos.get("last_mark"),
    }


def failsafe_hold(state, marks=None, *, close_reason="") -> dict:
    """Confirm the hold. A red month is not a close, and a missing premium is not a close.

    The pair stays open. This records the real premium and the words
    hold, not a sell. It does not sell.
    """
    book = state if isinstance(state, dict) else {}
    opens = [row for row in (book.get("open") or []) if isinstance(row, dict)]
    scanned = scan_marks(marks if isinstance(marks, dict) else {})
    premium = None
    for row in scanned["premium"]:
        close = _public_print(row.get("close"))
        if close is not None:
            premium = close
    asked = str(close_reason or "")
    red_only = "red" in asked.lower() and "month" in asked.lower()
    if not opens:
        book["failsafe"] = HOLD_SENTENCE
        return {
            "sold": False,
            "closed": False,
            "hold": True,
            "hit": False,
            "sentence": HOLD_SENTENCE,
            "premium": None,
            "open": 0,
            "reason": "flat sleeve has nothing to close",
        }
    pos = opens[0]
    pos["failsafe"] = HOLD_SENTENCE
    if premium is None:
        kept = _public_print(pos.get("failsafe_premium"))
        if kept is None:
            kept = _public_print(pos.get("premium"))
        note = "missing premium is not a close"
    else:
        pos["failsafe_premium"] = premium
        kept = premium
        note = HOLD_SENTENCE
    book["open"] = [pos]
    return {
        "sold": False,
        "closed": False,
        "hold": True,
        "hit": False,
        "sentence": HOLD_SENTENCE,
        "premium": kept,
        "open": 1,
        "refused_red_month": red_only,
        "reason": note,
    }


def _brain(root):
    if DESK_ROOT not in sys.path:
        sys.path.insert(0, DESK_ROOT)
    import desk_brain
    return desk_brain, DESK_ROOT if root is None else root


def _printed_premium(state, row) -> float | None:
    """The premium that printed. A typed number and a spot dollar price are not it."""
    if isinstance(row, dict):
        printed = _public_print(row.get("premium"))
        if printed is not None:
            return printed
    for pos in (state.get("open") or []) if isinstance(state, dict) else []:
        if not isinstance(pos, dict):
            continue
        for source in (pos.get("failsafe_premium"), pos.get("premium"), pos.get("last_mark")):
            printed = _public_print(source)
            if printed is not None:
                return printed
    return None


def _write_month(row: dict, premium, root):
    """Journal the month-mark. The reserved exit fee is not spent."""
    brain, base = _brain(root)
    month = str(row.get("month") or "")
    fill = f"BTCUSDT|{month}" if month else "BTCUSDT|month-mark"
    saved = brain.record_decision(
        base,
        bot="btc-carry",
        action="month-mark",
        ticker=str(row.get("ticker") or "BTCUSDT"),
        side="long spot / short perp",
        reasons=["month-mark"],
        note="month-mark; reserved exit fee stays reserved",
        fill_id=fill,
        exit_name="month-mark",
        stake=row.get("cost") if row.get("cost") is not None else NOTIONAL,
    )
    journal = brain.load_journal(base)
    for prev in journal.get("decisions") or []:
        if not isinstance(prev, dict):
            continue
        if prev.get("bot") != "btc-carry" or str(prev.get("fill_id") or "") != fill:
            continue
        if str(prev.get("exit_name") or "") != "month-mark":
            continue
        if premium is None:
            prev.pop("premium", None)
        else:
            prev["premium"] = premium
        prev["fee_spent"] = False
        prev["exit_fee"] = "reserved"
        prev.pop("fee", None)
        prev.pop("hit", None)
        prev.pop("result", None)
        saved = prev
        break
    brain.save_journal(journal, base)
    return saved


def record_month(state, claimed=None, *, root=None) -> dict:
    """Write the month-mark with the premium that printed.

    A number passed in is not that premium. The reserved exit fee stays
    reserved. The pair is not journaled as closed.
    """
    book = state if isinstance(state, dict) else {}
    _public_print(claimed)
    marks = [
        row for row in (book.get("closed") or [])
        if isinstance(row, dict) and row.get("exit") == "month-mark"
    ]
    if not marks:
        return {
            "recorded": False,
            "rows": [],
            "fee_spent": False,
            "sold": False,
            "open": len([row for row in (book.get("open") or []) if isinstance(row, dict)]),
        }
    written = []
    for row in marks:
        premium = _printed_premium(book, row)
        saved = _write_month(row, premium, root)
        if premium is not None:
            row["premium"] = premium
        row["fee_spent"] = False
        row.pop("hit", None)
        row.pop("result", None)
        written.append(saved)
    return {
        "recorded": True,
        "rows": written,
        "fee_spent": False,
        "sold": False,
        "open": len([row for row in (book.get("open") or []) if isinstance(row, dict)]),
    }


def learn_buys(reason=None) -> bool:
    """A month-mark does not authorize a buy, and it is not a settle."""
    return False


def learning_row(pos) -> dict | None:
    """One month-mark. A close that did not happen is not a row."""
    if not isinstance(pos, dict):
        return None
    if str(pos.get("exit") or "") != "month-mark":
        return None
    month = str(pos.get("month") or "").strip()
    if not month:
        return None
    stake = _num(pos.get("cost") if pos.get("cost") is not None else pos.get("stake"))
    if stake is None or stake <= 0:
        stake = NOTIONAL
    return {
        "market": "BTC-CARRY",
        "bucket": "month-mark",
        "stake": stake,
        "fill_id": f"BTCUSDT|{month}",
        "reason": f"month-mark; {HOLD_SENTENCE}",
        "side": "HOLD",
        "paper_only": True,
    }


def tell_learning(pos, root) -> str:
    """Write one month-mark. The same month is not written twice."""
    row = learning_row(pos)
    if not row:
        return "empty"
    if DESK_ROOT not in sys.path:
        sys.path.insert(0, DESK_ROOT)
    import pimp_desk
    fill = row["fill_id"]
    if any(str(item.get("fill_id") or "") == fill for item in pimp_desk.load_learning(root)):
        return "duplicate"
    pimp_desk.record_learning(root, row)
    return "recorded"


def learn_book(state, root=None) -> dict:
    """The learning book gets the month-mark and the hold sentence.

    A flat book writes nothing. A settle that did not happen is not invented.
    This does not buy.
    """
    book = state if isinstance(state, dict) else {}
    marks = [row for row in (book.get("closed") or []) if learning_row(row)]
    if not marks:
        return {"wrote": 0, "settle": False, "buy": False, "rows": []}
    wrote = 0
    rows = []
    for pos in marks:
        status = tell_learning(pos, root)
        rows.append(status)
        if status == "recorded":
            wrote += 1
    return {"wrote": wrote, "settle": False, "buy": learn_buys(None), "rows": rows}


def hold_step(state: dict, marks: dict, cfg: dict, now: dt.datetime, *, block_entries: bool = False, intent_path=None) -> dict:
    """Apply the hold. Never flips. Never adds a second leg after a red month."""
    cfg = locked_cfg(cfg)
    now = _as_utc(now)
    state = json.loads(json.dumps(state))
    state["open"] = list(state.get("open") or [])
    state["closed"] = list(state.get("closed") or [])
    state["paper_only"] = True
    state["shadow_only"] = True
    state["live_orders"] = False
    funding = list(marks.get("funding") or [])
    premium = list(marks.get("premium") or [])
    if not state["open"]:
        if block_entries or not premium or not funding:
            state["last_action"] = "flat"
            return state
        placed = place_open(
            state,
            {"action": "open", "floor": cfg["venue_min_edge"]},
            {"symbol": cfg.get("symbol") or "BTCUSDT", "funding": funding, "premium": premium},
            intent_path=intent_path,
            now=now,
        )
        state["last_action"] = "open" if placed.get("bought") else "flat"
        return state
    pos = state["open"][0]
    pos["notional"] = NOTIONAL
    pos["leverage"] = 1
    pos["cost"] = NOTIONAL
    opened = str(pos.get("opened") or "")
    applied = set(pos.get("applied") or [])
    notional = float(pos["notional"])
    for row in funding:
        stamp = str(row.get("time") or "")
        if not stamp or stamp <= opened or stamp in applied:
            continue
        rate = _num(row.get("rate"))
        if rate is None:
            continue
        pnl = round(notional * rate, 6)
        pos["funding_pnl"] = round(float(pos.get("funding_pnl") or 0) + pnl, 6)
        state["cash"] = round(float(state.get("cash") or 0) + pnl, 4)
        _month_bucket(pos, stamp)["funding"] = round(_month_bucket(pos, stamp)["funding"] + pnl, 6)
        applied.add(stamp)
    premium_time = str(pos.get("premium_time") or opened)
    for row in premium:
        stamp = str(row.get("time") or "")
        close = _num(row.get("close"))
        if not stamp or close is None or stamp <= premium_time:
            continue
        previous = _num(pos.get("premium")) or 0.0
        pnl = round(-notional * (close - previous), 6)
        pos["basis_pnl"] = round(float(pos.get("basis_pnl") or 0) + pnl, 6)
        state["cash"] = round(float(state.get("cash") or 0) + pnl, 4)
        _month_bucket(pos, stamp)["basis"] = round(_month_bucket(pos, stamp)["basis"] + pnl, 6)
        pos["premium"] = close
        pos["premium_time"] = stamp
        premium_time = stamp
    pos["applied"] = sorted(applied)[-400:]
    # Heartbeat the open on each hold check. Archive premium_time can lag wall
    # clock by weeks; doctor must not read that lag as a dead book.
    pos["price_at"] = now.isoformat(timespec="seconds")
    watch_pair(state, {"funding": funding, "premium": premium, "symbol": "BTCUSDT"}, now)
    failsafe_hold(state, {"funding": funding, "premium": premium, "symbol": "BTCUSDT"})
    state["pass_bar"] = _pass_bar(state)
    state["last_action"] = "hold"
    if len(state["open"]) != 1:
        state["open"] = state["open"][:1]
    return state


def _month_bucket(pos: dict, stamp: str) -> dict:
    months = pos.setdefault("months", {})
    key = stamp[:7]
    bucket = months.get(key)
    if not isinstance(bucket, dict):
        bucket = {"funding": 0.0, "basis": 0.0}
        months[key] = bucket
    return bucket


def _seal_finished_months(state: dict, pos: dict, now: dt.datetime) -> None:
    """A finished month is a mark. The pair stays open. The round trip is not paid again."""
    current = now.astimezone(dt.timezone.utc).strftime("%Y-%m")
    sealed = set(pos.get("sealed") or [])
    notional = float(pos.get("notional") or NOTIONAL)
    for key in sorted((pos.get("months") or {})):
        if key >= current or key in sealed:
            continue
        bucket = pos["months"][key]
        gross = round(float(bucket.get("funding") or 0) + float(bucket.get("basis") or 0), 6)
        after = round(gross - notional * MONTHLY_HAIRCUT, 6)
        state["closed"].append({
            "ticker": pos.get("ticker") or "BTCUSDT",
            "team": "BTC carry",
            "side": "long spot / short perp",
            "exit": "month-mark",
            "pnl": round(gross, 4),
            "after_fee": after,
            "month": key,
            "closed": f"{key}-01T00:00:00+00:00",
            "cost": notional,
            "paper_only": True,
            "shadow_only": True,
            "note": "mark only; the hold stays open",
        })
        sealed.add(key)
    pos["sealed"] = sorted(sealed)


def _pass_bar(state: dict) -> dict:
    gross = []
    for row in state.get("closed") or []:
        if row.get("exit") != "month-mark":
            continue
        after = _num(row.get("after_fee"))
        if after is None:
            continue
        gross.append(after / NOTIONAL + MONTHLY_HAIRCUT)
    scored = score_months(gross)
    return {
        "n": scored["n"],
        "held_median": scored["held_median"],
        "flip_mean": scored["flip_mean"],
        "pass": scored["pass"],
        "flip_reject": True,
    }


def _exit_plan() -> dict:
    return {
        "kind": "hold+refuse_monthly_flip",
        "hold": True,
        "red_month_exit": False,
        "monthly_flip": False,
        "staff_close_backstop": True,
        "shadow_only": True,
        "auto_promote": False,
        "fee_floors_locked": True,
        "unlevered": True,
    }


def run_once(
    desk_root: str | None = None,
    cfg: dict | None = None,
    fetch=None,
    now: dt.datetime | None = None,
) -> int:
    desk_root = desk_root or DESK_ROOT
    cfg = locked_cfg(cfg or load_config(os.path.join(desk_root, "btc-carry-paper", "config.json")))
    now = _as_utc(now or dt.datetime.now(dt.timezone.utc))
    if any(os.environ.get(name) for name in KEY_ENV):
        print("SIGNAL: SKIP key is set")
        print("CARD: " + FLAT_CARD)
        print("no trade")
        return 0
    tower = os.path.join(desk_root, "btc-carry-paper")
    os.makedirs(tower, exist_ok=True)
    path = os.path.join(tower, "paper_account.json")
    state = _read_state(path) or empty_state(cfg)
    fetch = fetch or (lambda: fetch_marks(now))
    try:
        marks = fetch() or {}
    except Exception as exc:
        marks = {"funding": [], "premium": [], "error": exc.__class__.__name__}
    if not isinstance(marks, dict):
        marks = {"funding": [], "premium": [], "error": "bad marks"}
    scanned = scan_marks(marks)
    marks = dict(marks)
    marks["funding"] = scanned["funding"]
    marks["premium"] = scanned["premium"]
    if scanned["data_skip"] and not str(marks.get("error") or "").strip():
        detail = str(scanned["reason"] or "")
        marks["error"] = detail[5:] if detail.startswith("data ") else detail
    intent_path = os.path.join(tower, "buy_intent.json")
    reconcile_open_intent(state, intent_path)
    blocked = os.environ.get("DESK_BLOCK_ENTRIES") == "1"
    before = len(state.get("open") or [])
    decision = decide_hold(
        state, marks, floor=cfg.get("venue_min_edge"), block_entries=blocked and before == 0,
    )
    state = hold_step(
        state, marks, cfg, now,
        block_entries=(blocked and before == 0) or decision["action"] != "open",
        intent_path=intent_path,
    )
    state["decision"] = decision["action"]
    state["floor"] = decision["floor"]
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    record_month(state, root=desk_root)
    learn_book(state, root=desk_root)
    _record_month_marks(desk_root, state)
    _write_json(path, state)
    _append_research(tower, now, state, marks)
    error = str(marks.get("error") or "")
    if state.get("open"):
        print("SIGNAL: HOLD BTCUSDT unlevered")
        print("CARD: " + densified_hold_card(state))
        if error and not (marks.get("funding") or marks.get("premium")):
            print("SIGNAL: SKIP data " + error)
    else:
        print("SIGNAL: SKIP flat")
        if error:
            print("SIGNAL: SKIP data " + error)
        print("CARD: " + densified_flat_card(error=error))
        print("no trade")
    return 0


def _record_month_marks(desk_root: str, state: dict) -> None:
    """A sealed month counts toward incubation. It does not graduate the book."""
    done = set(state.get("incubated") or [])
    fresh = []
    for row in state.get("closed") or []:
        if row.get("exit") != "month-mark":
            continue
        key = str(row.get("month") or "")
        if not key or key in done:
            continue
        fresh.append(row)
    if not fresh:
        return
    try:
        if desk_root not in sys.path:
            sys.path.insert(0, desk_root)
        import desk_roi_plan
    except Exception:
        return
    for row in fresh:
        try:
            desk_roi_plan.record_incubation_settle(
                desk_root,
                series="BTC-CARRY",
                bot="btc-carry",
                pnl=row.get("after_fee"),
                contracts=1,
                note="shadow month mark; no auto-promote",
            )
        except Exception:
            return
        done.add(str(row.get("month") or ""))
    state["incubated"] = sorted(done)


def _latest_at_or_before(rows: list[dict], now: dt.datetime) -> dict | None:
    stamp = now.isoformat(timespec="seconds")
    chosen = None
    for row in rows:
        if str(row.get("time") or "") <= stamp:
            chosen = row
    return chosen


def _dedupe_rows(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for row in sorted(rows, key=lambda item: str(item.get("time") or "")):
        key = str(row.get("time") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _append_research(tower: str, now: dt.datetime, state: dict, marks: dict) -> None:
    path = os.path.join(tower, "research.jsonl")
    line = json.dumps({
        "at": now.isoformat(timespec="seconds"),
        "action": state.get("last_action"),
        "open": len(state.get("open") or []),
        "cash": state.get("cash"),
        "error": marks.get("error") or "",
        "paper_only": True,
    }) + "\n"
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        return


def _kalshi_urlopen(req, timeout):
    """Kalshi GETs share one pace / back-off / cache across towers (kalshi_gateway)."""
    if DESK_ROOT not in sys.path:
        sys.path.insert(0, DESK_ROOT)
    try:
        import kalshi_gateway
    except ImportError:
        return urllib.request.urlopen(req, timeout=timeout)
    return kalshi_gateway.urlopen(req, timeout=timeout)


def _urlopen(url: str) -> bytes | None:
    if "fapi.binance.com" in url:
        return None
    req = urllib.request.Request(url, headers=UA)
    try:
        with _kalshi_urlopen(req, timeout=8) as resp:
            return resp.read()
    except urllib.error.HTTPError:
        return None
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def _read_state(path: str) -> dict | None:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: str, payload: dict) -> None:
    # Follow the desk's volume link so the save is not undone by the next re-link.
    if os.path.islink(path):
        path = os.path.realpath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def _parse_time(value) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        ms = int(raw)
        if ms > 10_000_000_000:
            ms = ms / 1000.0
        try:
            return dt.datetime.fromtimestamp(ms, dt.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def _num(value) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def reset_account(desk_root: str | None = None) -> None:
    tower = os.path.join(desk_root or DESK_ROOT, "btc-carry-paper")
    for name in ("paper_account.json", "research.jsonl"):
        path = os.path.join(tower, name)
        if os.path.isfile(path):
            os.remove(path)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        reset_account()
        print("reset paper account")
        return 0
    if "--research" in argv:
        print(json.dumps(research_card(), indent=2))
        return 0
    if "--twins" in argv:
        # Observe-only ETH/SOL twin board. Never opens desk cash.
        print(json.dumps(twin_research_card(), indent=2, sort_keys=True))
        return 0
    return run_once()


if __name__ == "__main__":
    raise SystemExit(main())
