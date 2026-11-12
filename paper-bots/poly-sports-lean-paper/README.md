# Poly sports lean

Shadow paper tower for Kalshi game-winner markets in the NBA, NFL and NHL (KXNBAGAME, KXNFLGAME, KXNHLGAME). Paper only. It spends no desk cash.

## How it prices a game
Polymarket's moneyline books for these leagues are deep and usually 1–2¢ wide, so their mid-price is a good outside read on who wins.

1. **Match:** a Polymarket game matches a Kalshi event when the Eastern date of the start time plus the two team codes in the slug (`nba-tor-phi-2026-11-12`) equal the Kalshi event code (`26NOV12TORPHI`). A few codes differ between the venues (for example Jacksonville `jax` → `JAC`, Montreal `mon` → `MTL`) and are mapped in `lean_model.py`.
2. **Fair value:** the Polymarket moneyline mid for that team. Polymarket's first outcome is the first team in the slug.
3. **Quality checks:** Polymarket spread at most 3¢ and liquidity at least $10k.

On the first live check, matched games sat within about 1¢ of each other, so this tower is built to buy rarely: only when Kalshi has not caught up with a move Polymarket already made.

## When it buys
- Pre-game only, from **48 hours** to **5 minutes** before start.
- Edge = fair − ask − Kalshi fee must be at least the locked sports floor **0.06**. An edge above **0.15** is logged but not bought.
- $25 fixed ticket from a $500 sleeve, max 4 open, one per game, one new buy per check.

## Exits
- **Model flip:** sell at the bid when bid − fee beats the fair by 2¢.
- **Otherwise:** hold to the Kalshi result.

Engine: `../kalshi_shadow_tower.py`. Matching: `lean_model.py`. Registry row: `../new_towers.py`.
