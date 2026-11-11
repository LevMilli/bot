# Game total

Paper shadow for `game-total`. It logs and buys nothing.

The series ticker is taken from the repo. If that name is not there, the log says the ticker is missing and the check skips. No ticker, fill, or fair price is invented. Stake stays 0. There is no desk risk share. Live orders stay off.

Game total on the six leagues. A total settles on the combined score. The game-winner series do not. Clears the sports floor 0.06 once a series exists.

## Run

```bash
python bot.py
python bot.py --reset
```
