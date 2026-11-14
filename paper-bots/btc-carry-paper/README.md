# BTC carry paper tower (Coinbase)

Shadow sleeve. Long 0.01 BTC on Coinbase spot and short one nano BTC perp
(BIP) on Coinbase Financial Markets. Price moves cancel out. What is left is
the hourly funding: when the rate is positive, shorts get paid.

It moved from Binance on 2026-11-14 because Binance does not serve US
residents and Binance.US has no perpetual futures. The old Binance book is
kept, untouched, in `paper_account.binance-retired.json`. The Coinbase book
starts fresh at $1,500 and its results count from zero.

Pretend money only. It reads Coinbase's public market data (no key, no
account, no order). If any Coinbase or Binance key is in the environment, the
check refuses to run.

## Wallet layout (built to match the real thing)

| Account | Holds | Product |
| --- | --- | --- |
| Coinbase spot wallet | 0.01 BTC per contract and spare USD | `BTC-USD` |
| Coinbase Financial Markets futures account | USD margin for the short | `BIP-20DEC30-CDE` (0.01 BTC per contract) |

Money moves, all simulated with pretend USD:

1. Open: buy 0.01 BTC on spot at the ask, sweep margin to futures (2x
   Coinbase's overnight short margin, read live), sell 1 BIP at the bid.
2. Every hour: the posted funding rate is credited (or charged) on
   `0.01 x mark x rate`. A missed hour uses the last rate seen and is counted
   as estimated on the card.
3. Top-up: if the futures account falls below 1.5x overnight margin, USD is
   swept in from spot. If spot USD runs out, a slice of spot BTC is sold (with
   the taker fee) and the card says the hedge drifted.
4. Forced close: below Coinbase's intraday margin, both legs close and the
   0.80% liquidation fee is charged.
5. Daily at 5 PM ET: funding and the day's price change post to the futures
   account. Margin above 3x is swept back to spot. One result is written.
6. Close: sell the BTC at the bid, buy back the BIP at the ask, sweep the
   futures USD back to spot.

## Fees (locked, can go up, never down)

| Cost | Value |
| --- | --- |
| Spot taker | 0.90% each side (Coinbase Advanced US intro tier) |
| Perp fee | 0.05% of notional per contract per side, at least $0.20 |
| Liquidation | 0.80% |
| Spreads | the live bid/ask on both books |

A full round trip on one contract is about 1.9% of the position.

## Rules

- Entry: at least 24 real hourly funding rates seen. The 7-day average as a
  yearly rate, minus the full round trip, plus the entry basis, must be at
  least the locked `coinbase_btc_carry` floor of 0.02 (2% a year).
- Exit: after 30 days, close if the 7-day funding is below -2% a year.
- One result per daily settle. 50 results before the tower is judged. The
  pass bar is a positive total and a positive median after every fee.
- Nothing auto-promotes. Real money stays off.

## What real money would need (not built)

- A Coinbase account with futures approval.
- One API key with view and trade only (no transfer, no withdraw), saved in
  Railway, never in code or chat.
- A separate real-order piece with its own tests and limits.
- 50 practice results and Levi's OK.

## Run

```bash
python bot.py --research   # print the locked card and the wallet layout
python bot.py              # one paper check
python bot.py --reset
```
