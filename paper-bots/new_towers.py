"""Registry for the new Kalshi shadow towers (engine: kalshi_shadow_tower.py).

One row per tower. ``pimp_desk._install_new_towers`` reads this list and fills
BOTS, ACTIONS, ACCOUNT_FILES, AUTO, BOT_PLANS, ROI waivers, starter cash and
settlement files; ``desk_profit`` reads VENUES. A tower joins by adding one row
here plus its folder. Every row starts shadow_only: $25 fixed ticket from a $500
sleeve, no desk cash, no tower risk share. Each one reuses an existing locked
venue floor; none adds or lowers a floor.
"""
from __future__ import annotations

TOWERS = (
    {
        "id": "weather-high",
        "name": "Weather high",
        "folder": "weather-high-paper",
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "weather",
        "every_sec": 300,
        "timeout": 75,
        "max_open": 7,
        "blurb": (
            "Shadow Kalshi daily-high brackets for seven cities. Prices each bracket from the "
            "station's recorded high plus the ensemble forecast. Buys only after the afternoon "
            "lock and only when edge after fee clears 0.05. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXHIGH NY / Chicago / Miami / Austin / Denver / Philadelphia / LA brackets, settled on the NWS climate report",
            "Fair = recorded high so far (NWS station) + Open-Meteo ensemble for the hours left, anchored to the NWS forecast high",
            "Buy window: after 15:00 local standard time on the day; earlier brackets are logged for calibration",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked econ 0.05 and ≤ 0.25 trust cap",
            "Fixed $25 ticket in whole contracts; max 7 open, one per city-day, one new buy per check",
            "Extra slots: up to 2 more past max open, only when edge ≥ 2× the floor (still under the trust cap); tagged extra",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Econ floor 0.05 cannot be lowered in config",
            "Missing station, forecast or book → that city skips; nothing invented",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("weather high", "weather"),
        "office": "Weather high",
        "color": "#5ec8ff",
    },
    {
        "id": "gas-weekly",
        "name": "Gas weekly",
        "folder": "gas-weekly-paper",
        "keep": ("aaa_history.json",),  # 21-day momentum fit must survive a deploy
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "econ",
        "every_sec": 900,
        "timeout": 60,
        "max_open": 2,
        "blurb": (
            "Shadow Kalshi weekly gas strikes on the AAA national average. Projects today's AAA "
            "price to settlement with fading momentum and buys only when edge after fee clears "
            "0.05. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXAAAGASW \"greater than $X\" strikes, settled on the AAA US regular average for the settle date",
            "Fair = AAA today projected with fading momentum (phi 0.9 until fitted from its own daily history), normal spread",
            "Until 21 days of AAA history: buys only within 1 day of settle; earlier strikes are logged for scoring",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked econ 0.05 and ≤ 0.25 trust cap",
            "Fixed $25 ticket in whole contracts; max 2 open, one per week, one new buy per check",
            "Extra slots: up to 2 more past max open, only when edge ≥ 2× the floor (still under the trust cap); tagged extra",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Econ floor 0.05 cannot be lowered in config",
            "AAA page fails to parse or no open strikes → skip; nothing invented",
            "AAA read at most once an hour",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("gas weekly", "gas"),
        "office": "Gas weekly",
        "color": "#ffb347",
    },
    {
        "id": "crypto-ladder",
        "name": "Crypto ladder",
        "folder": "crypto-ladder-paper",
        "venue": "kalshi_btc15m",
        "floor": 0.05,
        "kind": "crypto",
        "every_sec": 300,
        "timeout": 60,
        "max_open": 2,
        "blurb": (
            "Shadow Kalshi daily BTC and ETH strikes (5pm ET). Prices each strike from Coinbase "
            "spot and Deribit's option smile, and buys only when edge after fee clears 0.05. "
            "Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXBTCD / KXETHD \"above $X at 5pm ET\" strikes, settled on the CF Benchmarks 60-second average",
            "Fair = lognormal N(d2) from Coinbase spot and Deribit implied vol at that strike, blended across expiries",
            "Window: 15 minutes to 30 hours before the print",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked BTC 0.05 and ≤ 0.20 trust cap",
            "Fixed $25 ticket in whole contracts; max 2 open, one per event, one new buy per check",
            "Extra slots: up to 2 more past max open, only when edge ≥ 2× the floor (still under the trust cap); tagged extra",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "BTC floor 0.05 cannot be lowered in config",
            "Deribit vs Coinbase gap > 0.5%, missing spot or smile → that coin skips",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("crypto ladder", "ladder"),
        "office": "Crypto ladder",
        "color": "#f7931a",
    },
    {
        "id": "nasdaq",
        "name": "Nasdaq",
        "folder": "nasdaq-paper",
        "venue": "kalshi_inx",
        "floor": 0.02,
        "kind": "index",
        "every_sec": 300,
        "timeout": 60,
        "max_open": 2,
        "blurb": (
            "Shadow Kalshi end-of-day Nasdaq 100 strikes and ranges. Prices each from the live "
            "index and the Nasdaq volatility index, regular hours only, and buys only when edge "
            "after fee clears 0.02. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXNASDAQ100U strikes and KXNASDAQ100 ranges for today's 4pm ET close",
            "Fair = lognormal from live ^NDX and ^VXN over the trading minutes left (252 x 390 a year)",
            "Window: regular hours, more than 10 minutes before the close; index quote under 5 minutes old",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked index 0.02 and ≤ 0.15 trust cap",
            "Fixed $25 ticket in whole contracts; max 2 open, one per event, one new buy per check",
            "Extra slots: up to 2 more past max open, only when edge ≥ 2× the floor (still under the trust cap); tagged extra",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Index floor 0.02 cannot be lowered in config",
            "Market closed, stale or missing index quote → skip; nothing invented",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("nasdaq", "ndx", "nasdaq 100"),
        "office": "Nasdaq",
        "color": "#4d8bff",
    },
    {
        "id": "more-15m",
        "name": "More 15m",
        "folder": "more-15m-paper",
        "venue": "kalshi_btc15m",
        "floor": 0.05,
        "kind": "crypto",
        "every_sec": 60,
        "timeout": 50,
        "max_open": 4,
        "blurb": (
            "Shadow Kalshi 15-minute up/down windows no other tower reads: Solana, XRP, Dogecoin, "
            "BNB, Hyperliquid, the S&P 500, EUR/USD and USD/JPY. Prices each window from the live "
            "price against the window open, and buys only when edge after fee clears 0.05. "
            "Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXSOL15M / KXXRP15M / KXDOGE15M / KXBNB15M / KXHYPE15M (CF Benchmarks 60-second average), "
            "KXINX15M (S&P 500), KXEURUSD15M / KXUSDJPY15M (Pyth)",
            "Fair = N(ln(live / open) / (1-minute move x sqrt(minutes left))); 1-minute move from the last hour (x1.0; USD/JPY x1.3, from calibration)",
            "Coins move together: at most 2 open bets the same direction across the five coins per window",
            "Live price: Coinbase mid for coins (Kraken backup); Hyperliquid oracle for the S&P 500 and FX, "
            "shifted by the offset learned at each window open (needs 3 opens before any buy)",
            "Window: 3 to 14 minutes left",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked BTC 0.05 and ≤ 0.20 trust cap",
            "Fixed $25 ticket in whole contracts; max 4 open, one per window, one new buy per check",
            "Extra slots: up to 2 more past max open, only when edge ≥ 2× the floor (still under the trust cap); tagged extra",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "BTC floor 0.05 cannot be lowered in config",
            "Missing live price, short candle history or no open price → that market skips; nothing invented",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("more 15m", "alt 15m", "sol 15m", "fx 15m"),
        "keep": ("index_basis.json",),  # learned open offsets survive redeploys
        "office": "More 15m",
        "color": "#14f195",
    },
    {
        "id": "poly-sports-lean",
        "name": "Poly sports lean",
        "folder": "poly-sports-lean-paper",
        "venue": "kalshi_sports",
        "floor": 0.06,
        "kind": "sports",
        "every_sec": 300,
        "timeout": 60,
        "max_open": 4,
        "blurb": (
            "Shadow Kalshi NBA, NFL and NHL game winners. Uses Polymarket's moneyline mid for "
            "the same game as the fair price and buys only when Kalshi lags it by more than the "
            "0.06 floor after fee. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXNBAGAME / KXNFLGAME / KXNHLGAME winners, matched to Polymarket by Eastern date + team codes",
            "Fair = Polymarket moneyline mid; only when its spread ≤ 3¢ and liquidity ≥ $10k",
            "Window: 5 minutes to 48 hours before start (pre-game only)",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked sports 0.06 and ≤ 0.15 trust cap",
            "Fixed $25 ticket in whole contracts; max 4 open, one per game, one new buy per check",
            "Extra slots: up to 2 more past max open, only when edge ≥ 2× the floor (still under the trust cap); tagged extra",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the Polymarket fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Sports floor 0.06 cannot be lowered in config",
            "Game must match exactly one Kalshi event with both team codes; otherwise skipped",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("poly sports lean", "poly lean", "sports lean"),
        "office": "Poly sports lean",
        "color": "#2ec4b6",
    },
    {
        "id": "favorite-harvest",
        "name": "Favorite harvest",
        "folder": "favorite-harvest-paper",
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "macro",
        "every_sec": 900,
        "timeout": 90,
        "max_open": 3,
        "blurb": (
            "Shadow Kalshi heavy favorites (88-94c) 1, 3 or 6 hours before a scheduled close. "
            "Fair is the cautious win rate the calibration lab measured for that price band. "
            "Buys only when it beats ask plus fee by the 0.05 floor. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "Weather highs, gas weekly, BTC/ETH daily, Nasdaq, S&P: sides priced 88-94c",
            "Only 1, 3 or 6 hours (±) before close, matching the lab's horizons",
            "Fair = low end of the Wilson 95% win-rate range for that family, horizon and 5c band",
            "Waits (logs only) until a cell has at least 50 settled sides",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked 0.05 and ≤ 0.10 trust cap",
            "Fixed $25 ticket in whole contracts; max 3 open, one per event, one new buy per check",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the cautious fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Floor 0.05 cannot be lowered in config",
            "No buys if the calibration table is missing or more than 48 hours old",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("favorite harvest", "favorites", "harvest"),
        "office": "Favorite harvest",
        "color": "#e6c84f",
    },
    {
        "id": "treasury-10y",
        "name": "10-year Treasury",
        "folder": "treasury-10y-paper",
        "keep": ("ust_daily.json",),
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "macro",
        "every_sec": 600,
        "timeout": 60,
        "max_open": 2,
        "blurb": (
            "Shadow Kalshi daily 10-year Treasury yield markets. Prices each strike from the live "
            "10-year yield, its usual daily move and the gap to the official Treasury number it "
            "settles on. Buys only when edge after fee clears 0.05. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXUST10A: \"above X%\" on the Treasury's official 10-year par yield for today",
            "Fair = live ^TNX + measured TNX-to-Treasury gap, with the 60-day typical daily move scaled to minutes left",
            "Only on the settlement day, 9:00 ET to 15 minutes before 3:30pm ET, quote under 10 minutes old",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked econ 0.05 and ≤ 0.15 trust cap",
            "Fixed $25 ticket in whole contracts; max 2 open, one per event, one new buy per check",
            "Extra slots: up to 2 more past max open, only when edge ≥ 2× the floor (still under the trust cap); tagged extra",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Econ floor 0.05 cannot be lowered in config",
            "No buys on holidays or when the yield quote is stale",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("10 year treasury", "treasury", "10y", "bonds"),
        "office": "10-year Treasury",
        "color": "#9ad1d4",
    },
    {
        "id": "cpi-nowcast",
        "name": "CPI nowcast",
        "folder": "cpi-nowcast-paper",
        "keep": ("nowcast_cache.json",),
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "macro",
        "every_sec": 1800,
        "timeout": 120,
        "max_open": 4,
        "blurb": (
            "Shadow Kalshi monthly CPI markets (headline and core, monthly and yearly). Prices each "
            "strike from the Cleveland Fed's daily inflation nowcast and how far that nowcast has "
            "usually missed. Buys only when edge after fee clears 0.05. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXCPI / KXCPICORE / KXCPIYOY / KXCPICOREYOY: \"above X%\" on the BLS CPI print",
            "Fair = Cleveland Fed nowcast, with its measured historical miss (by days to release) widened 25%",
            "Only the month the nowcast covers, nowcast under 5 days old, not in the last 2 hours before release",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked econ 0.05 and ≤ 0.15 trust cap",
            "Fixed $25 ticket in whole contracts; max 4 open, one per event, one new buy per check",
            "Extra slots: up to 2 more past max open, only when edge ≥ 2× the floor (still under the trust cap); tagged extra",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Econ floor 0.05 cannot be lowered in config",
            "Big model-vs-market gaps (edge over 0.15) are logged, never bought",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("cpi", "inflation", "cpi nowcast", "cleveland fed"),
        "office": "CPI nowcast",
        "color": "#e8a0bf",
    },
    {
        "id": "gdp-nowcast",
        "name": "GDP nowcast",
        "folder": "gdp-nowcast-paper",
        "keep": ("gdpnow_cache.json",),
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "macro",
        "every_sec": 3600,
        "timeout": 120,
        "max_open": 2,
        "blurb": (
            "Shadow Kalshi quarterly GDP markets. Prices each strike from the Atlanta Fed's GDPNow "
            "estimate and how far GDPNow has usually missed at that distance from the print. Buys "
            "only in the last 45 days, when edge after fee clears 0.05. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXGDP: \"above X%\" on BEA's first (advance) real GDP print",
            "Fair = GDPNow minus its usual run-high, with its measured miss by days to the print",
            "Buys only in the last 45 days before the print; earlier rows are logged for calibration",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked econ 0.05 and ≤ 0.15 trust cap",
            "Fixed $25 ticket in whole contracts; max 2 open, one per event, one new buy per check",
            "Extra slots: up to 2 more past max open, only when edge ≥ 2× the floor (still under the trust cap); tagged extra",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Econ floor 0.05 cannot be lowered in config",
            "GDPNow older than 10 days or for a different quarter: no buys",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("gdp", "gdpnow", "gdp nowcast", "atlanta fed"),
        "office": "GDP nowcast",
        "color": "#b5d99c",
    },
    {
        "id": "soccer-tennis-lean",
        "name": "Soccer & tennis lean",
        "folder": "soccer-tennis-lean-paper",
        "venue": "kalshi_sports",
        "floor": 0.06,
        "kind": "sports",
        "every_sec": 600,
        "timeout": 120,
        "max_open": 6,
        "blurb": (
            "Shadow Kalshi soccer and tennis winners. Uses Polymarket's moneyline mid for the same "
            "game as the fair price and buys only when Kalshi lags it by more than the 0.06 floor "
            "after fee. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "EPL, La Liga, Champions League, Bundesliga, Serie A, Ligue 1, MLS, ATP and WTA game winners",
            "Fair = Polymarket moneyline mid (soccer win/draw/win scaled to add up to 1)",
            "Matched by date and team or player names; a game is used only if every side matches",
            "Pre-game only: 10 minutes to 48 hours before start; Polymarket spread ≤ 3¢ and liquidity ≥ $5k",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked sports 0.06 and ≤ 0.15 trust cap",
            "Fixed $25 ticket in whole contracts; max 6 open, one per event, one new buy per check",
            "Extra slots: up to 2 more past max open, only when edge ≥ 2× the floor (still under the trust cap); tagged extra",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Sports floor 0.06 cannot be lowered in config",
            "No Odds API credits used (those stay with sports-sharp-lag)",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("soccer", "tennis", "soccer tennis", "football", "epl", "atp", "wta"),
        "office": "Soccer & tennis lean",
        "color": "#f2a65a",
    },
    {
        "id": "qqq-momentum",
        "name": "QQQ momentum",
        "folder": "qqq-momentum-paper",
        "venue": "equity_qqq",
        "floor": 0.02,
        "kind": "index",
        "every_sec": 300,
        "timeout": 60,
        "max_open": 1,
        "blurb": (
            "Shadow paper QQQ shares. Intraday momentum: goes long or short when QQQ breaks out of "
            "its normal daily range at a half-hour check, trails a stop, and is always flat by the "
            "close. No broker is connected. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "Band = max/min(open, yesterday's close) × (1 ± 14-day average move from the open at that time)",
            "Checks only at HH:00 and HH:30, 10:00 to 15:30 New York; acts only on a bar that closed in the last 10 minutes",
            "Long above the upper band, short below the lower band, clearing it by 2% of the band width (locked equity_qqq 0.02)",
            "Fixed $25 ticket (fractional paper shares), one position at a time",
            "Costs: $0.0035 a share commission plus 1¢ a share slippage each way",
        ],
        "sell": [
            "Trailing stop at the band or VWAP, whichever is tighter, checked at the half-hour checks",
            "Always flat at the 16:00 close (earlier on half days)",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new entries; exits and the close still run",
            "No late fills: a missed check is logged, not back-filled",
            "Public Yahoo bars only, cached 4 minutes. No broker, no keys",
            "Published replications find this edge thin on QQQ after costs. Incubation n≥50 before any desk share",
        ],
        "aliases": ("qqq", "nasdaq etf", "qqq momentum", "intraday momentum"),
        "office": "QQQ momentum",
        "color": "#5ccfe6",
    },
    {
        "id": "crypto-hourly",
        "name": "Crypto hourly",
        "folder": "crypto-hourly-paper",
        "venue": "kalshi_btc15m",
        "floor": 0.05,
        "kind": "crypto",
        "every_sec": 300,
        "timeout": 90,
        "max_open": 3,
        "blurb": (
            "Shadow Kalshi hourly SOL, XRP, DOGE and BNB strikes and ranges. Prices each from the "
            "coin's recent Coinbase moves and buys only when edge after fee clears 0.05. "
            "Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXSOLD / KXXRPD / KXDOGED / KXBNBD hourly strikes, plus KXSOL / KXXRP / KXDOGE / KXBNB ranges",
            "Fair = Coinbase spot now, spread by realized volatility (5-minute moves near the close, 1-hour moves further out)",
            "Only 10 minutes to 30 hours before the close; a series with no open markets is noted and skipped",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked BTC 0.05 and ≤ 0.20 trust cap",
            "Fixed $25 ticket in whole contracts; max 3 open, one per event, at most 2 the same way in one hour",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "BTC floor 0.05 cannot be lowered in config",
            "Missing Coinbase candles or Kalshi book → that coin skips; nothing invented",
            "No option smile for these coins, so fat tails are only partly priced. Incubation n≥50 before any desk share",
        ],
        "aliases": ("crypto hourly", "sol hourly", "xrp hourly", "doge hourly", "bnb hourly"),
        "office": "Crypto hourly",
        "color": "#9945ff",
    },
    {
        "id": "weather-low",
        "name": "Weather low",
        "folder": "weather-low-paper",
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "weather",
        "every_sec": 600,
        "timeout": 170,
        "max_open": 6,
        "blurb": (
            "Shadow Kalshi daily low temperature brackets in 24 cities. Uses what the station "
            "has seen so far, the NWS night low and about 80 ensemble runs. Buys only when edge "
            "after fee clears 0.05. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXLOWT brackets in 24 cities, settled on the NWS climate report low",
            "Fair = lowest reading so far, plus each ensemble run for the rest of the day moved onto the NWS night low",
            "Whole-degree 5-minute readings count only as a bound, not as the exact low",
            "Before 10:00 local standard time the low can still drop: logged for scoring, no buys",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked econ 0.05 and ≤ 0.25 trust cap",
            "Fixed $25 ticket in whole contracts; max 6 open, one per city-day, one new buy per check",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Econ floor 0.05 cannot be lowered in config",
            "Missing station, forecast or book → that city skips; nothing invented",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("weather low", "low temperature", "daily low"),
        "office": "Weather low",
        "color": "#7aa7ff",
    },
    {
        "id": "weather-cities",
        "name": "Weather cities",
        "folder": "weather-cities-paper",
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "weather",
        "every_sec": 600,
        "timeout": 170,
        "max_open": 6,
        "blurb": (
            "Shadow Kalshi daily high temperature brackets in 17 more cities, using the same "
            "method as Weather high. Buys only when edge after fee clears 0.05. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXHIGHT brackets in Atlanta, Boston, Dallas, DC, Newark, Houston, Las Vegas, Minneapolis, New Orleans, Oklahoma City, Phoenix, San Diego, San Antonio, Louisville, Seattle, San Francisco and Trenton",
            "Fair = highest reading so far, plus each ensemble run for the rest of the day moved onto the NWS high",
            "Whole-degree 5-minute readings count only as a bound, not as the exact high",
            "Before 15:00 local standard time the high can still climb: logged for scoring, no buys",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked econ 0.05 and ≤ 0.25 trust cap",
            "Fixed $25 ticket in whole contracts; max 6 open, one per city-day, one new buy per check",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Econ floor 0.05 cannot be lowered in config",
            "Missing station, forecast or book → that city skips; nothing invented",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("weather cities", "more weather", "city highs"),
        "office": "Weather cities",
        "color": "#4fd1c5",
    },
    {
        "id": "monthly-precip",
        "name": "Monthly rain and snow",
        "folder": "monthly-precip-paper",
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "weather",
        "every_sec": 1800,
        "timeout": 150,
        "max_open": 3,
        "blurb": (
            "Shadow Kalshi monthly rain totals in 18 cities and snow totals in 9. Adds the month "
            "so far to every forecast run that reaches month end. Buys only in the last 14 days, "
            "when edge after fee clears 0.05. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXRAIN<city>M and KX<city>SNOWM \"more than K inches\" markets, settled on the NWS climate report",
            "Fair = month-to-date total from the last complete climate report, plus each ensemble run's amount for the rest of the month, widened ±35% (rain) or ±50% (snow)",
            "Only runs that reach the last day of the month count; under 20 such runs → the city skips",
            "Buys only with 14 or fewer days left; earlier prices are logged for scoring",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked econ 0.05 and ≤ 0.25 trust cap",
            "Fixed $25 ticket in whole contracts; max 3 open, one per city-month",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Econ floor 0.05 cannot be lowered in config",
            "Stale climate report (over 4 days) or short forecast → that city skips; nothing invented",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("monthly rain", "monthly snow", "rain total", "snow total", "precip"),
        "office": "Monthly rain and snow",
        "color": "#6fa8dc",
    },
    {
        "id": "gas-monthly",
        "name": "Gas monthly",
        "folder": "gas-monthly-paper",
        "keep": ("aaa_history.json",),  # momentum fit must survive a deploy
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "econ",
        "every_sec": 900,
        "timeout": 60,
        "max_open": 2,
        "blurb": (
            "Shadow Kalshi month-end gas strikes on the AAA national average, using the Gas "
            "weekly model. Buys only within 14 days of settle (3 days until fitted), when edge "
            "after fee clears 0.05. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXAAAGASM \"greater than $X\" strikes, settled on the AAA US regular average for the settle date",
            "Fair = AAA today projected with fading momentum (same model as Gas weekly), normal spread",
            "Fits momentum from its own daily AAA history plus Gas weekly's (read only)",
            "Never buys more than 14 days out; until 21 days of history, only within 3 days of settle",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked econ 0.05 and ≤ 0.25 trust cap",
            "Fixed $25 ticket in whole contracts; max 2 open, one per month",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Econ floor 0.05 cannot be lowered in config",
            "AAA page fails to parse → no prices that check; nothing invented",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("gas monthly", "month end gas", "gas month"),
        "office": "Gas monthly",
        "color": "#ff8c42",
    },
    {
        "id": "spy-momentum",
        "name": "SPY momentum",
        "folder": "spy-momentum-paper",
        "venue": "equity_qqq",
        "floor": 0.02,
        "kind": "index",
        "every_sec": 300,
        "timeout": 60,
        "max_open": 1,
        "blurb": (
            "Shadow paper SPY shares. Same intraday momentum rules as QQQ momentum, on SPY: "
            "goes long or short on a breakout at a half-hour check, trails a stop, and is always "
            "flat by the close. No broker is connected. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "Band = max/min(open, yesterday's close) × (1 ± 14-day average move from the open at that time)",
            "Checks only at HH:00 and HH:30, 10:00 to 15:30 New York; acts only on a bar that closed in the last 10 minutes",
            "Long above the upper band, short below the lower band, clearing it by 2% of the band width (locked equity_qqq 0.02)",
            "Fixed $25 ticket (fractional paper shares), one position at a time",
            "Costs: $0.0035 a share commission plus 1¢ a share slippage each way",
        ],
        "sell": [
            "Trailing stop at the band or VWAP, whichever is tighter, checked at the half-hour checks",
            "Always flat at the 16:00 close (earlier on half days)",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new entries; exits and the close still run",
            "No late fills: a missed check is logged, not back-filled",
            "Public Yahoo bars only, cached 4 minutes. No broker, no keys",
            "Moves with QQQ most days, so it is close to the same bet. Incubation n≥50 before any desk share",
        ],
        "aliases": ("spy", "spy momentum", "s&p etf"),
        "office": "SPY momentum",
        "color": "#3d7dd8",
    },
    {
        "id": "iwm-momentum",
        "name": "IWM momentum",
        "folder": "iwm-momentum-paper",
        "venue": "equity_qqq",
        "floor": 0.02,
        "kind": "index",
        "every_sec": 300,
        "timeout": 60,
        "max_open": 1,
        "blurb": (
            "Shadow paper IWM shares. Same intraday momentum rules as QQQ momentum, on IWM "
            "(small companies): goes long or short on a breakout at a half-hour check, trails a "
            "stop, and is always flat by the close. No broker is connected. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "Band = max/min(open, yesterday's close) × (1 ± 14-day average move from the open at that time)",
            "Checks only at HH:00 and HH:30, 10:00 to 15:30 New York; acts only on a bar that closed in the last 10 minutes",
            "Long above the upper band, short below the lower band, clearing it by 2% of the band width (locked equity_qqq 0.02)",
            "Fixed $25 ticket (fractional paper shares), one position at a time",
            "Costs: $0.0035 a share commission plus 1¢ a share slippage each way",
        ],
        "sell": [
            "Trailing stop at the band or VWAP, whichever is tighter, checked at the half-hour checks",
            "Always flat at the 16:00 close (earlier on half days)",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new entries; exits and the close still run",
            "No late fills: a missed check is logged, not back-filled",
            "Public Yahoo bars only, cached 4 minutes. No broker, no keys",
            "Often moves with QQQ and SPY, so partly the same bet. Incubation n≥50 before any desk share",
        ],
        "aliases": ("iwm", "iwm momentum", "russell etf", "small caps"),
        "office": "IWM momentum",
        "color": "#d97706",
    },
    {
        "id": "treasury-tenors",
        "name": "Treasury tenors",
        "folder": "treasury-tenors-paper",
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "macro",
        "every_sec": 600,
        "timeout": 90,
        "max_open": 3,
        "blurb": (
            "Shadow Kalshi 2-, 5- and 30-year Treasury yield markets, using the 10-year tower's "
            "method. Prices only on the settlement day and buys only when edge after fee clears "
            "0.05. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXUST2A / KXUST5A / KXUST30A \"above X%\" markets, settled on the official Treasury par yield for that day",
            "Fair = live CNBC yield (Yahoo ^FVX / ^TYX backup for 5 and 30 years) + measured gap to the official yield, spread by recent daily moves",
            "Only on the settlement day, 9:00 ET until 15 minutes before 3:30pm ET, with a quote under 10 minutes old",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked econ 0.05 and ≤ 0.15 trust cap",
            "Fixed $25 ticket in whole contracts; max 3 open, one per event",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Econ floor 0.05 cannot be lowered in config",
            "Stale or missing yield quote → that tenor skips; the 2-year has no backup feed",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("treasury tenors", "2 year treasury", "5 year treasury", "30 year treasury"),
        "office": "Treasury tenors",
        "color": "#a3c4bc",
    },
    {
        "id": "calibration-lab",
        "name": "Calibration lab",
        "folder": "calibration-lab-paper",
        "keep": ("calibration.json", "calibration_rows.jsonl", "calibration_rows_15m.jsonl"),
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "research",
        "research": True,
        "every_sec": 21600,
        "timeout": 300,
        "max_open": 0,
        "blurb": (
            "Research building. Every 6 hours it looks at Kalshi markets that settled in the last "
            "14 days and counts how often each price band actually won 1, 3 and 6 hours before close. "
            "It also counts the 15-minute crypto, commodity, FX and S&P windows 1, 2, 5 and 10 minutes "
            "before close in a separate table, and scores each new tower's fair prices against the market. "
            "Buys nothing, holds no cash."
        ),
        "buy": [
            "Never buys. Zero cash, zero stake, no tower risk share",
            "Families: weather highs, gas weekly, BTC/ETH daily, Nasdaq, S&P (scheduled closes only)",
            "15-minute families (kept separate): crypto, commodities, FX and S&P 15m windows, 1/2/5/10 minutes before close",
            "Win rate per 5¢ band with a Wilson 95% range; cautious edge = low end − price − fee",
        ],
        "sell": [
            "Nothing to sell",
            "Writes calibration.json for other towers to read (favorite harvest, scorecards)",
        ],
        "failsafes": [
            "Public Kalshi data only, through the shared gateway",
            "At most 25 candle calls a run, 5 per family, so no family starves the rest",
            "15m families: at most 12 one-minute candle calls a run, in their own table_15m; the daily table is unchanged",
            "Markets with no price history are remembered so they are not fetched again",
        ],
        "aliases": ("calibration lab", "calibration"),
        "office": "Calibration lab",
        "color": "#c792ea",
    },
    {
        "id": "settlement-auditor",
        "name": "Settlement auditor",
        "folder": "settlement-auditor-paper",
        "keep": ("audit.json",),
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "research",
        "research": True,
        "every_sec": 86400,
        "timeout": 180,
        "max_open": 0,
        "blurb": (
            "Support building. Once a day it rechecks every paper trade that was held to the end "
            "against Kalshi's official result, and flags any trade whose recorded result or payout "
            "does not match. Buys nothing, holds no cash."
        ),
        "buy": [
            "Never buys. Zero cash, zero stake, no tower risk share",
            "Checks every desk bot's settled Kalshi trades (sold trades are skipped)",
            "Flags a wrong result, or a payout that does not match the result",
        ],
        "sell": [
            "Nothing to sell",
            "Writes audit.json; each trade is checked once, a mismatch stays listed until fixed",
        ],
        "failsafes": [
            "Public Kalshi data only, through the shared gateway",
            "At most 40 Kalshi reads a run; the rest wait for the next run",
            "Read-only on other bots' books: it never edits a trade",
        ],
        "aliases": ("settlement auditor", "auditor", "audit"),
        "office": "Settlement auditor",
        "color": "#8fb8de",
    },
    {
        "id": "scorekeeper",
        "name": "Scorekeeper",
        "folder": "scorekeeper-paper",
        "keep": ("scorecard.json",),
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "research",
        "research": True,
        "every_sec": 21600,
        "timeout": 180,
        "max_open": 0,
        "blurb": (
            "Support building. Every 6 hours it grades each bot on its paper record after fees: "
            "promote, keep, pause or retire, and shows the 50-result promotion card for every practice "
            "tower. It only suggests; it never changes a bot. Buys nothing."
        ),
        "buy": [
            "Never buys. Zero cash, zero stake, no tower risk share",
            "Grades need 50+ closed trades; under that a bot shows \"too few\"",
            "P&L per trade is after fees and after the desk's 1 cent a contract fill tax",
        ],
        "sell": [
            "Nothing to sell",
            "Promote: even the low end of the 95% range is above $0. Keep: average above $0",
            "Pause: average $0 or worse but could still be positive. Retire: clearly losing",
            "Promotion card: each practice tower's count toward 50 results, average after fees, cautious low end",
            "Ready to review at 50 results; promotion still needs Levi's OK, never automatic",
        ],
        "failsafes": [
            "Read-only: suggests only, never pauses, funds or edits a bot",
            "No network reads; it only reads the desk's own state files",
            "Writes scorecard.json",
        ],
        "aliases": ("scorekeeper", "scorecard", "grades"),
        "office": "Scorekeeper",
        "color": "#e6c07b",
    },
    {
        "id": "whatif-lab",
        "name": "What-if lab",
        "folder": "whatif-lab-paper",
        "keep": ("whatif.json", "exits.json"),
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "research",
        "research": True,
        "every_sec": 21600,
        "timeout": 300,
        "max_open": 0,
        "blurb": (
            "Research building. Every 6 hours it checks what the towers' logged-but-not-bought rows "
            "would have made after fees (weather before its window, edges over the trust cap), and how "
            "long Kalshi vs Polymarket price gaps last. Its exit lab grades every closed Kalshi trade "
            "under each exit rule (hold, +10c, +15c, model flip, time stop). Buys nothing."
        ),
        "buy": [
            "Never buys. Zero cash, zero stake, no tower risk share",
            "A would-be trade is the first time a contract cleared the tower's floor after fee",
            "Flags a group only with 50+ settled rows and a 95% low end above $0",
        ],
        "sell": [
            "Nothing to sell",
            "Writes whatif.json: missed-trade grades per tower and gap stats for the Polymarket towers",
            "Maker check: would a resting bid 1 cent above the best bid have filled, and beaten taking the ask?",
            "Exit lab: exits.json grades hold to the end, +10c, +15c, model flip and a half-way time stop on every closed trade",
        ],
        "failsafes": [
            "Reads only the towers' own logs plus Kalshi results through the shared gateway",
            "At most 40 Kalshi reads a run; an open contract is read again after 12 hours",
            "Suggests only: it never turns a window or cap on",
            "Exit lab uses Kalshi 1-minute candles: at most 6 market and 20 candle reads a run; a graded trade is never read again",
        ],
        "aliases": ("what-if lab", "whatif", "what if", "missed trades", "gap monitor"),
        "office": "What-if lab",
        "color": "#7fd1b9",
    },
    {
        "id": "market-snapshots",
        "name": "Market snapshots",
        "folder": "market-snapshots-paper",
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "research",
        "research": True,
        "every_sec": 60,
        "timeout": 120,
        "max_open": 0,
        "blurb": (
            "Support building. Every 15 minutes it saves the best bid, ask and sizes of every open "
            "market in the series the towers watch, and every minute it records the 15-minute windows "
            "in their last 14 minutes, so future ideas can be tested on real price history. Buys nothing."
        ),
        "buy": [
            "Never buys. Zero cash, zero stake, no tower risk share",
            "23 series: weather, gas, crypto daily, Nasdaq, S&P, Treasury, CPI, GDP and game winners",
            "One public Kalshi read per series per full run (every 15 minutes), through the shared gateway",
            "15-minute windows every minute in their last 14 minutes: one batched read, plus one listing when a window rolls over",
        ],
        "sell": [
            "Nothing to sell",
            "Saves recordings/YYYY-MM-DD.jsonl.gz on the /data volume (about 2 MB a day)",
        ],
        "failsafes": [
            "Size cap 150 MB: the oldest days are deleted first",
            "Best bid/ask and sizes only, not the full order book",
            "One series failing does not stop the rest",
        ],
        "aliases": ("snapshots", "book snapshots"),
        "office": "Market snapshots",
        "color": "#b4a7f5",
    },
    {
        "id": "fill-realism-lab",
        "name": "Fill-realism lab",
        "folder": "fill-realism-lab-paper",
        "keep": ("fill_realism.json",),
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "research",
        "research": True,
        "every_sec": 3600,
        "timeout": 180,
        "max_open": 0,
        "blurb": (
            "Research building. Every hour it checks each tower's pretend fills against what really "
            "traded on Kalshi: was there real trading at our price, how far our price sat from the "
            "tape, and would a resting order have filled. Buys nothing and changes no tower."
        ),
        "buy": [
            "Never buys. Zero cash, zero stake, no tower risk share",
            "Each tower buy is checked once against Kalshi's public trades around it",
            "A tower whose fills beat the tape by half a cent on average is flagged",
        ],
        "sell": [
            "Nothing to sell",
            "Writes fill_realism.json: tape cover, tape gap, fill-quality score, no-fills and a daily spot check",
            "Maker practice book kept apart: would a bid one cent under the ask have filled?",
        ],
        "failsafes": [
            "Reads only the towers' own books plus public Kalshi, Coinbase and Yahoo data",
            "At most 40 Kalshi reads and 10 candle reads a run",
            "Suggests only: every fill rule it measures stays off until Levi turns it on",
        ],
        "aliases": ("fill realism", "fill lab", "fill-realism lab"),
        "office": "Fill-realism lab",
        "color": "#9fd3c7",
    },
    {
        "id": "model-lab",
        "name": "Model lab",
        "folder": "model-lab-paper",
        "keep": ("model_lab.json",),
        "venue": "kalshi_btc15m",
        "floor": 0.05,
        "kind": "research",
        "research": True,
        "every_sec": 300,
        "timeout": 90,
        "max_open": 0,
        "blurb": (
            "Research building. Every 5 minutes it prices the open Kalshi 15-minute BTC, ETH, SOL, XRP "
            "and DOGE windows four ways (today's method, blended swings, fatter tails, time of day) and "
            "scores each against the real result. Buys nothing; no tower reads it to trade."
        ),
        "buy": [
            "Never buys. Zero cash, zero stake, no tower risk share",
            "Logs log-only inputs too: jump guard, top-of-book imbalance, BTC pulling the other coins",
            "A method or input gets a verdict only after 50 settled windows",
        ],
        "sell": [
            "Nothing to sell",
            "Writes model_lab.json: Brier score per method, error by minutes left, swing multipliers, exit-rule replay",
        ],
        "failsafes": [
            "Public Coinbase candles and Kalshi markets only, through the shared gateway",
            "Swing multipliers move at most 0.15 a week, and only after 50 windows",
            "Suggests only: changing a tower's model needs a practice twin, 50 results and Levi's OK",
        ],
        "aliases": ("model lab", "models"),
        "office": "Model lab",
        "color": "#f5a3c7",
    },
    {
        "id": "ncaab-gap",
        "name": "NCAAB gap",
        "folder": "ncaab-gap-paper",
        "venue": "kalshi_sports",
        "floor": 0.06,
        "kind": "sports",
        "every_sec": 180,
        "timeout": 120,
        "max_open": 6,
        "blurb": (
            "Shadow Kalshi men's college basketball game winners. Prices each side from ESPN's "
            "sportsbook line and live win chance, and buys only when edge after fee clears the "
            "sports floor 0.06. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXNCAAMBGAME game winners matched to ESPN's Division I scoreboard by date and team name",
            "Fair = ESPN live win chance during the game, the sportsbook moneyline (no-vig) before it",
            "Window: live games, or tip-off within 3 hours; Kalshi spread no wider than 5¢",
            "Sides with fair under 0.72 are logged only; 0.72 to 0.80 need edge ≥ 0.08",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked sports 0.06 and ≤ 0.20 trust cap",
            "Fixed $25 ticket in whole contracts; max 6 open, one per game, one new buy per check",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Sports floor 0.06 cannot be lowered in config",
            "No ESPN line, no match or an ambiguous team name → that game skips",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("ncaab gap", "college basketball", "ncaab"),
        "office": "NCAAB gap",
        "color": "#f2a65a",
    },
    {
        "id": "sports-gap-poly",
        "name": "Sports gap + Polymarket",
        "folder": "sports-gap-poly-paper",
        "venue": "kalshi_sports",
        "floor": 0.06,
        "kind": "sports",
        "every_sec": 180,
        "timeout": 120,
        "max_open": 4,
        "blurb": (
            "Shadow twin of the sports gap idea with a second opinion. NBA, NFL and NHL sides "
            "are priced from ESPN and from Polymarket, and bought only when both agree and the "
            "lower of the two still clears the sports floor 0.06. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXNBAGAME / KXNFLGAME / KXNHLGAME winners matched to ESPN and to the Polymarket moneyline",
            "Fair = the lower of ESPN's chance and the Polymarket mid for that side",
            "Logged only if the two differ by more than 0.15, Polymarket's spread is over 4¢ or its liquidity under $5k",
            "Sides with fair under 0.72 are logged only; 0.72 to 0.80 need edge ≥ 0.08",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked sports 0.06 and ≤ 0.15 trust cap",
            "Fixed $25 ticket in whole contracts; max 4 open, one per game, one new buy per check",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Sports floor 0.06 cannot be lowered in config",
            "Polymarket missing or unmatched → that game is logged only, never bought on ESPN alone",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("sports gap poly", "polymarket check"),
        "office": "Sports gap + Polymarket",
        "color": "#7fd1ae",
    },
    {
        "id": "fight-golf-esports-lean",
        "name": "UFC, golf & esports lean",
        "folder": "fight-golf-esports-lean-paper",
        "venue": "kalshi_sports",
        "floor": 0.06,
        "kind": "sports",
        "every_sec": 600,
        "timeout": 150,
        "max_open": 6,
        "blurb": (
            "Shadow Kalshi UFC fights, golf tournament winners and esports matches (League of "
            "Legends, CS2, Valorant, Dota 2). Fair is Polymarket's price for the same outcome; "
            "buys only when edge after fee clears the sports floor 0.06. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXUFCFIGHT, KXPGATOUR, KXLOLGAME, KXCS2GAME, KXVALORANTGAME, KXDOTA2GAME",
            "Fair = Polymarket mid for the same fighter, golfer or team, matched by name",
            "Pre-event only: 10 minutes to 48 hours before start; Polymarket spread ≤ 3¢ and liquidity ≥ $5k",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked sports 0.06 and ≤ 0.15 trust cap",
            "Fixed $25 ticket in whole contracts; max 6 open, one per event, one new buy per check",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Sports floor 0.06 cannot be lowered in config",
            "Ambiguous or missing name match → skipped; nothing invented",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("ufc golf esports", "fight golf esports", "ufc lean"),
        "office": "UFC, golf & esports lean",
        "color": "#e88fb4",
    },
    {
        "id": "sp500-model",
        "name": "S&P model",
        "folder": "sp500-model-paper",
        "venue": "kalshi_inx",
        "floor": 0.02,
        "kind": "index",
        "every_sec": 300,
        "timeout": 60,
        "max_open": 2,
        "blurb": (
            "Shadow twin that gives the Kalshi S&P 500 markets a real fair price: the chance "
            "the index closes above each strike, from the live S&P and the VIX. Buys only when "
            "edge after fee clears the index floor 0.02. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXINXU strikes and KXINX ranges for today's 4pm ET close",
            "Fair = lognormal chance from the live S&P 500 and the VIX over the trading minutes left",
            "Regular hours only, more than 10 minutes before the close, index quote under 5 minutes old",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked index 0.02 and ≤ 0.15 trust cap",
            "Rows in the 80–90¢ band the Kalshi S&P tower uses are tagged for side-by-side comparison",
            "Fixed $25 ticket in whole contracts; max 2 open, one per event, one new buy per check",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Index floor 0.02 cannot be lowered in config",
            "Stale or missing index quote → no buys that check",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("s&p model", "sp500 model", "spx model"),
        "office": "S&P model",
        "color": "#9fb8ff",
    },
    {
        "id": "fed-curve",
        "name": "Fed curve",
        "folder": "fed-curve-paper",
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "macro",
        "every_sec": 1800,
        "timeout": 120,
        "max_open": 2,
        "blurb": (
            "Shadow Kalshi Fed decision markets with two independent reads: the fed funds "
            "futures curve and Polymarket. Buys only when both agree and the lower one still "
            "clears the economics floor 0.05. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "KXFEDDECISION hold / cut / hike outcomes for the next two meetings",
            "Curve = 30-day fed funds futures chained month by month (the CME FedWatch method)",
            "Fair = the lower of the curve chance and the Polymarket mid; logged only if they differ by more than 0.15",
            "Edge = fair − Kalshi ask − Kalshi fee; buy only if edge ≥ locked econ 0.05 and ≤ 0.15 trust cap",
            "Fixed $25 ticket in whole contracts; max 2 open, one per meeting, one new buy per check",
        ],
        "sell": [
            "Model flip: sell at the bid when bid − fee beats the model fair by 2¢",
            "Holds to the Kalshi result otherwise: $1 per contract when our side wins",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new buys; exits still run",
            "Econ floor 0.05 cannot be lowered in config",
            "Missing or stale futures, or no Polymarket price → logged only",
            "Incubation n≥50 settles before any desk share. No auto-promote",
        ],
        "aliases": ("fed curve", "fed futures"),
        "office": "Fed curve",
        "color": "#c9b06b",
    },
    {
        "id": "coinbase-maker",
        "name": "Coinbase maker",
        "folder": "coinbase-maker-paper",
        "venue": "coinbase_spot",
        "floor": 0.05,
        "kind": "crypto",
        "every_sec": 300,
        "timeout": 60,
        "max_open": 1,
        "blurb": (
            "Shadow twin of Coinbase spot that assumes limit orders at the lower maker fee and "
            "only fills when a later candle trades through our price. Same ETH and SOL signal "
            "and the same 0.05 floor. Spends no desk cash."
        ),
        "buy": [
            "Shadow sleeve only — spends no desk cash and takes no tower risk share",
            "ETH-USD and SOL-USD 15-minute Coinbase candles (public, no key)",
            "Signal: up bar with z ≥ 2 and 25% of the move minus the 1.0% maker round trip ≥ locked 0.05",
            "Limit buy at the signal close; fills only if a later bar's low trades below it; cancelled after 2 bars",
            "Fixed $25 paper ticket, one order or position at a time",
        ],
        "sell": [
            "Take-profit: resting limit sell at entry + 6%, maker fee, fills only if a bar trades above it",
            "Stop −1.5%, a z ≤ −2 bar, or 24 hours: market sell at 0.90% taker plus 0.10% slippage",
        ],
        "failsafes": [
            "Desk entry_gate still blocks new orders; exits still run",
            "Floor 0.05 is locked; a bar must move about 24% before it can buy",
            "No back-dated orders: only a signal bar from the last 20 minutes places an order",
            "Incubation n≥50 before any desk share. No auto-promote",
        ],
        "aliases": ("coinbase maker", "maker fee"),
        "office": "Coinbase maker",
        "color": "#6fa8ff",
    },
    {
        "id": "meme-price-check",
        "name": "Meme price check",
        "folder": "meme-price-check-paper",
        "keep": ("price_check.json",),  # the would-block tally must survive a deploy
        "venue": "solana_dex",
        "floor": 0.02,
        "kind": "research",
        "research": True,
        "every_sec": 900,
        "timeout": 120,
        "max_open": 0,
        "blurb": (
            "Support building for the Memecoin tower. Every 15 minutes it compares DexScreener's "
            "price with Jupiter's for each coin Memecoin holds or just checked, and counts how "
            "often a 2% gap would have stopped a trade. Buys nothing."
        ),
        "buy": [
            "Never buys. Zero cash, zero stake, no tower risk share",
            "Reads Memecoin's open positions and recent checks (read-only), up to 30 coins",
            "Would block when the two prices differ by more than 2% or either is missing",
        ],
        "sell": [
            "Nothing to sell",
            "Saves the running tally and the last 200 would-block rows in price_check.json",
        ],
        "failsafes": [
            "Fails closed: a missing price counts as a block, never as agreement",
            "Memecoin's own buys and sales are not changed",
        ],
        "aliases": ("meme price check", "jupiter check"),
        "office": "Meme price check",
        "color": "#d4a5ff",
    },
    {
        "id": "result-splits",
        "name": "Result splits",
        "folder": "result-splits-paper",
        "keep": ("splits.json",),
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "research",
        "research": True,
        "every_sec": 21600,
        "timeout": 180,
        "max_open": 0,
        "blurb": (
            "Research building. Every 6 hours it splits each tower's closed paper trades by market, "
            "by why the trade closed, by the hour it was bought and by side, so you can see which "
            "leagues, coins, metals or scan times earn their keep. Losses stay in. Buys nothing."
        ),
        "buy": [
            "Never buys. Zero cash, zero stake, no tower risk share",
            "P&L per trade is after fees and after the desk's 1 cent a contract fill tax",
            "Each group: trades, wins, losses, total, average, win rate, average win vs average loss, 95% low end",
        ],
        "sell": [
            "Nothing to sell",
            "Flags 'clearly losing' (50+ trades, even the high end below $0) and 'wins often, loses money'",
            "Writes splits.json. Suggests only: it never pauses a market or a tower",
        ],
        "failsafes": [
            "No network reads; it only reads the desk's own state files",
            "Trades with no stored result are counted and listed, never dropped",
            "Read-only on other bots' books",
        ],
        "aliases": ("result splits", "splits", "breakdown"),
        "office": "Result splits",
        "color": "#a3d977",
    },
    {
        "id": "risk-room",
        "name": "Risk room",
        "folder": "risk-room-paper",
        "keep": ("risk_room.json",),
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "research",
        "research": True,
        "every_sec": 900,
        "timeout": 120,
        "max_open": 0,
        "blurb": (
            "Support building. Every 15 minutes it lists the whole city's open paper bets by what "
            "they ride on (Bitcoin, the S&P, one game...) and flags when several towers hold the "
            "same bet. Display only. Buys nothing."
        ),
        "buy": [
            "Never buys. Zero cash, zero stake, no tower risk share",
            "Groups every open position by underlying: coin, index, metal, weather city or single game",
            "Shows open cost per group, its share of all open cost, and which towers hold it on which side",
        ],
        "sell": [
            "Nothing to sell",
            "Flags 'stacked' (2+ towers), 'same side, same game' and 'heavy' (40%+ of open cost)",
            "Writes risk_room.json. Display only: it never blocks, sizes or sells a trade",
        ],
        "failsafes": [
            "No network reads; it only reads the desk's own state files",
            "Unknown tickers keep their own series name, so nothing is dropped",
            "Read-only on other bots' books",
        ],
        "aliases": ("risk room", "exposure"),
        "office": "Risk room",
        "color": "#ff7a7a",
    },
    {
        "id": "freshness-inspector",
        "name": "Freshness inspector",
        "folder": "freshness-inspector-paper",
        "keep": ("freshness.json",),
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "research",
        "research": True,
        "every_sec": 900,
        "timeout": 120,
        "max_open": 0,
        "blurb": (
            "Support building. Every 15 minutes it checks that every building ran on time, shows "
            "each one's last and next run, and measures how old the price was behind each paper "
            "buy. Display only. Buys nothing."
        ),
        "buy": [
            "Never buys. Zero cash, zero stake, no tower risk share",
            "Late = a timer building whose last run is older than 3 gaps (at least gap + 30 minutes)",
            "Price age = buy time minus the time the price was read; over 60 seconds is flagged stale",
        ],
        "sell": [
            "Nothing to sell",
            "Writes freshness.json: every building's status, last run, next run and price ages",
        ],
        "failsafes": [
            "No network reads; it only reads the desk's own run and state files",
            "Display only: it never blocks a buy or restarts a tower",
            "Trades that did not store a separate price time are counted, not guessed",
        ],
        "aliases": ("freshness", "freshness inspector", "stale data"),
        "office": "Freshness inspector",
        "color": "#ffd166",
    },
)

BY_ID = {row["id"]: row for row in TOWERS}
PAUSED: frozenset = frozenset()
ACTIVE = tuple(row for row in TOWERS if row["id"] not in PAUSED)
VENUES = {row["id"]: row["venue"] for row in TOWERS}
RESEARCH = frozenset(row["id"] for row in TOWERS if row.get("research"))
