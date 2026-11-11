# Coinbase spot paper tower

Shadow sleeve for the paper desk. It reads public Coinbase Exchange candles. It
places no orders, uses no API key, and spends no desk cash.

## Why the base is "skip"

US Coinbase Advanced intro fees after 16 Sep 2026 are **0.50% maker / 0.90% taker**
(help.coinbase.com advanced-trade fees; rechecked in Oct and Nov 2026 guides).
This tower assumes a market fill, so it locks the **US taker**, not the cheaper
maker or EU rate.

| Input | Locked value |
| --- | --- |
| Taker | 0.90% each side |
| Slippage | 0.10% each side |
| Round trip | 2.00% |
| Venue floor `coinbase_spot` | 0.05 excess return after that round trip |
| Sample | n ≥ 20, hit ≥ 40%, median > 0, mean ≥ 0.05, latest 20 included |
| History | 45 days of completed 15-minute candles |

A buy is a replay of an up bar held to the stop, the fee-floor take-profit, a
z ≤ −2 flip, or 24 hours, after the 2% round trip. The bar that already printed
is not the profit. Scoring 25% of that bar asked for a ~28% print and skipped
small up bars that also lose the fee. The check records the skip and does not
invent a fill. Pace does not waive the floor. The haircut stays capped at 0.25
and is not used to turn a past bar into an entry.

## What it will and will not trade

- **ETH-USD and SOL-USD**, long only, fixed $25 from a $500 shadow sleeve, max 1 open.
- **BTC-USD is research-only.** The BTC 15m tower already owns that factor.
- No short. A Coinbase spot cash book cannot short.
- New longs wait while `btc15m` holds a YES.
- Learning skip after 8 settles on a product with under 40% hits.
- Each close counts toward incubation (`COINBASE-ETH-USD`, `COINBASE-SOL-USD`). Staff graduate only at n ≥ 50. No auto-promote.

## Exits (before the next entry)

Stop −1.5%, take-profit once the price move covers the round trip plus the 0.05 floor, model-flip when z ≤ −2, time stop at 24 hours.

A 16-bar (~4 hour) return is written on the research row as `observe_return`. It does not buy.

## Run

```bash
python bot.py --research   # print the locked card, write nothing
python bot.py             # one paper check
python bot.py --reset
```
