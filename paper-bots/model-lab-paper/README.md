# Model lab

Research building. Buys nothing, holds no cash, and no tower reads it to trade.

Every 5 minutes it reads Coinbase 1-minute candles and the open Kalshi
15-minute up-or-down markets for BTC, ETH, SOL, XRP and DOGE. For each window
with 1 to 14 minutes left it logs four fair prices:

- now: last-hour 1-minute move, normal tails (how More 15m prices today)
- blend: a 15/60/240-minute mix of the move
- student: same move, fatter tails
- tod: same move times a time-of-day factor

plus log-only inputs: a jump guard, top-of-book imbalance and whether BTC is
pulling the other coins the same way.

When a window settles it scores each method (Brier score; lower is better),
the error by minutes left, the real swing per market (a multiplier that may
move at most 0.15 a week, only after 50 windows), and three exit rules on the
logged price paths. A verdict needs 50 settled windows. Using any of it in a
tower is Levi's call.

Writes `model_lab.json`. Shared math lives in `paper-bots/shared_models.py`.
See `MODEL_CARDS.md` for each tower's model card and the change rules.
