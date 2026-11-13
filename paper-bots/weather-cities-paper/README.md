# Weather cities

Shadow paper tower for Kalshi's daily high temperature brackets in 17 cities that Weather high does not cover: Atlanta, Boston, Dallas, Washington DC, Newark, Houston, Las Vegas, Minneapolis, New Orleans, Oklahoma City, Phoenix, San Diego, San Antonio, Louisville, Seattle, San Francisco and Trenton (KXHIGHT series). Paper only. It spends no desk cash.

## How it prices a bracket
Same method as Weather high: the highest reading so far, plus about 80 ensemble runs for the rest of the day moved onto the NWS high, drawn with noise and rounded to whole degrees.

One difference: whole-degree 5-minute readings count only as a bound (reading minus 0.5C), not as the exact high. Weather high itself is unchanged.

## When it buys
- Before 15:00 local standard time prices are logged for scoring, not bought.
- Edge = fair − ask − Kalshi fee must be at least the locked econ floor **0.05**. Edge above **0.25** is logged, not bought.
- $25 fixed ticket from a $500 sleeve, max 6 open, one per city-day.
- A city with no open markets is noted and skipped.

## Exits
Model flip at the bid, otherwise hold to the Kalshi result.

Shared code: `../weather_extra.py`. Registry row: `../new_towers.py`.
