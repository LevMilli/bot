# config.py
# every number on the desk lives here. when you retune, you edit this file and nothing else.

MODEL = "grok-4.7"          # only used by the OPTIONAL Grok hook below (paid API, off by default)
PAPER = True                # week one: fake fills at real prices. bot.py refuses to run if this is False

TICKET_USD = 25             # default ticket; desk Kelly-lite may size down to cash
MIN_TICKET_USD = 10         # still trade when cash is thin but edge clears
RED_DAY_TICKET_USD = 10     # red-day ticket ceiling — lose less per knife
MAX_OPEN = 6                # green-day concurrent paper tickets
MAX_OPEN_RED = 1            # red-day: one open max (ROI rescue — was 2)
MAX_ENTRIES_PER_DAY = 8     # fewer attempts while stop-bleed week runs
# Desk daily stop stays $150; meme locks new entries earlier to protect the tower.
DAILY_LOSS_HALT_USD = 150
RED_DAY_ENTRY_LOCK_USD = 5  # today ≤ −$5 → entries off (was −$8; −$7.57 board still bought)
COOLDOWN_HOURS = 12         # half-day cooldown so the tower can re-enter winners faster
# Speed lane only when Chicago-day realized PnL is non-negative (accurate still allowed).
SPEED_ONLY_IF_TODAY_NONNEG = True
SPEED_REQUIRE_M5_NONNEG = True  # no speed entries into a falling 5m knife
SPEED_MIN_LIQUIDITY_USD = 50000  # speed lane needs deeper pool than accurate floor
# Soft red: today < 0 → accurate-only already; also shrink tickets (see bot).
ACCURATE_ONLY_WHEN_TODAY_NEG = True

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

# Dual lanes: accurate (high conf) + speed (lower conf, still facts-gated).
MIN_CONFIDENCE_ACCURATE = 0.80
MIN_CONFIDENCE_SPEED = 0.72
MIN_CONFIDENCE = MIN_CONFIDENCE_ACCURATE  # legacy alias

EXIT = {
    "stop_pct": -12,                        # ROI rescue: cut earlier than −18% Masters week-0
    "ladder": [(100, 0.50), (200, 0.25)],   # +100% sells half, +200% sells a quarter
    "trail_pct": 25,                        # tighter trail so winners keep more
    "time_stop_hours": 4,                   # dead money out faster (was 6h)
    "time_stop_min_pct": 20,
    "liq_drop_pct": 35,                     # pool bleed → exit sooner
    # Model-flip: leave before the hard stop when momentum collapses.
    "model_flip_confidence_floor": 0.45,
    "model_flip_momentum_h1_floor": -6,
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
    "momentum_h1_too_hot": 80,      # anti-top: reject hotter pumps earlier (was 120)
    # volume = 1h volume / liquidity (turnover)
    "vol_turnover_bad": 0.1, "vol_turnover_good": 1.5,
    # liquidity in USD
    "liq_bad": 30000, "liq_good": 250000,
    # buy pressure = buys / (buys + sells) over 1h
    "buy_ratio_bad": 0.45, "buy_ratio_good": 0.65,
    "min_txns_h1": 100,             # thinner books out (was 80)
}

# OPTIONAL Grok hook -- DISABLED. Grok API is paid (console.x.ai).
# To try it later: set GROK_ENABLED = True and export XAI_API_KEY=... in your shell.
# The rule scorer still runs; Grok can only turn a BUY into a SKIP, never the reverse.
GROK_ENABLED = False
GROK_TIMEOUT_SEC = 30

# polite rate limiting for the free public APIs
HTTP = {"timeout_sec": 20, "dexscreener_pause_sec": 0.3, "rugcheck_pause_sec": 1.2, "retries": 2}
