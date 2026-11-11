# Point spread

Paper shadow for `point-spread`. It logs and buys nothing.

The series is read from the public API. An open book is logged and nothing is bought. If the public API does not list the series, the card says so and the check skips. No ticker, fill, or fair price is invented. Stake stays 0. There is no desk risk share. Live orders stay off.

Point spread on the six leagues. The game-winner series are a different settle. Clears the sports floor 0.06 after the taker once a series exists. Spread cap is the game-winner cap when that cap is already in the repo.

## Run

```bash
python bot.py
python bot.py --reset
```
