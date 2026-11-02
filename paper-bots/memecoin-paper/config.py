# config.py
# every number on the desk lives here. when you retune, you edit this file and nothing else.

MODEL = "grok-4.7"          # only used by the OPTIONAL Grok hook below (paid API, off by default)
PAPER = True                # week one: fake fills at real prices. bot.py refuses to run if this is False

TICKET_USD = 25             # default ticket; desk Kelly-lite may size down to cash
MIN_TICKET_USD = 10         # still trade when cash is thin but edge clears
MAX_OPEN = 4                # 4 x $25 = $100 in the market, max
MAX_ENTRIES_PER_DAY = 6
# Align with desk daily_loss_stop so a −$50 meme day does not idle the whole teller
# while sports/BTC still have desk risk budget.
DAILY_LOSS_HALT_USD = 150
COOLDOWN_HOURS = 24         # no re-entry into a token you just left

FACTS = {                   # the rug filter. code only, no model
    "max_risk_score": 40,       # rugcheck score_normalised, 0-100, higher = riskier
    "min_lp_locked_pct": 90,    # biggest pool: LP locked or burned
    "max_top10_pct": 30,        # top 10 holders, pools and lockers excluded
    "max_dev_pct": 5,           # supply still sitting in the creator wallet
    "max_insiders": 0,          # insider-flagged holders + insider graph hits
    "min_liquidity_usd": 30000,
    "max_ticket_share": 0.01,   # your ticket is never more than 1% of the pool
    "min_age_min": 30,          # younger than this, every report is still guessing
    "max_age_hours": 72,
}

MIN_CONFIDENCE = 0.80       # margin goal: ≥80% confidence + facts + fee-aware venue edge

EXIT = {
    "stop_pct": -35,                        # hard stop from entry
    "ladder": [(100, 0.50), (200, 0.25)],   # +100% sells half, +200% sells a quarter
    "trail_pct": 30,                        # the rest: out when price falls 30% from its peak
    "time_stop_hours": 6,                   # not up 20% after 6 hours -> out, dead money
    "time_stop_min_pct": 20,
    "liq_drop_pct": 40,                     # pool liquidity down 40% from entry -> out now
    # Model-flip: leave before the hard −35% when confidence/momentum collapses.
    "model_flip_confidence_floor": 0.45,
    "model_flip_momentum_h1_floor": -12,
}

LOG = "checks.csv"
POSITIONS = "positions.json"
TRADES = "trades.csv"

# ---------------------------------------------------------------------------
# Added for the free version (replaces the paid Grok model call)
# ---------------------------------------------------------------------------
START_BANKROLL_USD = 100    # paper money: 4 x $25

PAPER_FILL = {
    "swap_fee_pct": 1.0,        # ~1% DEX/aggregator fee, charged on every paper buy and sell
    # slippage is estimated from the real pool size (constant-product math):
    # price impact = ticket / (liquidity/2 + ticket). nothing else is assumed.
}

# Free rule-based scorer. Each signal is mapped to 0..1 between "bad" and "good",
# then combined with the weights below. Output = confidence 0..1.
SCORER = {
    "weights": {"momentum": 0.30, "volume": 0.25, "liquidity": 0.20, "buy_pressure": 0.25},
    # momentum = DexScreener priceChange.h1 (%). <= bad -> 0, >= good -> 1
    "momentum_h1_bad": -10, "momentum_h1_good": 40,
    "momentum_m5_floor": -5,        # 5-min change below this -> momentum score halved (falling knife)
    "momentum_h1_too_hot": 300,     # h1 pump above this -> momentum score halved (likely top)
    # volume = 1h volume / liquidity (turnover)
    "vol_turnover_bad": 0.1, "vol_turnover_good": 1.5,
    # liquidity in USD
    "liq_bad": 30000, "liq_good": 250000,
    # buy pressure = buys / (buys + sells) over 1h
    "buy_ratio_bad": 0.45, "buy_ratio_good": 0.65,
    "min_txns_h1": 50,              # fewer 1h txns than this -> buy pressure score 0 (too thin)
}

# OPTIONAL Grok hook -- DISABLED. Grok API is paid (console.x.ai).
# To try it later: set GROK_ENABLED = True and export XAI_API_KEY=... in your shell.
# The rule scorer still runs; Grok can only turn a BUY into a SKIP, never the reverse.
GROK_ENABLED = False
GROK_TIMEOUT_SEC = 30

# polite rate limiting for the free public APIs
HTTP = {"timeout_sec": 20, "dexscreener_pause_sec": 0.3, "rugcheck_pause_sec": 1.2, "retries": 2}
