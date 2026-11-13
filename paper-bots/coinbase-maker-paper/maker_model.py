"""Coinbase maker: pure fill and fee rules for the limit-order twin.

Same signal as the Coinbase spot tower (z >= 2 up move on a completed 15-minute
bar, 25% capture haircut, locked floor 0.05), but the costs assume resting
limit orders:

* Entry: a limit buy at the signal bar's close. It fills only if a LATER bar's
  low trades below that price (touching is not enough). Unfilled after 2 bars,
  it is cancelled.
* Take-profit: a resting limit sell at entry x (1 + 1.0% round trip + 0.05).
  It fills only if a later bar's high trades above it. Maker fee.
* Stop -1.5%, a z <= -2 bar, and the 24-hour time stop are market sells:
  taker fee 0.90% plus 0.10% slippage. A bar that hits both the stop and the
  take-profit counts as the stop (the worse one).

Maker fee 0.50% each side (US Coinbase Advanced intro schedule, 16 Sep 2026).
Round trip at maker = 1.0%, so a bar must move about 24% (not 28%) before the
long clears the 0.05 floor. Still rare; the floor, not the fee, is the bar.
"""
from __future__ import annotations

import math
import statistics

LOCKED_FLOOR = 0.05
HAIRCUT = 0.25
MAKER_FEE = 0.005
TAKER_FEE = 0.009
SLIPPAGE = 0.001
MIN_Z = 2.0
STOP_PCT = 0.015
TIME_STOP_H = 24.0
EXPIRE_BARS = 2
BAR_SEC = 900
PRODUCTS = ("ETH-USD", "SOL-USD")


def maker_trip() -> float:
    return 2.0 * MAKER_FEE


def take_profit_move(floor: float = LOCKED_FLOOR) -> float:
    return maker_trip() + max(LOCKED_FLOOR, floor)


def bar_needed(floor: float = LOCKED_FLOOR) -> float:
    """Up move a 15m bar needs before the long clears the floor."""
    return (maker_trip() + max(LOCKED_FLOOR, floor)) / HAIRCUT


def parse_candles(rows, now_ts: float) -> list[dict]:
    """Coinbase [time, low, high, open, close, volume] -> completed bars, oldest first."""
    out = []
    for row in rows or []:
        if not isinstance(row, list) or len(row) < 5:
            continue
        try:
            t, low, high, opn, close = (float(x) for x in row[:5])
        except (TypeError, ValueError):
            continue
        if min(low, high, opn, close) <= 0 or t + BAR_SEC > now_ts:
            continue
        out.append({"t": int(t), "low": low, "high": high, "open": opn, "close": close})
    out.sort(key=lambda b: b["t"])
    dedup = {}
    for b in out:
        dedup[b["t"]] = b
    return list(dedup.values())


def signal(closes: list[float], floor: float = LOCKED_FLOOR) -> dict:
    """z, return and edge for the last close; action buy or skip."""
    floor = max(LOCKED_FLOOR, floor)
    rets = [b / a - 1.0 for a, b in zip(closes, closes[1:]) if a > 0]
    row = {"action": "skip", "reason": "", "z": None, "ret": None, "edge": None}
    if len(rets) < 8:
        row["reason"] = "need 8 bars"
        return row
    sigma = statistics.pstdev(rets[:-1])
    ret = rets[-1]
    row["ret"] = round(ret, 6)
    if sigma <= 1e-12 or not math.isfinite(ret):
        row["reason"] = "no sigma"
        return row
    z = ret / sigma
    edge = HAIRCUT * abs(ret) - maker_trip()
    row.update(z=round(z, 3), edge=round(edge, 6))
    if ret <= 0:
        row["reason"] = "spot cash book is long-only"
    elif z + 1e-12 < MIN_Z:
        row["reason"] = f"z {z:.2f} < {MIN_Z:g}"
    elif edge + 1e-12 < floor:
        row["reason"] = f"edge {edge:.4f} < floor {floor:.2f}"
    else:
        row.update(action="buy", reason="fee-clear long at maker")
    return row


def z_of(closes: list[float]) -> float | None:
    got = signal(closes)
    return got["z"]


def entry_fills(limit: float, bar: dict) -> bool:
    return bar["low"] < limit - 1e-12


def exit_on_bar(pos: dict, bar: dict, z: float | None, age_h: float) -> tuple[str, float, bool] | None:
    """(reason, price, maker?) if this bar closes the position, else None."""
    stop = pos["entry"] * (1.0 - STOP_PCT)
    if bar["low"] <= stop + 1e-12:
        return "stop", min(stop, bar["open"]), False
    if bar["high"] > pos["take_profit"] + 1e-12:
        return "take-profit", pos["take_profit"], True
    if z is not None and z <= -MIN_Z + 1e-12:
        return "model-flip", bar["close"], False
    if age_h + 1e-12 >= TIME_STOP_H:
        return "time", bar["close"], False
    return None


def pnl(stake: float, entry: float, exit_px: float, maker_exit: bool) -> tuple[float, float]:
    """(pnl, fees) in dollars on a $stake ticket."""
    gross = stake * (exit_px / entry - 1.0)
    out_fee = MAKER_FEE if maker_exit else TAKER_FEE + SLIPPAGE
    fees = stake * MAKER_FEE + stake * (exit_px / entry) * out_fee
    return round(gross - fees, 4), round(fees, 4)
