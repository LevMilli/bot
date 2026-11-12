# Favorite harvest

Shadow paper tower. Spends no desk cash.

## Idea

Heavy favorites (88–94¢) close to a scheduled close often win a bit more often
than their price says. This tower only buys when settled history shows that,
with a safety margin.

## How it prices

- Families: weather highs, gas weekly, BTC/ETH daily, Nasdaq and S&P.
- Only sides priced 88–94¢, about 1, 3 or 6 hours before close
  (0.5–1.5 h, 2–4 h, 5–7 h).
- Fair = the low end of the Wilson 95% range of how often sides in that 5¢ band
  actually won, from `calibration-lab-paper/calibration.json`.
- Edge = fair − ask − Kalshi fee. Buy only if edge ≥ 0.05 (locked) and ≤ 0.10.

## Waiting rules

- No cell yet, or fewer than 50 settled sides in it: logs only.
- Calibration table missing or more than 48 hours old: no buys.

## Money and exits

- $25 fixed ticket from a $500 paper sleeve, max 3 open, one per event.
- Model flip: sells at the bid when bid − fee beats the fair by 2¢.
- Otherwise holds to the Kalshi result.
