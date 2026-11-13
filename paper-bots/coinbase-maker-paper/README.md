# Coinbase maker

Shadow twin of Coinbase spot that assumes limit orders at the maker fee. Paper only. No key, no orders sent. It spends no desk cash.

## Rules
- Same signal as Coinbase spot: ETH-USD and SOL-USD 15-minute candles, an up bar with z of at least 2, 25% capture haircut, locked floor **0.05**.
- Fees: 0.50% maker each side (US Coinbase Advanced intro schedule). Round trip 1.0% instead of 2.0%.
- Entry: limit buy at the signal close. It fills only if a later bar's low trades below it; cancelled after 2 bars.
- Take-profit: resting limit sell at entry + 6% (maker), fills only if a bar trades above it.
- Stop -1.5%, a z of -2 or lower, and the 24-hour stop are market sells at 0.90% taker plus 0.10% slippage. A bar that hits both stop and take-profit counts as the stop.
- No back-dated orders: only a signal bar that closed in the last 20 minutes places an order.
- $25 ticket from a $500 sleeve, one order or position at a time.

## Honest note
Even at the maker fee a 15-minute bar must move about 24% (instead of 28%) before a long clears the 0.05 floor. It will still almost never trade. The blocker is how the floor is measured on top of a 25% capture, not the fee.

Model: `maker_model.py`. Coinbase spot is not changed.
