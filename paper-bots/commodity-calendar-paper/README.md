# Commodity calendar

Paper shadow for `commodity-calendar`. It logs and buys nothing.

The series is read from the public API. An open book is logged and nothing is bought. If the public API does not list the series, the card says so and the check skips. No ticker, fill, or fair price is invented. Stake stays 0. There is no desk risk share. Live orders stay off.

Listed calendar in WTI or gold. CL=F and GC=F are 15-minute spot inputs, not this spread. The commodity 0.05 floor is a binary lock and is not a futures commission. This tower does not inherit the 15-minute stake ladder.

## Run

```bash
python bot.py
python bot.py --reset
```
