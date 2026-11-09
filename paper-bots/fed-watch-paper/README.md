# Fed Watch (shadow)

CME FedWatch implied probability vs Kalshi Fed / rates ask.

- **Floor:** locked `kalshi_econ` **0.05** (never soften).
- **Edge:** `fedwatch_fair − ask − Kalshi fee ≥ 0.05`.
- **Quotes:** `fedwatch_quotes.json` or injected bins. Empty → wait. **No invent.**
- **Paper / shadow only.** No desk cash. No `tower_risk_budgets` share.
- **Idea-bank:** `KXFED` / rates stay idea-bank for main AUTO — research sleeve only. Staff graduate refused by incubation rules.

## Run

```bash
python bot.py
python bot.py --reset
make -C .. living-macro-harvest       # public Kalshi Fed/CPI asks → bins (fair stays null)
make -C .. living-fed-watch-harvest   # staff CLI when bins + FedWatch fair are available
```

`living-macro-harvest` writes Kalshi asks only. `fedwatch_fair` stays null until CME FedWatch is staff-dropped — never invent. Main AUTO stays idea-bank for econ.

Incubation: n ≥ 50 fee-aware settles before any staff review. No auto-promote. Main AUTO stays refused for econ series.
