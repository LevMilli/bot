"""
desk_more.py — Phase 0/1 “trade more, hopefully make more” helpers.

Tracks:
  T Throughput — skip leaderboard, weekend attribution, near-miss shadow, depth rank
  R Recycling — sticky open audit
  Q Quality — tower budgets, CLV, hillclimb lever, hit decay hooks

Paper only. No live orders. No profit guarantee.
"""
from __future__ import annotations

import json
import math
import os
import time
from typing import Any, Iterable

MORE_NAME = "desk_more_state.json"
CLV_NAME = "desk_sports_clv.json"

# Canonical skip codes for the staff leaderboard.
SKIP_CODES = (
    "WEEKEND",
    "edge",
    "cushion",
    "z",
    "depth",
    "news",
    "correlation",
    "entry_gate",
    "learning",
    "vol_safe",
    "cash",
    "open_risk",
    "max_open",
    "fair",
    "ask_band",
    "close_game",
    "already_holding",
    "calendar",
    "data",
    "budget",
    "other",
)

# Plan E1 #129 — stable public taxonomy (uppercase) mapped from internal codes.
SKIP_TAXONOMY_STABLE = (
    "EDGE",
    "Z",
    "P",
    "DEPTH",
    "NEWS",
    "WEEKEND",
    "CORR",
    "BUDGET",
    "LEARN",
    "CALENDAR",
    "DATA",
)
_SKIP_TO_STABLE = {
    "edge": "EDGE",
    "cushion": "EDGE",
    "z": "Z",
    "fair": "P",
    "ask_band": "P",
    "close_game": "P",
    "depth": "DEPTH",
    "news": "NEWS",
    "WEEKEND": "WEEKEND",
    "correlation": "CORR",
    "open_risk": "BUDGET",
    "max_open": "BUDGET",
    "entry_gate": "BUDGET",
    "budget": "BUDGET",
    "vol_safe": "BUDGET",
    "cash": "BUDGET",
    "learning": "LEARN",
    "calendar": "CALENDAR",
    "data": "DATA",
    "already_holding": "DATA",
    "other": "DATA",
}


def stable_skip_code(code: str | None) -> str:
    """Map internal skip code → stable taxonomy label (EDGE/Z/P/…)."""
    raw = str(code or "").strip()
    if not raw:
        return "DATA"
    if raw in SKIP_TAXONOMY_STABLE:
        return raw
    return _SKIP_TO_STABLE.get(raw, _SKIP_TO_STABLE.get(raw.lower(), "DATA"))

# Soft per-tower share of desk max_open_risk (must sum ≤ 1.0).
DEFAULT_TOWER_BUDGET_SHARE = {
    "sports-gap": 0.35,
    "btc15m": 0.30,
    "commodity-15m": 0.15,
    "kalshi-sp": 0.08,
    "kalshi-sized": 0.07,
    "memecoin": 0.05,
}

# Depth need for depth-adjusted edge (contracts at/below ask).
DEFAULT_DEPTH_NEED = 10.0

# Sports pre-tip book warm windows (T−15 / T−5). Priority only — never waives floors.
TIP_WARM_WINDOWS_MIN = (15, 5)
KALSHI_PUBLIC = "https://api.elections.kalshi.com/trade-api/v2"
SPORTS_SERIES_BY_LEAGUE = {
    "NFL": "KXNFLGAME",
    "NCAAF": "KXNCAAFGAME",
    "NBA": "KXNBAGAME",
    "WNBA": "KXWNBAGAME",
    "MLB": "KXMLBGAME",
    "NHL": "KXNHLGAME",
}

# Near-miss shadow: tiny stake, never counts toward desk open-risk.
NEAR_MISS_STAKE = 2.0
NEAR_MISS_Z_BAND = (0.55, 0.65)
NEAR_MISS_P_BAND = (0.76, 0.80)

# Sticky: open longer than expected settle window (hours).
STICKY_HOURS = {
    "btc15m": 1.0,
    "commodity-15m": 1.0,
    "sports-gap": 8.0,
    "kalshi-sp": 36.0,
    "kalshi-sized": 36.0,
    "memecoin": 12.0,
}

# Hillclimb: one lever at a time; kill if taxed EV drops 2 weeks.
HILLCLIMB_LEVERS = (
    "VOL_SAFE",
    "HIT_FOR_BIG",
    "venue_min_edge_btc",
    "min_cushion_btc",
    "kelly_fraction",
)

# Per-series vol prior offsets added to volatility_score (higher → safer).
SERIES_VOL_PRIORS = {
    "KXBTC15M": 0.00,
    "KXETH15M": 0.02,
    "KXPALLADIUM15M": 0.08,
    "KXNATGAS15M": 0.15,
    "KXCOPPER15M": 0.06,
    "KXBRENT15M": 0.10,
    "KXWTI15M": 0.10,
    "KXSILVER15M": 0.08,
    "KXGOLD15M": 0.04,
    "KXPLATINUM15M": 0.07,
}

HIT_DECAY_HALFLIFE_DAYS = 14.0  # exponential decay on settled hits


def more_path(root: str | None = None) -> str:
    base = root or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, MORE_NAME)


def clv_path(root: str | None = None) -> str:
    base = root or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, CLV_NAME)


def _empty_more() -> dict:
    return {
        "paper_only": True,
        "version": 1,
        "skip_day": {},
        "near_miss": [],
        "sticky": [],
        "hillclimb": {
            "active_lever": None,
            "baseline": None,
            "weeks": [],
            "note": "Change one lever per week; revert if taxed EV falls 2 weeks.",
        },
        "last_at": None,
    }


def _empty_clv() -> dict:
    return {
        "paper_only": True,
        "version": 1,
        "rows": [],
        "last_at": None,
    }


def load_more(root: str | None = None) -> dict:
    path = more_path(root)
    if not os.path.exists(path):
        return _empty_more()
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return _empty_more()
    except (OSError, json.JSONDecodeError):
        return _empty_more()
    base = _empty_more()
    base.update({k: data.get(k, base[k]) for k in base})
    if not isinstance(base.get("skip_day"), dict):
        base["skip_day"] = {}
    if not isinstance(base.get("near_miss"), list):
        base["near_miss"] = []
    if not isinstance(base.get("sticky"), list):
        base["sticky"] = []
    if not isinstance(base.get("hillclimb"), dict):
        base["hillclimb"] = _empty_more()["hillclimb"]
    return base


def save_more(state: dict, root: str | None = None) -> None:
    path = more_path(root)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    state = dict(state)
    state["paper_only"] = True
    nm = list(state.get("near_miss") or [])
    if len(nm) > 500:
        nm = nm[-500:]
    state["near_miss"] = nm
    sticky = list(state.get("sticky") or [])
    if len(sticky) > 200:
        sticky = sticky[-200:]
    state["sticky"] = sticky
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def load_clv(root: str | None = None) -> dict:
    path = clv_path(root)
    if not os.path.exists(path):
        return _empty_clv()
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return _empty_clv()
    except (OSError, json.JSONDecodeError):
        return _empty_clv()
    base = _empty_clv()
    base.update({k: data.get(k, base[k]) for k in base})
    if not isinstance(base.get("rows"), list):
        base["rows"] = []
    return base


def save_clv(state: dict, root: str | None = None) -> None:
    path = clv_path(root)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    state = dict(state)
    state["paper_only"] = True
    rows = list(state.get("rows") or [])
    if len(rows) > 2000:
        rows = rows[-2000:]
    state["rows"] = rows
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def _finite(x) -> float | None:
    try:
        n = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def classify_skip(reason: str | None, *, weekday: int | None = None) -> str:
    """Map free-text skip reason → canonical code.

    weekday: 0=Mon … 6=Sun (Python). Sat/Sun + calendar skip → WEEKEND.
    """
    text = str(reason or "").strip().lower()
    if not text:
        return "other"
    if weekday is not None and int(weekday) >= 5:
        if any(k in text for k in ("weekend", "closed", "inx", "equity", "market closed", "no live")):
            return "WEEKEND"
    if "weekend" in text:
        return "WEEKEND"
    if "correlation" in text or "correlated" in text:
        return "correlation"
    if "entry_gate" in text or "daily loss" in text or "max open risk is reached" in text:
        return "entry_gate"
    if (
        "learning" in text
        or "adverse cool" in text
        or ("bucket" in text and "cool" in text)
    ):
        return "learning"
    if "news" in text or "blackout" in text or "fomc" in text or "cpi" in text:
        return "news"
    if "calendar" in text or "forexfactory" in text or "ff event" in text:
        return "calendar"
    # Stale-world / clock-skew are feed freshness — not capacity invent (DATA).
    if (
        "stale-world" in text
        or "clock-skew" in text
        or ("data" in text and ("error" in text or "missing" in text or "unavailable" in text))
    ):
        return "data"
    # Daily-R settle-only is a budget lock (fee-clear profit target) — not DATA/other.
    # Keeps zero-buy / skip_board BUDGET taxonomy honest beside CARD densify.
    if (
        "settle-only" in text
        or "daily r budget" in text
        or "tower budget" in text
        or "budget full" in text
        or ("budget" in text and "left" in text)
    ):
        return "budget"
    if "cushion" in text:
        return "cushion"
    if " z " in f" {text} " or text.startswith("z ") or "thin cushion vs" in text or "coinbase-only" in text:
        return "z"
    if "depth" in text or "contracts at/below" in text:
        return "depth"
    if "vol" in text and ("safe" in text or "high" in text or "extreme" in text):
        return "vol_safe"
    if "fair" in text and ("<" in text or "floor" in text or "safer" in text):
        return "fair"
    if "close game" in text:
        return "close_game"
    if "ask" in text and ("band" in text or "outside" in text or "range" in text):
        return "ask_band"
    if "already holding" in text:
        return "already_holding"
    if "cash" in text or "broke" in text:
        return "cash"
    if "max open risk" in text or "open-risk" in text or "open risk" in text:
        return "open_risk"
    if "max open position" in text:
        return "max_open"
    if "edge" in text or "gap" in text and ("<" in text or "short" in text or "min" in text):
        return "edge"
    if "p " in text and "<" in text:
        return "fair"
    return "other"


def is_weekend_attribution(code: str, weekday: int | None) -> bool:
    if code == "WEEKEND":
        return True
    if weekday is not None and int(weekday) >= 5 and code in ("other", "edge", "fair"):
        return True
    return False


def depth_adjusted_edge(edge, depth=None, need: float = DEFAULT_DEPTH_NEED) -> float:
    """edge × min(1, depth/need). Missing depth → raw edge (no boost, no haircut)."""
    e = _finite(edge)
    if e is None:
        return 0.0
    e = max(0.0, e)
    d = _finite(depth)
    if d is None or need <= 0:
        return round(e, 6)
    return round(e * min(1.0, max(0.0, d) / float(need)), 6)


def opportunity_score_v2(edge, confidence, depth=None, need: float = DEFAULT_DEPTH_NEED) -> float:
    """Depth-adjusted edge × confidence (Phase 1 rank)."""
    adj = depth_adjusted_edge(edge, depth, need=need)
    c = _finite(confidence)
    if c is None:
        c = 0.0
    c = max(0.0, min(1.0, c))
    return round(adj * c, 6)


def prefetch_map(jobs: Iterable, worker, *, max_workers: int = 8) -> tuple[dict, dict]:
    """Parallel map for orderbook / spot jobs.

    ``jobs`` are hashable keys (or any hashable). ``worker(job) -> value``.
    Returns ``({job: value}, {job: error_str})``. Empty jobs → empty maps.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    jobs_list = list(jobs or [])
    ok: dict = {}
    errors: dict = {}
    if not jobs_list:
        return ok, errors

    def _one(job):
        try:
            return job, worker(job), None
        except Exception as exc:  # noqa: BLE001
            return job, None, str(exc)

    workers = min(int(max_workers) if max_workers else 1, max(1, len(jobs_list)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(_one, job) for job in jobs_list]
        for fut in as_completed(futs):
            job, value, err = fut.result()
            if err:
                errors[job] = err
            else:
                ok[job] = value
    return ok, errors


def sports_quote_cache_path(root: str | None = None) -> str:
    base = root or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "sports-gap-paper", "quote_cache.json")


def inx_quote_cache_path(root: str | None = None, *, bot: str = "kalshi-sp") -> str:
    """Quote cache path for INX tower (kalshi-sp or kalshi-sized)."""
    base = root or os.path.dirname(os.path.abspath(__file__))
    folder = "kalshi-sized-paper" if str(bot) == "kalshi-sized" else "kalshi-sp500-paper"
    return os.path.join(base, folder, "quote_cache.json")


def _inx_quote_cache_put(root: str | None, url: str, body: Any, *, bot: str = "kalshi-sp") -> None:
    path = inx_quote_cache_path(root, bot=bot)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data: dict = {}
    try:
        with open(path, encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            data = loaded
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        data = {}
    data[str(url)] = {"at": time.time(), "body": body, "warm": "pre_noon_1150_ct"}
    if len(data) > 80:
        newest = sorted(
            data.items(),
            key=lambda item: float((item[1] or {}).get("at") or 0),
        )[-80:]
        data = dict(newest)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    os.replace(tmp, path)


# Pre-noon INX warm window (#515): 11:50 CT ±2 min observe-only book warm.
INX_PRE_NOON_WARM_HHMM = (11, 50)
INX_PRE_NOON_WINDOW_MIN = 2
INX_WARM_SERIES = ("KXINXU",)


def _sports_quote_cache_load(root: str | None = None) -> dict:
    path = sports_quote_cache_path(root)
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}


def _sports_quote_cache_put(root: str | None, url: str, body: Any) -> None:
    """Write one URL body into sports-gap quote_cache (warm path)."""
    path = sports_quote_cache_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = _sports_quote_cache_load(root)
    data[str(url)] = {"at": time.time(), "body": body}
    if len(data) > 80:
        newest = sorted(
            data.items(),
            key=lambda item: float((item[1] or {}).get("at") or 0),
        )[-80:]
        data = dict(newest)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    os.replace(tmp, path)


def _default_kalshi_fetch(url: str):
    import urllib.request

    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (paper warm_tip_books)"}
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def series_markets_url(series: str) -> str:
    tick = str(series or "").strip()
    return (
        f"{KALSHI_PUBLIC}/markets?series_ticker={tick}&status=open&limit=1000"
    )


def in_inx_pre_noon_warm_window(now_ct=None) -> bool:
    """True when local CT clock is within ±2 min of 11:50 (pre-noon warm)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    if now_ct is None:
        now_ct = datetime.now(ZoneInfo("America/Chicago"))
    elif getattr(now_ct, "tzinfo", None) is None:
        now_ct = now_ct.replace(tzinfo=ZoneInfo("America/Chicago"))
    target_m = INX_PRE_NOON_WARM_HHMM[0] * 60 + INX_PRE_NOON_WARM_HHMM[1]
    now_m = int(now_ct.hour) * 60 + int(now_ct.minute)
    return abs(now_m - target_m) <= int(INX_PRE_NOON_WINDOW_MIN)


def warm_inx_books_pre_noon(
    root: str | None,
    *,
    now_ct=None,
    fetch=None,
    series: tuple | list | None = None,
    bots: tuple | list | None = None,
    force: bool = False,
) -> dict:
    """Pre-noon INX book warm at 11:50 CT into quote cache (#515).

    Observe-only — never places orders; still honors 1/day buy limit.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    if now_ct is None:
        now_ct = datetime.now(ZoneInfo("America/Chicago"))
    in_window = bool(force) or in_inx_pre_noon_warm_window(now_ct)
    series_list = list(series or INX_WARM_SERIES)
    bot_list = [str(b) for b in (bots or ("kalshi-sp", "kalshi-sized"))]
    if not in_window:
        return {
            "paper_only": True,
            "fee_floors_locked": True,
            "observe_only": True,
            "orders_placed": False,
            "warmed": False,
            "in_window": False,
            "now_ct": now_ct.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "target_hhmm": f"{INX_PRE_NOON_WARM_HHMM[0]:02d}:{INX_PRE_NOON_WARM_HHMM[1]:02d}",
            "buys_still_1_per_day": True,
            "note": "Outside 11:50 CT warm window — no fetch. 1/day buy limit unchanged.",
        }
    fetcher = fetch or _default_kalshi_fetch
    warmed: list[dict] = []
    errors: dict[str, str] = {}
    for ser in series_list:
        url = series_markets_url(str(ser))
        try:
            body = fetcher(url)
            for bot in bot_list:
                _inx_quote_cache_put(root, url, body, bot=bot)
            warmed.append({
                "series": str(ser),
                "url": url,
                "markets_n": len((body or {}).get("markets") or [])
                if isinstance(body, dict) else 0,
                "bots": list(bot_list),
            })
        except Exception as exc:  # noqa: BLE001
            errors[str(ser)] = str(exc)[:160]
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "orders_placed": False,
        "warmed": True,
        "in_window": True,
        "now_ct": now_ct.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "target_hhmm": f"{INX_PRE_NOON_WARM_HHMM[0]:02d}:{INX_PRE_NOON_WARM_HHMM[1]:02d}",
        "warmed_n": len(warmed),
        "warmed_rows": warmed,
        "errors": errors,
        "buys_still_1_per_day": True,
        "max_trades_per_day": 1,
        "note": (
            "Pre-noon INX book warm @11:50 CT into quote_cache. Observe latency only — "
            "still 1/day buy limit; never softens INX 0.02 floor."
        ),
    }


def warm_tip_books(
    root: str | None,
    minutes_to_tip: float | int = 15,
    *,
    games: list | None = None,
    fetch=None,
    series_by_league: dict | None = None,
    put_cache=None,
) -> dict:
    """Prefetch Kalshi books for tip-soon games into sports quote_cache.

    Covers T−15 / T−5 warm windows (plan 447–448, 513–514). Never places
    orders and never waives venue floors — observe/warm only.
    """
    horizon = float(minutes_to_tip) if minutes_to_tip is not None else 15.0
    if horizon <= 0:
        horizon = 15.0
    league_map = dict(series_by_league or SPORTS_SERIES_BY_LEAGUE)
    fetcher = fetch or _default_kalshi_fetch
    writer = put_cache or (
        lambda url, body: _sports_quote_cache_put(root, url, body)
    )
    soon: list[dict] = []
    for g in games or []:
        if not isinstance(g, dict):
            continue
        tip = _finite(g.get("tip_in_min"))
        if tip is None:
            tip = _finite(g.get("eta_min"))
        if tip is None or tip <= 0 or tip > horizon + 1e-9:
            continue
        soon.append(g)
    series_keys: dict[str, str] = {}
    for g in soon:
        league = str(g.get("league") or "").strip().upper()
        series = str(g.get("series") or "").strip() or league_map.get(league, "")
        if not series:
            continue
        series_keys[series] = league or series
    warmed: list[dict] = []
    errors: dict[str, str] = {}
    for series, league in sorted(series_keys.items()):
        url = series_markets_url(series)
        try:
            body = fetcher(url)
            writer(url, body)
            warmed.append({
                "series": series,
                "league": league,
                "url": url,
                "markets_n": len((body or {}).get("markets") or [])
                if isinstance(body, dict)
                else 0,
            })
        except Exception as exc:  # noqa: BLE001
            errors[series] = str(exc)[:160]
    ticker_warmed = 0
    for g in soon:
        tick = str(g.get("kalshi_ticker") or g.get("market_ticker") or "").strip()
        if not tick or tick.startswith("http") or len(tick) < 6:
            continue
        if not tick.upper().startswith("KX"):
            continue
        url = f"{KALSHI_PUBLIC}/markets/{tick}/orderbook"
        try:
            body = fetcher(url)
            writer(url, body)
            ticker_warmed += 1
        except Exception as exc:  # noqa: BLE001
            errors[tick] = str(exc)[:160]
    band = 5 if horizon <= 5 + 1e-9 else (15 if horizon <= 15 + 1e-9 else int(horizon))
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "orders_placed": False,
        "minutes_to_tip": horizon,
        "tip_band": band,
        "games_n": len(soon),
        "warmed_n": len(warmed),
        "ticker_warmed_n": ticker_warmed,
        "warmed": warmed,
        "errors": errors,
        "windows": list(TIP_WARM_WINDOWS_MIN),
        "note": (
            f"Pre-tip warm T−{band}: prefetched {len(warmed)} series book(s) "
            "into quote_cache. Never waives sports 0.06 floor."
        ),
    }


def record_skip_codes(
    root: str | None,
    *,
    bot: str,
    reasons: list | None,
    weekday: int | None = None,
    day: str | None = None,
) -> list[str]:
    """Persist canonical skip codes for today's leaderboard."""
    codes = [classify_skip(r, weekday=weekday) for r in (reasons or ["other"])]
    if not codes:
        codes = ["other"]
    state = load_more(root)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    day_key = day or time.strftime("%Y-%m-%d", time.gmtime())
    day_row = state.setdefault("skip_day", {}).setdefault(
        day_key, {"by_code": {}, "by_bot": {}, "weekend_n": 0, "weekday_n": 0},
    )
    for code in codes:
        day_row["by_code"][code] = int(day_row["by_code"].get(code) or 0) + 1
        bot_map = day_row["by_bot"].setdefault(bot, {})
        bot_map[code] = int(bot_map.get(code) or 0) + 1
        if is_weekend_attribution(code, weekday):
            day_row["weekend_n"] = int(day_row.get("weekend_n") or 0) + 1
        else:
            day_row["weekday_n"] = int(day_row.get("weekday_n") or 0) + 1
    state["last_at"] = now
    save_more(state, root)
    return codes


def skip_leaderboard(root: str | None = None, *, day: str | None = None, top: int = 8) -> dict:
    state = load_more(root)
    day_key = day or time.strftime("%Y-%m-%d", time.gmtime())
    day_row = (state.get("skip_day") or {}).get(day_key) or {}
    by_code = day_row.get("by_code") or {}
    ranked = sorted(((k, int(v)) for k, v in by_code.items()), key=lambda kv: -kv[1])[: int(top)]
    weekend_n = int(day_row.get("weekend_n") or 0)
    weekday_n = int(day_row.get("weekday_n") or 0)
    total = weekend_n + weekday_n
    stable_counts: dict[str, int] = {}
    for code, n in by_code.items():
        key = stable_skip_code(code)
        stable_counts[key] = int(stable_counts.get(key) or 0) + int(n)
    stable_top = sorted(stable_counts.items(), key=lambda kv: -kv[1])[: int(top)]
    return {
        "paper_only": True,
        "day": day_key,
        "top": [{"code": c, "n": n, "stable": stable_skip_code(c)} for c, n in ranked],
        "stable_top": [{"code": c, "n": n} for c, n in stable_top],
        "taxonomy": list(SKIP_TAXONOMY_STABLE),
        "weekend_n": weekend_n,
        "weekday_n": weekday_n,
        "total": total,
        "weekend_share": round(weekend_n / total, 4) if total else None,
        "by_bot": day_row.get("by_bot") or {},
        "note": "WEEKEND skips are normal Sat/Sun — not a broken desk.",
    }


# E1 #116 — while memecoin is red, starve its share and feed BTC/commodity.
# ROI rescue: fire at −$5 so −$7.57 boards starve meme before another ticket.
MEME_RED_SHARE = 0.03
MEME_RED_LOCK_USD = 5.0
# Starve losers → feed fee-clear sports/BTC/commodity (never lower venue min_edge).
FEE_CLEAR_TOWERS = ("sports-gap", "btc15m", "commodity-15m")
INX_DRAWDOWN_CASH = 460.0
INX_LOSER_SHARE = 0.02
SPORTS_RED_TODAY = -10.0
SPORTS_RED_SHARE = 0.20


def _feed_fee_clear(
    shares: dict[str, float],
    cut: float,
    *,
    exclude: set[str] | None = None,
) -> None:
    """Redistribute cut into fee-clear towers (skip any currently being starved)."""
    if cut <= 1e-12:
        return
    skip = set(exclude or ())
    # Prefer sports tip books, then BTC, then commodity microstructure.
    weights = {"sports-gap": 0.40, "btc15m": 0.35, "commodity-15m": 0.25}
    live = {k: w for k, w in weights.items() if k not in skip}
    if not live:
        live = {"btc15m": 0.55, "commodity-15m": 0.45}
    total_w = sum(live.values()) or 1.0
    for bot_id, w in live.items():
        shares[bot_id] = float(shares.get(bot_id) or 0.0) + cut * (w / total_w)


def _cut_share(shares: dict[str, float], bot_id: str, target: float) -> float:
    cur = float(shares.get(bot_id) or 0.0)
    if cur <= target + 1e-12:
        shares[bot_id] = min(cur, target)
        return 0.0
    cut = cur - target
    shares[bot_id] = target
    return cut


def effective_tower_shares(
    cfg: dict | None = None,
    *,
    meme_today: float | None = None,
    red_lock_usd: float | None = None,
    today_by_bot: dict | None = None,
    cash_by_bot: dict | None = None,
    realized_by_bot: dict | None = None,
) -> dict[str, float]:
    """Tower budget shares: starve losers, feed fee-clear sports/BTC/commodity."""
    cfg = cfg or {}
    shares = cfg.get("tower_risk_budgets") if isinstance(cfg.get("tower_risk_budgets"), dict) else None
    shares = {str(k): float(v) for k, v in dict(shares or DEFAULT_TOWER_BUDGET_SHARE).items()}
    today_map = {str(k): _finite(v) for k, v in dict(today_by_bot or {}).items()}
    cash_map = {str(k): _finite(v) for k, v in dict(cash_by_bot or {}).items()}
    realized_map = {str(k): _finite(v) for k, v in dict(realized_by_bot or {}).items()}
    lock = float(MEME_RED_LOCK_USD if red_lock_usd is None else red_lock_usd)
    meme = meme_today
    if meme is None:
        meme = today_map.get("memecoin")
    if meme is None:
        meme = _finite(cfg.get("meme_today"))
    cut_total = 0.0
    exclude: set[str] = set()
    if meme is not None and meme <= -lock:
        cut_total += _cut_share(shares, "memecoin", float(MEME_RED_SHARE))
        exclude.add("memecoin")
    # INX drawdown: shrink both S&P twins, feed fee-clear towers.
    for inx_id in ("kalshi-sp", "kalshi-sized"):
        cash = cash_map.get(inx_id)
        if cash is not None and cash <= float(INX_DRAWDOWN_CASH):
            cut_total += _cut_share(shares, inx_id, float(INX_LOSER_SHARE))
            exclude.add(inx_id)
    sports_today = today_map.get("sports-gap")
    sports_realized = realized_map.get("sports-gap")
    sports_red_pnl = None
    if sports_today is not None and sports_realized is not None:
        sports_red_pnl = min(sports_today, sports_realized)
    elif sports_today is not None:
        sports_red_pnl = sports_today
    elif sports_realized is not None:
        sports_red_pnl = sports_realized
    sports_red = sports_red_pnl is not None and sports_red_pnl <= float(SPORTS_RED_TODAY)
    if sports_red:
        cut_total += _cut_share(shares, "sports-gap", float(SPORTS_RED_SHARE))
        exclude.add("sports-gap")
    _feed_fee_clear(shares, cut_total, exclude=exclude)
    # Barbell: meme sleeve ≤15% of desk even when green — never expand to use margin.
    try:
        import desk_roi_plan
        meme_cap = float(desk_roi_plan.BARBELL_MEME_MAX)
    except Exception:
        meme_cap = 0.15
    cut_meme = _cut_share(shares, "memecoin", meme_cap)
    if cut_meme > 1e-12:
        _feed_fee_clear(shares, cut_meme, exclude=exclude | {"memecoin"})
    return shares


def selective_max_buys(
    bot_id: str,
    *,
    base: int,
    today: float | None = None,
    green_boost: int = 1,
) -> int:
    """
    Selective volume: fee-clear towers may take +1 buy/check when today ≥ 0.
    Red days never boost; sports red already capped elsewhere.
    Does not touch venue min_edge.
    """
    base_n = max(1, int(base))
    bid = str(bot_id or "")
    if bid not in FEE_CLEAR_TOWERS:
        return base_n
    if today is not None and today < 0:
        return base_n
    if today is not None and today >= 0:
        return base_n + max(0, int(green_boost))
    return base_n


def tower_budgets(
    cfg: dict | None = None,
    *,
    meme_today: float | None = None,
    red_lock_usd: float | None = None,
    today_by_bot: dict | None = None,
    cash_by_bot: dict | None = None,
    realized_by_bot: dict | None = None,
) -> dict[str, float]:
    """Dollar caps per tower from desk max_open_risk × share (loser-starve aware)."""
    cfg = cfg or {}
    desk_cap = float(cfg.get("max_open_risk") if cfg.get("max_open_risk") is not None else 100.0)
    shares = effective_tower_shares(
        cfg,
        meme_today=meme_today,
        red_lock_usd=red_lock_usd,
        today_by_bot=today_by_bot,
        cash_by_bot=cash_by_bot,
        realized_by_bot=realized_by_bot,
    )
    out = {}
    for bot_id, share in shares.items():
        try:
            s = float(share)
        except (TypeError, ValueError):
            continue
        if s < 0:
            continue
        out[str(bot_id)] = round(desk_cap * min(1.0, s), 2)
    return out


def tower_budget_remaining(
    bot_id: str,
    open_risk_for_bot: float,
    cfg: dict | None = None,
) -> dict:
    """How much of this tower's budget is left (never raises desk cap)."""
    budgets = tower_budgets(cfg)
    cap = float(budgets.get(bot_id) or 0.0)
    used = max(0.0, float(open_risk_for_bot or 0.0))
    left = round(max(0.0, cap - used), 2)
    return {
        "bot": bot_id,
        "cap": cap,
        "used": round(used, 2),
        "left": left,
        "full": left <= 1e-9 and cap > 0,
    }


def tower_budget_blocks(
    bot_id: str,
    open_risk_for_bot: float,
    stake: float,
    cfg: dict | None = None,
) -> str:
    """Human reason when tower budget would be exceeded (desk cap still applies separately)."""
    info = tower_budget_remaining(bot_id, open_risk_for_bot, cfg)
    if info["cap"] <= 0:
        return ""
    try:
        need = float(stake)
    except (TypeError, ValueError):
        need = 0.0
    if need <= 0:
        return ""
    if need > info["left"] + 1e-9:
        return (
            f"tower risk budget full for {bot_id} "
            f"(${info['used']:.2f} + ${need:.2f} > ${info['cap']:.2f} tower share). "
            "Other towers can still buy inside desk open-risk."
        )
    return ""


def is_near_miss(
    *,
    reasons: list | None = None,
    z=None,
    p=None,
    edge=None,
    min_edge: float = 0.05,
) -> dict:
    """
    True when exactly one soft gate missed in a narrow band (shadow study lane).
    Soft allowlist is z|p only — edge is never a near-miss promote candidate
    (fee floors locked). Never auto-buys live desk risk — caller tags shadow_only.
    """
    reasons = list(reasons or [])
    z_n = _finite(z)
    p_n = _finite(p)
    soft = []
    if z_n is not None and NEAR_MISS_Z_BAND[0] <= z_n < NEAR_MISS_Z_BAND[1]:
        soft.append("z")
    if p_n is not None and NEAR_MISS_P_BAND[0] <= p_n < NEAR_MISS_P_BAND[1]:
        soft.append("p")
    # Edge just-under is observed for notes only — never qualifies soft promote.
    e_n = _finite(edge)
    edge_just_under = bool(
        e_n is not None and (min_edge - 0.01) <= e_n < min_edge
    )
    text = " | ".join(str(r) for r in reasons).lower()
    hard = any(
        k in text
        for k in ("weekend", "correlation", "entry_gate", "daily loss", "depth 0")
    )
    # "news" alone is hard — but fail-closed / unavailable calendar CDN misses
    # must not wipe soft-band densify. Real FOMC/CPI/news-window blackouts stay hard.
    if "news" in text and not hard:
        calendar_fp = any(
            s in text
            for s in (
                "fail-closed",
                "calendar unavailable",
                "unavailable (fail-closed)",
                "did-not-load",
                "calendar did not",
            )
        )
        real_blackout = any(
            s in text
            for s in ("news window", "blackout", "fomc", "cpi", "nfp", "high-impact")
        )
        if real_blackout or not calendar_fp:
            hard = True
    # Soft z|p in band is enough — ask-outside / regime / cushion companions
    # are common on 15m skips and must not wipe densify (hard gates still block).
    ok = (not hard) and len(soft) == 1
    return {
        "near_miss": ok,
        "soft": soft,
        "edge_just_under": edge_just_under,
        "stake": NEAR_MISS_STAKE if ok else 0.0,
        "shadow_only": True,
        "note": (
            f"shadow near-miss on {soft[0]}" if ok else "not a near-miss"
        ),
    }


def record_near_miss(root: str | None, row: dict) -> dict:
    state = load_more(root)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # Persist organic ask/entry + league/series when callers pass them.
    # Dropping ask forced settle labels onto default entry 0.5 (±stake),
    # wiping sports soft-p would_pnl densify (gap_bot already sends ask).
    item = {
        "at": now,
        "bot": row.get("bot"),
        "ticker": row.get("ticker"),
        "side": row.get("side"),
        "soft": row.get("soft"),
        "z": row.get("z"),
        "p": row.get("p"),
        "edge": row.get("edge"),
        "stake": NEAR_MISS_STAKE,
        "shadow_only": True,
        "note": row.get("note") or "",
    }
    ask = _finite(row.get("ask"))
    if ask is None:
        ask = _finite(row.get("entry_price"))
    if ask is not None and 0.0 < float(ask) < 1.0:
        item["ask"] = round(float(ask), 4)
        item["entry_price"] = item["ask"]
    # Commodity stores edge = p − ask − fee − edge_buf; keep historical buf for
    # ask catch-up invert (never invent from live venue settings).
    edge_buf = _finite(row.get("edge_buf"))
    if edge_buf is not None and float(edge_buf) >= 0:
        item["edge_buf"] = round(float(edge_buf), 4)
    league = str(row.get("league") or "").strip()
    if league:
        item["league"] = league
    series = str(row.get("series") or "").strip()
    if series:
        item["series"] = series
    state.setdefault("near_miss", []).append(item)
    state["last_at"] = now
    save_more(state, root)
    return item


def parse_opened_age_hours(opened: str | None, now_epoch: float | None = None) -> float | None:
    if not opened:
        return None
    text = str(opened).strip()
    # Accept "...Z" or naive ISO.
    try:
        from datetime import datetime, timezone
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = now_epoch if now_epoch is not None else time.time()
        return max(0.0, (now - dt.timestamp()) / 3600.0)
    except Exception:
        return None


def sticky_positions(
    bots: Iterable[dict],
    *,
    now_epoch: float | None = None,
) -> list[dict]:
    """List opens older than per-tower settle expectation."""
    out = []
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bot_id = str(bot.get("id") or "")
        limit = float(STICKY_HOURS.get(bot_id, 24.0))
        for pos in list(bot.get("positions") or []):
            if not isinstance(pos, dict):
                continue
            opened = pos.get("opened") or pos.get("opened_at") or pos.get("at")
            age = parse_opened_age_hours(opened, now_epoch=now_epoch)
            if age is None:
                continue
            if age + 1e-9 >= limit:
                out.append({
                    "bot": bot_id,
                    "ticker": pos.get("ticker"),
                    "side": pos.get("side"),
                    "age_hours": round(age, 2),
                    "limit_hours": limit,
                    "opened": opened,
                    "risk": pos.get("risk") if pos.get("risk") is not None else pos.get("cost"),
                    "note": "sticky — settle harness / exit audit",
                    "exit_priority": True,
                })
    out.sort(key=lambda r: -float(r.get("age_hours") or 0))
    return out


def sticky_for_bot(
    bots: Iterable[dict] | None,
    bot: str,
    *,
    now_epoch: float | None = None,
) -> list[dict]:
    """Sticky opens for one tower (exit-priority queue)."""
    bot_id = str(bot or "")
    return [r for r in sticky_positions(bots or [], now_epoch=now_epoch) if r.get("bot") == bot_id]


def sticky_entry_blocks(
    bot: str,
    *,
    today: float | None = None,
    bots: Iterable[dict] | None = None,
    sticky_rows: list | None = None,
    now_epoch: float | None = None,
    red_only: bool = True,
) -> str:
    """E1 #136/#137 — block speculative entries while sticky opens need exits.

    Default: only on red day (today < 0). Exits/settles still run. Floors locked.
    """
    bot_id = str(bot or "")
    if not bot_id:
        return ""
    if red_only and (today is None or float(today) >= 0):
        return ""
    rows = sticky_rows
    if rows is None:
        rows = sticky_for_bot(bots, bot_id, now_epoch=now_epoch)
    mine = [r for r in (rows or []) if isinstance(r, dict) and (
        not r.get("bot") or str(r.get("bot")) == bot_id
    )]
    if not mine:
        return ""
    oldest = max(float(r.get("age_hours") or 0) for r in mine)
    return (
        f"sticky-open SLA: {len(mine)} open(s) past settle window "
        f"(oldest {oldest:.1f}h) — exits first before new speculative buys"
    )[:160]


def sticky_sla_status(
    bots: Iterable[dict] | None = None,
    *,
    now_epoch: float | None = None,
) -> dict:
    """Observe board: sticky counts + exit-priority flag (never softens floors)."""
    rows = sticky_positions(bots or [], now_epoch=now_epoch)
    by_bot: dict[str, int] = {}
    for r in rows:
        b = str(r.get("bot") or "unknown")
        by_bot[b] = int(by_bot.get(b) or 0) + 1
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "sticky_count": len(rows),
        "by_bot": by_bot,
        "exit_priority": bool(rows),
        "top": rows[:8],
        "label": (
            f"sticky SLA n={len(rows)} exit_priority={'yes' if rows else 'no'}"
        ),
        "note": (
            "Sticky opens past settle expectation get exit priority; "
            "red-day speculative entries block until clears. Floors locked."
        ),
    }


def remember_sticky(root: str | None, rows: list[dict]) -> None:
    state = load_more(root)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state["sticky"] = list(rows or [])[:80]
    state["last_at"] = now
    save_more(state, root)


def series_vol_prior(series: str | None) -> float:
    if not series:
        return 0.0
    key = str(series).strip().upper()
    # Strip date suffixes: KXBTC15M-... → KXBTC15M
    for known in SERIES_VOL_PRIORS:
        if key.startswith(known):
            return float(SERIES_VOL_PRIORS[known])
    return 0.0


def effective_depth_need(
    series: str | None,
    base_need: float | None = None,
) -> float:
    """Raise depth need on high-σ series (NatGas first). Floor never softens.

    Plan #471–472: vol prior bumps effective need so thin/high-vol books must
    show more depth before ranking as good. Base need is a lower bound.
    """
    need = float(base_need) if base_need is not None else float(DEFAULT_DEPTH_NEED)
    if need <= 0:
        need = float(DEFAULT_DEPTH_NEED)
    prior = max(0.0, float(series_vol_prior(series)))
    # NatGas prior 0.15 → ~1.3× need; Gold 0.04 → ~1.08×. Never below base.
    bumped = need * (1.0 + prior * 2.0)
    return round(max(need, bumped), 4)


def apply_series_vol_prior(vol: dict, series: str | None) -> dict:
    """Bump vol score by series prior (NatGas hotter than Gold)."""
    vol = dict(vol or {})
    prior = series_vol_prior(series)
    if prior <= 0:
        vol["series_prior"] = 0.0
        return vol
    score = float(vol.get("score") or 0.35) + prior
    score = round(max(0.0, min(1.0, score)), 4)
    reasons = list(vol.get("reasons") or [])
    reasons.append(f"series prior +{prior:.2f} for {series}")
    vol["score"] = score
    vol["reasons"] = reasons
    vol["series_prior"] = prior
    if score >= 0.85:
        vol["regime"] = "extreme"
    elif score >= 0.65:
        vol["regime"] = "high"
    elif score >= 0.40:
        vol["regime"] = "elevated"
    else:
        vol["regime"] = "calm"
    return vol


def decay_weight(age_days: float, half_life: float = HIT_DECAY_HALFLIFE_DAYS) -> float:
    if half_life <= 0:
        return 1.0
    age = max(0.0, float(age_days))
    return math.pow(0.5, age / float(half_life))


def decayed_hit_rate(
    history: list | None,
    *,
    window_days: int = 40,
    half_life: float = HIT_DECAY_HALFLIFE_DAYS,
    now_ts: float | None = None,
) -> dict:
    """Exponentially decayed hit rate so old wins don't oversize forever."""
    from datetime import datetime, timezone

    now = now_ts if now_ts is not None else time.time()
    w_hits = 0.0
    w_n = 0.0
    n = 0
    for row in history or []:
        if not isinstance(row, dict):
            continue
        pnl = _finite(row.get("pnl"))
        if pnl is None:
            continue
        closed = str(row.get("closed") or row.get("closed_at") or "")
        try:
            text = closed[:-1] + "+00:00" if closed.endswith("Z") else closed
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (now - dt.timestamp()) / 86400.0)
        except Exception:
            age_days = 0.0
        if age_days > float(window_days):
            continue
        w = decay_weight(age_days, half_life=half_life)
        w_n += w
        if pnl > 0:
            w_hits += w
        n += 1
    hit = (w_hits / w_n) if w_n > 1e-9 else None
    return {
        "n": n,
        "hit_rate_decayed": None if hit is None else round(hit, 4),
        "weight_sum": round(w_n, 4),
        "half_life_days": half_life,
        "window_days": window_days,
    }


def record_sports_clv(
    root: str | None,
    *,
    ticker: str,
    side: str,
    fair_entry,
    fair_exit=None,
    close_fair=None,
    pnl=None,
    league: str = "",
    exit_reason: str = "",
    clv_kind: str = "line",
) -> dict:
    """Closing-line value: entry fair vs later fair/close. Positive CLV = we beat the close.

    clv_kind='line' = model/market fair (counts toward green_boost).
    clv_kind='binary' = settle 0/1 proxy — stored for autopsy but excluded from beat rate.
    """
    fe = _finite(fair_entry)
    fc = _finite(close_fair)
    if fc is None:
        fc = _finite(fair_exit)
    clv = None
    if fe is not None and fc is not None:
        # For YES/home-style: bought when fair was higher than later close → good CLV
        clv = round(fe - fc, 4)
    kind = str(clv_kind or "line").strip().lower() or "line"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    row = {
        "at": now,
        "ticker": ticker,
        "side": side,
        "league": league,
        "fair_entry": fe,
        "fair_close": fc,
        "clv": clv,
        "pnl": _finite(pnl),
        "exit": exit_reason[:80],
        "clv_kind": kind,
    }
    state = load_clv(root)
    state.setdefault("rows", []).append(row)
    state["last_at"] = now
    save_clv(state, root)
    return row


CLV_BEAT_BAR = 0.52
CLV_LEAGUE_MIN_N = 10
CLV_LEAGUE_ORDER = ("NFL", "NCAAF", "NBA", "WNBA", "MLB", "NHL")


def clv_by_league(
    root: str | None = None,
    *,
    min_n: int = CLV_LEAGUE_MIN_N,
    beat_bar: float = CLV_BEAT_BAR,
) -> dict:
    """Phase 4 per-league CLV board — NFL/NCAAF/NBA/WNBA/MLB/NHL north star."""
    state = load_clv(root)
    rows = [
        r for r in (state.get("rows") or [])
        if isinstance(r, dict) and _clv_counts_for_boost(r)
    ]
    by: dict[str, list] = {}
    for r in rows:
        lg = str(r.get("league") or "UNK").strip().upper() or "UNK"
        by.setdefault(lg, []).append(r)
    leagues = []
    for lg in list(CLV_LEAGUE_ORDER) + sorted(k for k in by if k not in CLV_LEAGUE_ORDER):
        local = by.get(lg) or []
        if not local and lg not in CLV_LEAGUE_ORDER:
            continue
        n = len(local)
        if n == 0 and lg in CLV_LEAGUE_ORDER:
            leagues.append({
                "league": lg,
                "n": 0,
                "avg_clv": None,
                "beat_close_rate": None,
                "beat_bar": float(beat_bar),
                "min_n": int(min_n),
                "thin": True,
                "pass": False,
            })
            continue
        if n == 0:
            continue
        avg = round(sum(float(r["clv"]) for r in local) / n, 4)
        pos = sum(1 for r in local if float(r["clv"]) > 0)
        rate = round(pos / n, 4)
        thin = n < int(min_n)
        ok = (not thin) and rate + 1e-12 >= float(beat_bar)
        leagues.append({
            "league": lg,
            "n": n,
            "avg_clv": avg,
            "beat_close_rate": rate,
            "beat_bar": float(beat_bar),
            "min_n": int(min_n),
            "thin": thin,
            "pass": ok,
        })
    thin_n = sum(1 for L in leagues if L.get("thin"))
    pass_n = sum(1 for L in leagues if L.get("pass"))
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "observe_only": True,
        "board_chip": False,
        "beat_bar": float(beat_bar),
        "min_n": int(min_n),
        "leagues": leagues,
        "thin_n": thin_n,
        "pass_n": pass_n,
        "label": f"clv_leagues pass={pass_n} thin={thin_n}/{len(leagues)}",
        "note": (
            f"Per-league CLV — beat-close ≥{beat_bar:.0%} once n≥{min_n}. "
            "NFL packs stay stricter on fair floors; this board never softens venue edge."
        ),
    }


def _clv_counts_for_boost(row: dict) -> bool:
    """Line CLV only — binary settle proxies invert beat-close and must not gate green_boost."""
    if not isinstance(row, dict) or row.get("clv") is None:
        return False
    kind = str(row.get("clv_kind") or "").strip().lower()
    if kind == "binary":
        return False
    # Exact 0/1 close is Kalshi/model wipe — never line CLV for green_boost.
    # Prefer-1 leftover after #446: mid-open gap-decay/flip used to count wipe
    # as line because only settled exits were stripped.
    if kind in ("", "line"):
        fc = _finite(row.get("fair_close"))
        if fc is None:
            fc = _finite(row.get("close_fair"))
        if fc is not None and (abs(fc - 0.0) < 1e-12 or abs(fc - 1.0) < 1e-12):
            return False
    return True


def clv_summary(root: str | None = None) -> dict:
    state = load_clv(root)
    all_rows = [r for r in (state.get("rows") or []) if isinstance(r, dict) and r.get("clv") is not None]
    rows = [r for r in all_rows if _clv_counts_for_boost(r)]
    n = len(rows)
    avg = round(sum(float(r["clv"]) for r in rows) / n, 4) if n else None
    pos = sum(1 for r in rows if float(r["clv"]) > 0)
    rate = round(pos / n, 4) if n else None
    leagues = clv_by_league(root)
    return {
        "paper_only": True,
        "fee_floors_locked": True,
        "n": n,
        "avg_clv": avg,
        "beat_close_rate": rate,
        "beat_bar": CLV_BEAT_BAR,
        "pass": n < 20 or (rate is not None and rate + 1e-12 >= CLV_BEAT_BAR),
        "by_league": leagues,
        "recent": rows[-20:],
        "binary_excluded_n": max(0, len(all_rows) - n),
        "note": (
            "CLV>0 means entry fair beat later fair/close (learning north star for sports). "
            "Exact 0/1 wipe closes (settle or mid-open) excluded from beat-close / green_boost."
        ),
    }


def hillclimb_state(root: str | None = None, cfg: dict | None = None) -> dict:
    state = load_more(root)
    hc = dict(state.get("hillclimb") or {})
    cfg = cfg or {}
    active = cfg.get("hillclimb_lever") if cfg.get("hillclimb_lever") is not None else hc.get("active_lever")
    if active is not None and str(active) not in HILLCLIMB_LEVERS and str(active) != "":
        active = None
    return {
        "paper_only": True,
        "levers": list(HILLCLIMB_LEVERS),
        "active_lever": active or None,
        "baseline": hc.get("baseline"),
        "weeks": list(hc.get("weeks") or [])[-8:],
        "kill_rule": "Revert lever if taxed EV drops for 2 consecutive weeks while fill count rose.",
        "note": hc.get("note") or "One lever per week.",
    }


def set_hillclimb_lever(root: str | None, lever: str | None) -> dict:
    state = load_more(root)
    if lever and str(lever) not in HILLCLIMB_LEVERS:
        raise ValueError(f"unknown lever {lever}")
    state.setdefault("hillclimb", {})
    state["hillclimb"]["active_lever"] = lever
    state["last_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_more(state, root)
    return hillclimb_state(root)


def more_summary(root: str | None = None, *, bots: list | None = None, cfg: dict | None = None) -> dict:
    sticky = sticky_positions(bots or [])
    if root is not None:
        remember_sticky(root, sticky)
    meme_today = None
    today_by_bot: dict[str, float] = {}
    cash_by_bot: dict[str, float] = {}
    realized_by_bot: dict[str, float] = {}
    for bot in bots or []:
        if not isinstance(bot, dict):
            continue
        bot_id = str(bot.get("id") or "")
        if not bot_id:
            continue
        t = _finite(bot.get("today"))
        c = _finite(bot.get("cash"))
        r = _finite(bot.get("realized"))
        if t is not None:
            today_by_bot[bot_id] = t
        if c is not None:
            cash_by_bot[bot_id] = c
        if r is not None:
            realized_by_bot[bot_id] = r
        if bot_id == "memecoin":
            meme_today = t
    shares = effective_tower_shares(
        cfg, meme_today=meme_today, today_by_bot=today_by_bot,
        cash_by_bot=cash_by_bot, realized_by_bot=realized_by_bot,
    )
    red = meme_today is not None and meme_today <= -float(MEME_RED_LOCK_USD)
    return {
        "paper_only": True,
        "version": 1,
        "skip_leaderboard": skip_leaderboard(root),
        "tower_budgets": tower_budgets(
            cfg, meme_today=meme_today, today_by_bot=today_by_bot,
            cash_by_bot=cash_by_bot, realized_by_bot=realized_by_bot,
        ),
        "tower_shares": shares,
        "meme_red_day": red,
        "meme_red_share": MEME_RED_SHARE if red else None,
        "fee_clear_towers": list(FEE_CLEAR_TOWERS),
        "selective_volume": {
            "note": "Green fee-clear towers may +1 buy/check; venue min_edge floors stay locked.",
            "towers": list(FEE_CLEAR_TOWERS),
        },
        "near_miss_count": len((load_more(root).get("near_miss") or [])),
        "near_miss_recent": list((load_more(root).get("near_miss") or []))[-12:],
        "sticky": sticky[:20],
        "sticky_count": len(sticky),
        "clv": clv_summary(root),
        "hillclimb": hillclimb_state(root, cfg),
        "series_vol_priors": dict(SERIES_VOL_PRIORS),
        "hit_decay_halflife_days": HIT_DECAY_HALFLIFE_DAYS,
        "depth_need": DEFAULT_DEPTH_NEED,
        "tracks": ["throughput", "recycling", "quality", "expansion"],
    }


def self_check() -> None:
    assert classify_skip("WEEKEND — equity closed", weekday=6) == "WEEKEND"
    assert classify_skip("correlation veto vs btc", weekday=1) == "correlation"
    assert classify_skip("cushion $20 < $40", weekday=2) == "cushion"
    assert stable_skip_code("edge") == "EDGE"
    assert stable_skip_code("correlation") == "CORR"
    assert stable_skip_code("fair") == "P"
    assert classify_skip("forexfactory calendar closed", weekday=2) == "calendar"
    assert classify_skip("tower budget left $0", weekday=2) == "budget"
    assert depth_adjusted_edge(0.10, 5, need=10) == round(0.05, 6)
    assert depth_adjusted_edge(0.10, 20, need=10) == round(0.10, 6)
    assert opportunity_score_v2(0.10, 0.8, 5, need=10) < opportunity_score_v2(0.10, 0.8, 20, need=10)
    ok_map, err_map = prefetch_map([1, 2], lambda j: j + 1)
    assert ok_map == {1: 2, 2: 3} and err_map == {}
    warm_calls: list[str] = []

    def _fake_fetch(url: str):
        warm_calls.append(url)
        return {"markets": [{"ticker": "KXTEST"}]}

    warm = warm_tip_books(
        None,
        15,
        games=[
            {"league": "NBA", "series": "KXNBAGAME", "tip_in_min": 12},
            {"league": "NFL", "series": "KXNFLGAME", "tip_in_min": 4},
            {"league": "NHL", "series": "KXNHLGAME", "tip_in_min": 60},
        ],
        fetch=_fake_fetch,
        put_cache=lambda _u, _b: None,
    )
    assert warm["orders_placed"] is False
    assert warm["fee_floors_locked"] is True
    assert warm["warmed_n"] == 2  # 60m tip excluded from T−15
    assert len(warm_calls) == 2
    warm5 = warm_tip_books(
        None,
        5,
        games=[
            {"league": "NBA", "series": "KXNBAGAME", "tip_in_min": 12},
            {"league": "NFL", "series": "KXNFLGAME", "tip_in_min": 4},
        ],
        fetch=_fake_fetch,
        put_cache=lambda _u, _b: None,
    )
    assert warm5["warmed_n"] == 1 and warm5["tip_band"] == 5
    budgets = tower_budgets({"max_open_risk": 100})
    assert abs(sum(budgets.values()) - 100) < 0.05
    block = tower_budget_blocks("memecoin", 4.0, 3.0, {"max_open_risk": 100})
    assert "tower risk budget" in block
    red_shares = effective_tower_shares({"tower_risk_budgets": dict(DEFAULT_TOWER_BUDGET_SHARE)}, meme_today=-25)
    assert abs(red_shares["memecoin"] - MEME_RED_SHARE) < 1e-9
    assert red_shares["btc15m"] > DEFAULT_TOWER_BUDGET_SHARE["btc15m"]
    assert red_shares["commodity-15m"] > DEFAULT_TOWER_BUDGET_SHARE["commodity-15m"]
    assert red_shares["sports-gap"] > DEFAULT_TOWER_BUDGET_SHARE["sports-gap"]
    assert abs(sum(red_shares.values()) - sum(DEFAULT_TOWER_BUDGET_SHARE.values())) < 1e-9
    inx_shares = effective_tower_shares(
        {"tower_risk_budgets": dict(DEFAULT_TOWER_BUDGET_SHARE)},
        cash_by_bot={"kalshi-sp": 444.0, "kalshi-sized": 500.0},
    )
    assert abs(inx_shares["kalshi-sp"] - INX_LOSER_SHARE) < 1e-9
    assert inx_shares["btc15m"] > DEFAULT_TOWER_BUDGET_SHARE["btc15m"]
    assert selective_max_buys("btc15m", base=3, today=1.0) == 4
    assert selective_max_buys("btc15m", base=3, today=-1.0) == 3
    assert selective_max_buys("memecoin", base=2, today=5.0) == 2
    nm = is_near_miss(z=0.60, p=0.85, reasons=["z 0.60 < 0.65"])
    assert nm["near_miss"] is True and nm["shadow_only"] is True
    assert series_vol_prior("KXNATGAS15M-FOO") > series_vol_prior("KXGOLD15M")
    # #471–472: vol prior raises effective depth need; never softens below base.
    assert effective_depth_need("KXNATGAS15M", 10.0) > effective_depth_need("KXGOLD15M", 10.0)
    assert effective_depth_need("KXNATGAS15M", 10.0) >= 10.0
    from datetime import datetime
    from zoneinfo import ZoneInfo
    mock_1150 = datetime(2026, 11, 7, 11, 50, tzinfo=ZoneInfo("America/Chicago"))
    assert in_inx_pre_noon_warm_window(mock_1150) is True
    mock_noon = datetime(2026, 11, 7, 12, 30, tzinfo=ZoneInfo("America/Chicago"))
    assert in_inx_pre_noon_warm_window(mock_noon) is False
    assert decay_weight(0) == 1.0
    assert decay_weight(HIT_DECAY_HALFLIFE_DAYS) == 0.5
    dhr = decayed_hit_rate(
        [{"pnl": 5, "closed": "2026-11-01T12:00:00Z"}] * 5,
        now_ts=time.mktime(time.strptime("2026-11-01", "%Y-%m-%d")),
    )
    assert dhr["n"] == 5
    assert dhr["hit_rate_decayed"] == 1.0


if __name__ == "__main__":
    self_check()
    print("desk_more self_check ok")
