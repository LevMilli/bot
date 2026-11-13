# UFC, golf & esports lean

Shadow paper tower for Kalshi UFC fights (KXUFCFIGHT), PGA Tour winners (KXPGATOUR) and esports matches (KXLOLGAME, KXCS2GAME, KXVALORANTGAME, KXDOTA2GAME). Paper only. It spends no desk cash.

## How it prices a market
- **Fair price:** Polymarket's mid for the same fighter, golfer or team (public Polymarket API, no key).
- **Fights and esports:** two-way markets matched by name (`../soccer-tennis-lean-paper/match_model.py`, read-only).
- **Golf:** each golfer's "win the tournament" market, matched by last name and first initial.

## When it buys
- Pre-event only: 10 minutes to 48 hours before start.
- Polymarket spread no wider than 3 cents and liquidity at least $5k.
- Edge = fair - Kalshi ask - Kalshi fee must be at least the locked sports floor **0.06** and no more than **0.15**.
- $25 fixed ticket from a $500 sleeve, max 6 open, one per event.

## Exits
- Model flip at the bid, or hold to the Kalshi result.

Model: `fge_model.py`. The parked esports-match shell is not changed.
