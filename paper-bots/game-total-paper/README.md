# Game total

Paper shadow for `game-total`. It logs and buys nothing.

The series is read from the public API. An open book is logged and nothing is bought. If the public API does not list the series, the card says so and the check skips. No ticker, fill, or fair price is invented. Stake stays 0. There is no desk risk share. Live orders stay off.

Game total on the six leagues. A total settles on the combined score. The game-winner series do not. Clears the sports floor 0.06 once a series exists.

## Run

```bash
python bot.py
python bot.py --reset
```
