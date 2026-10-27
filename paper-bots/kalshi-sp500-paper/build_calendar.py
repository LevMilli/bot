"""
build_calendar.py - one-off helper that builds the list of macro "skip days"
(CPI, jobs report, GDP, PCE) from Kalshi's OWN public economic markets.

Why this way: the BLS website blocks automated downloads, and its archive
pages don't list past release dates in text. Kalshi's CPI / jobs / GDP / PCE
markets stop trading (close_time) a few minutes before each 8:30 AM ET release, so
the ET date of close_time is the release date. We keep that ET date only when
close_time falls between 07:00 and 09:00 ET, which is the release window. Anything outside it
is flagged for manual review instead of being guessed.

FOMC dates are typed in from federalreserve.gov/monetarypolicy/fomccalendars.htm
(fetched Oct 26, 2026). Output: calendar.json
"""
import json, datetime as dt
from zoneinfo import ZoneInfo
from q import get
ET = ZoneInfo("America/New_York")
SERIES = {"CPI": "KXCPI", "JOBS": "KXPAYROLLS", "GDP": "KXGDP", "PCE": "KXPCECORE"}
out, review = {}, []
for label, s in SERIES.items():
    evs = get(f"/events?series_ticker={s}&limit=200").get("events", [])
    dates = set()
    for e in evs:
        if not e["event_ticker"].startswith("KX"):
            continue  # legacy pre-2024 format, outside our backtest window
        ms = []
        for base in ("/markets", "/historical/markets"):
            ms = get(f"{base}?event_ticker={e['event_ticker']}&limit=1").get("markets", [])
            if ms: break
        if not ms: continue
        ct = dt.datetime.fromisoformat(ms[0]["close_time"].replace("Z", "+00:00")).astimezone(ET)
        if dt.date(2024, 10, 1) <= ct.date() <= dt.date(2026, 12, 31):
            if 7 <= ct.hour < 9:
                dates.add(str(ct.date()))
            else:
                review.append((label, e["event_ticker"], ct.isoformat()))
    out[label] = sorted(dates)
out["FOMC"] = ["2024-11-07","2024-12-18","2025-01-29","2025-03-19","2025-05-07","2025-06-18",
               "2025-07-30","2025-09-17","2025-10-29","2025-12-10","2026-01-28","2026-03-18",
               "2026-04-29","2026-06-17","2026-07-29","2026-09-16","2026-10-28","2026-12-09"]
# Elections: US general election Nov 5 2024; midterms Nov 3 2026 (+ day after each)
out["ELECTION"] = ["2024-11-05","2024-11-06","2026-11-03","2026-11-04"]
out["_needs_review"] = review
json.dump(out, open("calendar.json", "w"), indent=1)
for k, v in out.items(): print(k, len(v), v)
