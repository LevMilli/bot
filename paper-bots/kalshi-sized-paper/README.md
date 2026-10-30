# Sized Kalshi paper bot

Practice bot for Kalshi's public Bitcoin level markets (`KXBTCD`: BTC above a strike at a listed time). One run reads public prices, estimates its own probability, and may record **one pretend fill**.

Real orders are not implemented. There is no API key, no wallet, no login, and no live-trading switch. The only network calls are public GETs (Kalshi, Coinbase, Kraken Futures, Bitstamp, Deribit, and the ForexFactory calendar).

## Run one paper check

```bash
cd paper-bots/kalshi-sized-paper
python3 sized_bot.py             # one check
python3 sized_bot.py --self-test # stake and risk rules, offline
python3 sized_bot.py --reset     # delete the paper account and start again at $100
```

## Where state is written

Both files stay in this folder and are gitignored:

- `state.json` — paper cash, open position, closed positions, and whether the bankroll halt is on
- `paper_trades.md` — one section per check (time in US Central), with the model probability, the ask, the stake, and the action

## Stake rules

The stake follows **this bot's model probability** for the side it would buy (a zero-drift normal: distance from the strike divided by a volatility estimate). The contract's own price is not that probability.

| Model probability | Paper dollars paid (price + Kalshi taker fee) |
|---|---|
| 80% or higher | **$10 to $30**. $10 at 80%, $30 at 100%, straight line in between. |
| 55% up to 80% | **Under $10**. The target starts at $2 and rises toward $9.99. |
| Below 55% | No paper buy. |

A buy also needs the model to clear the ask by the fee plus 3 cents, a spread of 5 cents or less, and an ask between 5 cents and 85 cents. The dollars actually reserved stay inside that band. One contract of rounding can push a high-probability ticket slightly above the raw budget, and it still cannot exceed $30.

## Risk defaults

Set in `config.json`:

| Setting | Default | Why this number |
|---|---|---|
| Daily loss stop | **$20** realized | Tighter than `kalshi-sp500-paper`, which stops at $50. Sports-gap has no daily loss stop. |
| Max open risk | **$40** | One high ticket is at most $30, so $40 cannot hold a second one. The S&P bot's $25 stake cap and the sports bot's $1–$3 tickets are smaller, and neither can hold this $10–$30 stake rule, so those tighter ticket sizes were not copied. |
| Max open positions | **1** | Same tightness as the S&P bot's one trade per day. Sports-gap allows 3. |
| Paper bankroll | **$100**, halt at **$80** | A 20% drawdown halt, same fraction as the S&P bot ($400 halt on a $500 start). `--reset` clears it. |
| Big-news days | skip new buys | Any **USD, high-impact** event on today's Central date (CPI, jobs, FOMC, and similar items on the public weekly calendar). If that calendar cannot be read, the bot skips new buys. Open paper positions can still settle. |

Weekends are left on because the default series is BTC. Realized P&L is what hits the daily stop; the open-risk cap covers a position that has not settled yet.

## What the probability is

Spot is the average of the public BTC quotes that answer. Sigma is the larger of Deribit DVOL and recent one-minute realized volatility, with a floor so a quiet hour cannot print a fake certainty. The bot then looks at the soonest `KXBTCD` event that closes in 20 minutes to 4 hours.

An 80% reading only raises the paper stake. It is not a forecast that 80% of tickets win, and it is not a profit target. The S&P paper backtest in `kalshi-sp500-paper/Backtest_Report.md` won about 88% of trades and still failed: one loss wiped out about seven wins, and 1¢ worse fills lost money over the sample.

Paper fills assume the shown ask is available. That is optimistic. This is practice software, not financial advice.
