# Fill-realism lab

Research building. Buys nothing, holds no cash, changes no tower.

Every hour it takes each tower's Kalshi buys (open and closed, wins and losses)
and reads Kalshi's public trades around the moment of the buy, once per buy:

- Tape cover: did real trading at our price or better, in the five minutes
  before the buy, cover our whole contract count? A buy that was not covered is
  one a tape check would have blocked.
- Tape gap: our price minus the average real trade price in the same minute.
  A tower whose fills beat the tape on average is flagged.
- Early sales: our exit bid against real trades near the sale.
- Maker practice book: would a resting bid one cent under our ask have been
  filled by trades that went through it? Kept apart; never added to a tower.
- Coinbase spot and QQQ: our fill against the next 1-minute bar's open.
- No-fills in the last day per shadow tower, by plain reason.

Writes `fill_realism.json`. All settings live in `paper-bots/fill_realism.py`.
At most 40 Kalshi reads and 10 candle reads a run.
