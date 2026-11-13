# Treasury tenors

Shadow paper tower for Kalshi's 2-, 5- and 30-year Treasury yield markets (KXUST2A, KXUST5A, KXUST30A). Paper only. It spends no desk cash.

## How it prices a market
Same method as the 10-year Treasury tower, one tenor at a time:

1. **Level now:** the live CNBC yield for that tenor (US2Y, US5Y, US30Y). Backup: Yahoo ^FVX (5-year) and ^TYX (30-year). There is no Yahoo 2-year index, so the 2-year has no backup.
2. **How far it can still move:** the typical daily change of the official par yield over the last 60 trading days, scaled to the minutes left until 3:30pm ET.
3. **Basis:** the measured gap between the live feed and the official yield, added as a shift and as extra noise.
4. **Rounding:** the official yield has two decimals.

Official history comes from one Treasury.gov file for all tenors (FRED DGS2 / DGS5 / DGS30 as backup), cached 6 hours.

## When it buys
- Only on the settlement day, from 9:00 ET until 15 minutes before the 3:30pm ET strike, with a quote under 10 minutes old. These series list weekly (Friday) events.
- Edge = fair − ask − Kalshi fee must be at least the locked econ floor **0.05**. Edge above **0.15** is logged, not bought.
- $25 fixed ticket from a $500 sleeve, max 3 open, one per event.
- A tenor with no open markets is noted and skipped.

## Exits
Model flip at the bid, otherwise hold to the Kalshi result.

Model: `ust_tenor_model.py` (a copy of the 10-year model with the tenor made a setting; the 10-year tower is unchanged). Registry row: `../new_towers.py`.
