# BTC 15m signal

Paper only. Pretend money. This tower places no real orders and holds no exchange keys.

BTC 15-minute paper account. A timer check can paper-buy. It places nothing.

- Tower id: `btc15m`
- Script: `btc15m_signal.py`
- Venue floor: `kalshi_btc15m` 0.05 (locked, never lower)
- Vault tower: it spends desk cash and has a tower risk share.

## Buy rules

- Track KXBTC15M + KXETH15M + KXBTCD ladder history each check
- Confident early (≥10m): BTC + ETH singles under the same fee-aware gates
- Volatile: hold + history; ≤5m fee-aware paper parlay (BTC+ETH legs)
- p ≥ ask + fee + venue kalshi_btc15m; model p ≥ 80%; brain journal
- BTC cushion ≥ $35 / ETH ≥ $1.50; z ≥ 0.60; ask 70–92¢; dual lane
- Kelly-lite stake; correlation + learning clear; desk open-risk cap
- Adapt: recognize vol → play safe; proven ≥80% record → play bigger
- History sweep: metals/energy 15m (palladium, natgas, copper, brent, WTI, silver…)

## Sell rules

- Take-profit: paper-sell when bid ≥ fill + 0.15 (cap 0.99)
- Model-flip: side flips or fair collapses by δ → paper sell at bid
- Else settle when Kalshi resolves yes/no

## Failsafes

- Desk entry_gate (daily loss / max open / open risk)
- Full signal checklist (no spot/σ → skip)
- News calendar fail-closed (unavailable = skip BUY)
- Correlation veto + starve; cash / max 12 opens / learning
- Pause file

The same rules are listed in the desk's BOT_PLANS in `pimp_desk.py`. If this page and the code ever disagree, the code wins and this page gets fixed.
