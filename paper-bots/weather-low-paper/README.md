# Weather low

Shadow paper tower for Kalshi's daily low temperature brackets (KXLOWT, 24 cities). Paper only. It spends no desk cash.

## How it prices a bracket
Kalshi settles on the low in the NWS climate report for the station named in the rules, for the climate day (midnight to midnight local standard time).

1. **Seen so far:** the lowest NWS reading at the station since the climate day began. Hourly reports carry tenths of a degree and count as exact. The 5-minute reports in between carry whole degrees C, so they only say the low is at most that reading plus 0.5C.
2. **Still to come:** about 80 ensemble runs (GFS and ECMWF) for the rest of the climate day, moved so their median matches the NWS night low.
3. **Draws:** each run is drawn many times with a little noise and rounded to whole degrees, never above what was already seen.

## When it buys
- Before 10:00 local standard time the low can still drop, so prices are logged for scoring, not bought.
- Edge = fair − ask − Kalshi fee must be at least the locked econ floor **0.05**. Edge above **0.25** is logged, not bought.
- $25 fixed ticket from a $500 sleeve, max 6 open, one per city-day.
- A city with no open markets is noted and skipped.

## Exits
Model flip at the bid, otherwise hold to the Kalshi result.

Shared code: `../weather_extra.py` (reads `../weather-high-paper/weather_model.py` without changing it). Registry row: `../new_towers.py`.
