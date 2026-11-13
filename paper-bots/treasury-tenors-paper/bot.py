#!/usr/bin/env python3
"""Treasury tenors: shadow paper tower for Kalshi's 2-, 5- and 30-year yield markets.

A twin of the 10-year Treasury tower for the other tenors Kalshi lists:
KXUST2A, KXUST5A and KXUST30A. Each prices "above X%" from the live yield for
that tenor, the recent daily moves of the official par yield, and the measured
gap between the two (``ust_tenor_model.py``). It buys a side only when the edge
after the Kalshi fee clears the locked econ floor of 0.05.

Paper only. Shadow only. $25 fixed ticket from a $500 sleeve, max 3 open, one
per event (so at most one per tenor per day). Only on the settlement day, from
9:00 ET until 15 minutes before the 3:30pm ET strike, and only when the live
quote is under 10 minutes old. A tenor whose series has no open market is
noted and skipped. Exits: model flip at the bid, settle backstop.
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
import ust_tenor_model as um  # noqa: E402

SPEC = {"id": "treasury-tenors", "name": "Treasury tenors", "floor": 0.05, "max_open": 3, "max_edge": 0.15}
# tenor -> Kalshi series, Treasury CSV column, FRED id, CNBC symbol, Yahoo index (or None)
TENORS = {
    "2Y": {"series": "KXUST2A", "column": "2 Yr", "fred": "DGS2", "cnbc": "US2Y", "yahoo": None},
    "5Y": {"series": "KXUST5A", "column": "5 Yr", "fred": "DGS5", "cnbc": "US5Y", "yahoo": "%5EFVX"},
    "30Y": {"series": "KXUST30A", "column": "30 Yr", "fred": "DGS30", "cnbc": "US30Y", "yahoo": "%5ETYX"},
}
CACHE = "ust_tenors.json"
CACHE_HOURS = 6
STALE_OK_HOURS = 72
TREASURY = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
            "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
            "&field_tdr_date_value={year}&page&_format=csv")
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={fred}&cosd={start}"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={iv}&range={rng}"
CNBC_QUOTE = ("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol"
              "?symbols={sym}&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json")
CNBC_CHART = "https://ts-api.cnbc.com/harmony/app/charts/1Y.json?symbol={sym}"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
FRED_UA = {"User-Agent": "curl/8.5.0"}


def _yahoo_closes(body: dict) -> dict:
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
    try:
        row = body["FormattedQuoteResult"]["FormattedQuote"][0]
        level = float(str(row["last"]).rstrip("%"))
        at = dt.datetime.strptime(str(row["last_time"]), "%Y-%m-%dT%H:%M:%S.%f%z")
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    return level, (now - at).total_seconds()


def _read(url: str) -> str:
    headers = FRED_UA if "fred.stlouisfed.org" in url else UA
    return public_http.read(url, headers=headers, timeout=30, tries=2).decode("utf-8")


def _why(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    return f"HTTP {code}" if code else type(exc).__name__


def _official(now: dt.datetime, read, tenors: list[str]) -> tuple[dict, str]:
    """{tenor: {day: official par yield}}: Treasury.gov first (one file, all tenors), FRED as backup."""
    out = {}
    try:
        texts = [read(TREASURY.format(year=year)) for year in (now.year - 1, now.year)]
        for tenor in tenors:
            rows = {}
            for text in texts:
                rows.update(um.parse_treasury_csv(text, TENORS[tenor]["column"]))
            if len(rows) >= 21:
                out[tenor] = rows
        if len(out) == len(tenors):
            return out, "treasury.gov"
        first = "Treasury.gov short"
    except Exception as exc:  # noqa: BLE001 - any refusal falls through to FRED
        first = f"Treasury.gov {_why(exc)}"
    start = (now - dt.timedelta(days=400)).strftime("%Y-%m-%d")
    misses = []
    for tenor in tenors:
        if tenor in out:
            continue
        try:
            rows = um.parse_fred_csv(read(FRED.format(fred=TENORS[tenor]["fred"], start=start)))
        except Exception as exc:  # noqa: BLE001
            misses.append(f"FRED {TENORS[tenor]['fred']} {_why(exc)}")
            continue
        if len(rows) >= 21:
            out[tenor] = rows
        else:
            misses.append(f"FRED {TENORS[tenor]['fred']} empty")
    if not out:
        raise RuntimeError(", ".join([first] + misses))
    return out, "fred"


def _history(now: dt.datetime, tenors: list[str], read=None) -> dict:
    """{tenor: {sd_day, basis{feed: [mean, sd]}, ...}}, refreshed at most every 6 hours."""
    path = os.path.join(HERE, CACHE)
    cache = engine.read_json(path) or {}
    try:
        age = (now - dt.datetime.fromisoformat(cache["at"])).total_seconds() / 3600.0
    except (KeyError, TypeError, ValueError):
        age = None
    have = cache.get("tenors") or {}
    if age is not None and age < CACHE_HOURS and all(t in have for t in tenors):
        return have
    read = read or _read
    try:
        official, source = _official(now, read, tenors)
    except RuntimeError:
        if age is not None and age < STALE_OK_HOURS and have:
            return have
        raise
    built = {}
    for tenor, cmt in official.items():
        info = TENORS[tenor]
        feeds = [("cnbc", CNBC_CHART.format(sym=info["cnbc"]), _cnbc_closes)]
        if info["yahoo"]:
            feeds.append(("yahoo", YAHOO.format(sym=info["yahoo"], iv="1d", rng="6mo"), _yahoo_closes))
        gaps = {}
        for name, url, parse in feeds:
            try:
                gap = um.basis(cmt, parse(json.loads(read(url))))
            except Exception:  # noqa: BLE001 - a missing feed just drops out
                gap = None
            if gap is not None:
                gaps[name] = [round(gap[0], 5), round(gap[1], 5)]
        sd_day = um.daily_sd(cmt)
        if sd_day is None or not gaps:
            continue
        built[tenor] = {"sd_day": round(sd_day, 5), "basis": gaps, "last_official": cmt[max(cmt)],
                        "last_official_day": max(cmt), "source": source}
    if not built:
        if age is not None and age < STALE_OK_HOURS and have:
            return have
        raise RuntimeError("no tenor had both official history and a live-feed history")
    try:
        engine.write_json(path, {"at": now.isoformat(timespec="seconds"), "tenors": built, "paper_only": True})
    except OSError:
        pass
    return built


def _live_yield(tenor: str, now: dt.datetime):
    """(feed, yield %, age seconds). CNBC real time first; Yahoo index (15 min delayed) as backup."""
    info = TENORS[tenor]
    misses = []
    try:
        got = _cnbc_quote(engine.public_json(CNBC_QUOTE.format(sym=info["cnbc"]), headers=UA), now)
        if got:
            return ("cnbc", *got)
        misses.append("CNBC quote empty")
    except Exception as exc:  # noqa: BLE001
        misses.append(f"CNBC quote {_why(exc)}")
    if info["yahoo"]:
        try:
            body = engine.public_json(YAHOO.format(sym=info["yahoo"], iv="1m", rng="1d"), headers=UA)
            meta = body["chart"]["result"][0]["meta"]
            return ("yahoo", float(meta["regularMarketPrice"]), now.timestamp() - int(meta["regularMarketTime"]))
        except Exception as exc:  # noqa: BLE001
            misses.append(f"Yahoo {info['yahoo'].replace('%5E', '^')} {_why(exc)}")
    else:
        misses.append("no Yahoo backup for this tenor")
    raise RuntimeError(", ".join(misses))


def quotes_for(tenor: str, markets: list[dict], level: float, hist: dict, now: dt.datetime) -> list[dict]:
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
        why = (f"{hist['feed']} {level:.3f}%, basis {hist['basis_mean']:+.3f}, daily move sd "
               f"{hist['sd_day'] * 100:.1f}bp, {minutes:.0f} min to 3:30pm ET: P {p_yes:.3f}")
        for side in engine.sides(market):
            side["fair"] = p_yes if side["side"] == "yes" else 1.0 - p_yes
            side["label"] = f"{tenor} {day.strftime('%b %d')} {what}"
            side["why"] = why
            out.append(side)
    return out


def model(cfg: dict, now: dt.datetime, *, list_markets=None, live=None, history=None):
    today = now.astimezone(um.ET).date()
    if um.minutes_left(now, today) is None:
        return [], "outside the settlement-day window (9:00-15:30 ET weekdays)"
    list_markets = list_markets or engine.kalshi_open_markets
    live = live or _live_yield
    history = history or _history
    notes, quotes, todays = [], [], {}
    for tenor, info in TENORS.items():
        try:
            markets = list_markets(info["series"])
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Kalshi {info['series']} list {_why(exc)}")
            continue
        if not markets:
            notes.append(f"no open markets: {info['series']}")
            continue
        markets = [m for m in markets if um.event_day(str(m.get("event_ticker") or "")) == today]
        if markets:
            todays[tenor] = markets
    if not todays:
        return [], "; ".join(notes + ["no 2Y/5Y/30Y market settles today"])
    try:
        hist_all = history(now, sorted(todays))
    except RuntimeError as exc:
        return [], "; ".join(notes + [f"Treasury yield history refused ({exc}); waiting"])
    for tenor, markets in todays.items():
        hist = hist_all.get(tenor)
        if not hist:
            notes.append(f"{tenor} history unavailable")
            continue
        try:
            feed, level, age = live(tenor, now)
        except RuntimeError as exc:
            notes.append(f"{tenor} quote missing ({exc})")
            continue
        if age > um.MAX_QUOTE_AGE_SEC:
            notes.append(f"{tenor} quote {age / 60:.0f} min old")
            continue
        gap = (hist.get("basis") or {}).get(feed)
        if not gap:
            notes.append(f"{tenor} no basis for {feed}")
            continue
        h = dict(hist, feed=f"CNBC {tenor}" if feed == "cnbc" else TENORS[tenor]["yahoo"].replace("%5E", "^"),
                 basis_mean=gap[0], basis_sd=gap[1])
        quotes.extend(quotes_for(tenor, markets, level, h, now))
    if not quotes:
        notes.append("no tenor market in window")
    return quotes, "; ".join(notes)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        return engine.reset(SPEC, HERE)
    return engine.run_tower(SPEC, HERE, model)


if __name__ == "__main__":
    raise SystemExit(main())
