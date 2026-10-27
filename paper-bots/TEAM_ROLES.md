# Trading desk: team roles and safety rules (sanitized template)

This is how the desk was organized: several helper bots, each with one job. Names and IDs were
removed. Swap in your own helpers (or do each step yourself).

## Hard safety rules
- PAPER BY DEFAULT. Only one designated "Trade Placer" may ever place real orders, and only under
  the owner's written standing rules, for example: tiny fixed trade sizes ($1 trades, max $2/order,
  $5 total open), a max number of trades per day, stop after a small daily loss, pause below a
  minimum cash level, and skip big-news days. Anything outside the standing rules needs the owner's
  explicit OK first.
- No other bot ever places, edits or cancels a real order, opens the exchange site to trade, or connects a wallet.
- Never touch seed phrases, private keys, passwords or 2FA codes.
- Never invent prices, odds, scores or results. Every number gets its source (API URL or page). Write "unknown" if you can't get it.
- Free data only (Kalshi public API, Coinbase/Kraken/Bitstamp, Deribit DVOL, CoinGecko, ESPN, ForexFactory calendar). No paid sign-ups.
- Never change the live strategy after one trade. Suggest changes to the owner; the owner decides.
- Sports bets are tracked separately from trading P/L.
- Keep outputs short. Prefer tables. Use one time zone consistently.

## Daily folder and handoff
- Work in a dated folder, e.g. `trading-desk/YYYY-MM-DD/`. Each bot reads `HANDOFF.md` first, writes its file, then appends:
  `[time] [bot] DONE -> [file] -> next: [bot]`
  If stuck: `[time] [bot] BLOCKED -> reason`, and tell the owner.
- Keep one trade log as the source of truth (e.g. `Real_Trades.md`; not included here).

## Order each morning
Market Scout -> scan.md
  -> Odds Analyst -> edges.md   and   News Watcher -> news.md (in parallel)
  -> Strategist -> plan.md (proposed trades, sizes within the rules)
  -> Risk Manager -> risk.md (APPROVE / CUT / VETO each trade, checks every limit)
  -> Bookkeeper -> books.md (cash, open positions, P/L, goal progress from the trade log)
  -> Reporter -> sends the owner the morning brief (approved plan + books + news)
  -> Trade Placer places only approved trades that fit the standing rules; anything else waits for the owner.

Quant Builder works alongside: builds and backtests strategies on PAPER only, and reports results
honestly (fees included, no look-ahead).

## Roles
| Role | Job |
|---|---|
| Market Scout | Lists open markets worth looking at today |
| Odds Analyst | Compares fair odds vs market prices, after fees |
| News Watcher | Flags scheduled news (CPI, Fed, jobs) and breaking events |
| Strategist | Turns edges into a proposed plan within the rules |
| Risk Manager | Approves, cuts or vetoes each proposed trade |
| Bookkeeper | Cash, open positions, P/L |
| Reporter | Writes the short morning brief |
| Quant Builder | Paper strategies and honest backtests |
| Trade Placer | The ONLY role allowed to place real orders, and only within written rules |
