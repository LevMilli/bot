# Exclusive set

Same-venue shadow logger. It reads mutually exclusive Kalshi legs of one event and buys nothing.

## Rule

1. Group the public book by event. One venue. One set.
2. Every leg needs a public yes ask. A missing ask skips the basket. Nothing is invented.
3. Cost of a leg is the ask plus the Kalshi taker, `ceil(0.07 · p · (1 − p))` per contract.
4. The basket is interesting only when `1 − sum(cost)` clears the floor.
   - Sports set: **0.06** (the locked sports floor).
   - Any other Kalshi set: **0.05**.
5. The INX floor of 0.02 is not this tower's floor. `KXINXU` is refused.
6. A logged basket is not a position. Stake stays 0. There is no desk risk share.

The three baskets in `dutch_book_observe` stay examples. They are not read and they do not count as evidence. A check logs the public mutually exclusive baskets it actually reads, including a basket that is only the house edge, and names that event on the card. A future paper buy is not in this tower. It would wait for 30 settled public sets with taxed EV at least 0, then incubation n ≥ 50 before any desk share. Live orders stay off.

## Run

```bash
python bot.py           # public sports series, plus exclusive_book.json if present
python bot.py --reset
```

`exclusive_book.json` may list extra series to fetch, or public market rows. A file marked `dutch_book_observe` or `example` is ignored. Empty book → wait. No invented asks.
