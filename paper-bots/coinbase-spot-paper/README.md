# Coinbase spot paper tower

Shadow sleeve for the paper desk. It reads public Coinbase Exchange candles. It
places no orders, uses no API key, and spends no desk cash.

## Why a 15-minute bar does not buy

US Coinbase Advanced intro fees after 16 Sep 2026 are **0.50% maker / 0.90% taker**
(help.coinbase.com advanced-trade fees; rechecked in Oct and Nov 2026 guides).
This tower assumes a market fill, so it locks the **US taker**, not the cheaper
maker or EU rate.

| Input | Locked value |
| --- | --- |
| Taker | 0.90% each side |
| Slippage | 0.10% each side |
| Round trip | 2.00% |
| Venue floor `coinbase_spot` | 0.05 mean net after that round trip |
| Sample | n ≥ 20, hit rate ≥ 40%, median net > 0 |

A 15-minute ETH or SOL bar is usually a few tenths of a percent. Keeping 25% of
that bar never clears a 2% round trip plus a 0.05 floor, so that rule cannot
trade. The book now uses a daily cross above the 50-day average, and it buys
only when the closed trades of that same rule clear every row in the table.
From 2020 through November 2026 the average of that rule was positive because a
few large legs were large, and the typical trade still lost. The gate stays
shut until the typical trade is a profit. The floor is not lowered to force a fill.

## What it will and will not trade

- **ETH-USD and SOL-USD**, long only, fixed $25 from a $500 shadow sleeve, max 1 open.
- **BTC-USD is research-only.** The BTC 15m tower already owns that factor.
- No short. A Coinbase spot cash book cannot short.
- New longs wait while `btc15m` holds a YES.
- Learning skip after 8 settles on a product with under 40% hits.
- Each close counts toward incubation (`COINBASE-ETH-USD`, `COINBASE-SOL-USD`). Staff graduate only at n ≥ 50. No auto-promote.

## Exits (the same ones the sample uses)

Stop −15% filled at the close, model-flip when the close is back under the 50-day average, time stop at 120 days.

A fixed take-profit at round-trip plus the floor lost money on this daily sample, so it is not an exit. A 16-day return is written on the research row as `observe_return`. It does not buy.

## Run

```bash
python bot.py --research   # print the locked card, write nothing
python bot.py             # one paper check
python bot.py --reset
```
