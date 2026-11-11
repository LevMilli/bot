# BTC options

Paper shadow for `btc-options`. It logs and buys nothing.

The series ticker is taken from the repo. If that name is not there, the log says the ticker is missing and the check skips. No ticker, fill, or fair price is invented. Stake stays 0. There is no desk risk share. Live orders stay off.

Listed BTC options, implied versus later realized. Does not trade KXBTC15M, KXETH15M, or KXBTCD. The BTC 0.05 floor is the binary lock, not an options commission. This tower does not sell options.

## Run

```bash
python bot.py
python bot.py --reset
```
