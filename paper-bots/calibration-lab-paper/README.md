# Calibration lab

Research building on the Research helpers floor. It never buys and holds no cash.

## What it does

Every 6 hours it:

1. Lists Kalshi markets that settled in the last 14 days for families with a
   fixed close time: weather highs, gas weekly, BTC/ETH daily, Nasdaq and S&P.
   Sports are left out because a game's close time is not known ahead of time.
2. Reads each market's hourly price history and notes the standing bid and ask
   1, 3 and 6 hours before close.
3. Groups every side a buyer could have paid into 5¢ bands and counts how often
   it won. Each cell gets a Wilson 95% range and a cautious edge:
   `low end of win rate − average price − Kalshi fee`.
4. Scores each new tower's logged fair prices against the market asks on
   contracts that have settled (Brier score, lower is better).

The result is `calibration.json`. Other towers read it with
`calibration_lab.lookup(family, horizon_hours, price)`.

## Limits

- At most 25 price-history calls a run and 5 per family, so a busy family
  cannot starve the rest. The rest waits for the next run.
- Busy series (BTC/ETH daily) keep the newest 5,000 settled markets each.
- Markets with no price history are remembered so they are not fetched again.
- Rows older than 120 days are dropped.
- Public Kalshi data only, through the shared gateway.
