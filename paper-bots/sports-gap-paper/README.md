# Sports "gap" bot for Kalshi: PAPER ONLY

This is a practice bot. It **never places real orders**. It has no API key, no wallet and no login, and it only reads free public data. The money is pretend: a $100 paper bankroll.

## What it does (one run)
1. Asks ESPN's free scoreboard which games are **in progress** (NFL, college football, NBA, WNBA, MLB, NHL).
2. Finds the matching Kalshi game-winner market. The series are `KXNFLGAME`, `KXNCAAFGAME`, `KXNBAGAME`, `KXWNBAGAME`, `KXMLBGAME` and `KXNHLGAME`. A market only counts as a match if it has the same date and both teams.
3. Gets a "fair" win probability:
   - **NFL, NCAAF, NBA, WNBA, MLB:** ESPN's live win probability, taken from `summary?event=ID` → `winprobability`.
   - **NHL:** ESPN doesn't publish one, so the bot uses its own simple model. It treats goals as random (Poisson), uses the time left and the score, and gets team strength from the pre-game betting line. Because this model is cruder, its saved gap is 2 points higher than the other sports (8 points at the locked 6-point bar).
4. Works out the **gap**: fair probability − Kalshi YES ask − Kalshi taker fee. The fee is `ceil(0.07 × P × (1−P) × 100) / 100` per contract.
5. Makes a **paper buy** only if all of these are true:
   - the gap is **6 points or more** after the fee (8 for the NHL model). 6 points is the locked sports floor (0.06); it can be raised, never lowered.
   - the desk pace line (6–12 trades/hour) is **display only** — it does **not** waive the edge bar or the close-game filter (`edge_for_hour` keeps the saved min_edge).
   - the bid/ask spread is 5¢ or less
   - the price is between 5¢ and **92¢** (the 92¢ cap)
   - at most **4 buys per check**
   - games are watched from **3 hours** before the start (pre-game books)
   - fewer than 12 positions are open (the old cap was 3 in this script and 4 on the desk), and the bot doesn't already hold this game
   - there is enough paper cash
   - the paper learning log is not skipping that sport and probability bucket
   - open count and open risk stay inside desk caps after any sells this check
   - when started from the PIMP desk, the desk `entry_gate` is also clear (daily loss / max open / open risk)

   Trade size follows the model probability. Under 80% the paper stake is about **$20**. At 80% or higher it scales from **$20 to $100**. The fill buys enough contracts to land near that stake. It does not place a real order.
6. Each check **sells/settles first**, then paper-buys. Exits a paper position in one of two ways:
   - **Sells at the bid** once the gap has closed (the bid minus the fee is at or above fair value).
   - **Settles** when ESPN shows the game as final: $1 per contract if the team won, $0 if it lost.

Everything is written to:
- `paper_trades.md`: every check and every trade. Each row has the time (CT), the game, the score, the fair probability, the Kalshi bid/ask, the gap and the action taken.
- `state.json`: paper cash, open positions and closed positions with their profit or loss.

## Run it
```bash
python3 gap_bot.py          # one check
python3 gap_bot.py --reset  # start over at $100
```
During games, run it about every 5 minutes, using cron or a scheduled routine.

## Honest limits (please read)
- **Speed:** Kalshi prices move within seconds of a big play, and professional market makers react far faster than a bot that checks every few minutes. Many "gaps" are really just **stale data**: ESPN's number lags behind, or Kalshi has already priced in a play that ESPN hasn't shown yet.
- **ESPN's probability is a model, not the truth.** It doesn't know about injuries, momentum, or the fact that starters get rested in blowouts. When ESPN and the market disagree, the market is often the one that's right. The NHL model is even simpler.
- **Paper fills are optimistic.** The bot assumes it can buy at the shown ask and sell at the shown bid with unlimited size and no delay. Real fills would be worse.
- **Hype posts** like "$1,000 → $30,649" are unproven. You can't see the losing streaks, the luck or the cherry-picking behind them. Run this on paper for many games before believing any edge exists. Even then, past paper results don't guarantee anything.
- This is not financial advice. Check whether prediction markets are legal where you live before ever using real money.
