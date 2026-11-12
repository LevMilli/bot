#!/usr/bin/env python3
"""10-year Treasury: shadow paper tower for Kalshi's daily 10Y par yield markets.

Prices today's KXUST10A "above X%" markets from the live ^TNX yield, the
recent daily moves of the official 10-year par yield, and the measured gap
between the two (``ust_model.py``). Buys a side only when the edge after the
Kalshi fee clears the locked econ floor of 0.05.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 2 open, one
per event. Only on the settlement day, from 9:00 ET until 15 minutes before
the 3:30pm ET strike, and only when the ^TNX quote is under 10 minutes old.
Exits: model flip at the bid, settle backstop.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
for path in (DESK_ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import kalshi_shadow_tower as engine  # noqa: E402
import public_http  # noqa: E402
import ust_model as um  # noqa: E402

SPEC = {"id": "treasury-10y", "name": "10-year Treasury", "floor": 0.05, "max_open": 2, "max_edge": 0.15}
SERIES = "KXUST10A"
CACHE = "ust_daily.json"
CACHE_HOURS = 6
TREASURY = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
            "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
            "&field_tdr_date_value={year}&page&_format=csv")
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10&cosd={start}"
STALE_OK_HOURS = 72  # keep using the last good history this long if every source refuses
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?interval={iv}&range={rng}"
CNBC_QUOTE = ("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol"
              "?symbols=US10Y&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json")
CNBC_CHART = "https://ts-api.cnbc.com/harmony/app/charts/1Y.json?symbol=US10Y"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def _tnx_closes(body: dict) -> dict:
    try:
        res = body["chart"]["result"][0]
        stamps, closes = res["timestamp"], res["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError):
        return {}
    out = {}
    for stamp, close in zip(stamps, closes):
        if close is None:
            continue
        day = dt.datetime.fromtimestamp(int(stamp), dt.timezone.utc).astimezone(um.ET).strftime("%Y-%m-%d")
        out[day] = float(close)
    return out


def _cnbc_closes(body: dict) -> dict:
    """{YYYY-MM-DD: close} from CNBC's daily US10Y bars (Tradeweb on-the-run yield)."""
    out = {}
    try:
        bars = body["barData"]["priceBars"]
    except (KeyError, TypeError):
        return {}
    for bar in bars or []:
        try:
            stamp = str(bar["tradeTime"])
            out[f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"] = float(bar["close"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _cnbc_quote(body: dict, now: dt.datetime):
    """(yield %, age seconds) from CNBC's real-time US10Y quote, or None."""
    try:
        row = body["FormattedQuoteResult"]["FormattedQuote"][0]
        level = float(str(row["last"]).rstrip("%"))
        at = dt.datetime.strptime(str(row["last_time"]), "%Y-%m-%dT%H:%M:%S.%f%z")
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    return level, (now - at).total_seconds()


FRED_UA = {"User-Agent": "curl/8.5.0"}  # FRED stalls browser-style and custom agents


def _read(url: str) -> str:
    headers = FRED_UA if "fred.stlouisfed.org" in url else UA
    return public_http.read(url, headers=headers, timeout=30, tries=2).decode("utf-8")


def _why(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    return f"HTTP {code}" if code else type(exc).__name__


def _official(now: dt.datetime, read) -> tuple[dict, str]:
    """Official 10y par yield by day: Treasury.gov first, FRED DGS10 as backup."""
    try:
        cmt = {}
        for year in (now.year - 1, now.year):
            cmt.update(um.parse_treasury_csv(read(TREASURY.format(year=year))))
        if len(cmt) >= 21:
            return cmt, "treasury.gov"
        first = "Treasury.gov empty"
    except Exception as exc:  # noqa: BLE001 - any refusal falls through to FRED
        first = f"Treasury.gov {_why(exc)}"
    try:
        start = (now - dt.timedelta(days=400)).strftime("%Y-%m-%d")
        cmt = um.parse_fred_csv(read(FRED.format(start=start)))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"{first}, FRED {_why(exc)}") from exc
    if len(cmt) < 21:
        raise RuntimeError(f"{first}, FRED empty")
    return cmt, "fred"


def _history(now: dt.datetime, read=None) -> dict:
    """Daily sd and basis, refreshed at most every 6 hours.

    If every source refuses, the last good history is reused for up to 72 hours
    (the daily move size and basis barely change day to day). Past that it
    raises with a note naming which source failed.
    """
    path = os.path.join(HERE, CACHE)
    cache = engine.read_json(path) or {}
    try:
        age = (now - dt.datetime.fromisoformat(cache["at"])).total_seconds() / 3600.0
    except (KeyError, TypeError, ValueError):
        age = None
    if age is not None and age < CACHE_HOURS and cache.get("sd_day"):
        return cache
    read = read or _read
    try:
        cmt, source = _official(now, read)
        closes, misses = {}, []
        for name, url, parse in (("cnbc", CNBC_CHART, _cnbc_closes),
                                 ("tnx", YAHOO.format(iv="1d", rng="6mo"), _tnx_closes)):
            try:
                closes[name] = parse(json.loads(read(url)))
            except Exception as exc:  # noqa: BLE001
                misses.append(f"{'CNBC' if name == 'cnbc' else 'Yahoo ^TNX'} history {_why(exc)}")
        if not any(closes.values()):
            raise RuntimeError(", ".join(misses) or "no yield history")
    except RuntimeError:
        if age is not None and age < STALE_OK_HOURS and cache.get("sd_day"):
            return cache
        raise
    sd_day = um.daily_sd(cmt)
    gaps = {name: um.basis(cmt, rows) for name, rows in closes.items() if rows}
    gaps = {name: gap for name, gap in gaps.items() if gap is not None}
    if sd_day is None or not gaps:
        return {}
    cache = {"at": now.isoformat(timespec="seconds"), "sd_day": round(sd_day, 5),
             "basis": {name: [round(g[0], 5), round(g[1], 5)] for name, g in gaps.items()},
             "last_official": cmt[max(cmt)], "last_official_day": max(cmt), "source": source,
             "paper_only": True}
    try:
        engine.write_json(path, cache)
    except OSError:
        pass
    return cache


def quotes_for(markets: list[dict], level: float, hist: dict, now: dt.datetime) -> list[dict]:
    out = []
    for market in markets:
        day = um.event_day(str(market.get("event_ticker") or ""))
        minutes = um.minutes_left(now, day) if day else None
        if minutes is None or minutes < um.MIN_MINUTES:
            continue
        p_yes = um.fair_yes(market, level, hist["sd_day"], minutes, hist["basis_mean"], hist["basis_sd"])
        if p_yes is None:
            continue
        kind = str(market.get("strike_type"))
        strike = market.get("floor_strike") if kind.startswith("greater") else market.get("cap_strike")
        what = ("above " if kind.startswith("greater") else "below ") + f"{float(strike):.2f}%"
        why = (f"{hist.get('feed', 'TNX')} {level:.3f}%, basis {hist['basis_mean']:+.3f}, daily move sd "
               f"{hist['sd_day'] * 100:.1f}bp, {minutes:.0f} min to 3:30pm ET: P {p_yes:.3f}")
        for side in engine.sides(market):
            side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
            side["label"] = f"10Y {day.strftime('%b %d')} {what}"
            side["why"] = why
            out.append(side)
    return out


def _live_yield(now: dt.datetime):
    """(feed, yield %, age seconds). CNBC real-time first; Yahoo ^TNX is 15 min delayed."""
    misses = []
    try:
        got = _cnbc_quote(engine.public_json(CNBC_QUOTE, headers=UA), now)
        if got:
            return ("cnbc", *got)
        misses.append("CNBC quote empty")
    except Exception as exc:  # noqa: BLE001
        misses.append(f"CNBC quote {_why(exc)}")
    try:
        got = _live_tnx(now)
        if got:
            return ("tnx", *got)
        misses.append("Yahoo ^TNX quote empty")
    except Exception as exc:  # noqa: BLE001
        misses.append(f"Yahoo ^TNX quote {_why(exc)}")
    raise RuntimeError(", ".join(misses))


def _live_tnx(now: dt.datetime):
    body = engine.public_json(YAHOO.format(iv="1m", rng="1d"), headers=UA)
    try:
        meta = body["chart"]["result"][0]["meta"]
        return float(meta["regularMarketPrice"]), now.timestamp() - int(meta["regularMarketTime"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def model(cfg: dict, now: dt.datetime):
    today = now.astimezone(um.ET).date()
    if um.minutes_left(now, today) is None:
        return [], "outside the settlement-day window (9:00-15:30 ET weekdays)"
    try:
        feed, level, age = _live_yield(now)
    except RuntimeError as exc:
        return [], f"10Y yield quote missing ({exc}); waiting"
    if age > um.MAX_QUOTE_AGE_SEC:
        return [], f"10Y yield quote {age / 60:.0f} min old (bond market closed?)"
    try:
        hist = _history(now)
    except RuntimeError as exc:
        return [], f"Treasury yield history refused ({exc}); waiting"
    gap = (hist.get("basis") or {}).get(feed) if hist else None
    if not gap:
        return [], "Treasury yield history unavailable; waiting"
    hist = dict(hist, feed="CNBC 10Y" if feed == "cnbc" else "TNX", basis_mean=gap[0], basis_sd=gap[1])
    try:
        markets = engine.kalshi_open_markets(SERIES)
    except Exception as exc:  # noqa: BLE001
        return [], f"Kalshi {SERIES} list {_why(exc)}; waiting"
    quotes = quotes_for(markets, level, hist, now)
    return quotes, "" if quotes else "no 10Y market for today in window"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
