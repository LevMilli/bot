# Rule changes and Levi's decisions

Every change to a money, risk or city-look rule gets one line here: the date, what changed,
why, and the replay or logged result behind it. Newest first.

## Decisions Levi has made (follow these)

- Real money stays off.
- Locked edge floors never go lower: kalshi_sports 0.06, kalshi_btc15m 0.05,
  kalshi_commodity15m 0.05, kalshi_inx 0.02, solana_dex 0.02, coinbase_spot 0.05,
  binance_btc_carry 0.02, kalshi_econ 0.05, equity_qqq 0.02.
- Existing towers keep their trading behavior. New ideas go in as a shadow twin or behind a
  flag that is off by default.
- More 15m is frozen.
- Shadow towers: shadow only, $25 ticket, $500 sleeve, reuse a locked floor. They count after
  50 settled results. Promotion still needs Levi's OK.
- Favorite harvest stays off until its cells have 50 past results.
- Losses always count in totals. No filter hides a loss.
- City look: towers, not television. Closed towers stay black. Shadow buildings stay hidden
  until they trade.
- Clean PRs with every test passing may be merged. A PR with a failing test is never merged.
- Plain words in every message to Levi.

## Change log

| Date | Change | Why | Evidence |
| --- | --- | --- | --- |
| 2026-11-13 | Added safety locks: startup floor check and log line, locked-limit tests, repo secret scan, 50-results check, promotion card | Plan steps 1-98 and 941-980 | Tests only. No tower trades differently |
