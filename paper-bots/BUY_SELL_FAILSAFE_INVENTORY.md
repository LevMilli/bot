# Paper bots — BUY / SELL / FAILSAFE inventory

Sources under `paper-bots/`. Desk gates: `pimp_desk.py`. Desk settings: `pimp-trading.json`.
ROI policy: `DESK_ROI_SYSTEM.md` → `snapshot.roi_system`.

Desk `entry_gate` blocks **entry** actions only (`ACTIONS[..].entry: True`): sports-gap `run`, kalshi-sp `scan`, memecoin `run`, **and btc15m `run`**. It does **not** block kalshi settle/brief. Quiet hours hold Discord alerts only — they do **not** stop script runs.

---

## 0. Desk-level gates (`pimp_desk.py`)

### DEFAULTS (also mirrored in `pimp-trading.json`)
| Key | Default | Notes |
|---|---|---|
| `stake_lo_max` | $20 | Below 80% model prob |
| `stake_hi_min` / `stake_hi_max` | $20 / $100 | At ≥80%, linear scale to 100% |
| `stake_hi_prob` | 0.8 | Locked; not overridable from raw save |
| `daily_loss_stop` | $150 | Desk-wide realized today across bots |
| `max_open_risk` | $100 | Sum of open risk across bots |
| `max_open_positions` | 12 | Sum of open counts across bots |
| `min_edge` | 0.04 | After fee; sports reads this |
| `pace_min` / `pace_target` | 6 / 12 | Display/count only — **does not waive edge** (`edge_for_hour` returns saved edge, `loosened=False`) |
| `quiet_start` / `quiet_end` | 22:00 / 07:00 CT | Alerts held; bots still run |
| `week_goal` | $25 | UI only |

Helpers: `paper_stake_dollars()`, `contracts_for_stake()`, `learning_skip()` (≥8 settles in market×bucket and hit rate &lt;40% → skip), `prob_bucket()` (0.1-wide).

### `entry_gate()` blockers (entry actions)
1. Desk today PnL ≤ −`daily_loss_stop` ($150)
2. Desk open_count ≥ `max_open_positions` (12)
3. Desk open_risk ≥ `max_open_risk` ($100)

Kalshi **scan** is hard-blocked when the gate is hit; settle/brief still run.  
Sports / BTC / memecoin **still run** with `DESK_BLOCK_ENTRIES=1` so exits/settles can free risk; only new paper buys stay off.

### Pause / pace / other
- **Pause:** `pimp-pause.json` — per-bot or `all`; `run_bot` returns blocked; timer skips paused slots.
- **Manual rate limit:** 30s between manual runs (`MANUAL_GAP_SEC`).
- **Sports idle:** if last sports summary says no live games, timer gap → 900s (else 300s).
- **AUTO schedule:** sports/btc every 300s; kalshi brief 08:00–12:29, scan 12:30–14:55, settle 16:00–23:30 CT; memecoin 09:00 / 15:00 / 21:00 windows.
- **Paper mode hard refuse:** kalshi without `paper_mode:true`; memecoin without `PAPER=True`.

### Desk state / control files
`pimp-trading.json`, `pimp-pause.json`, `pimp-learning.json`, `pimp-auto.json`, `pimp-good.json`, plus runs/heartbeat/audit/notes/alerts/backup under desk root.

---

## 1. sports-gap-paper

**Files:** `sports-gap-paper/gap_bot.py`, `README.md`

### Entry / BUY
Live ESPN game + matched Kalshi series (`KXNFLGAME`, `KXNCAAFGAME`, `KXNBAGAME`, `KXWNBAGAME`, `KXMLBGAME`, `KXNHLGAME`). Fair: ESPN WP (most leagues) or NHL Poisson model. Side = max of `fair − ask − fee`. Fee = `ceil(0.07·P·(1−P)·100)/100`.

Buy when all pass:
- Gap ≥ desk `min_edge` (default **0.04**); NHL model uses `need_edge + 0.02` (**0.06** when desk edge is 0.04)
- Not already holding `game_key`
- Home fair **outside** close-game band **[0.40, 0.60]**
- Spread `ask−bid` ≤ **0.05**
- Ask in **[0.05, 0.95]**
- Open positions &lt; desk `max_open_positions` (fallback 12)
- Enough paper cash; contracts via desk `paper_stake_dollars` / `contracts_for_stake` (fallback: &lt;80% → $20, else scale $20–$100)
- Bot-local daily loss stop: closed PnL today ≤ −desk `daily_loss_stop` ($150) → entries off
- Desk `learning_skip` for league + fair bucket

### Exit / SELL
1. **Gap closed:** bid − fee ≥ fair → sell at bid  
2. **Settle:** ESPN final; $1/contract if side wins else $0; ties wait  
No stop / trail / TP ladder. Each check **runs exits before new paper buys**.

### Failsafes
Bot-local: close-game band, spread, price bounds, max open, **intra-check max open risk**, cash, daily loss, learning skip, public GET fail → skip league. Desk: `entry_gate` on timer/manual run; pause; stake curve; min_edge override.

### State written
- `sports-gap-paper/state.json` — cash ($100 start), open, closed, runs  
- `sports-gap-paper/paper_trades.md` — check log (capped ~256KB)  
- `sports-gap-paper/quote_cache.json` — 60s GET cache  
- Desk `pimp-learning.json` on settle/sell  

### Desk override
Reads `load_settings` for min_edge, max_open, daily_loss_stop, stake. Subject to desk entry_gate. Pace **does not** loosen edge.

---

## 2. kalshi-sp500-paper

**Files:** `bot.py`, `signal_engine.py`, `risk_manager.py`, `Strategy.md`, `config.json`, `paper_sim.py`

### Entry / BUY (`scan`)
- Window **12:30–14:55 CT** (unless `--any-time`)
- Series `KXINXU`, settle **15:00 CT**
- Among YES/NO sides with ask in **[0.80, 0.90]**, pick highest ask (tie: tighter spread, YES, ticker)
- Re-confirm order book still in band
- Stake: `floor($25 / ask)` contracts (`max_stake_dollars: 25`), bankroll-capped **after taker fee**; `n < 1` → skip
- Desk `learning_skip("S&P", bucket(ask))`

### Exit / SELL
**Hold to Kalshi settlement only.** No stop, no TP. If unsettled and side bid &lt; **0.50** → log invalidation only (`invalidation_log_below`).

### Failsafes (`risk_manager` + config)
| Rule | Threshold |
|---|---|
| Kill switch | bankroll ≤ **$400** (`halted` until human) |
| Weekend | skip |
| News/holiday | `calendar.json` (FOMC, CPI, jobs, GDP/PCE, election±1, holidays/half-days) |
| Max trades/day | **1** |
| Daily loss | realized today ≤ −**$50** |
| paper_mode | must be `true` or refuse |
| Band empty / OB leave band | no trade |

### State written
- `paper_state.json` — bankroll ($500 start), open, closed, halted  
- `Trade_Ledger.md`, `Learning.md` (bot-local)  
- Desk `pimp-learning.json` on settle  

### Desk override
`entry_gate` blocks **scan** only (not settle/brief). Stake stays **$25 fixed** — ignores desk stake curve. Bot daily loss **$50** vs desk **$150** (both can apply; desk blocks before script). Pause applies. Calendar missing → warning only.

---

## 3. btc15m-signal

**File:** `btc15m-signal/btc15m_signal.py`

### Entry / BUY (signal + paper_buy)
Nearest open `KXBTC15M`. Side = YES if spot &gt; target else NO. `p = Φ(cushion/σ)`. Need `p ≥ ask + fee + 0.05`.

Hard skips if any fail:
| Check | Threshold |
|---|---|
| Minutes left | ≥ **10** |
| Edge buffer | **0.05** over ask+fee |
| Cushion | ≥ **$40** |
| z = cushion/σ | ≥ **0.5** (0.6 if Coinbase-only spot) |
| Ask band | **[0.65, 0.85]** |
| Spread | ≤ **0.03** |
| Depth at/below ask | ≥ **5** contracts |
| Last 5×1m candles | must **not** move toward target; unknown → skip |
| USD High news | ForexFactory ±**30** min of block → skip; calendar **fail-closed** if unavailable |
| Paper ask | **[0.05, 0.95]**; one open per ticker; open count &lt; **12** (hardcoded); cash; desk stake; learning_skip("BTC", …) |

σ = max(DVOL-implied, realized); if DVOL fails → realized × **1.2**.

### Exit / SELL
**Settle only** when Kalshi `result` ∈ {yes,no} after close_time.  
`TAKE_PROFIT_ADD=0.15` / `CAP=0.99` is **printed suggestion only — never executed**. No stop/trail.

### Failsafes
Signal checklist above; no spot/σ → skip; desk learning_skip; cash/open cap. **Subject to desk `entry_gate`** (`entry: True`, ROI system). No bot-local daily loss stop.

### State written
- `paper_account.json` — cash ($100), open, closed  
- `quote_cache.json`  
- Desk `pimp-learning.json` on settle  

### Desk override
Uses desk stake sizing. Pause stops timer/manual. entry_gate / desk daily-loss / max-open-risk **block** this action when hit. Hardcoded max 12 opens (not desk setting). Waivers: `settle_only_btc15m`, `tp_print_only`.

---

## 4. memecoin-paper

**Files:** `bot.py`, `config.py`

### Entry / BUY
DexScreener candidates → RugCheck facts → rule scorer. Flat ticket **$25**.

**FACTS (fail closed if missing):**
- age **30 min – 72 h**; liq ≥ **$30k**; ticket ≤ **1%** of pool  
- risk_score ≤ **40**; LP locked ≥ **90%**; top10 ≤ **30%**; dev ≤ **5%**; insiders ≤ **0**  
- confidence ≥ **0.7** (weights: mom 0.30, vol 0.25, liq 0.20, buy_pressure 0.25)  
- Optional Grok veto only (disabled)

**Risk gates:** already open; cooldown **24h** after close; `MAX_OPEN` **4**; `MAX_ENTRIES_PER_DAY` **6**; daily realized ≤ −**$50**; cash ≥ ticket; desk `learning_skip(symbol, conf bucket)`.

### Exit / SELL (strongest among bots)
| Rule | Threshold |
|---|---|
| Liq drop | ≥ **40%** from entry → full out |
| Hard stop | ≤ **−35%** from entry → full out |
| Ladder | **+100%** sell **50%**; **+200%** sell **25%** of original |
| Trail | after first ladder: ≥ **30%** off peak → rest out |
| Time stop | held ≥ **6h** and &lt; **+20%** → out |
| Unpriceable | HOLD (never invent price) |

Paper fill: **1%** swap fee + constant-product impact.

### Failsafes
All facts fail-closed; daily halt $50; max open 4; cooldown; `PAPER` must be True. Desk entry_gate applies. Stake is **flat $25** — ignores desk stake curve.

### State written
- `positions.json` — cash ($100), open, cooldown, realized_pnl  
- `trades.csv`, `checks.csv`  
- Desk learning on full close  

### Desk override
entry_gate / pause. Own limits ($50 daily, 4 open) usually tighter than desk. No desk min_edge (not a Kalshi-edge bot).

---

## 5. kalshi-sized (`kalshi-sized-paper/bot.py`)

Live Tower 5: KXINXU with desk **Kelly-lite** stake (84–92¢ band), model-flip sell under 50¢, settle on result. Fallback `_sized_view()` only if the folder is missing from a checkout.

---

## Cross-bot gaps (ops-relevant)

| Gap | Detail |
|---|---|
| **Weak / missing sells** | Kalshi S&P: settle-only, invalidation log-only. BTC: settle-only; TP is advisory print. Sports: gap-close or settle; no stop/trail. |
| **Strong sells** | Memecoin only (stop / ladder / trail / time / liq). |
| **Desk-only failsafes** | Desk daily $150 / max open 12 / max risk $100 gate sports, kalshi scan, memecoin, **and BTC**. Quiet hours ≠ trade halt. Pace does not loosen edge. |
| **Bot vs desk mismatch** | Kalshi daily $50 + $25 stake vs desk $150 + $20–$100 curve. Memecoin $25 flat + max 4. BTC max-open hardcoded 12. |
| **Learning skip** | Shared desk count (≥8 settles, &lt;40% hits) — sports/kalshi/btc/meme all call it; not a model. |
| **Double daily-loss** | Sports implements desk stop inside script; also blocked by entry_gate. Kalshi has separate $50. Memecoin $50. BTC none local (desk gate only). |

---

## Quick reference — who can paper-buy under desk gate

| Bot | Desk `entry_gate` | Desk stake | Own daily stop | Own max open | Exit quality |
|---|---|---|---|---|---|
| sports-gap | Yes | Yes | Yes ($150 via desk cfg) | Yes (desk) | Partial (gap/settle) |
| kalshi-sp scan | Yes | No ($25) | Yes ($50) | 1/day | Weak (settle only) |
| btc15m | **Yes** | Yes | No | Hardcoded 12 | Weak (settle; TP print-only) |
| memecoin | Yes | No ($25 flat) | Yes ($50) | 4 | Strong |
| kalshi-sized | Kelly-lite KXINXU 84–92¢ | Model-flip &lt;50¢ / settle | Calendar + desk gate + kill | Partial |
