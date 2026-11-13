"""Meme price check: pure logic for the second-price test (idea B15).

For each memecoin the paper tower holds or just looked at, compare the
DexScreener price (deepest Solana pair for that mint) with Jupiter's price.
A gap over 2%, or either price missing, is a "would block": the memecoin tower
would have skipped that buy or held off that sale if the check were on.
"""
from __future__ import annotations

import csv
import os

MAX_GAP = 0.02
MAX_MINTS = 30
RECENT_CHECK_ROWS = 400
DEX = "https://api.dexscreener.com/tokens/v1/solana/{mints}"
JUP = "https://lite-api.jup.ag/price/v3?ids={mints}"


def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def watch_list(positions: dict | None, checks_path: str | None) -> list[dict]:
    """Open positions first, then the newest mints from checks.csv (unique, max 30)."""
    out, seen = [], set()
    for pos in (positions or {}).get("open") or []:
        mint = str((pos or {}).get("mint") or "").strip() if isinstance(pos, dict) else ""
        if mint and mint not in seen:
            seen.add(mint)
            out.append({"mint": mint, "symbol": str(pos.get("symbol") or ""), "why": "open"})
    rows = []
    if checks_path and os.path.exists(checks_path):
        try:
            with open(checks_path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))[-RECENT_CHECK_ROWS:]
        except (OSError, csv.Error):
            rows = []
    for row in reversed(rows):
        mint = str(row.get("mint") or "").strip()
        if mint and mint not in seen:
            seen.add(mint)
            out.append({"mint": mint, "symbol": str(row.get("symbol") or ""), "why": "checked"})
    return out[:MAX_MINTS]


def dex_prices(pairs) -> dict:
    """{mint: (price, liquidity)} from the deepest pair per base token."""
    best = {}
    for pair in pairs or []:
        if not isinstance(pair, dict):
            continue
        mint = str((pair.get("baseToken") or {}).get("address") or "")
        price = _f(pair.get("priceUsd"))
        liq = _f((pair.get("liquidity") or {}).get("usd")) or 0.0
        if not mint or price is None:
            continue
        if mint not in best or liq > best[mint][1]:
            best[mint] = (price, liq)
    return best


def jup_prices(body) -> dict:
    out = {}
    for mint, row in (body or {}).items() if isinstance(body, dict) else []:
        price = _f((row or {}).get("usdPrice")) if isinstance(row, dict) else None
        if price is not None:
            out[mint] = price
    return out


def compare(watch: list[dict], dex: dict, jup: dict) -> list[dict]:
    rows = []
    for item in watch:
        d = (dex.get(item["mint"]) or (None, None))[0]
        j = jup.get(item["mint"])
        row = dict(item, dex=d, jupiter=j, gap=None)
        if d is None or j is None:
            row.update(block=True, reason="DexScreener price missing" if d is None else "Jupiter price missing")
        else:
            gap = abs(d - j) / j
            row["gap"] = round(gap, 5)
            row.update(block=gap > MAX_GAP + 1e-12,
                       reason=f"prices differ {gap:.1%}" if gap > MAX_GAP + 1e-12 else "agree")
        rows.append(row)
    return rows
