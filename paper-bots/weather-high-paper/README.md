# Weather high

Shadow paper tower for Kalshi daily high temperature brackets (KXHIGHNY, KXHIGHCHI, KXHIGHMIA, KXHIGHAUS, KXHIGHDEN, KXHIGHPHIL, KXHIGHLAX). Paper only. It spends no desk cash.

## How it prices a bracket
Kalshi settles on the NWS climate report for each city's station (CLINYC Central Park, CLIMDW Midway, CLIMIA, CLIAUS, CLIDEN, CLIPHL, CLILAX). The day runs midnight to midnight local standard time, and the high is a whole °F.

1. **High so far:** the max of that station's NWS observations since the day began.
2. **Rest of day:** every Open-Meteo ensemble member (GFS plus ECMWF, about 80 runs) for the hours left.
3. **Anchor:** the ensemble is shifted so its median high matches the NWS point forecast high.
4. **Draws:** the final high per draw is `max(high so far + small pad, member + noise)`. A bracket's fair value is the share of draws that land in it.

## When it buys
- Only after **15:00 local standard time** on the day. This is the afternoon lock, when most of the high is already recorded. Morning and next-day brackets are priced and logged to `research.jsonl` for the calibration lab, but not bought.
- Edge = fair − ask − Kalshi fee must be at least the locked econ floor **0.05**. An edge above **0.25** is logged but not bought, because it usually means a bad input.
- $25 fixed ticket from a $500 sleeve, max 3 open, one per city-day, one new buy per check.

## Exits
- **Model flip:** sell at the bid when bid − fee beats the model fair by 2¢.
- **Otherwise:** hold to the Kalshi result.

Engine: `../kalshi_shadow_tower.py`. Registry row: `../new_towers.py`.
