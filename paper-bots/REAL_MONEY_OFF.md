# How real money stays off

This desk trades pretend money only. Here is what keeps it that way, in plain words.

1. No order code. No file in paper-bots imports an exchange trading library, calls an order
   endpoint, or signs a request with an exchange key. A test (`test_plan_safety.py`) scans
   every file and fails the build if one ever shows up.
2. No live switch. `pimp_desk.LIVE_SWITCH_BUILT` is `False`. There is no button or setting
   that turns on real orders. Every tower config says `paper_only: true` and
   `live_orders: false`, and a test fails if any of them changes.
3. Public reads only. Towers read public prices (Kalshi, Coinbase candles, DexScreener and
   others) with no login. Every fill is a pretend fill at the ask that was read.
4. No keys handed to towers. The desk starts each tower with a short list of allowed
   variables (`_ENV_KEEP` in `pimp_desk.py`) and sets `PAPER_ONLY=1`. Exchange keys are never
   passed down, even if one is set on the host.
5. Key names are flagged. At startup the desk logs, by name only, any set variable that looks
   like an exchange or wallet key. The value is never read or printed.
6. Locked floors. The edge floors below can be raised but never lowered. The desk logs them
   in one line at startup and refuses to start if one is missing or lower.

| Venue | Locked floor |
| --- | --- |
| kalshi_sports | 0.06 |
| kalshi_btc15m | 0.05 |
| kalshi_commodity15m | 0.05 |
| kalshi_inx | 0.02 |
| solana_dex | 0.02 |
| coinbase_spot | 0.05 |
| binance_btc_carry | 0.02 (retired tower; lock kept) |
| coinbase_btc_carry | 0.02 |
| kalshi_econ | 0.05 |
| equity_qqq | 0.02 |

7. Desk limits that stay put: daily loss stop $150, max open risk $100, max 12 open,
   stakes $20 or less under 80% confidence, Kelly 0.25 or lower, quiet hours 10 PM to 7 AM CT.
8. No secrets in the repo. A test scans every tracked file for text that looks like an API
   key, token, webhook or private key, and fails if it finds one. It reports only the kind
   of secret and the file, never the text.

## Allowed variables

These are the variable names the code reads. None of them is an exchange trading key.

- Desk service: `PORT`, `DESK_SERVICE_HOST`, `DESK_SERVICE_URL`, `DESK_SERVICE_KEY` (private desk API key, not an exchange key), `PAPER_TIMER`
- Data and storage: `PAPER_DATA_DIR`, `PAPER_BACKUP_DIR`, `PAPER_KEEP_SETTLEMENTS`, `KALSHI_GATEWAY_DIR`, `KALSHI_TAPE_BUDGET_SEC`, `PUBLIC_HTTP_GAP_SECONDS`
- Notes to Discord: `PAPER_RECAP_WEBHOOK`, `PAPER_AUDIT_WEBHOOK`
- Pretend fill settings: `PAPER_STRICT_FILL`, `PAPER_COINBASE_MAX_SLIP`, `PAPER_MEME_MAX_SLIP`, `FED_PM_MAX_SPREAD`
- Set by the desk for each tower run: `PAPER_ONLY`, `DESK_BLOCK_ENTRIES`, `DESK_BLOCK_REASON`, `DESK_SHADOW`, `DESK_SHADOW_ID`, `DESK_SHADOW_ACCOUNT`, `DESK_SHADOW_VENUE_EDGE`
- Read-only data keys: `ODDS_API_KEY`, `ODDS_API_BOOKMAKER` (sports odds), `XAI_API_KEY` (memecoin notes)

Names the code only checks for so it can refuse or strip them: `KALSHI_API_KEY`,
`COINBASE_API_KEY`, `COINBASE_API_SECRET`, `COINBASE_API_SECRET_KEY`, `WALLET_SECRET`.
These should not be set.
