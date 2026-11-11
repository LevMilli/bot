# Esports match

Paper shadow for `esports-match`. It logs and buys nothing.

The series ticker is taken from the repo. If that name is not there, the log says the ticker is missing and the check skips. No ticker, fill, or fair price is invented. Stake stays 0. There is no desk risk share. Live orders stay off.

Match winner in a titled esports league. It is not in the six-sport book. Clears the sports floor 0.06 once a series exists. Buying the favorite is not a fill.

## Run

```bash
python bot.py
python bot.py --reset
```
