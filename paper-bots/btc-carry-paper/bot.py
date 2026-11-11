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


def hold_step(state: dict, marks: dict, cfg: dict, now: dt.datetime, *, block_entries: bool = False) -> dict:
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
        entry = _latest_at_or_before(premium, now) or premium[-1]
        notional = float(cfg["notional_usd"])
        fee = round(notional * ENTRY_FEE_RATE, 4)
        state["cash"] = round(float(state.get("cash") or cfg["starter_cash"]) - fee, 4)
        state["entry_fees"] = int(state.get("entry_fees") or 0) + 1
        state["open"].append({
            "ticker": cfg["symbol"],
            "team": "BTC carry",
            "side": "long spot / short perp",
            "contracts": 1,
            "cost": notional,
            "notional": notional,
            "leverage": 1,
            "entry_fee": fee,
            "exit_fee_reserved": round(notional * EXIT_FEE_RATE, 4),
            "funding_pnl": 0.0,
            "basis_pnl": 0.0,
            "premium": entry["close"],
            "premium_time": entry["time"],
            "opened": now.isoformat(timespec="seconds"),
            "applied": [],
            "months": {},
            "sealed": [],
            "why": "held unlevered carry; round trip is not paid every month",
            "price_source": "https://data.binance.vision/",
            "price_at": entry["time"],
            "paper_only": True,
            "shadow_only": True,
            "fill_id": f"btc-carry|{now.isoformat(timespec='seconds')}",
            "exit_plan": _exit_plan(),
        })
        state["last_action"] = "open"
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
    _seal_finished_months(state, pos, now)
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
    blocked = os.environ.get("DESK_BLOCK_ENTRIES") == "1"
    before = len(state.get("open") or [])
    decision = decide_hold(
        state, marks, floor=cfg.get("venue_min_edge"), block_entries=blocked and before == 0,
    )
    state = hold_step(
        state, marks, cfg, now,
        block_entries=(blocked and before == 0) or decision["action"] != "open",
    )
    state["decision"] = decision["action"]
    state["floor"] = decision["floor"]
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
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


def _urlopen(url: str) -> bytes | None:
    if "fapi.binance.com" in url:
        return None
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
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
    tmp = path + ".tmp"
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
