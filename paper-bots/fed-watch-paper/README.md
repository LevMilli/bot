# Fed Watch (shadow)

Polymarket "Fed Decision in <month>?" odds vs the Kalshi `KXFEDDECISION` ask on the
same FOMC meeting and outcome (hike 50+, hike 25, hold, cut 25, cut 50+).

- **Fair:** Polymarket mid of best bid/ask. Skipped when the spread is over
  `FED_PM_MAX_SPREAD` (default 0.04).
- **Both sides:** YES uses fair vs Kalshi YES ask; NO uses 1 − fair vs Kalshi NO ask.
- **Floor:** locked `kalshi_econ` **0.05** (never soften).
- **Edge:** `fair − ask − Kalshi fee ≥ 0.05`. Biggest edge is bought first.
- **Ticket:** $25 in whole contracts. Max 1 open. Settles from the Kalshi result.
- **Feed:** `fed_feed.py`, public Kalshi + Polymarket gamma APIs, no keys. A failed read
  falls back to `fedwatch_quotes.json`; no matching meeting → wait. **No invent.**
- **Paper / shadow only.** No desk cash. No `tower_risk_budgets` share.
- **Idea-bank:** `KXFED` / rates stay idea-bank for main AUTO — research sleeve only.

## Run

```bash
python bot.py
python bot.py --reset
```

Incubation: n ≥ 50 fee-aware settles before any staff review. No auto-promote. Main AUTO stays refused for econ series.
