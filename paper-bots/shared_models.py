"""Shared model helpers for the towers. Paper only. Pure math, no network.

No existing tower imports this file yet, so nothing here changes how any
tower trades. Tests prove the shared fair-price helper gives the same
numbers as BTC 15m, More 15m and Commodity 15m today (plan step 420). Moving a
tower onto it is a proposal for Levi (step 419), not something done here.

What is here (plan steps in brackets):

* ``fair_up``: price vs target with time left, log or dollar distance, normal
  or fatter-tailed (418, 421).
* Volatility: realized per-minute move, a 15/60/240-minute blend, a
  time-of-day factor, a news factor and a jump guard (422-426).
* Per-market multipliers learned from calibration, refreshed weekly with a
  cap on how far they move (427-429), and a settlement-source basis (430).
* Fair-price error by minutes left and the trust cap it suggests (431-432).
* A confidence score and a confidence stake inside the $25 cap (433-434).
* Log-only features: book imbalance, tape momentum, cross-market pull and a
  same-direction crowding penalty (435, 437, 439, 441).
* One shared exit helper: take profit, model flip, time stop, "little left
  to gain" and "time decay" (442, 444, 446).
* Cautious statistics: Wilson bounds, an "enough data?" check, a cautious
  learning skip with a "recovered" rule, and a cautious expectancy (450-454).
* ``brier`` / ``compare``: score two fair-price methods on the same rows (replay).
"""
from __future__ import annotations

import datetime as dt
import math
import statistics

MIN_N = 50                 # results needed before anything counts (house rule)
STAKE_CAP = 25.0           # shadow ticket


# ------------------------------------------------------------------ distributions
def phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def student_cdf(z: float, df: float = 4.0) -> float:
    """CDF of a Student-t scaled to unit variance (fatter tails than normal).

    Same spread as the normal (so the same sigma means the same typical move),
    but big moves are more likely. Simpson's rule on the density; df > 2.
    """
    if df <= 2:
        raise ValueError("df must be above 2 for a finite variance")
    if not math.isfinite(z):
        return 1.0 if z > 0 else 0.0
    scale = math.sqrt(df / (df - 2.0))
    t = abs(z) * scale
    c = math.gamma((df + 1) / 2) / (math.sqrt(df * math.pi) * math.gamma(df / 2))
    f = lambda x: c * (1 + x * x / df) ** (-(df + 1) / 2)  # noqa: E731
    n = 400
    h = t / n
    s = f(0) + f(t) + sum((4 if i % 2 else 2) * f(i * h) for i in range(1, n))
    half = s * h / 3
    p = 0.5 + half
    return p if z >= 0 else 1.0 - p


def tail_cdf(z: float, tails: str = "normal", df: float = 4.0) -> float:
    return student_cdf(z, df) if tails == "student" else phi(z)


# ------------------------------------------------------------------ fair price (418-421)
def fair_up(level: float, target: float, sigma: float, minutes: float | None = None, *,
            mode: str = "log", tails: str = "normal", df: float = 4.0,
            clip: tuple | None = None) -> float:
    """P(price at the close >= target).

    ``mode="log"``: z = ln(level / target) / (sigma * sqrt(minutes)), sigma a
    per-minute log move (More 15m). ``mode="dollar"``: z = (level - target) /
    sigma, sigma already in dollars for the time left (BTC 15m, Commodity 15m);
    ``minutes`` is then ignored.
    """
    if mode == "log":
        if minutes is None or level <= 0 or target <= 0:
            raise ValueError("log mode needs minutes and positive prices")
        spread = float(sigma) * math.sqrt(float(minutes))
        z = math.log(float(level) / float(target)) / spread if spread > 0 else (math.inf if level >= target else -math.inf)
    else:
        z = (float(level) - float(target)) / float(sigma) if sigma > 0 else (math.inf if level >= target else -math.inf)
    p = tail_cdf(z, tails, df)
    if clip:
        p = min(clip[1], max(clip[0], p))
    return p


def side_fair(p_up: float, side: str) -> float:
    return p_up if str(side).lower() == "yes" else 1.0 - p_up


# ------------------------------------------------------------------ volatility (422-426)
def log_returns(closes) -> list[float]:
    vals = [float(c) for c in closes or [] if c and float(c) > 0]
    return [math.log(b / a) for a, b in zip(vals, vals[1:])]


def realized_sigma(closes, minutes: int = 60, sample: bool = False) -> float | None:
    """Per-minute log-move spread over the last ``minutes`` 1-minute closes."""
    rets = log_returns(list(closes or [])[-(int(minutes) + 1):])
    if len(rets) < max(5, min(10, int(minutes) // 2)):
        return None
    return statistics.stdev(rets) if sample else statistics.pstdev(rets)


BLEND = ((15, 0.5), (60, 0.3), (240, 0.2))


def blended_sigma(closes, blend=BLEND) -> float | None:
    """Weighted mix of the 15, 60 and 240-minute realized move (422).

    Windows without enough data drop out and the weights are renormalised.
    """
    parts = [(realized_sigma(closes, m), w) for m, w in blend]
    parts = [(s, w) for s, w in parts if s is not None]
    if not parts:
        return None
    total = sum(w for _, w in parts)
    return sum(s * w for s, w in parts) / total


# Hours are UTC. US cash open 13:30-15:00 (14:30-16:00 in winter is close enough
# for a log-only factor); Asia open 00:00-02:00. Starting guesses; the model lab
# measures the real ratio before anyone uses them.
TIME_OF_DAY = (((13.5, 15.0), 1.25), ((0.0, 2.0), 1.10))


def time_of_day_mult(now: dt.datetime, table=TIME_OF_DAY) -> float:
    hour = now.astimezone(dt.timezone.utc).hour + now.astimezone(dt.timezone.utc).minute / 60.0
    for (lo, hi), mult in table:
        if lo <= hour < hi:
            return float(mult)
    return 1.0


def news_mult(now: dt.datetime, events, window_min: float = 15.0, mult: float = 1.5) -> float:
    """Bigger swings expected within ``window_min`` of a scheduled release (425)."""
    t = now.timestamp()
    for when in events or []:
        ts = when.timestamp() if isinstance(when, dt.datetime) else float(when)
        if abs(ts - t) <= window_min * 60:
            return float(mult)
    return 1.0


def jump_guard(closes, k: float = 3.0, lookback: int = 60) -> dict:
    """Skip (log-only for now) when the last minute moved more than k x normal (426)."""
    rets = log_returns(list(closes or [])[-(lookback + 2):])
    if len(rets) < 10:
        return {"jump": False, "ratio": None}
    *prior, last = rets
    normal = statistics.pstdev(prior)
    ratio = abs(last) / normal if normal > 0 else None
    return {"jump": bool(ratio is not None and ratio > k), "ratio": None if ratio is None else round(ratio, 3)}


# ------------------------------------------------------------------ multipliers (427-430)
def measured_multiplier(z_scores) -> float | None:
    """Spread of real outcomes in model z units. 1.0 = the model's swing is right.

    (More 15m found 1.31 for USD/JPY this way.)
    """
    zs = [float(z) for z in z_scores or [] if z is not None and math.isfinite(float(z))]
    if len(zs) < 2:
        return None
    return statistics.pstdev(zs)


def next_multiplier(old: float, measured: float | None, n: int, *, max_step: float = 0.15,
                    min_n: int = MIN_N, lo: float = 0.7, hi: float = 2.0) -> float:
    """Weekly refresh: move toward the measured value, at most ``max_step`` a week (428-429)."""
    if measured is None or int(n) < int(min_n):
        return float(old)
    step = max(-max_step, min(max_step, float(measured) - float(old)))
    return round(max(lo, min(hi, float(old) + step)), 4)


def apply_basis(level: float, offset: float | None, weight: float = 1.0) -> float:
    """Shift our spot onto the settlement source's print (430)."""
    return float(level) + float(weight) * float(offset or 0.0)


# ------------------------------------------------------------------ error by minutes left (431-432)
BUCKETS = ((0, 3), (3, 6), (6, 9), (9, 12), (12, 16))


def error_by_minutes(rows, buckets=BUCKETS) -> list[dict]:
    """``rows``: [{"minutes", "fair", "won"}]. Brier score and bias per bucket."""
    out = []
    for lo, hi in buckets:
        grp = [r for r in rows or [] if r.get("minutes") is not None and lo <= float(r["minutes"]) < hi
               and r.get("fair") is not None and r.get("won") is not None]
        if not grp:
            out.append({"minutes": f"{lo}-{hi}", "n": 0, "brier": None, "bias": None})
            continue
        b = sum((float(r["fair"]) - (1.0 if r["won"] else 0.0)) ** 2 for r in grp) / len(grp)
        bias = sum(float(r["fair"]) - (1.0 if r["won"] else 0.0) for r in grp) / len(grp)
        out.append({"minutes": f"{lo}-{hi}", "n": len(grp), "brier": round(b, 4), "bias": round(bias, 4)})
    return out


def trust_cap(bucket: dict, base: float = 0.20, floor_cap: float = 0.08) -> float | None:
    """Suggested trust cap for one bucket: wider errors -> smaller cap (432).

    Needs 50 rows; returns None (keep today's cap) until then. Never above ``base``.
    """
    if not bucket or int(bucket.get("n") or 0) < MIN_N or bucket.get("brier") is None:
        return None
    # A coin flip scores 0.25; a sharp model scores near 0. Cap shrinks as Brier rises.
    sharp = max(0.0, min(1.0, 1.0 - float(bucket["brier"]) / 0.25))
    cap = base * sharp - abs(float(bucket.get("bias") or 0.0))
    return round(max(floor_cap, min(base, cap)), 4)


# ------------------------------------------------------------------ confidence (433-434)
def confidence(z: float | None, edge: float | None, n_history: int = 0, hit_low: float | None = None) -> float:
    """0-1: how sure the model is. Distance from the target, edge size and track record."""
    parts = []
    if z is not None:
        parts.append(min(1.0, abs(float(z)) / 3.0))
    if edge is not None:
        parts.append(min(1.0, max(0.0, float(edge)) / 0.20))
    if n_history >= MIN_N and hit_low is not None:
        parts.append(max(0.0, min(1.0, float(hit_low))))
    return round(sum(parts) / len(parts), 4) if parts else 0.0


def confidence_stake(conf: float, cap: float = STAKE_CAP, floor_share: float = 0.4) -> float:
    """Stake inside the $25 cap: 40% of the cap at zero confidence, the full cap at 1 (434)."""
    c = max(0.0, min(1.0, float(conf)))
    return round(min(cap, cap * (floor_share + (1.0 - floor_share) * c)), 2)


# ------------------------------------------------------------------ log-only features (435-441)
def book_imbalance(bids, asks, levels: int = 3) -> float | None:
    """(bid size - ask size) / total over the top levels. +1 all bids, -1 all offers (435)."""
    b = sum(float(q) for _, q in sorted(bids or [], reverse=True)[:levels])
    a = sum(float(q) for _, q in sorted(asks or [])[:levels])
    return None if a + b <= 0 else round((b - a) / (a + b), 4)


def tape_momentum(trades, now_ts: float, window_sec: float = 60.0) -> dict:
    """Last minute of trades: contracts bought on YES minus NO, and the price drift (437)."""
    rows = []
    for t in trades or []:
        ts = t.get("ts")
        if ts is None:
            try:
                ts = dt.datetime.fromisoformat(str(t.get("created_time")).replace("Z", "+00:00")).timestamp()
            except (TypeError, ValueError):
                continue
        if now_ts - float(ts) <= window_sec and float(ts) <= now_ts:
            rows.append((float(ts), t))
    rows.sort(key=lambda r: r[0])
    net = 0.0
    prices = []
    for _, t in rows:
        n = float(t.get("count_fp") or t.get("count") or 0)
        side = str(t.get("taker_side") or "").lower()
        net += n if side == "yes" else (-n if side == "no" else 0.0)
        px = t.get("yes_price_dollars")
        if px is not None:
            prices.append(float(px))
    drift = round(prices[-1] - prices[0], 4) if len(prices) >= 2 else 0.0
    return {"trades": len(rows), "net_yes": round(net, 2), "drift": drift}


def cross_market(lead_ret: float | None, rets: dict) -> dict:
    """Is BTC moving the other coins right now? Share moving the same way as BTC (439)."""
    if not lead_ret or not rets:
        return {"same_way": None, "n": len(rets or {})}
    sign = 1 if lead_ret > 0 else -1
    same = sum(1 for r in rets.values() if r and (1 if r > 0 else -1) == sign)
    return {"same_way": round(same / len(rets), 3), "n": len(rets)}


def crowding_penalty(open_sides, new_side: str, per_extra: float = 0.01, free: int = 1) -> float:
    """Extra edge needed when many open bets already point the same way (441).

    The first ``free`` same-way bets (counting the new one) cost nothing; each
    one past that needs ``per_extra`` more edge.
    """
    same = sum(1 for s in open_sides or [] if str(s).lower() == str(new_side).lower())
    return round(max(0, same + 1 - int(free)) * per_extra, 4)


# ------------------------------------------------------------------ exits (442-447)
EXIT_DEFAULTS = {
    "take_profit": None,       # sell when bid >= this price (BTC 15m: ask + add, capped)
    "flip_margin": 0.02,       # sell when bid - fee beats fair by this
    "time_stop_min": None,     # sell when fewer minutes are left than this
    "little_left": None,       # sell when fair - (bid - fee) is below this ("little left to gain")
    "decay_min": None,         # with fewer minutes than this ...
    "decay_cushion": None,     # ... and the model's fair below this, sell ("time decay")
}


def exit_decision(*, fair: float | None, bid: float | None, fee: float = 0.0,
                  minutes_left: float | None = None, rules: dict | None = None) -> dict:
    """One shared exit check. Returns {"sell": bool, "rule": name, "why": text}.

    Order: take profit, model flip, little left to gain, time decay, time stop.
    Only rules that are set run, so the default is "model flip only".
    """
    r = dict(EXIT_DEFAULTS, **(rules or {}))
    if bid is None or not (0.0 < float(bid) < 1.0):
        return {"sell": False, "rule": "", "why": "no bid"}
    net = float(bid) - float(fee or 0.0)
    if r["take_profit"] is not None and float(bid) + 1e-9 >= float(r["take_profit"]):
        return {"sell": True, "rule": "take-profit", "why": f"bid {bid:.2f} reached {r['take_profit']:.2f}"}
    if fair is not None and r["flip_margin"] is not None and net > float(fair) + float(r["flip_margin"]):
        return {"sell": True, "rule": "model-flip", "why": f"bid after fee {net:.2f} beats fair {fair:.2f}"}
    if fair is not None and r["little_left"] is not None and float(fair) - net < float(r["little_left"]):
        return {"sell": True, "rule": "little-left",
                "why": f"only {100 * (float(fair) - net):.1f} cents left to gain"}
    if (fair is not None and minutes_left is not None and r["decay_min"] is not None
            and r["decay_cushion"] is not None and float(minutes_left) < float(r["decay_min"])
            and float(fair) < float(r["decay_cushion"])):
        return {"sell": True, "rule": "time-decay",
                "why": f"{minutes_left:.1f} min left and fair only {fair:.2f}"}
    if minutes_left is not None and r["time_stop_min"] is not None and float(minutes_left) < float(r["time_stop_min"]):
        return {"sell": True, "rule": "time-stop", "why": f"{minutes_left:.1f} min left"}
    return {"sell": False, "rule": "", "why": "hold"}


# ------------------------------------------------------------------ cautious statistics (450-454)
def wilson(wins: int, n: int, z: float = 1.96) -> tuple:
    """Wilson score interval for a win rate (453). (low, high); (0, 1) with no data."""
    n = int(n)
    if n <= 0:
        return 0.0, 1.0
    p = float(wins) / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def enough_data(n: int, min_n: int = MIN_N) -> bool:
    """The one shared "enough data?" check (454)."""
    try:
        return int(n) >= int(min_n)
    except (TypeError, ValueError):
        return False


def cautious_skip(wins: int, n: int, need: float, *, min_n: int = 10) -> bool:
    """Skip a bucket only when even the HIGH end of its win rate is below ``need`` (451).

    A raw rate punishes small, unlucky buckets; the Wilson high end waits for proof.
    """
    if int(n) < int(min_n):
        return False
    return wilson(wins, n)[1] < float(need)


def recovered(recent_wins: int, recent_n: int, need: float, *, min_n: int = 10) -> bool:
    """A skipped bucket comes back once its recent LOW end clears ``need`` (450)."""
    return int(recent_n) >= int(min_n) and wilson(recent_wins, recent_n)[0] >= float(need)


def cautious_expectancy(pnls, z: float = 1.0) -> float | None:
    """Mean P&L minus z standard errors (452). Losses count like wins."""
    vals = [float(x) for x in pnls or [] if x is not None]
    if len(vals) < 2:
        return None
    sd = statistics.stdev(vals)
    return round(statistics.fmean(vals) - z * sd / math.sqrt(len(vals)), 4)


# ------------------------------------------------------------------ replay scoring
def brier(rows, key: str = "fair") -> float | None:
    vals = [(float(r[key]), 1.0 if r["won"] else 0.0) for r in rows or []
            if r.get(key) is not None and r.get("won") is not None]
    if not vals:
        return None
    return round(sum((p - o) ** 2 for p, o in vals) / len(vals), 5)


def compare(rows, a: str, b: str) -> dict:
    """Brier for two methods on the same rows. Lower wins; 50 rows before a verdict."""
    both = [r for r in rows or [] if r.get(a) is not None and r.get(b) is not None and r.get("won") is not None]
    ba, bb = brier(both, a), brier(both, b)
    verdict = "need 50 rows"
    if enough_data(len(both)) and ba is not None and bb is not None:
        verdict = f"{b} better" if bb < ba else (f"{a} better" if ba < bb else "tie")
    return {"n": len(both), a: ba, b: bb, "verdict": verdict}
