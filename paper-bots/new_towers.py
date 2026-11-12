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
        "max_open": 3,
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
            "Fixed $25 ticket in whole contracts; max 3 open, one per city-day, one new buy per check",
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
        "id": "poly-sports-lean",
        "name": "Poly sports lean",
        "folder": "poly-sports-lean-paper",
        "venue": "kalshi_sports",
        "floor": 0.06,
        "kind": "sports",
        "every_sec": 300,
        "timeout": 60,
        "max_open": 2,
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
            "Fixed $25 ticket in whole contracts; max 2 open, one per game, one new buy per check",
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
        "id": "calibration-lab",
        "name": "Calibration lab",
        "folder": "calibration-lab-paper",
        "venue": "kalshi_econ",
        "floor": 0.05,
        "kind": "research",
        "research": True,
        "every_sec": 21600,
        "timeout": 180,
        "max_open": 0,
        "blurb": (
            "Research building. Every 6 hours it looks at Kalshi markets that settled in the last "
            "14 days and counts how often each price band actually won 1, 3 and 6 hours before close. "
            "It also scores each new tower's fair prices against the market. Buys nothing, holds no cash."
        ),
        "buy": [
            "Never buys. Zero cash, zero stake, no tower risk share",
            "Families: weather highs, gas weekly, BTC/ETH daily, Nasdaq, S&P (scheduled closes only)",
            "Win rate per 5¢ band with a Wilson 95% range; cautious edge = low end − price − fee",
        ],
        "sell": [
            "Nothing to sell",
            "Writes calibration.json for other towers to read (favorite harvest, scorecards)",
        ],
        "failsafes": [
            "Public Kalshi data only, through the shared gateway",
            "At most 25 candle calls a run, 5 per family, so no family starves the rest",
            "Markets with no price history are remembered so they are not fetched again",
        ],
        "aliases": ("calibration lab", "calibration"),
        "office": "Calibration lab",
        "color": "#c792ea",
    },
)

BY_ID = {row["id"]: row for row in TOWERS}
PAUSED: frozenset = frozenset()
ACTIVE = tuple(row for row in TOWERS if row["id"] not in PAUSED)
VENUES = {row["id"]: row["venue"] for row in TOWERS}
RESEARCH = frozenset(row["id"] for row in TOWERS if row.get("research"))
