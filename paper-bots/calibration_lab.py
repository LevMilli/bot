"""Calibration lab: how often Kalshi prices actually win. Paper only, read-only.

Every run it collects recently settled Kalshi markets for families with a
scheduled close (weather, gas, daily crypto, Nasdaq, S&P), reads the standing
bid / ask 1, 3 and 6 hours before close from Kalshi's public candlesticks, and
records the result. From those rows it builds a table:

    family × hours-before-close × 5¢ price band  →  n, wins, Wilson bounds

A side's price is what you would pay: the YES ask, or 1 − YES bid for NO.
"Edge low" is the Wilson lower bound on the win rate minus the average price
and the Kalshi fee, so a positive number means even the cautious estimate beats
the price after costs.

It also keeps a scorecard for the new shadow towers: the Brier score of the
last fair each tower logged for a contract before it settled, next to the
Brier score of the ask it saw. Lower is better.

15-minute families (B13). Kalshi's 15-minute crypto, commodity, FX and index
windows settle about 1,500 times a day, so their cells reach 50 in days. They
are kept apart from the daily families on purpose: their own rows file
(``calibration_rows_15m.jsonl``), their own horizons (1, 2, 5 and 10 minutes
before close, from 1-minute candles) and their own ``table_15m`` in
``calibration.json``. ``FAMILIES`` and ``table`` are unchanged, so towers that
read the daily table (favorite harvest) see exactly what they saw before.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import kalshi_shadow_tower as engine  # noqa: E402

LAB_DIR = os.path.join(HERE, "calibration-lab-paper")
ROWS = "calibration_rows.jsonl"
TABLE = "calibration.json"
# Nov 13: the markets behind the new practice towers, so they get recorded and graded.
CRYPTO_HOURLY = ("KXSOLD", "KXXRPD", "KXDOGED", "KXBNBD", "KXSOL", "KXXRP", "KXDOGE", "KXBNB")
WEATHER_LOWS = tuple(f"KXLOWT{c}" for c in (
    "NYC", "CHI", "MIA", "AUS", "DEN", "PHIL", "LAX", "ATL", "BOS", "DAL", "DC", "EWR",
    "HOU", "LV", "MIN", "NOLA", "OKC", "PHX", "SAN", "SATX", "SDF", "SEA", "SFO", "TTN"))
WEATHER_CITY_HIGHS = tuple(f"KXHIGHT{c}" for c in (
    "ATL", "BOS", "DAL", "DC", "EWR", "HOU", "LV", "MIN", "NOLA", "OKC", "PHX",
    "SAN", "SATX", "SDF", "SEA", "SFO", "TTN"))
MONTHLY_PRECIP = tuple(f"KXRAIN{c}M" for c in (
    "NYC", "ABQ", "CHI", "EWR", "IND", "MIN", "NOLA", "LAX", "HOU", "MIA", "SEA", "SFO",
    "AUS", "DEN", "ATL", "BOS", "DC", "PHIL")) + tuple(f"KX{c}SNOWM" for c in (
    "BOS", "CHI", "DEN", "DET", "SEA", "NYC", "DC", "PHIL", "MSP"))
GAS_MONTHLY = ("KXAAAGASM",)
FAMILIES = {
    "weather": ("KXHIGHNY", "KXHIGHCHI", "KXHIGHMIA", "KXHIGHAUS", "KXHIGHDEN", "KXHIGHPHIL", "KXHIGHLAX"),
    "gas": ("KXAAAGASW",),
    "crypto_daily": ("KXBTCD", "KXETHD"),
    "nasdaq": ("KXNASDAQ100U", "KXNASDAQ100"),
    "sp": ("KXINXU", "KXINX"),
    "weather_low": WEATHER_LOWS,
    "weather_cities": WEATHER_CITY_HIGHS,
    "precip_monthly": MONTHLY_PRECIP,
    "gas_monthly": GAS_MONTHLY,
    "crypto_hourly": CRYPTO_HOURLY,
}
HORIZONS = (1, 3, 6)
# B13: 15-minute families. Separate from FAMILIES so nothing that reads the daily
# table changes. Horizons here are minutes before close.
ROWS_15M = "calibration_rows_15m.jsonl"
FAMILIES_15M = {
    "crypto_15m": ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXBNB15M", "KXHYPE15M"),
    "commodity_15m": ("KXWTI15M", "KXBRENT15M", "KXNATGAS15M", "KXGOLD15M", "KXSILVER15M",
                      "KXCOPPER15M", "KXPLATINUM15M", "KXPALLADIUM15M"),
    "fx_15m": ("KXEURUSD15M", "KXUSDJPY15M"),
    "index_15m": ("KXINX15M",),
}
HORIZONS_15M = (1, 2, 5, 10)
LOOKBACK_15M_DAYS = 2      # about 190 windows per series: one listing page
KEEP_15M_DAYS = 45
MAX_BATCHES_15M = 12       # 1-minute candle calls per run; each covers about an hour of every series
CHUNK_15M_MIN = 60         # closes inside one call span at most this many minutes (10,000-candle cap)
BAND = 0.05
Z = 1.96
LOOKBACK_DAYS = 14
KEEP_DAYS = 120
MAX_BATCHES = 50          # candlestick calls per run (up to 100 markets each); 10 families x 5
FAMILY_BATCHES = 5        # per family per run, so one busy family cannot starve the rest
MAX_SCORE_LOOKUPS = 40    # market reads per run for the scorecard


# ------------------------------------------------------------------ math
def wilson(wins: int, n: int, z: float = Z) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = wins / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, mid - half), min(1.0, mid + half)


def band_of(price: float) -> str:
    lo = math.floor(round(price / BAND, 6)) * BAND
    return f"{lo:.2f}-{lo + BAND:.2f}"


def family_of(series: str, families: dict | None = None) -> str | None:
    for family, members in (FAMILIES if families is None else families).items():
        if series in members:
            return family
    return None


# ------------------------------------------------------------------ rows
def _ts(iso: str) -> int:
    return int(dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp())


def quote_at(candles: list[dict], when: int):
    """Standing (yes_bid, yes_ask) at ``when``: the last candle that ended by then."""
    best = None
    for c in candles or []:
        end = int(c.get("end_period_ts") or 0)
        if end <= when and (best is None or end > int(best.get("end_period_ts") or 0)):
            best = c
    if best is None:
        return None
    bid = engine.num(((best.get("yes_bid") or {}).get("close_dollars")))
    ask = engine.num(((best.get("yes_ask") or {}).get("close_dollars")))
    if bid is None or ask is None:
        return None
    return [round(bid, 4), round(ask, 4)]


def make_row(market: dict, series: str, candles: list[dict], horizons=HORIZONS, unit: int = 3600,
             families: dict | None = None) -> dict | None:
    """``unit`` is seconds per horizon step: 3600 for the daily families, 60 for 15m."""
    result = str(market.get("result") or "").lower()
    if result not in ("yes", "no"):
        return None
    close = _ts(market["close_time"])
    quotes = {}
    for h in horizons:
        q = quote_at(candles, close - h * unit)
        if q:
            quotes[str(h)] = q
    # A market with no quotes is still kept (empty q) so it is not fetched again.
    return {"ticker": market["ticker"], "series": series, "family": family_of(series, families),
            "close": market["close_time"], "result": result, "q": quotes}


def side_prices(row: dict, horizon: int):
    """[(side, price, won)] a buyer could have paid ``horizon`` hours before close."""
    q = (row.get("q") or {}).get(str(horizon))
    if not q:
        return []
    bid, ask = q
    out = []
    if 0.0 < ask < 1.0:
        out.append(("yes", ask, row["result"] == "yes"))
    if 0.0 < bid < 1.0:
        out.append(("no", round(1.0 - bid, 4), row["result"] == "no"))
    return out


def build_table(rows: list[dict], horizons=HORIZONS) -> dict:
    cells: dict = {}
    for row in rows:
        fam = row.get("family")
        if not fam:
            continue
        for h in horizons:
            for _side, price, won in side_prices(row, h):
                if not 0.05 <= price < 0.95:
                    continue
                cell = cells.setdefault((fam, h, band_of(price)), {"n": 0, "wins": 0, "cost": 0.0, "fee": 0.0})
                cell["n"] += 1
                cell["wins"] += int(won)
                cell["cost"] += price
                cell["fee"] += engine.fee(price)
    table: dict = {}
    for (fam, h, band), c in sorted(cells.items()):
        lo, hi = wilson(c["wins"], c["n"])
        avg, fee = c["cost"] / c["n"], c["fee"] / c["n"]
        table.setdefault(fam, {}).setdefault(str(h), {})[band] = {
            "n": c["n"], "wins": c["wins"], "win_rate": round(c["wins"] / c["n"], 4),
            "avg_price": round(avg, 4), "avg_fee": round(fee, 4),
            "wilson_lo": round(lo, 4), "wilson_hi": round(hi, 4),
            "edge_lo": round(lo - avg - fee, 4),
        }
    return table


def lookup(family: str, horizon: int, price: float, table: dict | None = None) -> dict | None:
    """The table cell for a side priced ``price`` about ``horizon`` hours before close."""
    if table is None:
        table = (engine.read_json(os.path.join(LAB_DIR, TABLE)) or {}).get("table") or {}
    return ((table.get(family) or {}).get(str(horizon)) or {}).get(band_of(price))


def lookup_15m(family: str, minutes: int, price: float, table: dict | None = None) -> dict | None:
    """The 15-minute cell for a side priced ``price`` about ``minutes`` minutes before close."""
    if table is None:
        table = (engine.read_json(os.path.join(LAB_DIR, TABLE)) or {}).get("table_15m") or {}
    return ((table.get(family) or {}).get(str(minutes)) or {}).get(band_of(price))


# ------------------------------------------------------------------ storage
def load_rows(lab_dir: str = LAB_DIR, name: str = ROWS) -> list[dict]:
    path = os.path.join(lab_dir, name)
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def save_rows(rows: list[dict], now: dt.datetime, lab_dir: str = LAB_DIR, name: str = ROWS,
              keep_days: int = KEEP_DAYS) -> list[dict]:
    cutoff = now - dt.timedelta(days=keep_days)
    keep, seen = [], set()
    for row in rows:
        try:
            if dt.datetime.fromisoformat(row["close"].replace("Z", "+00:00")) < cutoff:
                continue
        except (KeyError, ValueError):
            continue
        if row["ticker"] in seen:
            continue
        seen.add(row["ticker"])
        keep.append(row)
    path = os.path.join(lab_dir, name)
    if os.path.islink(path):  # kept on the volume: save through the link
        path = os.path.realpath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        for row in keep:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    os.replace(tmp, path)
    return keep


# ------------------------------------------------------------------ network
def settled_markets(series: str, now: dt.datetime, get=None) -> list[dict]:
    get = get or engine.public_json
    since = int((now - dt.timedelta(days=LOOKBACK_DAYS)).timestamp())
    out, cursor = [], ""
    # Newest first, at most 5 pages: busy series keep a rolling recent sample.
    for _ in range(5):
        url = (f"{engine.KALSHI}/markets?series_ticker={series}&status=settled"
               f"&min_close_ts={since}&limit=1000" + (f"&cursor={cursor}" if cursor else ""))
        data = get(url) or {}
        out.extend(m for m in data.get("markets") or [] if isinstance(m, dict))
        cursor = data.get("cursor") or ""
        if not cursor:
            break
    return out


def candles_batch(markets: list[dict], get=None) -> dict:
    get = get or engine.public_json
    closes = [_ts(m["close_time"]) for m in markets]
    start, end = min(closes) - (max(HORIZONS) + 1) * 3600, max(closes)
    tickers = ",".join(m["ticker"] for m in markets)
    data = get(f"{engine.KALSHI}/markets/candlesticks?market_tickers={tickers}"
               f"&start_ts={start}&end_ts={end}&period_interval=60") or {}
    return {str(m.get("market_ticker") or m.get("ticker")): m.get("candlesticks") or []
            for m in data.get("markets") or []}


def chunks(markets: list[dict], size: int = 100, span_h: int = 24) -> list[list[dict]]:
    """Newest first, up to ``size`` markets whose closes sit within ``span_h`` hours."""
    out, cur, first = [], [], None
    for m in sorted(markets, key=lambda m: _ts(m["close_time"]), reverse=True):
        t = _ts(m["close_time"])
        if cur and (len(cur) >= size or first - t > span_h * 3600):
            out.append(cur)
            cur = []
        if not cur:
            first = t
        cur.append(m)
    if cur:
        out.append(cur)
    return out


def collect(now: dt.datetime, known: set, get=None) -> tuple[list[dict], list[str]]:
    """New rows for markets not seen yet, at most MAX_BATCHES candlestick calls.

    Markets of a whole family are pooled, so one call can cover every city's
    brackets for the same day.
    """
    new, notes, batches = [], [], 0
    for family, members in FAMILIES.items():
        todo, series_of = [], {}
        for series in members:
            try:
                got = settled_markets(series, now, get)
            except Exception as exc:  # noqa: BLE001 - one series failing skips it
                notes.append(f"{series} skipped ({type(exc).__name__})")
                continue
            for m in got:
                if (m.get("ticker") not in known and m.get("close_time")
                        and str(m.get("result") or "").lower() in ("yes", "no")):
                    todo.append(m)
                    series_of[m["ticker"]] = series
        used = 0
        for chunk in chunks(todo):
            if batches >= MAX_BATCHES:
                notes.append("batch budget used; the rest waits for the next run")
                return new, notes
            if used >= FAMILY_BATCHES:
                notes.append(f"{family}: share used; the rest waits for the next run")
                break
            batches += 1
            used += 1
            try:
                candles = candles_batch(chunk, get)
            except Exception as exc:  # noqa: BLE001
                notes.append(f"{family} candles skipped ({type(exc).__name__})")
                continue
            for m in chunk:
                row = make_row(m, series_of[m["ticker"]], candles.get(m["ticker"]) or [])
                known.add(m["ticker"])
                if row:
                    new.append(row)
    return new, notes


# ------------------------------------------------------------------ 15-minute families (B13)
def settled_15m(series: str, now: dt.datetime, get=None) -> list[dict]:
    """Settled 15-minute windows of one series from the last LOOKBACK_15M_DAYS (newest first)."""
    get = get or engine.public_json
    since = int((now - dt.timedelta(days=LOOKBACK_15M_DAYS)).timestamp())
    data = get(f"{engine.KALSHI}/markets?series_ticker={series}&status=settled"
               f"&min_settled_ts={since}&limit=1000") or {}
    return [m for m in data.get("markets") or [] if isinstance(m, dict)]


def candles_15m(markets: list[dict], get=None) -> dict:
    get = get or engine.public_json
    closes = [_ts(m["close_time"]) for m in markets]
    start, end = min(closes) - (max(HORIZONS_15M) + 1) * 60, max(closes)
    tickers = ",".join(m["ticker"] for m in markets)
    data = get(f"{engine.KALSHI}/markets/candlesticks?market_tickers={tickers}"
               f"&start_ts={start}&end_ts={end}&period_interval=1") or {}
    return {str(m.get("market_ticker") or m.get("ticker")): m.get("candlesticks") or []
            for m in data.get("markets") or []}


def collect_15m(now: dt.datetime, known: set, get=None) -> tuple[list[dict], list[str]]:
    """New 15m rows. Every family is pooled into one call per hour of closes, newest first.

    One call holds up to 100 windows whose closes sit within CHUNK_15M_MIN minutes,
    so it stays under Kalshi's 10,000-candle cap (100 × ~72 one-minute candles).
    """
    todo, series_of, notes = [], {}, []
    for members in FAMILIES_15M.values():
        for series in members:
            try:
                got = settled_15m(series, now, get)
            except Exception as exc:  # noqa: BLE001 - one series failing skips it
                notes.append(f"{series} skipped ({type(exc).__name__})")
                continue
            for m in got:
                if (m.get("ticker") not in known and m.get("close_time")
                        and str(m.get("result") or "").lower() in ("yes", "no")):
                    todo.append(m)
                    series_of[m["ticker"]] = series
    new, batches = [], 0
    for chunk in chunks(todo, size=100, span_h=CHUNK_15M_MIN / 60):
        if batches >= MAX_BATCHES_15M:
            notes.append("15m batch budget used; the rest waits for the next run")
            break
        batches += 1
        try:
            candles = candles_15m(chunk, get)
        except Exception as exc:  # noqa: BLE001
            notes.append(f"15m candles skipped ({type(exc).__name__})")
            continue
        for m in chunk:
            row = make_row(m, series_of[m["ticker"]], candles.get(m["ticker"]) or [],
                           HORIZONS_15M, 60, FAMILIES_15M)
            known.add(m["ticker"])
            if row:
                new.append(row)
    return new, notes


# ------------------------------------------------------------------ scorecard
def _research_fairs(folder: str) -> dict:
    """{(ticker, side): (fair, ask)} — the last logged fair per contract."""
    out: dict = {}
    for name in ("research.jsonl.1", "research.jsonl"):
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                for d in row.get("decisions") or []:
                    fair, ask = engine.num(d.get("fair")), engine.num(d.get("ask"))
                    if fair is None or ask is None or not d.get("ticker") or d.get("side") not in ("yes", "no"):
                        continue
                    out[(d["ticker"], d["side"])] = (fair, ask)
    return out


def scorecard(desk_root: str, results: dict, get=None, budget: int = MAX_SCORE_LOOKUPS) -> dict:
    """Brier of each new tower's fairs vs the asks it saw, on settled contracts."""
    import new_towers

    get = get or engine.kalshi_market
    out = {}
    for spec in new_towers.ACTIVE:
        if spec.get("research"):
            continue
        fairs = _research_fairs(os.path.join(desk_root, spec["folder"]))
        model = market = 0.0
        n = 0
        for (ticker, side), (fair, ask) in fairs.items():
            result = results.get(ticker)
            if result is None and budget > 0:
                budget -= 1
                try:
                    result = str((get(ticker) or {}).get("result") or "").lower() or None
                except Exception:  # noqa: BLE001
                    result = None
                results[ticker] = result if result in ("yes", "no") else ""
            if result not in ("yes", "no"):
                continue
            won = 1.0 if result == side else 0.0
            model += (fair - won) ** 2
            market += (ask - won) ** 2
            n += 1
        out[spec["id"]] = {
            "n": n,
            "brier_model": round(model / n, 4) if n else None,
            "brier_ask": round(market / n, 4) if n else None,
            "beats_ask": (model < market) if n else None,
        }
    return out


# ------------------------------------------------------------------ run
def best_cells(table: dict, min_n: int = 30, top: int = 3) -> list[tuple]:
    cells = []
    for fam, by_h in table.items():
        for h, bands in by_h.items():
            for band, c in bands.items():
                if c["n"] >= min_n:
                    cells.append((c["edge_lo"], fam, h, band, c))
    return sorted(cells, reverse=True)[:top]


def run(desk_root: str = HERE, lab_dir: str = LAB_DIR, now: dt.datetime | None = None, get=None, market_get=None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    os.makedirs(lab_dir, exist_ok=True)
    rows = load_rows(lab_dir)
    known = {row["ticker"] for row in rows}
    new, notes = collect(now, known, get)
    rows = save_rows(rows + new, now, lab_dir)
    table = build_table(rows)
    saved = engine.read_json(os.path.join(lab_dir, TABLE)) or {}
    results = {row["ticker"]: row["result"] for row in rows}
    results.update({k: v for k, v in (saved.get("results_cache") or {}).items() if k not in results})
    # B13: the 15-minute families, kept in their own rows file and table.
    rows15 = load_rows(lab_dir, ROWS_15M)
    known15 = {row["ticker"] for row in rows15}
    try:
        new15, notes15 = collect_15m(now, known15, get)
    except Exception as exc:  # noqa: BLE001 - the 15m add-on must never stop the daily lab
        new15, notes15 = [], [f"15m families skipped ({type(exc).__name__})"]
    notes = notes + notes15
    rows15 = save_rows(rows15 + new15, now, lab_dir, ROWS_15M, KEEP_15M_DAYS)
    cards = scorecard(desk_root, results, market_get)
    cache = {k: v for k, v in results.items() if k not in {r["ticker"] for r in rows}}
    body = {
        "updated": now.isoformat(timespec="seconds"),
        "paper_only": True,
        "rows": len(rows),
        "new_rows": len(new),
        "families": {fam: sum(1 for r in rows if r.get("family") == fam) for fam in FAMILIES},
        "table": table,
        "rows_15m": len(rows15),
        "new_rows_15m": len(new15),
        "families_15m": {fam: sum(1 for r in rows15 if r.get("family") == fam) for fam in FAMILIES_15M},
        "horizons_15m_minutes": list(HORIZONS_15M),
        "table_15m": build_table(rows15, HORIZONS_15M),
        "scorecard": cards,
        "results_cache": dict(list(cache.items())[-5000:]),
        "notes": notes,
    }
    engine.write_json(os.path.join(lab_dir, TABLE), body)
    return body


def card(body: dict) -> str:
    fams = ", ".join(f"{k} {v}" for k, v in (body.get("families") or {}).items() if v)
    line = f"Calibration lab: {body.get('rows', 0):,} settled markets ({fams or 'none yet'}), {body.get('new_rows', 0)} new."
    best = best_cells(body.get("table") or {})
    if best:
        edge, fam, h, band, c = best[0]
        line += (f" Best band: {fam} {h}h before close at {band}: n {c['n']}, won {c['win_rate']:.0%}, "
                 f"cautious edge {edge:+.3f}.")
    if body.get("rows_15m"):
        line += f" 15m families: {body['rows_15m']:,} windows ({body.get('new_rows_15m', 0)} new)"
        best15 = best_cells(body.get("table_15m") or {}, min_n=50)
        if best15:
            edge, fam, h, band, c = best15[0]
            line += f", best {fam} {h}m before close at {band}: n {c['n']}, cautious edge {edge:+.3f}"
        line += "."
    scored = [f"{k} {v['brier_model']:.3f} vs ask {v['brier_ask']:.3f}"
              for k, v in (body.get("scorecard") or {}).items() if v.get("n")]
    if scored:
        line += " Scorecard (Brier, lower is better): " + "; ".join(scored) + "."
    return line
