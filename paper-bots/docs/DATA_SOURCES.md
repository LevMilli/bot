# Outside data sources

Every outside source the desk reads, who uses it, and how the desk keeps its
request rate low. All reads are public, read-only market or news data. The desk
places no real orders anywhere.

Review this file and each source's terms of use once a quarter (first Friday of
January, April, July and October). Check the terms page, the published rate
limit, and whether the desk still uses the source. Write the date here.

Last reviewed: 2026-11-13 (file created; terms and published limits not yet
checked one by one; see "Open items").

| Source | Host | Used by | Rate control today |
| --- | --- | --- | --- |
| Kalshi public markets | api.elections.kalshi.com | most Kalshi towers, strict fills, settlement, tape | Shared gateway (`kalshi_gateway.py`): one pace for every tower (8 reads per second by default, `KALSHI_READS_PER_SEC`), shared back-off on 429 that follows Retry-After, short shared cache |
| Coinbase Exchange | api.exchange.coinbase.com, api.coinbase.com | BTC 15m signal, More 15m, crypto ladder, Coinbase spot, exchange check | Read on the tower's own timer; no shared counter yet |
| Kraken | api.kraken.com, futures.kraken.com | BTC 15m signal, More 15m, exchange check | Read on the tower's own timer; no shared counter yet |
| Bitstamp | www.bitstamp.net | BTC 15m signal, exchange check | Read on the tower's own timer; no shared counter yet |
| Deribit | www.deribit.com | BTC 15m signal, crypto ladder, funding and volatility helpers | Read on the tower's own timer; no shared counter yet |
| Hyperliquid | api.hyperliquid.xyz | Commodity 15m, More 15m | Read on the tower's own timer; no shared counter yet |
| Binance public data | data.binance.vision | BTC carry | Read on the tower's own timer; no shared counter yet |
| Polymarket Gamma | gamma-api.polymarket.com | Poly sports lean, soccer and tennis lean, Fed watch | Read on the tower's own timer; no shared counter yet |
| ESPN scoreboard | site.api.espn.com | Sports gap | Read on the tower's own timer; no shared counter yet |
| The Odds API | api.the-odds-api.com | Sports sharp lag | Needs its own key; read on the tower's own timer |
| DexScreener | api.dexscreener.com | Memecoin, desk card | Read on the tower's own timer; no shared counter yet |
| RugCheck | api.rugcheck.xyz | Memecoin | Read on the tower's own timer; no shared counter yet |
| xAI | api.x.ai | Memecoin notes | Needs its own key; read on the tower's own timer |
| Yahoo Finance | query1.finance.yahoo.com | Commodity 15m, S&P desk, Nasdaq, QQQ, Treasury 10y | Read on the tower's own timer; no shared counter yet |
| CNBC quotes | quote.cnbc.com, ts-api.cnbc.com | Nasdaq, Treasury 10y | Read on the tower's own timer; no shared counter yet |
| US Treasury | home.treasury.gov | Treasury 10y | Read on the tower's own timer; no shared counter yet |
| FRED | fred.stlouisfed.org | Treasury 10y | Read on the tower's own timer; no shared counter yet |
| Cleveland Fed nowcast | www.clevelandfed.org | CPI nowcast | Read on the tower's own timer; no shared counter yet |
| Atlanta Fed GDPNow | www.atlantafed.org | GDP nowcast | Read on the tower's own timer; no shared counter yet |
| Economic calendar | nfs.faireconomy.media | Calendar helper, BTC 15m signal | Read on the tower's own timer; no shared counter yet |
| National Weather Service | api.weather.gov | Weather high | Read on the tower's own timer; no shared counter yet |
| Open-Meteo ensemble | ensemble-api.open-meteo.com | Weather high | Read on the tower's own timer; no shared counter yet |
| AAA gas prices | gasprices.aaa.com | Gas weekly | Read on the tower's own timer; no shared counter yet |
| Cloudflare trace | www.cloudflare.com | Desk ops clock check | Once an hour |

## Open items

- Check each source's published rate limit and terms page and fill them in here.
- A per-source request counter and a near-the-limit alert exist only for Kalshi
  (the gateway's `sent` and `count_429` on `/healthz`). Other sources still need one.
