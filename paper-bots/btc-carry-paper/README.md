# BTC carry paper tower

Shadow sleeve. Long BTC spot, short the BTC perpetual, unlevered, and held.
It reads the public Binance archive (`data.binance.vision` funding and 8h
premium index). It places no orders, uses no API key, and spends no desk cash.
It has no share of the desk risk budget.

This is not the BTC 15-minute tower and not the Coinbase spot tower. The
15-minute fee floor stays 0.05. This book does not use the Coinbase 0.90% taker.

## Fees

| Input | Locked value |
| --- | --- |
| Spot taker | 0.10% |
| Perp taker | 0.05% |
| Round trip | 0.30% (`2 × (0.10% + 0.05%)`) |
| When it is paid | Once to open, once if a person later closes. Not every month. |
| Pass-bar haircut | 0.03% of notional per month (the round trip spread across a year). It is not a second trade. |

A config that asks for the Coinbase 0.90% taker is put back on this schedule.
A config that asks for a cheaper taker is raised to this schedule. Leverage
above 1 is put back to 1.

## Hold

The sleeve opens one unlevered pair when a public funding mark and a premium
mark both exist, then sits. A red funding month is marked. It is not a close,
and it does not open a second leg to earn the loss back. Closing and reopening
every month is the version whose 2026 mean is −0.04%. That path is a reject.
The bot does not run it.

While the book is flat (no public mark yet, or the check was refused) the city
card line is:

`flat - BTC spot long / perp short not open; 0.30% round trip unpaid`

## Pass bar

Shadow until a person graduates it. Nothing auto-promotes.

The pass bar is: the after-fee monthly median stays positive. Flipping every month is a reject. On the 2026 archive months (January through October) the held median is +0.30% after the 0.03% haircut, and the flip-every-month mean is −0.04%.

## Twins (observe only)

ETH is the **same factor** as BTC — a research line inside this sleeve, not a
second tower and not desk cash. SOL’s 2026 held mean is red after the haircut —
**reject**. Staff board: `make -C .. living-funding-twins` or `python bot.py --twins`.

## Run

```bash
python bot.py --research   # print the locked card, write nothing
python bot.py --twins      # ETH observe / SOL reject (no cash)
python bot.py              # one paper check
python bot.py --reset
```
