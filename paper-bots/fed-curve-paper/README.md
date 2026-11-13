# Fed curve

Shadow twin of Fed Watch for Kalshi Fed decision markets (KXFEDDECISION), with a second, independent read. Paper only. It spends no desk cash.

## How it prices a market
- **Futures curve:** 30-day fed funds futures from Yahoo (ZQ contracts, rate = 100 - price), chained month by month the way CME FedWatch does it (`curve_model.py`). Meeting days come from the Kalshi markets. The expected move is split between the two nearest 25bp steps.
- **Polymarket:** the "Fed decision in ..." mid (`../fed-watch-paper/fed_feed.py`, read-only).
- **Fair = the lower of the two** for each side.

## When it buys
- Only the next two meetings (later ones stack the curve's error). Missing or stale futures (over 4 days), no Polymarket price, or a gap over 0.15 between the two reads → logged only.
- Edge = fair - Kalshi ask - Kalshi fee must be at least the locked economics floor **0.05** and no more than **0.15**.
- $25 fixed ticket from a $500 sleeve, max 2 open, one per meeting.

## Exits
- Model flip at the bid, or hold to the Kalshi result.

CME's own FedWatch page has no free public feed, so the curve is rebuilt from the futures prices. Fed Watch itself is not changed.
