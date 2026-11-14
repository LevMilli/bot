# Rule changes and Levi's decisions

Every change to a money, risk or city-look rule gets one line here: the date, what changed,
why, and the replay or logged result behind it. Newest first.

## Decisions Levi has made (follow these)

- Real money stays off.
- Locked edge floors never go lower: kalshi_sports 0.06, kalshi_btc15m 0.05,
  kalshi_commodity15m 0.05, kalshi_inx 0.02, solana_dex 0.02, coinbase_spot 0.05,
  binance_btc_carry 0.02, coinbase_btc_carry 0.02, kalshi_econ 0.05, equity_qqq 0.02.
- Existing towers keep their trading behavior. New ideas go in as a shadow twin or behind a
  flag that is off by default.
- More 15m is frozen, except the early-sale price re-read Levi approved on Nov 13.
- More 15m keeps practicing. No promotion (Levi, Nov 13).
- Crypto ladder keeps practicing for 50 more results, then Levi decides (Nov 13; it had 66
  settled results that day, so the decision comes at 116).
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
| 2026-11-13 | Fix-now and decisions PR: meme price check gets its paper-only settings; the shared decision journal uses a lock and a unique temp file (Coinbase spot save errors); More 15m and its two twins re-read the bid 3 seconds after each early-sale decision and book the lower bid, and every buy records when its prices were read; 77 new series added to market snapshots and 5 new calibration families; Kalshi fee charged once per order on BTC 15m and Commodity 15m buys and sells (Kalshi S&P and Sized Kalshi already did); Weather high time limit 75s to 150s | Nov 13 evening report: meme price check refused 19 times, 2 Coinbase spot save errors, fill lab found 258 of 520 More 15m buys had no real trading at our price, 65 weather-high timeouts | Tests for each change. Sale decisions and edge checks are unchanged; only the booked sale price can get worse, never better |
| 2026-11-13 | Added safety locks: startup floor check and log line, locked-limit tests, repo secret scan, 50-results check, promotion card | Plan steps 1-98 and 941-980 | Tests only. No tower trades differently |

## 2026-11-14 - BTC carry moves from Binance to Coinbase

Levi asked to move BTC carry to a venue he can actually use, laid out like a
real wallet. Binance does not serve US residents and Binance.US has no perps.

- New venue key `coinbase_btc_carry`, locked at 0.02 (same number as the old
  lock). `binance_btc_carry` 0.02 stays in the locked table; nothing uses it now.
- Real US retail fees: spot taker 0.90% each side, perp 0.05% (min $0.20) per
  contract per side, liquidation 0.80%. Round trip is about 1.9%, not 0.30%.
- Book is $1,500 so one real contract (0.01 BTC) plus margin fits. One result
  per daily 5 PM ET settle. The count starts at 0.
- The Binance book is archived as it was in `paper_account.binance-retired.json`.
