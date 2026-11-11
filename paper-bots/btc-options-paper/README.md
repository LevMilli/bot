# BTC options

Paper shadow for `btc-options`. It logs and buys nothing.

The series is read from the public API. An open book is logged and nothing is bought. If the public API does not list the series, the card says so and the check skips. No ticker, fill, or fair price is invented. Stake stays 0. There is no desk risk share. Live orders stay off.

Listed BTC options, implied versus later realized. Does not trade KXBTC15M, KXETH15M, or KXBTCD. The BTC 0.05 floor is the binary lock, not an options commission. This tower does not sell options.

## Run

```bash
python bot.py
python bot.py --reset
```
