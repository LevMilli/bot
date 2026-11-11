# Period winner

Paper shadow for `period-winner`. It logs and buys nothing.

The series is read from the public API. An open book is logged and nothing is bought. If the public API does not list the series, the card says so and the check skips. No ticker, fill, or fair price is invented. Stake stays 0. There is no desk risk share. Live orders stay off.

First-half or period winner, not the full game. A full-game win probability is not this fair. Clears the sports floor 0.06 once a series exists.

## Run

```bash
python bot.py
python bot.py --reset
```
