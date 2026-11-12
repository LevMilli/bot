# Scorekeeper

Support building on the Risk & Compliance floor. It buys nothing, holds no cash, and only suggests.

## What it does
Every 6 hours it grades each trading bot on its whole paper record and writes `scorecard.json`.

- P&L per closed trade is after fees and after the desk's fill tax (1 cent a contract, for fills that would be a bit worse in real life).
- A bot needs at least **50 closed trades** to get a grade. Under that it shows "too few".
- With 50+, it takes a 95% range for the average trade (average ± 1.96 × spread ÷ √trades):

| Grade | Meaning |
|---|---|
| promote | even the low end of the range is above $0 |
| keep | the average is above $0, but the low end is not yet |
| pause | the average is $0 or worse, but it could still be positive |
| retire | even the high end is below $0: clearly losing |

## Details
- Research buildings (calibration lab, auditor, itself) are not graded.
- No network reads. It only reads the desk's own state files, through the same views the dashboard uses.
- It never pauses, funds or edits a bot. You decide.

Model: `score_model.py`. Registry row: `../new_towers.py`.
