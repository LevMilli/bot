# Polymarket mentions

Paper shadow for `polymarket-mentions`. It logs and buys nothing.

The series is read from the public API. An open book is logged and nothing is bought. If the public API does not list the series, the card says so and the check skips. No ticker, fill, or fair price is invented. Stake stays 0. There is no desk risk share. Live orders stay off.

Mention contracts on Polymarket only. No mentions key was added under the locked floors. The taker coefficient is the mentions rate already in the repo. A logged edge would still have to clear 0.05. This tower does not buy a phrase.

## Run

```bash
python bot.py
python bot.py --reset
```
