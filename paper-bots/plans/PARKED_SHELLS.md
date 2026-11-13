# Parked shells and how each one wakes up (steps 926-940)

Five log-only shells live in the code but are not on the timer and not in the city. They are listed in `shadow_missing.PAUSED`. Each one buys nothing, holds no cash and keeps the sports floor 0.06. `test_shadow_missing.py` keeps them off the desk while paused.

A shell wakes only in this order, and every step needs the one before it:

1. A real market: the Kalshi series is listed on the public API, and its settle rule is written down.
2. A real fair price: a public, allowed data source exists. No invented prices.
3. Log-only for 2 weeks: fair vs price logged for every market, graded after fees in the what-if lab.
4. Positive logged rows: only then a $25 ticket, $500 practice book, shadow_only.
5. 50 settled results and Levi's OK before it counts anywhere.

Waking means removing the id from `shadow_missing.PAUSED`. That is Levi's call.

| Shell | Step 1: market | Step 2: fair source | Today |
|---|---|---|---|
| Player props | Confirm Kalshi lists player stat props for the six leagues (926) | A public player stats feed (926); fair model built log-only (927) | Blocked: no prop series on the public API, no allowed stats feed picked |
| Period winner | Confirm the period or half series and its rules (929) | Reuse the Sports gap win-probability model per period (930) | Blocked: series not confirmed |
| Champions League | Already in the Soccer & tennis lean league list | Polymarket moneyline through the lean engine (932); extra-time rule checked by the rule-match checker (933) | Waiting on the rule-match checker (A25) |
| Esports match | Kalshi esports series | A public odds source (935); lean engine (936) | Blocked: no public odds source found |
| Polymarket mentions | "Will X say Y" markets | Word counts from public transcripts, paired with the press-briefing words idea (938-939) | Blocked: no transcript feed picked |

Steps 928, 931, 934, 937 and 940 ("wake only after positive logged rows") are rules, not builds. They stay true because waking needs a code change to `PAUSED` and Levi's OK.
