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
tokens, (3) records a skip. A name that passes RugCheck and the confidence floor is still refused:
`conf − 0.5` is not a fee-aware edge, and new buys stay off while taxed expectancy is negative.
A midnight cash reload does not waive that refuse. Run it again whenever you like (every few
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
| `TICKET_USD` = 25 | Buy-in at 90% confidence and above. |
| `MIN_TICKET_USD` = 10 | Buy-in at 80% and on the speed lane. 85% is $17.50, linear in between. |
| `RED_DAY_TICKET_USD` = 10 | If today is red, the ticket ceiling stays $10. |
| `MAX_OPEN` = 6 | At most 6 positions when today is flat or green. |
| `MAX_OPEN_RED` = 1 | If today is red, at most 1 open position. |
| `MAX_ENTRIES_PER_DAY` = 8 | At most 8 buys per Chicago day. The residual refuse currently blocks all of them. |
| `DAILY_LOSS_HALT_USD` = 150 | If today's realized loss reaches $150, no new buys until tomorrow. |
| `RED_DAY_ENTRY_LOCK_USD` = 5 | If today is ≤ −$5, new entries are off. Exits still run. |
| `COOLDOWN_HOURS` = 12 | After fully exiting a token, don't buy it again for 12h. |
| `FACTS.max_risk_score` = 40 | RugCheck risk score (0-100, higher = riskier) must be ≤ 40. |
| `FACTS.min_lp_locked_pct` = 90 | Biggest pool's liquidity must be ≥ 90% locked or burned (so the dev can't pull it). |
| `FACTS.max_top10_pct` = 30 | Top 10 holders (excluding pools/lockers) hold ≤ 30% of supply. |
| `FACTS.max_dev_pct` = 5 | Creator wallet holds ≤ 5% of supply. |
| `FACTS.max_insiders` = 0 | Zero insider-flagged holders / insider-network wallets allowed. (Very strict: most tokens fail this.) |
| `FACTS.min_liquidity_usd` = 30000 | Pool must have ≥ $30k liquidity. Speed lane needs ≥ $50k. |
| `FACTS.max_ticket_share` = 0.01 | The ticket must be ≤ 1% of the pool. |
| `FACTS.min_age_min` / `max_age_hours` | Token must be 30 min – 72 h old. |
| `MIN_CONFIDENCE_ACCURATE` = 0.80 | Accurate lane. Speed lane starts at 0.72, and only when today is not red, the 5-minute change is ≥ 0, and liquidity is ≥ $50k. |
| `EXIT.stop_pct` = -12 | Down 12% from entry → sell everything. |
| `EXIT.ladder` | +100% → sell half; +200% → sell another quarter. |
| `EXIT.trail_pct` = 25 | After the first ladder sale, the rest sells if price drops 25% from its peak. |
| `EXIT.time_stop_hours` / `time_stop_min_pct` | Held 4h and not up 20% → sell (dead money). |
| `EXIT.liq_drop_pct` = 35 | Pool liquidity down 35% since entry → sell now (rug warning). |
| `EXIT.model_flip_momentum_h1_floor` = -6 | Price ≤ −6% from entry, and still above the hard stop → sell. The check uses the open position's price, not a fresh 1-hour momentum print. |
| `START_BANKROLL_USD` | Paper cash to start with ($100). |
| `PAPER_FILL.swap_fee_pct` | ~1% fee on each paper buy and sell (2% round trip). Slippage is estimated from the real pool size. DEX floor stays 0.02. |
| `SCORER` | The free rule-based scorer (replaces the paid Grok call): mixes 1h price momentum, 1h volume vs liquidity, liquidity size, and buys vs sells into a 0-1 confidence. That confidence is not a fee-aware edge. |
| `GROK_ENABLED` | Off. Grok's API is paid. If you ever turn it on (and set `XAI_API_KEY`), it can only veto a buy, never force one. |

To reset the paper account, delete `positions.json`, `trades.csv`, and `checks.csv` (they are created on the first run; none are shipped here).

This is practice software, not financial advice. Most meme coins go to zero.
