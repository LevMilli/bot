# Gas weekly

Shadow paper tower for Kalshi "US gas price this week" (KXAAAGASW). Paper only. It spends no desk cash.

## How it prices a strike
Each market asks: will the AAA national average for regular gas be strictly greater than $X on the settle date? Kalshi uses the price AAA shows that day at gasprices.aaa.com.

1. **Read AAA:** today's, yesterday's and a week ago's national average, plus the "price as of" date. Read at most once an hour, since AAA only updates once a day (early morning ET).
2. **Today's move:** half yesterday-to-today change, half the week's average daily change.
3. **Fading momentum:** each day ahead keeps `phi` of the day before's move. `phi` starts at 0.9.
4. **Spread:** day-to-day noise grows with the square root of days left, plus 35% of the projected drift, because the fade speed is a guess.
5. **Fair value:** the chance a normal with that mean and spread lands above the strike.

## Learning
Every AAA reading is saved to `aaa_history.json` (one price per day). Once it has 21 days of day-to-day changes, the tower fits `phi` and the noise from its own history (phi held to 0.3–0.98, noise to 0.3–3¢).

## When it buys
- Until the model is fitted, it buys only **within 1 day of settlement**, when the momentum guess barely matters. Earlier strikes are priced and logged to `research.jsonl` for scoring, but not bought.
- Edge = fair − ask − Kalshi fee must be at least the locked econ floor **0.05**. An edge above **0.25** is logged but not bought.
- $25 fixed ticket from a $500 sleeve, max 2 open, one per week, one new buy per check.

## Exits
- **Model flip:** sell at the bid when bid − fee beats the model fair by 2¢.
- **Otherwise:** hold to the Kalshi result.

Engine: `../kalshi_shadow_tower.py`. Model: `gas_model.py`. Registry row: `../new_towers.py`.
