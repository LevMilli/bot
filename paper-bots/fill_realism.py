"""Fill realism: one shared place for how pretend fills are checked. Paper only.

Nothing in this file places an order, and nothing here changes how an existing
tower buys or sells. It holds:

* ``SETTINGS``: every fill-realism number in one place (plan step 255). The
  numbers mirror what ``strict_fill.py`` and ``kalshi_shadow_tower.py`` use
  today; a test keeps them in step. The boss dashboard can show them as is.
* ``GENEROUS_WAYS``: the list of ways a pretend fill can be kinder than a
  real one (step 198).
* Pure helpers the fill-realism lab and future shadow twins use: the tape
  check with a time window (207-209), walking a thin book across price levels
  (216-218), selling into the bid size shown (213-215), no-fill reasons
  (248-252), the maker fill rule with queue position, partial fills and
  cancels (227-233), fill-vs-tape gaps (219-221), a fill-quality score (240)
  and the daily spot-check sample (242).
* ``FEE_REFERENCE``: the fees each non-Kalshi tower is meant to charge, so a
  test fails if a tower ever charges less (222-226).

Flags (all off by default; Levi turns them on, never an agent):

* ``FILL_SHADOW_STRICT``    shadow-engine towers re-check the book before a buy
* ``FILL_SHADOW_SELL_DEPTH`` shadow-engine early sales need the bid size shown
* ``FILL_BTC15M_TAPE``      BTC 15m needs real Kalshi trading at our price
* ``FILL_COMMODITY_TAPE``   Commodity 15m needs real Kalshi trading at our price

A flag is on only when its environment variable is exactly ``1``.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import math
import os

# ------------------------------------------------------------------ settings (one file)
SETTINGS = {
    "requote_seconds": 3.0,         # strict_fill PAPER_REQUOTE_SECONDS default
    "depth_share": 0.5,             # strict_fill PAPER_DEPTH_SHARE: take half the book
    "max_slip": 0.03,               # strict_fill PAPER_MAX_SLIP: skip if the ask ran 3c+
    "fallback_slip": 0.01,          # strict_fill: book not re-read -> 1c worse
    "spot_max_slip": 0.05,          # strict_fill PAPER_SPOT_MAX_SLIP
    "spot_fallback_slip": 0.01,     # strict_fill PAPER_SPOT_FALLBACK_SLIP
    "tape_lookback_sec": 300,       # shadow engine TAPE_LOOKBACK_SEC (More 15m tape check)
    "tape_max_reads": 3,            # shadow engine TAPE_MAX_READS
    "sell_depth_share": 0.5,        # proposed: an early sale takes at most half the bid size
    "maker_queue": "last",          # a resting order is last in line at its price
    "maker_cancel_move": 0.03,      # a resting order is pulled when the market moves 3c away
    "tape_gap_window_sec": 60,      # fill-vs-tape: trades within the same minute
    "beats_tape_flag": 0.005,       # a tower whose fills beat the tape by 0.5c on average is flagged
    "spot_check_n": 10,             # daily random sample for a manual check
    "kalshi_taker_rate": 0.07,
    "kalshi_maker_rate": 0.0175,    # charged only on series that list maker fees (M default 0)
    "fee_review_days": 30,          # re-check every fee schedule monthly
}

FLAGS = {
    "shadow_strict": "FILL_SHADOW_STRICT",
    "shadow_sell_depth": "FILL_SHADOW_SELL_DEPTH",
    "btc15m_tape": "FILL_BTC15M_TAPE",
    "commodity_tape": "FILL_COMMODITY_TAPE",
}


def flag(name: str) -> bool:
    """True only when the flag's environment variable is exactly '1'. Default off."""
    var = FLAGS.get(name, name)
    return os.environ.get(var, "0").strip() == "1"


def flags_state() -> dict:
    return {name: flag(name) for name in FLAGS}


GENEROUS_WAYS = (
    "Filling at the ask we saw when we decided, not the ask a few seconds later when a real order lands",
    "Buying more contracts than the book showed at that price",
    "Buying at a price nobody on Kalshi actually traded at",
    "Counting tape trades from before our decision window started",
    "Counting tape trades at a worse price than ours as if they proved our fill",
    "Selling early at the bid for more contracts than the bid size shown",
    "Selling at the bid we read, when a real sale lands seconds later at a lower bid",
    "Taking a whole thin book at the best level instead of walking down the levels",
    "Counting a resting (maker) order as filled just because the price touched it",
    "Skipping the line: a resting order is last in the queue at its price",
    "Forgetting the fee, or charging less than the venue really charges",
    "Filling in a market that closed between the decision and the fill",
    "Filling after the price jumped past our limit",
    "Mixing maker and taker results in one tower's numbers",
    "Settling on a result that does not match Kalshi's official result",
)


# ------------------------------------------------------------------ small helpers
def _num(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _epoch(value):
    """Seconds since 1970 from an epoch number or an ISO time string."""
    if value is None:
        return None
    n = _num(value)
    if n is not None:
        return n / 1000.0 if n > 1e12 else n
    text = str(value).strip()
    zone = dt.timezone.utc
    for suffix, name in ((" UTC", None), (" CT", "America/Chicago"), (" ET", "America/New_York")):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            if name:
                try:
                    from zoneinfo import ZoneInfo
                    zone = ZoneInfo(name)
                except Exception:
                    return None
            break
    try:
        when = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=zone)
    return when.timestamp()


def trade_price(row: dict, side: str):
    """Price of a public Kalshi trade on ``side`` (yes/no), in dollars."""
    yes = _num(row.get("yes_price_dollars"))
    if yes is None:
        cents = _num(row.get("yes_price"))
        yes = None if cents is None else cents / 100.0
    if yes is None:
        return None
    return yes if str(side).lower() == "yes" else round(1.0 - yes, 4)


def trade_count(row: dict) -> float:
    return _num(row.get("count_fp")) or _num(row.get("count")) or 0.0


def trade_time(row: dict):
    return _epoch(row.get("created_time") or row.get("ts") or row.get("time"))


def kalshi_fee(price: float, contracts: int = 1, rate: float | None = None, multiplier: float = 1.0) -> float:
    """Kalshi fee for one order: rate x M x C x P x (1-P), rounded up to the cent."""
    p = _num(price)
    c = int(contracts or 0)
    if p is None or not (0.0 < p < 1.0) or c < 1:
        return 0.0
    r = SETTINGS["kalshi_taker_rate"] if rate is None else float(rate)
    return math.ceil(round(r * float(multiplier) * c * p * (1.0 - p) * 100, 6)) / 100.0


def maker_fee(price: float, contracts: int = 1, multiplier: float = 0.0) -> float:
    """Kalshi maker fee (step 227). M is 0 unless the series lists maker fees."""
    return kalshi_fee(price, contracts, rate=SETTINGS["kalshi_maker_rate"], multiplier=multiplier)


# ------------------------------------------------------------------ tape check (207-209)
def tape_cover(trades: list[dict], side: str, price: float, contracts: int, *,
               window_start, decided_at) -> dict:
    """Did real Kalshi trading cover our whole pretend buy?

    Counts only trades (a) at or after ``window_start`` and at or before
    ``decided_at`` and (b) at or better than our price for our side. The
    volume must cover our full contract count.
    """
    start, end = _epoch(window_start), _epoch(decided_at)
    vol, seen, early, worse = 0.0, 0, 0, 0
    for row in trades or []:
        if not isinstance(row, dict):
            continue
        when = trade_time(row)
        px = trade_price(row, side)
        if px is None:
            continue
        seen += 1
        if when is None or (start is not None and when < start) or (end is not None and when > end):
            early += 1
            continue
        if px > float(price) + 1e-9:
            worse += 1
            continue
        vol += trade_count(row)
    want = int(contracts or 0)
    return {"volume": round(vol, 2), "need": want, "covered": vol + 1e-9 >= want and want > 0,
            "trades_seen": seen, "outside_window": early, "worse_price": worse}


def tape_gate(ticker: str, side: str, price: float, contracts: int, *, now=None, fetch=None) -> str:
    """'' when real Kalshi trading covered the buy, else a plain no-fill reason.

    Used only behind ``FILL_BTC15M_TAPE`` / ``FILL_COMMODITY_TAPE`` (both off).
    ``fetch(ticker, now) -> [trade]``; a failed read is no buy, never a guess.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    if fetch is None:
        import kalshi_shadow_tower as engine
        fetch = engine.kalshi_tape
    try:
        trades = fetch(ticker, now)
    except Exception as exc:  # noqa: BLE001 - no tape, no buy
        return f"Kalshi tape read failed ({type(exc).__name__}); no buy"
    look = SETTINGS["tape_lookback_sec"]
    cover = tape_cover(trades, str(side).lower(), price, contracts,
                       window_start=now.timestamp() - look, decided_at=now.timestamp())
    if cover["covered"]:
        return ""
    return (f"Kalshi tape: {cover['volume']:g} contracts traded at {float(price):.2f} or better "
            f"in the last {int(look) // 60} min; need {int(contracts)}")


# ------------------------------------------------------------------ book walking (213-218)
def walk_book(offers: list, contracts: int, share: float | None = None, limit: float | None = None) -> dict:
    """Split a pretend buy across price levels, cheapest first (step 216).

    ``offers`` is [(price, size), ...]. We take at most ``share`` of each
    level, never pay above ``limit``, and record every level used (step 217).
    """
    share = SETTINGS["depth_share"] if share is None else float(share)
    want = int(contracts or 0)
    levels, got, spend = [], 0, 0.0
    for px, size in sorted((float(p), float(q)) for p, q in offers or [] if _num(p) is not None):
        if got >= want:
            break
        if limit is not None and px > float(limit) + 1e-9:
            break
        room = int(math.floor(max(0.0, size) * share + 1e-9))
        take = min(room, want - got)
        if take < 1:
            continue
        levels.append({"price": round(px, 4), "contracts": take})
        got += take
        spend += take * px
    avg = round(spend / got, 4) if got else None
    return {"contracts": got, "wanted": want, "avg_price": avg, "levels": levels,
            "short": want - got, "full": got >= want and want > 0}


def sell_cap(bids: list, contracts: int, share: float | None = None, floor_price: float | None = None) -> dict:
    """An early sale never sells more than the bid size shown (steps 214-215).

    ``bids`` is [(price, size), ...]; best (highest) first after sorting. Takes
    at most ``share`` of each level, never below ``floor_price``.
    """
    share = SETTINGS["sell_depth_share"] if share is None else float(share)
    want = int(contracts or 0)
    levels, got, take_in = [], 0, 0.0
    for px, size in sorted(((float(p), float(q)) for p, q in bids or [] if _num(p) is not None), reverse=True):
        if got >= want:
            break
        if floor_price is not None and px < float(floor_price) - 1e-9:
            break
        room = int(math.floor(max(0.0, size) * share + 1e-9))
        take = min(room, want - got)
        if take < 1:
            continue
        levels.append({"price": round(px, 4), "contracts": take})
        got += take
        take_in += take * px
    shown = sum(max(0.0, float(q)) for p, q in bids or [] if _num(p) is not None)
    return {"contracts": got, "wanted": want, "avg_price": round(take_in / got, 4) if got else None,
            "levels": levels, "bid_size_shown": round(shown, 2), "full": got >= want and want > 0}


# ------------------------------------------------------------------ no-fill reasons (248-252)
NO_FILL_REASONS = {
    "closed": "market closed before the fill",
    "jumped": "price jumped past our limit",
    "thin": "book too thin at our price",
    "no_tape": "no real Kalshi trading at our price",
    "no_book": "order book could not be read",
}


def no_fill(decided: float, *, quoted=None, limit=None, close_time=None, fill_at=None,
            status: str | None = None) -> str:
    """'' when a fill may happen, else one plain reason (steps 248, 250, 252)."""
    end = _epoch(close_time)
    when = _epoch(fill_at)
    if str(status or "").lower() in ("closed", "settled", "finalized", "determined") or (
            end is not None and when is not None and when >= end):
        return NO_FILL_REASONS["closed"]
    if quoted is None:
        return ""
    cap = float(decided) + SETTINGS["max_slip"] if limit is None else float(limit)
    if float(quoted) > cap + 1e-9:
        return NO_FILL_REASONS["jumped"]
    return ""


def classify_skip(reason: str) -> str:
    """Map a tower's skip text to a no-fill key, or '' if it is not a fill problem."""
    text = str(reason or "").lower()
    if "closed" in text and "fill" in text:
        return "closed"
    if "ran away" in text or "jumped" in text or "edge gone at the re-checked" in text:
        return "jumped"
    if "too thin" in text or "book depth" in text:
        return "thin"
    if "kalshi tape" in text:
        return "no_tape"
    if "book" in text and ("read" in text or "fail" in text):
        return "no_book"
    return ""


# ------------------------------------------------------------------ maker fills (227-234)
def maker_fill(side: str, price: float, contracts: int, trades: list[dict], *, queue_ahead: float = 0.0,
               placed_at=None, cancel_after=None, best_ask_path: list | None = None,
               cancel_move: float | None = None) -> dict:
    """Would a resting buy at ``price`` have filled? (steps 228-233)

    * Trades strictly better for us than our price (they traded THROUGH our
      price) fill us first-come up to their size.
    * Trades exactly at our price first eat the ``queue_ahead`` contracts that
      were resting before us (we are last in line), then fill us.
    * A partial fill is kept (step 232).
    * If ``best_ask_path`` [(time, ask), ...] moves more than ``cancel_move``
      above our price, the rest of the order is cancelled at that time (233).
    """
    side = str(side).lower()
    want = int(contracts or 0)
    start, stop = _epoch(placed_at), _epoch(cancel_after)
    move = SETTINGS["maker_cancel_move"] if cancel_move is None else float(cancel_move)
    cancelled_at = None
    for when, ask in best_ask_path or []:
        t, a = _epoch(when), _num(ask)
        if t is None or a is None or (start is not None and t < start):
            continue
        if a > float(price) + move + 1e-9:
            cancelled_at = t
            break
    if cancelled_at is not None:
        stop = cancelled_at if stop is None else min(stop, cancelled_at)
    queue = max(0.0, float(queue_ahead or 0.0))
    got, first_fill = 0.0, None
    rows = sorted((r for r in trades or [] if isinstance(r, dict)), key=lambda r: trade_time(r) or 0)
    for row in rows:
        when = trade_time(row)
        if when is None or (start is not None and when < start) or (stop is not None and when > stop):
            continue
        # A resting buy on ``side`` is hit by a seller; that prints as a trade on our side
        # at our price or lower.
        px = trade_price(row, side)
        if px is None:
            continue
        size = trade_count(row)
        if px < float(price) - 1e-9:
            take = size
        elif abs(px - float(price)) <= 1e-9:
            eat = min(queue, size)
            queue -= eat
            take = size - eat
        else:
            continue
        if take <= 0:
            continue
        fill = min(take, want - got)
        if fill > 0 and first_fill is None:
            first_fill = when
        got += fill
        if got >= want:
            break
    filled = int(math.floor(got + 1e-9))
    status = "filled" if filled >= want and want > 0 else ("partial" if filled > 0 else "none")
    if cancelled_at is not None and status != "filled":
        status = "cancelled" if filled == 0 else "partial-cancelled"
    return {"filled": filled, "wanted": want, "status": status, "first_fill": first_fill,
            "cancelled_at": cancelled_at, "queue_left": round(queue, 2),
            "fee": maker_fee(price, filled) if filled else 0.0}


def adverse_move(side: str, fill_price: float, later_price) -> float | None:
    """Price move after a maker fill, in our favour (+) or against us (-) (step 234)."""
    later = _num(later_price)
    if later is None:
        return None
    return round(later - float(fill_price), 4)


# ------------------------------------------------------------------ fill vs tape (219-221, 240)
def tape_gap(side: str, fill_price: float, trades: list[dict], at, window_sec: float | None = None) -> dict:
    """Our fill minus the volume-weighted tape price in the same minute (step 219).

    Positive gap = we paid more than the tape (honest or pessimistic).
    Negative gap = our pretend fill beat what real traders paid.
    """
    window = SETTINGS["tape_gap_window_sec"] if window_sec is None else float(window_sec)
    t0 = _epoch(at)
    vol, spend = 0.0, 0.0
    best = None
    for row in trades or []:
        if not isinstance(row, dict):
            continue
        when, px = trade_time(row), trade_price(row, side)
        if when is None or px is None or t0 is None or abs(when - t0) > window:
            continue
        n = trade_count(row)
        vol += n
        spend += n * px
        best = px if best is None else min(best, px)
    if vol <= 0:
        return {"tape_price": None, "gap": None, "tape_volume": 0.0, "best_tape": None}
    vwap = spend / vol
    return {"tape_price": round(vwap, 4), "gap": round(float(fill_price) - vwap, 4),
            "tape_volume": round(vol, 2), "best_tape": round(best, 4)}


def fill_quality(gaps: list, covered: list) -> int | None:
    """0-100: how honest our fills look next to what the tape allowed (step 240).

    Starts at 100. Loses 10 points per cent our fills beat the tape on
    average, and loses the share of buys the tape did not cover. Paying more
    than the tape is not punished (it is the safe side).
    """
    g = [x for x in (gaps or []) if _num(x) is not None]
    c = [bool(x) for x in (covered or []) if x is not None]
    if not g and not c:
        return None
    score = 100.0
    if g:
        avg = sum(g) / len(g)
        if avg < 0:
            score -= min(60.0, -avg * 100 * 10)
    if c:
        score -= 40.0 * (1.0 - sum(c) / len(c))
    return int(round(max(0.0, min(100.0, score))))


def beats_tape(gaps: list, flag_at: float | None = None) -> bool:
    """True when a tower's fills beat the tape on average (step 221)."""
    g = [x for x in (gaps or []) if _num(x) is not None]
    if len(g) < 5:
        return False
    cut = SETTINGS["beats_tape_flag"] if flag_at is None else float(flag_at)
    return sum(g) / len(g) < -cut


def daily_sample(rows: list[dict], day: str, n: int | None = None) -> list[dict]:
    """The same 10 fills for anyone who asks on the same day (step 242)."""
    n = SETTINGS["spot_check_n"] if n is None else int(n)

    def key(row):
        text = f"{day}|{row.get('bot')}|{row.get('ticker')}|{row.get('opened')}|{row.get('side')}"
        return hashlib.sha256(text.encode()).hexdigest()

    return sorted(rows or [], key=key)[:n]


# ------------------------------------------------------------------ fee reference (222-226)
FEE_REFERENCE = {
    "coinbase-spot": {"taker": 0.009, "slippage": 0.001, "sides": 2,
                      "source": "Coinbase Advanced US intro taker 0.90%, 16 Sep 2026 schedule"},
    "btc-carry": {"spot_taker": 0.001, "perp_taker": 0.0005,
                  "source": "Binance spot 0.10% and USD-M perp 0.05% regular-tier taker"},
    "memecoin": {"swap_fee_pct": 1.0, "price_impact": True,
                 "source": "About 1% DEX/aggregator fee on every buy and sell, plus pool impact"},
    "qqq-momentum": {"commission": 0.0035, "slippage": 0.01,
                     "source": "$0.0035 per share commission and 1 cent slippage, each side"},
    "kalshi": {"taker_rate": 0.07, "maker_rate": 0.0175,
               "source": "Kalshi fee schedule, version 7.7.26"},
}
FEE_CHECKED = "2026-11-13"


def fee_review_due(today: dt.date, checked: str = FEE_CHECKED) -> bool:
    """True once the fee table is more than a month old (steps 222, 226)."""
    try:
        last = dt.date.fromisoformat(checked)
    except ValueError:
        return True
    return (today - last).days > int(SETTINGS["fee_review_days"])
