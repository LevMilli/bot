# Monthly rain and snow

Shadow paper tower for Kalshi's monthly rain totals (KXRAIN<city>M, 18 cities) and snow totals (KX<city>SNOWM, 9 cities). Paper only. It spends no desk cash.

## How it prices a market
Each market asks: is the month's total at one NWS station strictly greater than K inches?

1. **Already fallen:** the month-to-date total from the last complete NWS climate report (read from the Iowa Environmental Mesonet copy). A report written before the day ended does not count. Trace counts as zero.
2. **Still to fall:** each ensemble run (GFS and ECMWF) that reaches the last day of the month adds up its amounts for the days not yet in the report, by local standard time.
3. **Spread:** the runs are too sure of themselves, so each is drawn many times with a random scale (about ±35% for rain, ±50% for snow) and a small chance of a shower the models missed.
4. Fair value is the share of draws above K.

## When it buys
- Only when at least 20 runs reach the end of the month. Today the runs reach about 15 days ahead, so a city is noted and skipped until then. December snow markets stay quiet until about mid-December.
- Only with 14 or fewer days left; earlier prices are logged for scoring.
- Edge = fair − ask − Kalshi fee must be at least the locked econ floor **0.05**. Edge above **0.25** is logged, not bought.
- $25 fixed ticket from a $500 sleeve, max 3 open, one per city-month.
- A climate report more than 4 days old skips that city.

## Exits
Model flip at the bid, otherwise hold to the Kalshi result.

Model: `precip_model.py`. Registry row: `../new_towers.py`.
