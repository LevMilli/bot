# Replay lab (the time machine)

Paper only. Read only. A replay never places an order, never writes to a tower's folder and never changes a tower's rules. It only writes a report. Turning any idea on stays Levi's call.

Code: `replay_lab.py`. Tests: `test_replay_lab.py`. Fixture day: `fixtures/replay/`.

## What it replays

| Tower | Recorded prices | How |
|---|---|---|
| More 15m, Crypto ladder, Nasdaq, Weather high and every other tower on the shared engine | each check's `research.jsonl` rows (fair, ask, bid per side) | fed back into the same `kalshi_shadow_tower.run_tower` the live tower uses, in a throwaway folder |
| BTC 15m, Commodity 15m | the window snapshots and settled results in `kalshi_crypto_history.json` | re-checks the rules a snapshot can show (time left, ask band, chance floor, edge after fee) and keeps every other recorded block (spread, depth, news, cushion, candles) as the live check saw it |

Fill rules are the live ones: fee once per order, the Kalshi tape check, the trust cap, max open and extra slots, one buy per check, the same-direction cap and the model-flip exit. A row that was never tape-checked live counts as "no tape" (cautious). A check where the desk gate was closed stays closed. A market with no known result stays open and is listed as unsettled. It is never guessed.

For BTC 15m and Commodity 15m the held-side bid is read from the other side's ask (yes bid = 1 - no ask). The replay holds to the result, plus a take profit when one is set. It does not copy those towers' other exits, so expect a gap against live. The replay-vs-live report shows that gap every day.

## Commands

```
make replay-more15m            # today's rules on every recorded day, plus the replay-vs-live gap
make replay-btc15m
make replay-commodity
make replay-idea IDEA=btc15m-tp-10
python3 replay_lab.py more-15m --set take_profit=0.2
```

Recorded days live on the desk volume, so run these on the desk (or on a copy of its folders). Each run is saved with its settings to `replay-runs/replay_runs.jsonl`.

## Named ideas (one rule each)

| Idea | Change |
|---|---|
| more15m-bar-under-20c | asks under 20 cents need edge 0.10 |
| more15m-tp-10 / -20 / -30 | take profit at ask + 10, 20 or 30 cents |
| commodity-cap-85 | no buy above 85 cents |
| commodity-extra-edge-85 | 3 cents more edge above 85 cents |
| btc15m-5min | buys allowed down to 5 minutes left (today: 10) |
| btc15m-tp-10 / -20 | take profit at +10 or +20 cents (today: +15) |

A what-if can raise a bar. It can never take the edge under a locked floor.

## Rules for reading a replay

1. Replay each idea on at least 7 days before it gets a practice twin.
2. Split the days: the earlier 60% are "tune" days, the later 40% are "check" days. Report results only on check days.
3. Show a cautious low end, not just the average. The low end is a block bootstrap of daily P&L, so streaky days are resampled together.
4. Count every variant tried on a tower. Each one makes the low end stricter (the 5% bar is split across all of them).
5. Never pick the best of 20 variants without a fresh test period. After 20 variants the report says so, and the winner needs new days it has never seen.
6. Losses always count. Unsettled trades are listed, never guessed.
7. Keep the full test suite green before every merge.

## Report template

```
Replay: <tower>
Rule change: <one rule, or none>
Days replayed: N. Tune days: T. Check days: C.
On check days only: X trades, W won, L lost, total $P.
Cautious low end per day: $L (variants tried: K).
Still open with no result: U (not guessed).
Verdict: worth a practice twin / not proven / not enough days.
Replay vs live: D days compared, B outside the tolerance.
Paper only. A replay suggests; changing a tower stays Levi's call.
```

## Other tests in this set

- `test_model_edges.py`: fair price math, zero time, zero volatility, missing price, the normal helper at extremes, sigma floors, basis learning (3 opens), trust cap at exactly 0.20, the 70 and 92 cent ask band, spread and depth at exactly the limit, the 30-minute news window, candles toward the target.
- `test_model_properties.py`: edge never rises when the fee rises, fair stays between 0 and 1, a ticket never spends more than the cash, open positions never pass the cap.
- `test_chaos_replay.py` (`make replay-chaos`, weekly): garbage data, timeouts, Kalshi 429 for a minute, disk full, clock jumps, overlapping passes.
- `test_city_snapshot.py`: every tower card has its fields, closed towers black with dark windows, quiet practice towers hidden, the vault's three lines, the offline banner on the fixture, and the versioned snapshot schema (`snapshot_schema.py`).
