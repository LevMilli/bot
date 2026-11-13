# What-if lab

Research building on floor 4. It buys nothing and holds no cash. It covers three items from the plan: the weather incubator, the cross-venue gap monitor and the maker quote simulator.

## Missed trades
Every tower logs each priced contract on each check (`research.jsonl`). The lab looks for rows whose edge after fee cleared the tower's floor but were not bought, and asks what they would have made:

| Group | What it is |
|---|---|
| log-only | priced only for calibration, e.g. weather before its buy window, GDP more than 45 days out |
| over trust cap | edge above the tower's trust cap (logged, not bought) |
| rule said buy | rows the buy rule passed, for comparison (max-open limits ignored) |

The first time a contract qualified is the would-be entry: one contract at that ask plus fee. Once Kalshi settles it, P&L is (1 if it won, else 0) − ask − fee. A group is flagged "worth a look" only with 50+ settled rows and a 95% low end above $0. It suggests only; turning a window or cap on stays your call.

## Cross-venue gaps
For Poly sports lean and Soccer & tennis lean it measures gap "episodes": runs of back-to-back checks where Kalshi stayed cheaper than Polymarket by at least the floor after fee. Over the last 7 days it reports how many, how long they lasted, how many lasted only one check, and the typical peak edge. Gaps that vanish within one check are hard to catch with real money.

## Maker check
Instead of paying the ask, what if the tower had rested a bid 1 cent above the best bid for 30 minutes? That bid would have been the new best bid, so any public Kalshi trade in the window where a seller hit a bid at or below it would have filled us first. Fills are graded at settlement with a maker fee of 0.0175 × p × (1 − p) a contract (Kalshi's maker rate; many series charge none) and compared with taking the ask on the same contracts. Queue size and our own size are ignored, so fill rates are on the high side. Up to 20 trade reads a run.

## Exit lab
For every closed Kalshi paper trade in the last 30 days (all trading towers), it rebuilds our side's bid from entry to close using Kalshi's public 1-minute candles (hourly for trades held more than a day) and grades each exit rule on the same trade, after fees:

| Rule | What it does |
|---|---|
| what it did | the tower's real P&L, losses included |
| hold to the end | $1 if our side won, else $0 |
| +10c / +15c | sell at the bid the first time it is 10 or 15 cents above the entry price |
| model flip | sell when bid − fee beats the tower's own logged fair by 2 cents (towers that log fairs only) |
| time stop | sell at the bid half way between entry and close |

If a rule never fires, the trade is held to the result. Each rule is compared with what the tower really made on exactly the same trades. A rule needs 50 graded trades before it is named the best cautious rule. Results go to `exits.json`. It suggests only; it never changes an exit. At most 6 market reads (100 tickers each) and 20 candle reads a run; a graded trade is never read again.

## Limits
- At most 40 Kalshi result reads per run, oldest first. A contract still open is read again after 12 hours.
- Each tower keeps the top 60 rows per check by edge, so very low-edge rows may be missing. That does not affect rows above the floor.

Model: `whatif_model.py`. Registry row: `../new_towers.py`.
