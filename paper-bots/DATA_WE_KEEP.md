# Data we keep and why

Pretend money only. These files exist so every idea can be tested on what the markets really did, before it ever touches a tower.

- **15-minute window recordings** (window history). The book, open price and result of every 15-minute window the towers trade, once a minute for the last 14 minutes. Why: More 15m, BTC 15m and Commodity 15m ideas can be replayed on real books instead of guesses. Kept 180 days, at most 300 MB.
- **Market snapshots.** Best prices of 23 daily series every 15 minutes. Why: price history for the daily towers. At most 150 MB.
- **Research logs** (every shadow tower). The fair, price, edge and reason for the best sides of each check, including every skip. Why: calibration and "what if" checks. About 4 MB per tower, one old copy kept.
- **Daily reports** (window history). Data gaps, calibration and skip reasons for the day. Why: a bad feed or a tower drifting off its own numbers shows up within a day. A tower is flagged when it is off by more than 5 points with 50 or more results. Kept 180 days.
- **Rule versions.** When each rule change went live. Why: results can be split before and after a change, so a change is judged on its own trades.
- **Trades.** Every paper trade, wins and losses alike. Losses always count in totals. Trade records are never filled in or edited after the fact.

What we never keep: keys, passwords, tokens, cookies, emails or account ids. A test checks every recording for them, and the shared saver removes anything that looks private.

Field meanings: `DATA_DICTIONARY.md`.
