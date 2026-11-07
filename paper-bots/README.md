# Trading bots (paper / signal-only) — starter pack

Four small Python programs for practicing with prediction markets and crypto **without risking money**.
Every one of them is **paper-only or signal-only**: they read **free public data** (no sign-up, no API key),
**place no real trades, need no login, and never connect a wallet**. They just print numbers and keep a
pretend ("paper") account in local files.

> **Risk disclaimer — please read.** This is learning software, **not financial advice**. Prediction
> markets and crypto can lose you all the money you put in. The backtest of the daily Kalshi S&P strategy
> (see `kalshi-sp500-paper/Backtest_Report.md`) **FAILED once realistic fills were used**: it won ~88% of
> trades but one loss wiped out ~7 wins, and with just 1¢ worse fills it lost money overall. The hourly
> version lost in every test. Online hype ("$1,000 → $30,000", "profit every hour") is **unproven** — you
> never see the losing streaks or cherry-picking. Paper results are optimistic (they assume perfect fills)
> and past results don't predict the future. Check whether prediction markets are legal where you live.

## What's inside
| Folder | What it is | Data it reads (all free) |
|---|---|---|
| `kalshi-sp500-paper/` | Kalshi S&P 500 daily paper bot: once a day buys (on paper) the safest 80–90¢ contract on the 3 PM CT close, skips big-news days, plus a full backtester | Kalshi public API |
| `sports-gap-paper/` | Live sports "gap" paper bot: compares ESPN's live win probability with Kalshi game prices, paper-buys big gaps | ESPN scoreboard, Kalshi public API |
| `memecoin-paper/` | Solana meme-coin paper bot: strict rug-pull filter, paper buys at real prices, stop/ladder/trailing exits | DexScreener, RugCheck |
| `btc15m-signal/` | `btc15m_signal.py`: Bitcoin 15-minute Kalshi **paper** bot. Prints BUY or SKIP, and paper-fills into `paper_account.json` when the checklist clears (TP print-only) | Kalshi, Coinbase, Kraken, Bitstamp, Deribit DVOL, ForexFactory calendar |
| `TEAM_ROLES.md` | How the "desk" of helper bots was organized, and the safety rules | — |
| `DESK_ROI_SYSTEM.md` | Desk-wide ROI rules every present bot must follow (paper only) | — |
| `BUY_SELL_FAILSAFE_INVENTORY.md` | Per-bot buy / sell / failsafe thresholds + entry_gate map | — |

## Install (once)
1. Install **Python 3.10 or newer** (https://www.python.org/downloads/). On Windows tick "Add Python to PATH".
2. Open a terminal in this folder and run:
   ```
   pip install -r requirements.txt
   ```
   (Use `python3` / `pip3` on Mac/Linux if `python` / `pip` don't work.)

## Run each one once
```
# 1) Bitcoin 15-min paper check (prints BUY/SKIP; may write paper_account.json).
cd btc15m-signal
python btc15m_signal.py
cd ..

# 2) Kalshi S&P 500 paper bot
cd kalshi-sp500-paper
python test_components.py          # self-tests + a live read-only data check
python bot.py brief --dry-run      # morning summary, writes nothing
python bot.py scan --dry-run --any-time   # what it WOULD buy right now (testing)
python backtest.py fetch daily     # (slow, downloads history) then:
python backtest.py report          # rebuilds Backtest_Report.md
cd ..

# 3) Sports gap paper bot (only does something while games are live)
cd sports-gap-paper
python gap_bot.py                  # one check; creates state.json + paper_trades.md
cd ..

# 4) Meme-coin paper bot
cd memecoin-paper
python bot.py                      # one scan; creates checks.csv, positions.json, trades.csv
cd ..
```
Each bot's own README / docstring explains the rules and settings. Every bot starts with a fresh,
empty paper account: no trade history or saved state is included in this pack.

## How the BTC 15-minute signal decides
- Target = the market's `floor_strike`. BTC price = average of Coinbase, Kraken Futures and Bitstamp.
- Side = **YES** if price is above the target, else **NO**. Cushion = distance from the target.
- Expected move until close: `sigma = price × DVOL/100 × sqrt(minutes_left / 525600)` (Deribit DVOL), and
  realized `stdev(last 60 one-minute returns) × price × sqrt(minutes_left)`; the larger is used (if DVOL
  fails: realized × 1.2).
- `z = cushion / sigma`, `p = Phi(z)` (normal probability), Kalshi fee = `ceil(0.07 × P × (1−P) × 100)/100`.
- **BUY only if all are true:** ≥10 min left; p ≥ ask + fee + 0.05; cushion ≥ $40; z ≥ 0.5 (0.6 if only
  Coinbase worked); ask 65–85¢; spread ≤ 3¢; ≥5 contracts offered at the ask; last 5 one-minute candles not
  moving toward the target; no USD high-impact news within 30 min of the block. Otherwise **SKIP** + reason.
- Suggested take-profit if you were filled: fill + 15¢, capped at 99¢ (print-only — not executed).
- On the PIMP desk, BTC `run` is an **entry** action: desk daily loss / max open / open risk gate it like the other towers. See `DESK_ROI_SYSTEM.md`.

## Living Trading Upgrade (staff pulse)
Paper-only living spine — floors locked, never auto-publishes Discord.

```
make living-help             # list smoke targets
make living-status
make living-selfcheck
make living-hud / living-hud-discord
make living-priority / living-priority-discord
make living-ritual-live / living-ritual-observe
make living-ritual-discord   # paste draft only — never auto-posts
make living-doctor / living-doctor-discord
make living-money            # fee ledger / fills observe tip
make living-rules            # paper / floors / Discord paste-only tip
make living-surfaces         # sunday twins + soft-max headroom
make living-smoke            # floors + guardrails + soft-max aggregate
make living-paste            # Discord paste-only target index
make living-paper            # paper_only + live=False assert
make living-makefile         # living-* Makefile target index
make living-venues           # sports 0.06 / BTC+commodity 0.05 / INX+DEX 0.02
make living-chicago          # Chicago CT calendar day
make living-export
make living-test
```

Staff map: `LIVING_UPGRADE.md`. Plan tickets: `POSITIVE_ROI_PLAN.md`.

## Notes
- All times are shown in US Central (CT) or UTC as labeled.
- The meme-coin bot has an optional, **disabled** hook for a paid AI API (needs your own key in an
  environment variable); it's off and nothing in this pack contains a key.
- Real trading is deliberately not built in. If you ever trade for real, do it by hand, tiny sizes, and
  only after a long paper record.
