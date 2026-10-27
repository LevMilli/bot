# memecoin-desk (PAPER ONLY)

A practice bot for Solana meme coins. It **never trades real money**: it has no wallet, no private
key, no seed phrase, and no way to sign a transaction. It pretends to buy ("paper fills") at the
**real current price** from free public APIs, so you can see how the rules would have done.

Live trading would need a Solana wallet and a signing key connected to a swap service. **We are not
connecting one.** If `PAPER` in `config.py` is set to `False`, the bot refuses to run.

## Run it once
```
cd memecoin-paper
python3 bot.py
```
Each run: (1) checks every open paper position against the exit rules, (2) scans new/trending Solana
tokens, (3) paper-buys anything that passes every check. Run it again whenever you like (every few
minutes is plenty; the free APIs have rate limits).

## Where the data comes from (free, no sign-up)
- **DexScreener**: token lists (latest profiles, latest boosts, top boosts), price, liquidity, pair age, volume, buys/sells.
- **RugCheck** `/v1/tokens/{mint}/report`: risk score, LP locked %, top holders, creator balance, insiders.
If any number is missing, that check **fails** and the token is skipped. Prices are never made up.

## Output files
- `checks.csv`: one row per token per run: every fact value, PASS/FAIL, confidence, decision, and why.
- `positions.json`: paper cash (starts at $100), open positions, cooldown list.
- `trades.csv`: every paper BUY/SELL with market price, estimated fill, fee, price impact, P&L.

## What each setting in config.py does
| Setting | Meaning |
|---|---|
| `PAPER` | Must be `True`. Fake fills only. |
| `TICKET_USD` = 25 | Every paper buy is $25. |
| `MAX_OPEN` = 4 | At most 4 positions open at once ($100 max in). |
| `MAX_ENTRIES_PER_DAY` = 6 | At most 6 buys per calendar day (Chicago time). |
| `DAILY_LOSS_HALT_USD` = 50 | If today's realized loss reaches $50, no new buys until tomorrow. |
| `COOLDOWN_HOURS` = 24 | After fully exiting a token, don't buy it again for 24h. |
| `FACTS.max_risk_score` = 40 | RugCheck risk score (0-100, higher = riskier) must be ≤ 40. |
| `FACTS.min_lp_locked_pct` = 90 | Biggest pool's liquidity must be ≥ 90% locked or burned (so the dev can't pull it). |
| `FACTS.max_top10_pct` = 30 | Top 10 holders (excluding pools/lockers) hold ≤ 30% of supply. |
| `FACTS.max_dev_pct` = 5 | Creator wallet holds ≤ 5% of supply. |
| `FACTS.max_insiders` = 0 | Zero insider-flagged holders / insider-network wallets allowed. (Very strict: most tokens fail this.) |
| `FACTS.min_liquidity_usd` = 30000 | Pool must have ≥ $30k liquidity. |
| `FACTS.max_ticket_share` = 0.01 | Your $25 must be ≤ 1% of the pool. |
| `FACTS.min_age_min` / `max_age_hours` | Token must be 30 min – 72 h old. |
| `MIN_CONFIDENCE` = 0.7 | Scorer's confidence (0-1) must be ≥ 0.7 to buy. |
| `EXIT.stop_pct` = -35 | Down 35% from entry → sell everything. |
| `EXIT.ladder` | +100% → sell half; +200% → sell another quarter. |
| `EXIT.trail_pct` = 30 | After the first ladder sale, the rest sells if price drops 30% from its peak. |
| `EXIT.time_stop_hours` / `time_stop_min_pct` | Held 6h and not up 20% → sell (dead money). |
| `EXIT.liq_drop_pct` = 40 | Pool liquidity down 40% since entry → sell now (rug warning). |
| `START_BANKROLL_USD` | Paper cash to start with ($100). |
| `PAPER_FILL.swap_fee_pct` | ~1% fee on each paper buy/sell. Slippage is estimated from the real pool size. |
| `SCORER` | The free rule-based scorer (replaces the paid Grok call): mixes 1h price momentum, 1h volume vs liquidity, liquidity size, and buys vs sells into a 0-1 confidence. |
| `GROK_ENABLED` | Off. Grok's API is paid. If you ever turn it on (and set `XAI_API_KEY`), it can only veto a buy, never force one. |

To reset the paper account, delete `positions.json`, `trades.csv`, and `checks.csv` (they are created on the first run; none are shipped here).

This is practice software, not financial advice. Most meme coins go to zero.
