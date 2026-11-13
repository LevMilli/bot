# Gas monthly

Shadow paper tower for Kalshi "US gas price at month end" (KXAAAGASM). Paper only. It spends no desk cash.

## How it prices a strike
Same model as Gas weekly (`../gas-weekly-paper/gas_model.py`, read here without changing it): today's AAA national average for regular, projected to the settle date with fading momentum, with a spread that grows with the days left.

## Learning
It saves one AAA reading a day to its own `aaa_history.json` and also reads Gas weekly's saved history (read only). With 21 days of changes it fits its own momentum and noise.

## When it buys
- Never more than **14 days** before settlement.
- Until momentum is fitted, only within **3 days** of settlement.
- Everything else is priced and logged to `research.jsonl` for scoring.
- Edge = fair − ask − Kalshi fee must be at least the locked econ floor **0.05**. Edge above **0.25** is logged, not bought.
- $25 fixed ticket from a $500 sleeve, max 2 open, one per month.

## Exits
Model flip at the bid, otherwise hold to the Kalshi result.

Registry row: `../new_towers.py`.
