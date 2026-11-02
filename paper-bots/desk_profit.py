"""Six desk profit helpers — paper only.

1) Correlation veto  2) Venue min_edge  3) Model-flip δ
4) Kelly-lite sizing  5) Shadow profiles  6) Expectancy / starve
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any


VENUE_KEYS = ("kalshi_sports", "kalshi_btc15m", "kalshi_inx", "solana_dex")

DEFAULT_VENUE_MIN_EDGE = {
    "kalshi_sports": 0.07,
    "kalshi_btc15m": 0.055,
    "kalshi_inx": 0.02,
    "solana_dex": 0.025,
}

DEFAULT_CORRELATION_PAIRS = (
    ("risk_on_btc", "risk_on_equity"),
    ("risk_off_btc", "risk_off_equity"),
)

BOT_VENUE = {
    "sports-gap": "kalshi_sports",
    "btc15m": "kalshi_btc15m",
    "kalshi-sp": "kalshi_inx",
    "kalshi-sized": "kalshi_inx",
    "memecoin": "solana_dex",
}


def _num(value) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def risk_factor_for(bot_id: str, side: str | None) -> str:
    """Directional risk tag for cross-bot correlation."""
    s = str(side or "").strip().lower()
    if bot_id == "btc15m":
        if s == "yes":
            return "risk_on_btc"
        if s == "no":
            return "risk_off_btc"
        return ""
    if bot_id in ("kalshi-sp", "kalshi-sized"):
        if s in ("yes", "y"):
            return "risk_on_equity"
        if s in ("no", "n"):
            return "risk_off_equity"
        return ""
    if bot_id == "memecoin":
        return "risk_on_meme"
    if bot_id == "sports-gap":
        if s in ("home", "away"):
            return f"sports_{s}"
        return ""
    return ""


def partner_factors(factor: str, pairs) -> set[str]:
    out: set[str] = set()
    if not factor:
        return out
    for row in pairs or ():
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            continue
        a, b = str(row[0]), str(row[1])
        if factor == a:
            out.add(b)
        if factor == b:
            out.add(a)
    return out


def open_risk_factor_rows(bots: list) -> list[dict]:
    """Flatten open positions into {bot, side, factor, edge, risk} rows."""
    rows = []
    for bot in bots or []:
        bot_id = str(bot.get("id") or "")
        for pos in bot.get("positions") or []:
            if not isinstance(pos, dict):
                continue
            side = pos.get("side") or ""
            factor = str(pos.get("risk_factor") or risk_factor_for(bot_id, side) or "")
            if not factor:
                continue
            edge = _num(pos.get("gap_at_entry"))
            if edge is None:
                edge = _num(pos.get("edge"))
            if edge is None:
                fair = _num(pos.get("fair_at_entry"))
                ask = _num(pos.get("ask") or pos.get("entry_price"))
                fee = _num(pos.get("fee") or pos.get("entry_fee")) or 0.0
                if fair is not None and ask is not None:
                    edge = fair - ask - fee
            risk = _num(pos.get("risk"))
            if risk is None:
                risk = _num(pos.get("cost")) or 0.0
            rows.append({
                "bot": bot_id,
                "side": str(side),
                "factor": factor,
                "edge": edge,
                "risk": float(risk or 0),
                "what": pos.get("ticker") or pos.get("team") or pos.get("game") or "",
            })
    return rows


def correlation_veto_reason(
    bot_id: str,
    side: str,
    edge,
    open_rows: list,
    pairs=None,
) -> str:
    """Empty string = ok. Blocks stacking paired directional factors."""
    factor = risk_factor_for(bot_id, side)
    if not factor:
        return ""
    partners = partner_factors(factor, pairs if pairs is not None else DEFAULT_CORRELATION_PAIRS)
    if not partners:
        return ""
    cand_edge = _num(edge)
    for row in open_rows or []:
        if row.get("bot") == bot_id:
            continue
        other = str(row.get("factor") or "")
        if other not in partners:
            continue
        other_edge = _num(row.get("edge"))
        # Keep the higher edge only: veto when an open paired book is as good or better.
        if cand_edge is None or other_edge is None or other_edge + 1e-12 >= cand_edge:
            return (
                f"correlation veto: open {row.get('bot')} {other} "
                f"blocks {bot_id} {factor}"
            )
        return (
            f"correlation veto: open {row.get('bot')} {other} "
            f"(lower edge) still stacks heat with {bot_id} {factor}"
        )
    return ""


def venue_min_edge(venue: str, cfg: dict | None = None, fallback: float = 0.06) -> float:
    cfg = cfg or {}
    raw = cfg.get("venue_min_edge") if isinstance(cfg.get("venue_min_edge"), dict) else {}
    merged = dict(DEFAULT_VENUE_MIN_EDGE)
    for key, value in (raw or {}).items():
        if key in VENUE_KEYS:
            n = _num(value)
            if n is not None:
                merged[key] = n
    if venue in merged:
        return float(merged[venue])
    top = _num(cfg.get("min_edge"))
    return float(top if top is not None else fallback)


def bot_venue_edge(bot_id: str, cfg: dict | None = None) -> float:
    venue = BOT_VENUE.get(bot_id)
    if not venue:
        return float(_num((cfg or {}).get("min_edge")) or 0.06)
    return venue_min_edge(venue, cfg)


def parse_venue_min_edge(raw) -> tuple[dict | None, str | None]:
    if raw is None:
        return dict(DEFAULT_VENUE_MIN_EDGE), None
    if not isinstance(raw, dict):
        return None, "venue_min_edge must be an object of venue → edge."
    out = dict(DEFAULT_VENUE_MIN_EDGE)
    for key, value in raw.items():
        if key not in VENUE_KEYS:
            return None, f"Unknown venue_min_edge key {key!r}."
        n = _num(value)
        if n is None or not (0.0 <= n <= 0.20):
            return None, f"venue_min_edge.{key} stays between 0 and 0.20."
        out[key] = round(n, 4)
    return out, None


def parse_correlation_pairs(raw) -> tuple[list | None, str | None]:
    if raw is None:
        return [list(p) for p in DEFAULT_CORRELATION_PAIRS], None
    if not isinstance(raw, list):
        return None, "correlation_pairs must be a list of [a, b] pairs."
    out = []
    for row in raw:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            return None, "Each correlation pair needs exactly two factor names."
        a, b = str(row[0]).strip(), str(row[1]).strip()
        if not a or not b or a == b:
            return None, "Correlation pair names must be distinct non-empty strings."
        out.append([a, b])
    return out, None


def parse_shadow(raw) -> tuple[dict | None, str | None]:
    if raw is None:
        return {
            "enabled": True,
            "btc15m": [{
                "id": "edge08",
                "params": {"venue_edge": 0.08},
                "promote_after": {"n": 30, "min_expectancy": 0.5},
            }],
        }, None
    if not isinstance(raw, dict):
        return None, "shadow must be an object."
    enabled = bool(raw.get("enabled", True))
    out: dict[str, Any] = {"enabled": enabled}
    for bot_id, profiles in raw.items():
        if bot_id == "enabled":
            continue
        if not isinstance(profiles, list):
            return None, f"shadow.{bot_id} must be a list of profiles."
        cleaned = []
        for prof in profiles:
            if not isinstance(prof, dict):
                return None, f"shadow.{bot_id} profiles must be objects."
            pid = str(prof.get("id") or "").strip()
            if not pid:
                return None, f"shadow.{bot_id} profile needs an id."
            params = prof.get("params") if isinstance(prof.get("params"), dict) else {}
            promote = prof.get("promote_after") if isinstance(prof.get("promote_after"), dict) else {}
            cleaned.append({
                "id": pid[:40],
                "params": dict(params),
                "promote_after": {
                    "n": int(float(promote.get("n") or 30)),
                    "min_expectancy": float(promote.get("min_expectancy") or 0.5),
                },
            })
        out[bot_id] = cleaned
    return out, None


def kelly_lite_dollars(
    prob,
    edge,
    cfg: dict | None = None,
    open_risk_used: float = 0.0,
    ask=None,
    curve_dollars: float | None = None,
    starve_mult: float = 1.0,
) -> float:
    """Size ∝ edge × confidence, never above curve cap or remaining open risk."""
    cfg = cfg or {}
    lo = float(cfg.get("stake_lo_max") if cfg.get("stake_lo_max") is not None else 20.0)
    hi_min = float(cfg.get("stake_hi_min") if cfg.get("stake_hi_min") is not None else 20.0)
    hi_max = float(cfg.get("stake_hi_max") if cfg.get("stake_hi_max") is not None else 100.0)
    bar = float(cfg.get("stake_hi_prob") if cfg.get("stake_hi_prob") is not None else 0.8)
    max_risk = float(cfg.get("max_open_risk") if cfg.get("max_open_risk") is not None else 100.0)
    remaining = max(0.0, max_risk - float(open_risk_used or 0.0))
    if remaining <= 1e-9:
        return 0.0
    if curve_dollars is None:
        # Fallback curve: under bar → lo, else linear hi_min..hi_max
        chance = _num(prob)
        if chance is None or chance + 1e-12 < bar:
            curve_dollars = lo
        else:
            span = 1.0 - bar
            t = 0.0 if span <= 0 else max(0.0, min(1.0, (float(chance) - bar) / span))
            curve_dollars = hi_min + t * (hi_max - hi_min)
    curve_cap = float(curve_dollars)
    mode = str(cfg.get("sizing") or "kelly_lite").strip().lower()
    mult = max(0.0, min(1.0, float(starve_mult if starve_mult is not None else 1.0)))
    if mode != "kelly_lite":
        return round(min(curve_cap, remaining) * mult, 2)
    e = max(0.0, float(_num(edge) or 0.0))
    # Without a measured edge, keep the probability curve (still open-risk capped).
    if e <= 1e-12:
        return round(min(curve_cap, remaining) * mult, 2)
    k = float(cfg.get("kelly_fraction") if cfg.get("kelly_fraction") is not None else 0.25)
    p = float(_num(prob) or 0.0)
    a = _num(ask)
    anchor = float(a) if a is not None else 0.5
    edge_term = e / 0.06
    conf_term = max(0.05, p - anchor)
    raw = k * edge_term * conf_term * 400.0
    if p + 1e-12 < bar:
        raw = min(raw, lo)
    else:
        raw = max(hi_min, raw)
    dollars = min(raw, curve_cap, remaining, hi_max)
    dollars = max(0.0, dollars) * mult
    if dollars < 1.0:
        return 0.0
    return round(dollars, 2)


def _parse_when(text: str) -> dt.datetime | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    # Prefer ISO-ish prefixes.
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S UTC",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            if fmt.endswith("Z") and raw.endswith("Z"):
                return dt.datetime.strptime(raw[:19] + "Z", "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=dt.timezone.utc
                )
            if "%z" in fmt:
                cleaned = raw.replace("Z", "+0000")
                if cleaned.count(":") == 2 and ("+" in cleaned[10:] or "-" in cleaned[10:]):
                    # 2026-01-01T12:00:00+00:00 → +0000
                    cleaned = cleaned[:-3] + cleaned[-2:] if cleaned[-3] == ":" else cleaned
                return dt.datetime.strptime(cleaned[:22], fmt)
            return dt.datetime.strptime(raw[: len(fmt.replace("%", "00"))], fmt)
        except ValueError:
            continue
    # "November 2, 2026, 3:00 PM Central" / "2026-10-28 14:00:00 CT"
    if " CT" in raw or " Central" in raw:
        chunk = raw.replace(" Central", "").replace(" CT", "").strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%B %d, %Y, %I:%M %p"):
            try:
                return dt.datetime.strptime(chunk, fmt)
            except ValueError:
                continue
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def bot_expectancy(history: list, window_days: int = 20, now: dt.datetime | None = None) -> dict:
    """EV per closed trade after fees from signed pnl rows."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    cutoff = now - dt.timedelta(days=max(1, int(window_days)))
    pnls: list[float] = []
    for row in history or []:
        if not isinstance(row, dict):
            continue
        pnl = _num(row.get("pnl"))
        if pnl is None:
            continue
        when = (
            _parse_when(str(row.get("closed") or ""))
            or _parse_when(str(row.get("closed_at") or ""))
            or _parse_when(str(row.get("when") or ""))
            or _parse_when(str(row.get("settled_at") or ""))
        )
        if when is not None:
            if when.tzinfo is None:
                when = when.replace(tzinfo=dt.timezone.utc)
            if when < cutoff:
                continue
        pnls.append(float(pnl))
    n = len(pnls)
    if n == 0:
        return {
            "n": 0,
            "hit_rate": None,
            "avg_win": None,
            "avg_loss": None,
            "expectancy": None,
            "after_fees": True,
            "window": f"{int(window_days)}d",
        }
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    hit = len(wins) / n
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(-p for p in losses) / len(losses)) if losses else 0.0
    ev = hit * avg_win - (1.0 - hit) * avg_loss
    return {
        "n": n,
        "hit_rate": round(hit, 4),
        "avg_win": round(avg_win, 4) if wins else None,
        "avg_loss": round(avg_loss, 4) if losses else None,
        "expectancy": round(ev, 4),
        "after_fees": True,
        "window": f"{int(window_days)}d",
    }


def starve_state(expectancy_row: dict, cfg: dict | None = None) -> dict:
    cfg = cfg or {}
    min_n = int(cfg.get("starve_min_n") if cfg.get("starve_min_n") is not None else 8)
    floor = float(cfg.get("starve_expectancy") if cfg.get("starve_expectancy") is not None else 0.0)
    factor = float(cfg.get("starve_factor") if cfg.get("starve_factor") is not None else 0.25)
    factor = max(0.0, min(1.0, factor))
    n = int((expectancy_row or {}).get("n") or 0)
    ev = _num((expectancy_row or {}).get("expectancy"))
    if n >= min_n and ev is not None and ev < floor:
        return {
            "starved": True,
            "starve_reason": f"EV ${ev:.2f} over {n} settles (< ${floor:.2f})",
            "starve_factor": factor,
        }
    return {"starved": False, "starve_reason": "", "starve_factor": 1.0}


def capital_weights(bot_rows: list) -> dict:
    """Positive-EV share; starved / missing EV get 0."""
    scores = {}
    for bot in bot_rows or []:
        bot_id = str(bot.get("id") or "")
        if not bot_id or bot.get("present") is False:
            continue
        if bot.get("starved"):
            scores[bot_id] = 0.0
            continue
        ev = _num(bot.get("expectancy"))
        scores[bot_id] = max(0.0, float(ev)) if ev is not None else 0.0
    total = sum(scores.values())
    if total <= 1e-12:
        live = [k for k, _ in scores.items()]
        if not live:
            return {"method": "expectancy", "weights": {}}
        even = round(1.0 / len(live), 4)
        return {"method": "expectancy", "weights": {k: even for k in live}}
    return {
        "method": "expectancy",
        "weights": {k: round(v / total, 4) for k, v in scores.items()},
    }


def model_flip_adverse(side: str, fair_at_entry, fair_now, delta: float) -> bool:
    """True when fair moved against the held side by ≥ delta."""
    entry = _num(fair_at_entry)
    now = _num(fair_now)
    d = _num(delta)
    if entry is None or now is None or d is None or d < 0:
        return False
    s = str(side or "").strip().lower()
    # YES/home: adverse if fair drops; NO/away: adverse if fair rises (against short-ish)
    if s in ("yes", "home", "buy", "long"):
        return (entry - now) >= d - 1e-12
    if s in ("no", "away", "sell", "short"):
        return (now - entry) >= d - 1e-12
    return abs(now - entry) >= d - 1e-12


def shadow_promote_ready(expectancy_row: dict, promote_after: dict | None) -> bool:
    rule = promote_after or {}
    need_n = int(rule.get("n") or 30)
    need_ev = float(rule.get("min_expectancy") or 0.5)
    n = int((expectancy_row or {}).get("n") or 0)
    ev = _num((expectancy_row or {}).get("expectancy"))
    return n >= need_n and ev is not None and ev >= need_ev
