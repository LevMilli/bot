# Strategy.md (Version 1, chosen Oct 26, 2026)
Market: Kalshi KXINXU (S&P 500 above/below), only the contract settling at 4 PM ET / 3 PM CT that day.

Entry: Once per trading day at 12:30 PM CT. Among all Yes and No sides whose ASK is 80-90c, buy the highest-priced one (the safest in the band). Fill at the ask plus fees.
Stake: up to $25 (floor(25 / ask) contracts).
Exit: Hold to settlement at 3 PM CT. No stop loss and no take profit.
Skip days: Fed decision days, CPI, jobs report, GDP/PCE, election day and the day after, market holidays and half days. Also skip if no contract is in the 80-90c band.
Risk: Max 1 trade per day, $50 daily loss limit, kill switch at a $400 paper bankroll (start $500).
Invalidation: If the S&P moves enough that the contract is under 50c, just log it. There is no action, because this version has no stop.
Mode: Paper only.
