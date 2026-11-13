# Speed runbook

Pretend money only. Speed work makes each check faster or cheaper. It never changes what a tower decides.

## The one rule
Never trade speed for a lower edge bar. A slow tower is made faster by reading less or reading smarter, never by skipping a check that guards the edge, never by loosening a floor, and never by using an older price than the tower would have read on its own. Any change that could alter a tower's inputs is built behind a flag that is off by default and goes to Levi first.

## What is measured
- Start-to-decision time of every check, per tower: the desk times each run from the moment the script starts to the moment it exits with its decision. The last 120 times per tower live in `run_speed.json` (kept on the /data volume). Settle runs are not counted as checks.
- Kalshi gateway wait per tower: how long each tower waited for its turn at the shared Kalshi door (reads, total wait, longest wait).
- Both show on the boss dashboard under "Speed against targets", slowest tower first, and in the snapshot as `speed`.

## Targets
| Group | Median target |
|---|---|
| 15-minute towers (BTC 15m, Commodity 15m, More 15m) | under 20 seconds |
| Sports towers | under 45 seconds |
| Everything else | under 60 seconds (soft line) |

## Monthly review
1. Open the boss dashboard, "Speed against targets". The first row is the slowest tower against its target.
2. If it is over target, look at its Kalshi wait. A high wait means the shared door is crowded: move research reads away from it first. A low wait means the time is inside the tower: find its slowest read.
3. Fix only the slowest tower that month. Write the change up as a proposal if it touches a tower's reads.
4. Before any speed change merges, `test_speed_same_decisions.py` must pass: it runs More 15m on the same inputs with and without the speed pieces and checks the paper account, the research log and the printed decision are identical.

## Already in place
- Commodity 15m and BTC 15m fetch order books in parallel (`desk_more.prefetch_map`).
- The shared Kalshi gateway: one pace, one back-off and a 10-second cache, so two towers reading one book cost one request.
- The calendar is cached for 15 minutes (`helpers/calendar_cache.py`).
- The engine runs cheap rules before the one expensive read: the Kalshi tape is read only for a side that already cleared the floor and every other rule, at most 3 a check.
- The snapshot response is gzip-compressed when the browser accepts it.
- The plaza view loads no bloom pass; a test keeps it that way.

## Proposals waiting for Levi (they change tower inputs, so they are not switched on)
- Share one spot price per pass between towers (BTC 15m and Crypto ladder, More 15m and Coinbase spot, Hyperliquid reads between Commodity 15m and More 15m).
- Cache DVOL for 60 seconds in BTC 15m.
- Shorter read timeouts in the existing towers.
