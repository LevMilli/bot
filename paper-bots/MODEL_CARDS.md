# Model cards

One card per 15-minute tower: what goes in, the math, and the known weak
spots. Review these once a month (plan step 457). Shared math lives in
`shared_models.py`; no tower uses it to trade yet.

## Model change rules

A model change reaches a tower only in this order (plan step 455):

1. Replay or forward-score it in the model lab (`model-lab-paper`) next to
   today's method, on the same windows. Lower Brier score wins.
2. It needs 50 settled windows before the lab gives a verdict.
3. If it wins, build it as a practice (shadow) twin with its own folder,
   $25 ticket, $500 sleeve and a locked floor that is never lower.
4. The twin needs 50 settled results of its own.
5. Levi reviews the numbers, losses included, and says yes or no. Nothing
   is promoted automatically. More 15m stays frozen.

## BTC 15m

- Inputs: Kalshi KXBTC15M / KXETH15M target (floor_strike), Coinbase spot,
  last-hour 1-minute closes, Deribit DVOL, order book, news calendar.
- Math: sigma in dollars for the time left = the larger of realized
  (sample stdev of last 60 1-minute log moves x price x sqrt(minutes)) and
  DVOL-implied; fair = N(cushion / sigma). Same as
  `shared_models.fair_up(mode="dollar")` (tested).
- Floor 0.05 (locked). Strict fill re-check on every buy.
- Known weak spots: normal tails understate sudden jumps; no time-of-day
  factor; no tape check (flag `FILL_BTC15M_TAPE`, off); CF Benchmarks
  60-second average at the close is not modelled.

## More 15m

- Inputs: Kalshi 15-minute up/down markets for SOL, XRP, DOGE, BNB, HYPE,
  S&P 500, EUR/USD, USD/JPY; Coinbase mid (Kraken backup) or Hyperliquid
  oracle; last-hour 1-minute candles.
- Math: fair = N(ln(level / open) / (sigma x sqrt(minutes - 0.67))), sigma
  the population stdev of last-hour 1-minute moves x multiplier (USD/JPY
  1.3), floored per asset; learned open offset for S&P and FX. Same as
  `shared_models.fair_up(mode="log")` (tested).
- Floor 0.05 (locked), tape check on, fee once per order. Fully frozen.
- Known weak spots: one-hour swing only; normal tails; coins move together
  (same-direction cap of 2 is the only guard); multipliers are hand-set.

## Commodity 15m

- Inputs: Kalshi 15-minute commodity markets (gold, silver, platinum,
  palladium, copper, WTI, Brent, natural gas), spot feed, order book.
- Math: sigma = spot x 0.0015 x sqrt(max(minutes, 1) / 15) (a fixed swing,
  not measured); fair = N(cushion / sigma). Same as
  `shared_models.fair_up(mode="dollar")` (tested).
- Floor 0.05 (locked). Strict fill re-check on every buy.
- Known weak spots: the swing is a fixed 0.15% for every metal and energy
  market; no realized volatility; no tape check (flag
  `FILL_COMMODITY_TAPE`, off).

## Shadow engine towers (weather, gas, crypto ladder, Nasdaq, S&P, and others)

- Each tower brings its own fair price; the engine does fee-aware entry,
  fixed ticket, trust cap, model-flip exit and settle backstop.
- Known weak spots: buys at the ask it read with no re-check (flag
  `FILL_SHADOW_STRICT`, off); early sales ignore the bid size (flag
  `FILL_SHADOW_SELL_DEPTH`, off).
