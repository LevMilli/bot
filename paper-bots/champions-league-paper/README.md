# Champions League

Paper shadow for `champions-league`. It logs and buys nothing.

The series is read from the public API. An open book is logged and nothing is bought. If the public API does not list the series, the card says so and the check skips. No ticker, fill, or fair price is invented. Stake stays 0. There is no desk risk share. Live orders stay off.

UEFA Champions League game winner. It is not a league in the six-sport book. Clears the sports floor 0.06 once a series exists. Buying the favorite is not a fill.

## Run

```bash
python bot.py
python bot.py --reset
```
