# Backtest_Report.md
_Generated 2026-10-26 16:44 CDT by `python3 backtest.py report` from Kalshi public-API data (no login)._ _Paper research only. Past results do not guarantee future results._

## Method (read first)
- **Market:** KXINXU (S&P 500 at/above strike). Only already-settled events. Result = Kalshi's official `result` field.
- **Entry price:** for entry time T we take Kalshi 1-minute candlesticks (`/historical/markets/{t}/candlesticks` before the
  Aug 27 2026 historical cutoff, `/markets/candlesticks` after) and use the **closing yes-bid / yes-ask of the last 1-minute bar ending at or
  before T** (look-back 3 h; a minute with no bar = quote unchanged). YES ask = yes_ask; NO ask = 1 - yes_bid. Nothing after T is used to choose
  the trade, so there is **no lookahead in the signal**. (The settled index value is used only to decide *which strikes to download first*; the
  download widens until the edge strikes are provably outside the band - see "edge check" below.)
- **Rule:** buy the highest-priced side with ask 80-90c (tie -> tighter spread, YES first). Size floor($25/ask). Pay the ask. Taker fee
  ceil-to-cent(0.07*C*P*(1-P)). Hold to settlement. Slippage test: fill at ask + 1c.
- **Skips:** calendar.json (FOMC decision days, CPI, jobs report, advance GDP, every PCE/Personal-Income release, election day + day after,
  holidays/half days; sources listed inside the file). $50 daily loss limit applied. The $400 kill switch is **reported** (date it would have
  fired) but the simulation keeps going so you can see the whole period.
- **Limits:** historical order-book depth is not available, so we assume our <=31 contracts fill at the displayed ask (UNVERIFIED for old
  dates). Quotes come from 1-minute bar closes, not tick data. A 1-minute bar can be a few seconds stale.
- **Split:** chronological by trading day: first 70% of days = in-sample, last 30% = out-of-sample. No parameters were tuned on either part
  (the rule was fixed in Strategy.md before this test), so in-sample vs out-of-sample here is a stability check, not a fitting check.

## 1. Version 1 - DAILY (12:30 PM CT entry, 3 PM CT settle)
### Pay-the-ask (base case)
Split date: in-sample = trading days before **2026-03-24** (first ~70% of days), out-of-sample = 2026-03-24 onward.

| Period | Trades | Skipped: news/holiday | Skipped: no 80-90c contract | No data / void | Win rate | Avg win | Avg loss | Total P&L | Max drawdown | Reward:risk (avg win/avg loss) | Break-even win rate | Expectancy / trade | Worst losing streak | $400 kill switch hit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Overall (2024-10-24 to 2026-10-23) | 289 | 87 | 120 | 1 | 87.9% | $3.56 | $-24.85 | $+35.16 | $157.80 | 0.143 | 87.5% | $+0.122 | 2 | 2025-08-05 |
| In-sample (2024-10-24 to 2026-03-23) | 180 | 63 | 104 | 0 | 85.0% | $3.75 | $-24.85 | $-97.24 | $157.80 | 0.151 | 86.9% | $-0.540 | 2 | 2025-08-05 |
| Out-of-sample (2026-03-24 to 2026-10-23) | 109 | 24 | 16 | 1 | 92.7% | $3.28 | $-24.82 | $+132.40 | $88.41 | 0.132 | 88.3% | $+1.215 | 1 | never |

### Sensitivity: +1c worse fill on every trade
Split date: in-sample = trading days before **2026-03-24** (first ~70% of days), out-of-sample = 2026-03-24 onward.

| Period | Trades | Skipped: news/holiday | Skipped: no 80-90c contract | No data / void | Win rate | Avg win | Avg loss | Total P&L | Max drawdown | Reward:risk (avg win/avg loss) | Break-even win rate | Expectancy / trade | Worst losing streak | $400 kill switch hit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Overall (2024-10-24 to 2026-10-23) | 289 | 87 | 120 | 1 | 87.9% | $3.25 | $-24.82 | $-42.79 | $192.23 | 0.131 | 88.4% | $-0.148 | 2 | 2025-07-24 |
| In-sample (2024-10-24 to 2026-03-23) | 180 | 63 | 104 | 0 | 85.0% | $3.43 | $-24.84 | $-145.31 | $192.23 | 0.138 | 87.9% | $-0.807 | 2 | 2025-07-24 |
| Out-of-sample (2026-03-24 to 2026-10-23) | 109 | 24 | 16 | 1 | 92.7% | $2.97 | $-24.74 | $+102.52 | $87.98 | 0.120 | 89.3% | $+0.941 | 1 | never |

### Coverage
- Events tested: 497 (2024-10-24 to 2026-10-26). Status counts: {'trade': 289, 'skip_no_band': 120, 'skip_news': 87, 'missing_data': 1}.
- Events with no usable data from the API: 1 (e.g. KXINXU-26OCT26H1600).
- Trades where the download-edge completeness check failed: 0 (0 = every in-band contract was seen).
- Average entry price paid: 86.6c; total fees: $68.22.
## 2. HOURLY variant (entry 30 min before each hourly settle, 9 AM-3 PM CT)
Hourly KXINXU settle times other than 3 PM CT only exist from **2025-02-13** (the 12 PM CT settle from 2024-11-29); the 3 PM CT settle exists from 2024-10-24. Max 1 trade per hourly event; same news-day skips; $50 daily loss limit.
### Pay-the-ask (base case)
Split date: in-sample = trading days before **2026-03-23** (first ~70% of days), out-of-sample = 2026-03-23 onward.

| Period | Trades | Skipped: news/holiday | Skipped: no 80-90c contract | No data / void | Win rate | Avg win | Avg loss | Total P&L | Max drawdown | Reward:risk (avg win/avg loss) | Break-even win rate | Expectancy / trade | Worst losing streak | $400 kill switch hit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Overall (2024-10-25 to 2026-10-26) | 2164 | 511 | 357 | 1 | 86.4% | $3.34 | $-24.81 | $-1080.72 | $1211.92 | 0.135 | 88.1% | $-0.499 | 5 | 2025-02-26 |
| In-sample (2024-10-25 to 2026-03-20) | 1353 | 343 | 285 | 0 | 85.5% | $3.35 | $-24.80 | $-987.30 | $1121.06 | 0.135 | 88.1% | $-0.730 | 5 | 2025-02-26 |
| Out-of-sample (2026-03-23 to 2026-10-26) | 811 | 168 | 72 | 1 | 87.8% | $3.32 | $-24.81 | $-93.42 | $236.57 | 0.134 | 88.2% | $-0.115 | 3 | 2026-07-27 |

### Sensitivity: +1c worse fill
Split date: in-sample = trading days before **2026-03-23** (first ~70% of days), out-of-sample = 2026-03-23 onward.

| Period | Trades | Skipped: news/holiday | Skipped: no 80-90c contract | No data / void | Win rate | Avg win | Avg loss | Total P&L | Max drawdown | Reward:risk (avg win/avg loss) | Break-even win rate | Expectancy / trade | Worst losing streak | $400 kill switch hit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Overall (2024-10-25 to 2026-10-26) | 2164 | 511 | 357 | 1 | 86.4% | $3.03 | $-24.81 | $-1647.88 | $1714.66 | 0.122 | 89.1% | $-0.761 | 5 | 2025-02-25 |
| In-sample (2024-10-25 to 2026-03-20) | 1353 | 343 | 285 | 0 | 85.5% | $3.05 | $-24.80 | $-1337.06 | $1436.33 | 0.123 | 89.1% | $-0.988 | 5 | 2025-02-25 |
| Out-of-sample (2026-03-23 to 2026-10-26) | 811 | 168 | 72 | 1 | 87.8% | $3.02 | $-24.84 | $-310.82 | $402.03 | 0.121 | 89.2% | $-0.383 | 3 | 2026-05-14 |

### Did it profit every hour?
**Overall:**
- Hours with a trade: 2164. Net profitable: **1869 (86.4%)**; losing: **295 (13.6%)**.
- Of all 2545 non-news trading hours with data, 85.0% had a trade (the rest had nothing in the 80-90c band or hit the $50 daily stop and earned $0).
- Trading days with at least one trade: 372. Net profitable days: 170 (45.7%), losing days: 202 (54.3%).

**In-sample:**
- Hours with a trade: 1353. Net profitable: **1157 (85.5%)**; losing: **196 (14.5%)**.
- Of all 1657 non-news trading hours with data, 81.7% had a trade (the rest had nothing in the 80-90c band or hit the $50 daily stop and earned $0).
- Trading days with at least one trade: 245. Net profitable days: 114 (46.5%), losing days: 131 (53.5%).

**Out-of-sample:**
- Hours with a trade: 811. Net profitable: **712 (87.8%)**; losing: **99 (12.2%)**.
- Of all 888 non-news trading hours with data, 91.3% had a trade (the rest had nothing in the 80-90c band or hit the $50 daily stop and earned $0).
- Trading days with at least one trade: 127. Net profitable days: 56 (44.1%), losing days: 71 (55.9%).

### By hour of day (overall, base case)
| Settle hour (CT) | Entry (CT) | Trades | Win rate | Total P&L | Expectancy |
|---|---|---|---|---|---|
| 9:00 | 8:30 | 354 | 84.2% | $-481.05 | $-1.359 |
| 10:00 | 9:30 | 344 | 86.9% | $-155.69 | $-0.453 |
| 11:00 | 10:30 | 330 | 90.0% | $+188.68 | $+0.572 |
| 12:00 | 11:30 | 321 | 82.9% | $-457.74 | $-1.426 |
| 13:00 | 12:30 | 318 | 88.4% | $+37.99 | $+0.119 |
| 14:00 | 13:30 | 311 | 88.4% | $+57.13 | $+0.184 |
| 15:00 | 14:30 | 186 | 82.3% | $-270.04 | $-1.452 |

### Coverage
- Events tested: 3057 (2024-10-24 to 2026-10-26). Status counts: {'skip_no_band': 357, 'trade': 2164, 'skip_news': 511, 'skip_daily_loss_limit': 24, 'missing_data': 1}.
- Events with no usable data from the API: 1 (e.g. KXINXU-26OCT26H1600).
- Trades where the download-edge completeness check failed: 0 (0 = every in-band contract was seen).
- Average entry price paid: 87.4c; total fees: $485.25.
## 3. Statistical check and verdict
**Daily V1 (base case):**
- Overall: expectancy $+0.122/trade, 95% CI $-0.954 to $+1.197 (t = +0.22; not statistically different from $0).
- In-sample: expectancy $-0.540/trade, 95% CI $-2.042 to $+0.962 (t = -0.70; not statistically different from $0).
- Out-of-sample: expectancy $+1.215/trade, 95% CI $-0.175 to $+2.605 (t = +1.71; not statistically different from $0).
**Hourly (base case):**
- Overall: expectancy $-0.499/trade, 95% CI $-0.908 to $-0.091 (t = -2.40; statistically different from $0).
- In-sample: expectancy $-0.730/trade, 95% CI $-1.260 to $-0.200 (t = -2.70; statistically different from $0).
- Out-of-sample: expectancy $-0.115/trade, 95% CI $-0.752 to $+0.521 (t = -0.35; not statistically different from $0).

**Verdict - Version 1 daily: FAIL (not proven; do not trust it with money yet).**
- Win rate looks great (~88%) but each loss (~-$24.85) wipes out ~7 wins (~+$3.56), so the strategy needs ~87.5-88.5% wins just to
  break even. It sits right on that line: +$35 over two years (+$0.12/trade) and **negative with just +1c worse fills** (-$43).
- In-sample (Oct 2024-Mar 2026) **lost $97** and would have hit the $400 kill switch on **2025-08-05**; out-of-sample (Mar-Oct 2026)
  made +$132 (+$1.21/trade) but the confidence interval includes $0 and the period is only ~7 months. The rule was not tuned, so the split
  is a stability test: the edge flipped sign between periods, which is the opposite of robust.
- Honest read: the 80-90c band is roughly fairly priced by Kalshi. Any edge is smaller than the spread + fee.

**Verdict - Hourly variant: FAIL in both splits.** It lost money in-sample and out-of-sample, at pay-the-ask and worse with +1c.
**"Profit every hour" is not realistic:** ~86% of hourly trades win, but fewer than half of trading days end positive, losing
streaks of up to 5 trades occurred, and one loss erases ~7 wins. More trades = more fees + spread paid, so the hourly version loses faster.

**Paper-trading status:** keep the bot in PAPER mode. Version 1 can be paper-traded forward to collect live evidence, but the
backtest does not support real-money use.

