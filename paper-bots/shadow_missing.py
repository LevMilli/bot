#!/usr/bin/env python3
"""Shared engine for the nine paper shadows that buy nothing.

Each tower looks in the repo for its own series ticker. A game-winner ticker,
a 15-minute series, or a spot symbol is not that ticker. When the series is
not named, the tower records that and skips. It does not invent a ticker, a
fill, or a fair price. Stake stays 0. Live orders stay off.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Files that already name series. The shadow folders are not a source of tickers.
SCAN_FILES = (
    "sports-gap-paper/gap_bot.py",
    "commodity-15m-paper/bot.py",
    "btc15m-signal/btc15m_signal.py",
    "desk_roi_plan.py",
)

SPORTS_FLOOR = 0.06
BINARY_FLOOR = 0.05
MENTIONS_CLEAR = 0.05
INX_FLOOR = 0.02

_TICKER = re.compile(r"\bKX[A-Z0-9]{3,}\b")
_QUOTED = re.compile(r"""['"]([^'"]+)['"]""")
_FLOAT = re.compile(r"[-+]?(?:\d+\.\d+|\d+)(?:[eE][-+]?\d+)?")


TOWERS = (
    {
        "id": "point-spread",
        "name": "Point spread",
        "folder": "point-spread-paper",
        "venue": "kalshi_sports",
        "floor": SPORTS_FLOOR,
        "series_attrs": ("SPREAD_SERIES", "POINT_SPREAD_SERIES"),
        "reject_attrs": ("SPORTS",),
        "spread_cap_attr": "MAX_SPREAD",
        "rule": (
            "Point spread on the six leagues. The game-winner series are a different settle. "
            "Clears the sports floor 0.06 after the taker once a series exists. Spread cap is the game-winner cap when that cap is already in the repo."
        ),
        "floor_line": "Sports floor 0.06 cannot be lowered",
    },
    {
        "id": "game-total",
        "name": "Game total",
        "folder": "game-total-paper",
        "venue": "kalshi_sports",
        "floor": SPORTS_FLOOR,
        "series_attrs": ("TOTAL_SERIES", "GAME_TOTAL_SERIES"),
        "reject_attrs": ("SPORTS",),
        "spread_cap_attr": "MAX_SPREAD",
        "rule": (
            "Game total on the six leagues. A total settles on the combined score. "
            "The game-winner series do not. Clears the sports floor 0.06 once a series exists."
        ),
        "floor_line": "Sports floor 0.06 cannot be lowered",
    },
    {
        "id": "commodity-calendar",
        "name": "Commodity calendar",
        "folder": "commodity-calendar-paper",
        "venue": "kalshi_commodity15m",
        "floor": BINARY_FLOOR,
        "series_attrs": ("CALENDAR_SERIES", "COMMODITY_CALENDAR_SERIES"),
        "reject_attrs": ("SERIES",),
        "commission_attrs": ("CALENDAR_COMMISSION", "COMMODITY_CALENDAR_COMMISSION"),
        "deferred_attrs": ("DEFERRED_MONTH", "CALENDAR_MONTHS"),
        "front_symbols": ("CL=F", "GC=F"),
        "binary_floor_not_a_fee": True,
        "rule": (
            "Listed calendar in WTI or gold. CL=F and GC=F are 15-minute spot inputs, not this spread. "
            "The commodity 0.05 floor is a binary lock and is not a futures commission. "
            "This tower does not inherit the 15-minute stake ladder."
        ),
        "floor_line": "Commodity binary floor 0.05 stays locked and is not this spread's commission",
    },
    {
        "id": "player-props",
        "name": "Player props",
        "folder": "player-props-paper",
        "venue": "kalshi_sports",
        "floor": SPORTS_FLOOR,
        "series_attrs": ("PROP_SERIES", "PLAYER_PROP_SERIES"),
        "reject_attrs": ("SPORTS",),
        "spread_cap_attr": "MAX_SPREAD",
        "rule": (
            "A player stat contract on the six leagues. Props are a different settle from the game winner. "
            "Clears the sports floor 0.06 once a series exists. Buying the favorite is not a fill."
        ),
        "floor_line": "Sports floor 0.06 cannot be lowered",
    },
    {
        "id": "period-winner",
        "name": "Period winner",
        "folder": "period-winner-paper",
        "venue": "kalshi_sports",
        "floor": SPORTS_FLOOR,
        "series_attrs": ("PERIOD_SERIES", "FIRST_HALF_SERIES"),
        "reject_attrs": ("SPORTS",),
        "rule": (
            "First-half or period winner, not the full game. "
            "A full-game win probability is not this fair. Clears the sports floor 0.06 once a series exists."
        ),
        "floor_line": "Sports floor 0.06 cannot be lowered",
    },
    {
        "id": "btc-options",
        "name": "BTC options",
        "folder": "btc-options-paper",
        "venue": "kalshi_btc15m",
        "floor": BINARY_FLOOR,
        "series_attrs": ("BTC_OPTIONS_SERIES", "OPTIONS_SERIES"),
        "reject_attrs": ("CRYPTO_SERIES",),
        "commission_attrs": ("OPTIONS_COMMISSION", "BTC_OPTIONS_COMMISSION"),
        "binary_floor_not_a_fee": True,
        "logs_gap": True,
        "rule": (
            "Listed BTC options, implied versus later realized. "
            "Does not trade KXBTC15M, KXETH15M, or KXBTCD. "
            "The BTC 0.05 floor is the binary lock, not an options commission. This tower does not sell options."
        ),
        "floor_line": "BTC binary floor 0.05 stays locked and is not an options commission",
    },
    {
        "id": "champions-league",
        "name": "Champions League",
        "folder": "champions-league-paper",
        "venue": "kalshi_sports",
        "floor": SPORTS_FLOOR,
        "series_attrs": ("UCL_SERIES", "CHAMPIONS_LEAGUE_SERIES"),
        "reject_attrs": ("SPORTS",),
        "rule": (
            "UEFA Champions League game winner. It is not a league in the six-sport book. "
            "Clears the sports floor 0.06 once a series exists. Buying the favorite is not a fill."
        ),
        "floor_line": "Sports floor 0.06 cannot be lowered",
    },
    {
        "id": "polymarket-mentions",
        "name": "Polymarket mentions",
        "folder": "polymarket-mentions-paper",
        "venue": "kalshi_econ",
        "floor": MENTIONS_CLEAR,
        "series_attrs": ("MENTION_MARKETS", "MENTION_SERIES"),
        "quoted_series": True,
        "taker_attr": "POLYMARKET_TAKER_RATE",
        "taker_key": "mentions",
        "rule": (
            "Mention contracts on Polymarket only. No mentions key was added under the locked floors. "
            "The taker coefficient is the mentions rate already in the repo. "
            "A logged edge would still have to clear 0.05. This tower does not buy a phrase."
        ),
        "floor_line": "No mentions floor was added under 0.05. INX and DEX stay at 0.02",
    },
    {
        "id": "esports-match",
        "name": "Esports match",
        "folder": "esports-match-paper",
        "venue": "kalshi_sports",
        "floor": SPORTS_FLOOR,
        "series_attrs": ("ESPORTS_SERIES", "ESPORTS_MATCH_SERIES"),
        "reject_attrs": ("SPORTS",),
        "rule": (
            "Match winner in a titled esports league. It is not in the six-sport book. "
            "Clears the sports floor 0.06 once a series exists. Buying the favorite is not a fill."
        ),
        "floor_line": "Sports floor 0.06 cannot be lowered",
    },
)

BY_ID = {row["id"]: row for row in TOWERS}


def spec_for(tower_id: str) -> dict:
    row = BY_ID.get(tower_id)
    if row is None:
        raise KeyError(tower_id)
    return row


def locked_floor(spec: dict) -> float:
    """Locked venue floor. A config file cannot pull it down."""
    fallback = float(spec["floor"])
    key = str(spec["venue"])
    try:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        import desk_profit
        live = float(desk_profit.DEFAULT_VENUE_MIN_EDGE[key])
    except Exception:
        live = fallback
    floor = max(fallback, live)
    if abs(floor - INX_FLOOR) < 1e-12 and fallback > INX_FLOOR:
        floor = fallback
    return floor


def locked_cfg(spec: dict, raw: dict | None = None) -> dict:
    cfg = dict(raw or {})
    floor = locked_floor(spec)
    cfg["paper_only"] = True
    cfg["live_orders"] = False
    cfg["shadow_only"] = True
    cfg["stake_usd"] = 0.0
    cfg["starter_cash"] = 0.0
    cfg["buys"] = False
    asked = _num(cfg.get("venue_min_edge"))
    if asked is None:
        asked = floor
    cfg["venue_min_edge"] = max(floor, asked)
    if abs(cfg["venue_min_edge"] - INX_FLOOR) < 1e-12 and floor > INX_FLOOR:
        cfg["venue_min_edge"] = floor
    return cfg


def evaluate(tower_id: str, desk_root: str | None = None, registry: dict | None = None) -> dict:
    """One log row. Buys nothing. A missing series is a skip, not a sample."""
    spec = spec_for(tower_id)
    desk_root = desk_root or HERE
    cfg = locked_cfg(spec)
    found = _scan(desk_root)
    if registry:
        _apply_registry(found, registry)
    rejected = _rejected(spec, found)
    series = [name for name in _series_tokens(spec, found) if name not in rejected]
    commission = _commission(spec, found)
    deferred = _deferred(spec, found)
    front = _front_symbols(spec, found)
    taker = _taker_rate(spec, found)
    cap = _spread_cap(spec, found)
    missing = not series
    if spec.get("deferred_attrs") and not deferred:
        missing = True
    reason = _reason(spec, missing=missing, commission=commission, series=series)
    row = {
        "tower": spec["id"],
        "action": "skip",
        "reason": reason,
        "ticker_missing": missing,
        "series": series,
        "rejected_series": sorted(rejected),
        "commission": commission,
        "deferred_month": deferred,
        "front_symbols": front,
        "taker_rate": taker,
        "spread_cap": cap,
        "floor": cfg["venue_min_edge"],
        "floor_key": spec["venue"],
        "binary_floor_not_a_fee": bool(spec.get("binary_floor_not_a_fee")),
        "inherits_15m_ladder": False,
        "sells": 0,
        "buys_favorite": False,
        "fair": None,
        "fill": None,
        "implied": None,
        "realized": None,
        "edge": None,
        "buys": 0,
        "stake_usd": 0.0,
        "paper_only": True,
        "shadow_only": True,
        "live_orders": False,
        "counts_as_evidence": False,
        "graded": False,
        "fill_tax_when_graded": 0.01,
    }
    if spec.get("logs_gap"):
        row["gap"] = None
    return row


def empty_state() -> dict:
    return {
        "cash": 0.0,
        "open": [],
        "closed": [],
        "paper_only": True,
        "shadow_only": True,
        "live_orders": False,
        "stake_usd": 0.0,
        "buys": 0,
        "checks": 0,
        "evidence_n": 0,
    }


def run_once(
    tower_id: str,
    desk_root: str | None = None,
    now: dt.datetime | None = None,
    registry: dict | None = None,
    cfg: dict | None = None,
) -> int:
    spec = spec_for(tower_id)
    desk_root = desk_root or HERE
    tower = os.path.join(desk_root, spec["folder"])
    os.makedirs(tower, exist_ok=True)
    locked_cfg(spec, cfg if cfg is not None else _read_json(os.path.join(tower, "config.json")))
    now = now or dt.datetime.now(dt.timezone.utc)
    decision = evaluate(tower_id, desk_root=desk_root, registry=registry)
    added = _append_evidence(tower, decision, now)
    state = _read_json(os.path.join(tower, "paper_account.json")) or empty_state()
    if not isinstance(state, dict):
        state = empty_state()
    state.update({
        "cash": 0.0,
        "open": [],
        "closed": [],
        "paper_only": True,
        "shadow_only": True,
        "live_orders": False,
        "stake_usd": 0.0,
        "buys": 0,
        "checks": int(state.get("checks") or 0) + 1,
        "last_check": now.isoformat(timespec="seconds"),
        "evidence_n": 0,
        "logged_n": len(added),
        "ticker_missing": bool(decision.get("ticker_missing")),
        "series": list(decision.get("series") or []),
        "reason": decision.get("reason") or "",
        "fair": None,
        "fill": None,
    })
    _write_json(os.path.join(tower, "paper_account.json"), state)
    _append_research(tower, now, decision)
    _emit(decision)
    return 0


def _reason(spec: dict, *, missing: bool, commission, series: list) -> str:
    parts = []
    if not series:
        parts.append("series ticker is not in the repo")
    elif spec.get("deferred_attrs") and missing:
        parts.append("deferred month is not in the repo")
    if spec.get("commission_attrs") and commission is None:
        parts.append("commission is not in the repo")
    if parts:
        return "; ".join(parts)
    return "series is named; no public book, so no fill and no fair are logged"


def _emit(decision: dict) -> None:
    reason = str(decision.get("reason") or "series ticker is not in the repo")
    print("SIGNAL: SKIP " + reason)
    print("CARD: " + reason)
    print("no trade")


def _append_evidence(tower: str, decision: dict, now: dt.datetime) -> list[dict]:
    """One standing skip line. A missing ticker is not evidence and is not repeated."""
    path = os.path.join(tower, "evidence.jsonl")
    key = (str(decision.get("reason") or ""), tuple(decision.get("series") or []))
    if key in _evidence_keys(path):
        return []
    payload = dict(decision)
    payload["at"] = now.isoformat(timespec="seconds")
    payload["counts_as_evidence"] = False
    payload["buys"] = 0
    payload["stake_usd"] = 0.0
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return [payload]


def _evidence_keys(path: str) -> set[tuple]:
    seen: set[tuple] = set()
    if not os.path.isfile(path):
        return seen
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                seen.add((str(row.get("reason") or ""), tuple(row.get("series") or [])))
    except OSError:
        return seen
    return seen


def _append_research(tower: str, now: dt.datetime, decision: dict) -> None:
    path = os.path.join(tower, "research.jsonl")
    payload = {
        "at": now.isoformat(timespec="seconds"),
        "paper_only": True,
        "shadow_only": True,
        "live_orders": False,
        "buys": 0,
        "stake_usd": 0.0,
        "fair": None,
        "fill": None,
        "decision": decision,
    }
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _scan(desk_root: str) -> dict[str, str]:
    found: dict[str, str] = {}
    names = set()
    for spec in TOWERS:
        names.update(spec.get("series_attrs") or ())
        names.update(spec.get("reject_attrs") or ())
        names.update(spec.get("commission_attrs") or ())
        names.update(spec.get("deferred_attrs") or ())
        if spec.get("spread_cap_attr"):
            names.add(spec["spread_cap_attr"])
        if spec.get("taker_attr"):
            names.add(spec["taker_attr"])
    names.add("YAHOO")
    for rel in SCAN_FILES:
        text = _read_text(os.path.join(desk_root, rel))
        if not text:
            continue
        for name in names:
            if name in found:
                continue
            body = _assignment_body(text, name)
            if body is not None:
                found[name] = body
    return found


def _apply_registry(found: dict[str, str], registry: dict) -> None:
    """Test hook. Does not write a ticker into the repo."""
    for name, value in (registry.get("assignments") or {}).items():
        if isinstance(value, (list, tuple)):
            inner = ", ".join(repr(str(item)) for item in value)
            found[str(name)] = "(" + inner + ")"
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            found[str(name)] = str(value)
        elif isinstance(value, str):
            found[str(name)] = value


def _series_tokens(spec: dict, found: dict[str, str]) -> list[str]:
    out: list[str] = []
    quoted = bool(spec.get("quoted_series"))
    for name in spec.get("series_attrs") or ():
        body = found.get(name)
        if not body:
            continue
        out.extend(_tokens(body, quoted=quoted))
    deduped = []
    seen = set()
    for name in out:
        if name in seen:
            continue
        seen.add(name)
        deduped.append(name)
    return deduped


def _rejected(spec: dict, found: dict[str, str]) -> set[str]:
    out: set[str] = set()
    for name in spec.get("reject_attrs") or ():
        body = found.get(name)
        if not body:
            continue
        out.update(_tokens(body, quoted=False))
    return out


def _commission(spec: dict, found: dict[str, str]):
    for name in spec.get("commission_attrs") or ():
        body = found.get(name)
        if body is None:
            continue
        match = _FLOAT.search(body)
        if not match:
            continue
        number = _num(match.group(0))
        if number is not None:
            return number
    return None


def _deferred(spec: dict, found: dict[str, str]) -> list[str]:
    out: list[str] = []
    for name in spec.get("deferred_attrs") or ():
        body = found.get(name)
        if not body:
            continue
        out.extend(_tokens(body, quoted=True))
    return out


def _front_symbols(spec: dict, found: dict[str, str]) -> list[str]:
    wanted = tuple(spec.get("front_symbols") or ())
    if not wanted:
        return []
    body = found.get("YAHOO") or ""
    present = []
    for symbol in wanted:
        if symbol in body:
            present.append(symbol)
    return present


def _taker_rate(spec: dict, found: dict[str, str]):
    attr = spec.get("taker_attr")
    key = spec.get("taker_key")
    if not attr or not key:
        return None
    body = found.get(attr) or ""
    match = re.search(r"""['"]%s['"]\s*:\s*([0-9.]+)""" % re.escape(str(key)), body)
    if not match:
        return None
    return _num(match.group(1))


def _spread_cap(spec: dict, found: dict[str, str]):
    name = spec.get("spread_cap_attr")
    if not name:
        return None
    body = found.get(name)
    if body is None:
        return None
    match = _FLOAT.search(body)
    if not match:
        return None
    return _num(match.group(0))


def _tokens(body: str, *, quoted: bool) -> list[str]:
    if quoted:
        raw = _QUOTED.findall(body)
    else:
        raw = _TICKER.findall(body)
    out = []
    for item in raw:
        text = str(item or "").strip()
        if not text or text in out:
            continue
        out.append(text)
    return out


def _assignment_body(text: str, name: str) -> str | None:
    pattern = re.compile(r"(?m)^%s\s*=" % re.escape(name))
    match = pattern.search(text)
    if match is None:
        return None
    rest = text[match.end():].lstrip()
    if not rest:
        return None
    opener = rest[0]
    if opener not in "([{":
        return rest.splitlines()[0].strip()
    closer = {"(": ")", "[": "]", "{": "}"}[opener]
    depth = 0
    quote = ""
    escape = False
    for index, ch in enumerate(rest):
        if quote:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == quote:
                quote = ""
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return rest[: index + 1]
    return None


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _read_text(path: str) -> str:
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def _read_json(path: str):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return data


def _write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def main(tower_id: str, argv: list[str] | None = None) -> int:
    spec = spec_for(tower_id)
    argv = list(sys.argv[1:] if argv is None else argv)
    tower = os.path.join(HERE, spec["folder"])
    if "--reset" in argv:
        os.makedirs(tower, exist_ok=True)
        _write_json(os.path.join(tower, "paper_account.json"), empty_state())
        print("reset paper account")
        return 0
    return run_once(tower_id)
