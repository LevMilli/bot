# 10-year Treasury

Shadow paper tower for Kalshi's daily 10-year Treasury markets (KXUST10A): "Will the 10-year par yield be above X% today?" Kalshi settles on the Treasury Department's official daily par yield (two decimals). Paper only. It spends no desk cash.

## How it prices a market
1. **Level:** the live 10-year yield from Cboe's ^TNX index.
2. **Gap to the official number:** ^TNX and the Treasury's par yield usually differ by about one basis point. The tower measures that gap over the last 60 trading days and adds it as extra uncertainty.
3. **How far it can still move:** the typical daily change in the official 10-year yield over the last 60 days, scaled to the minutes left until 3:30pm ET.
4. **Rounding:** "above 5.18%" needs a printed 5.19% or more.

## When it buys
- Only on the settlement day, from 9:00 ET to 15 minutes before 3:30pm ET, and only when the yield quote is under 10 minutes old (so no holiday trades).
- Edge = fair − ask − Kalshi fee must be at least the locked econ floor **0.05**. An edge above **0.15** is logged but not bought.
- $25 fixed ticket from a $500 sleeve, max 2 open, one per event, one new buy per check.

## Exits
- **Model flip:** sell at the bid when bid − fee beats the model fair by 2¢.
- **Otherwise:** hold to the Kalshi result.

Engine: `../kalshi_shadow_tower.py`. Model: `ust_model.py`. Registry row: `../new_towers.py`.
