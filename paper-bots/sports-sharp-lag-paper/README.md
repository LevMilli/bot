# Sports Sharp Lag

Shadow paper tower for the money-machine plan: **sharp sportsbook fair → Kalshi ask lag**.

## Rule

1. With `ODDS_API_KEY` set, `odds_feed.py` reads Pinnacle moneylines from
   [The Odds API](https://the-odds-api.com/), removes the vig, and pairs each side with
   the open Kalshi game market (`KX*GAME`, pre-game only, same ET date, unique team match).
   Only leagues with a Kalshi game in the next 36h spend a credit. Refreshes are paced so
   the monthly credits last (`ODDS_REFRESH_MINUTES` floor 30, `ODDS_API_MIN_LEFT` 25).
   Without a key it falls back to `sharp_quotes.json` (`[{ "game", "sharp_fair", "ask" }, …]`).
2. Edge = `sharp_fair − ask − Kalshi fee` (`ceil(0.07·p·(1−p))` per contract).
3. Buy only if edge ≥ locked sports floor **0.06**.
4. Fixed $25 ticket in whole contracts from a $500 shadow sleeve. Max 1 open. No desk cash. Never LIVE.
5. Open rows settle from the Kalshi market result ($1 per contract on YES).

Empty quotes → `waiting on sharp book` (no invented fills). Desk entry gate still blocks buys.

## Run

```bash
python bot.py --harvest   # ESPN fair + Kalshi ask → sharp_quotes.json (opt-in)
python bot.py             # decide from sharp_quotes.json
python bot.py --reset
make -C .. living-sharp-lag-harvest
```

Incomplete fair/ask legs are skipped — never invented. Incubation: graduate only at n ≥ 50 fee-aware settles. Staff only. No auto-promote.
