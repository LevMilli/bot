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
| `min_edge` | **0.06** | Desk fallback after fee; sports `MIN_GAP=0.06` |
| `venue_min_edge` | sports **0.06** / BTC+commodity **0.05** / INX+DEX **0.02** | Locked floors — raise OK, lower rejected |
| `pace_min` / `pace_target` | 6 / 12 | Display/count only — **does not waive edge** (`edge_for_hour` returns saved edge, `loosened=False`) |
| `quiet_start` / `quiet_end` | 22:00 / 07:00 CT | Alerts held; bots still run |
| `week_goal` | $25 | UI only |
| `starve_min_n` / `starve_factor` | **4** / **0.15** | Expectancy starve |
| `model_flip_exits` | True | Fee-clear + INX flips when adverse |

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
- **Sports idle:** if last sports summary says no live games, timer gap → 900s (else sports every **180s**).
- **AUTO cadence:** sports **180s** / BTC **60s** / commodity **90s** / meme **180s**.
- **INX AUTO:** kalshi-sp brief 08:00–11:59; forced scans 12:05 / 13:05 / 14:20; **settle+flip polls 13:00–15:55** then 16:00–23:30. Sized twin: run 12:05–14:55; settle 13:00–15:55 + 16:05–23:30.
- **Paper mode hard refuse:** kalshi without `paper_mode:true`; memecoin without `PAPER=True`.

### Desk state / control files
`pimp-trading.json`, `pimp-pause.json`, `pimp-learning.json`, `pimp-auto.json`, `pimp-good.json`, plus runs/heartbeat/audit/notes/alerts/backup under desk root.

---

## 1. sports-gap-paper

**Files:** `sports-gap-paper/gap_bot.py`, `README.md`

### Entry / BUY
Live ESPN game + matched Kalshi series (`KXNFLGAME`, `KXNCAAFGAME`, `KXNBAGAME`, `KXWNBAGAME`, `KXMLBGAME`, `KXNHLGAME`). Fair: ESPN WP (most leagues) or NHL Poisson model. Side = max of `fair − ask − fee`. Fee = `ceil(0.07·P·(1−P)·100)/100`.

Buy when all pass:
- Gap ≥ desk `min_edge` / venue floor (default **0.06**); NHL model uses `need_edge + 0.02` (**0.08** when desk edge is 0.06); speed lane +`MIN_GAP_SPEED_EXTRA` (0.02)
- Not already holding `game_key`
- Home fair **outside** close-game band **[0.40, 0.60]**
- Spread `ask−bid` ≤ **0.05**
- Ask in **[0.05, 0.92]** (`PRICE_BOUNDS`, 92¢ cap)
- Up to **4** buys per check (`MAX_BUYS_PER_CHECK`)
- Pre-game books watched from **3 hours** (180 min, `PREGAME_WINDOW_MIN`) before start
- Open positions &lt; desk `max_open_positions` (fallback 12)
- Enough paper cash; contracts via desk `paper_stake_dollars` / `contracts_for_stake` (fallback: &lt;80% → $20, else scale $20–$100)
- Bot-local daily loss stop: closed PnL today ≤ −desk `daily_loss_stop` ($150) → entries off
- Desk `learning_skip` for league + fair bucket
- Red-day caps: `min(today, realized)` &lt; 0 → max 2 buys + speed off; ≤ −$10 → max 1

Re-synced to the code on Nov 13, 2026 (plan step 458). `test_plan_docs.py` pins the 92¢ cap, 4 buys and 3-hour pre-game window to `gap_bot.py`.

### Exit / SELL
1. **Hard-stop shadow:** bid ≤ entry − **12¢** → log would-have; live sell staff-gated (`SPORTS_HARD_STOP_LIVE=False`)
2. **Time-to-final shadow:** ≤**5m** regulation left + underwater mark → log; live staff-gated (`SPORTS_TIME_FINAL_LIVE=False`)
3. **Gap-decay:** tip edge that died mid-game → sell
4. **Model-flip:** fair moves against entry by desk `model_flip_delta` (0.06)
5. **Gap closed:** bid − fee ≥ fair → sell at bid
6. **Scale-out:** fair +**8¢** since entry → sell ~50% (runner kept)
7. **Settle:** ESPN final; $1/contract if side wins else $0; ties wait
Each check **runs exits before new paper buys**.

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
1. **Model-flip:** unsettled and side bid &lt; **0.50** → **paper sell** at bid minus taker fee (`model_flip_sell` / desk `model_flip_exits`); mid-hold settle polls **13:00–15:55 CT** so flips fire before binary wipe
2. **Settle:** Kalshi result yes/no after **15:00 CT**
Residual `1−ask−fee` is **not** edge — bots call `desk_inx.refuse_residual_as_edge()` until a real model clears.

### Failsafes (`risk_manager` + config)
| Rule | Threshold |
|---|---|
| Kill switch | bankroll ≤ **$400** (`halted` until human) |
| Drawdown halt | cash ≤ **$460** → entries off |
| Weekend | skip |
| News/holiday | `calendar.json` (FOMC, CPI, jobs, GDP/PCE, election±1, holidays/half-days) |
| Pre-FOMC / post-print | `desk_inx.inx_entry_blocks` (+30m post macro) |
| Max trades/day | **1** |
| Daily loss | realized today ≤ −**$25** (`daily_loss_limit`) |
| paper_mode | must be `true` or refuse |
| Band empty / OB leave band | no trade |
| Midnight reload | blocked while `realized < 0` (no fresh $500 for structural losers) |

### State written
- `paper_state.json` — bankroll ($500 start), open, closed, halted  
- `Trade_Ledger.md`, `Learning.md` (bot-local)  
- Desk `pimp-learning.json` on settle  

### Desk override
`entry_gate` blocks **scan** only (not settle/brief). Stake stays **$25 fixed** — ignores desk stake curve. Bot daily loss **$25** vs desk **$150** (both can apply; desk blocks before script). Pause applies. Calendar missing → warning only.

---

## 3. btc15m-signal

**File:** `btc15m-signal/btc15m_signal.py`

### Entry / BUY (signal + paper_buy)
Nearest open `KXBTC15M`. Side = YES if spot &gt; target else NO. `p = Φ(cushion/σ)`. Need `p ≥ ask + fee + 0.05`.

Hard skips if any fail:
| Check | Threshold |
|---|---|
| Minutes left | ≥ **10** (`MIN_MINUTES_LEFT`) |
| Model chance | ≥ **0.80** accurate lane / **0.72** speed lane with +**0.02** extra edge |
| Edge buffer | **0.05** over ask+fee (locked `kalshi_btc15m` floor) |
| Cushion | ≥ **$35** BTC (`MIN_CUSHION_USD`), ≥ **$1.50** ETH (`MIN_CUSHION_ETH`) |
| z = cushion/σ | ≥ **0.60** (0.55 speed lane; **0.75** if Coinbase-only spot) |
| Ask band | **[0.70, 0.92]** (`ASK_MIN`, `ASK_MAX`) |
| Spread | ≤ **0.04** (`MAX_SPREAD`) |
| Depth at/below ask | ≥ **3** contracts (`MIN_DEPTH`) |
| Buys per check | up to **3** (`MAX_BUYS_PER_CHECK`) |
| Last 5×1m candles | must **not** move toward target; unknown → skip |
| USD High news | ForexFactory ±**30** min of block → skip; calendar **fail-closed** if unavailable |
| Paper ask | **[0.05, 0.95]**; one open per ticker; open count &lt; **12** (hardcoded); cash; desk stake; learning_skip("BTC", …) |

Re-synced to the code on Nov 13, 2026 (plan step 482). `test_plan_docs.py` pins these numbers to `btc15m_signal.py`.

σ = max(DVOL-implied, realized); if DVOL fails → realized × **1.2**.

### Exit / SELL
1. **Take-profit:** `TAKE_PROFIT_ADD=0.15` / `CAP=0.99` **executed** via `manage_take_profits` → `paper_sell` when bid ≥ TP (real sell path)
2. **Model-flip:** side/fair flips against the open → flatten
3. **Settle:** Kalshi `result` ∈ {yes,no} after close_time
No stop/trail. Adverse cool (≥5¢ mark drop → 20m) + anti-revenge (30m) on desk path.

### Failsafes
Signal checklist above; no spot/σ → skip; desk learning_skip; cash/open cap. **Subject to desk `entry_gate`** (`entry: True`, ROI system). No bot-local daily loss stop. Venue floor `kalshi_btc15m` **0.05** locked.

### State written
- `paper_account.json` — cash ($100), open, closed  
- `quote_cache.json`  
- Desk `pimp-learning.json` on settle  

### Desk override
Uses desk stake sizing. Pause stops timer/manual. entry_gate / desk daily-loss / max-open-risk **block** this action when hit. Hardcoded max 12 opens (not desk setting). TP is a real `paper_sell` — no advisory-only waiver.

---

## 4. memecoin-paper

**Files:** `bot.py`, `config.py`

### Entry / BUY
DexScreener candidates → RugCheck facts → rule scorer. Flat ticket **$25**.

**FACTS (fail closed if missing):**
- age **30 min – 72 h**; liq ≥ **$30k**; ticket ≤ **1%** of pool  
- risk_score ≤ **40**; LP locked ≥ **90%**; top10 ≤ **30%**; dev ≤ **5%**; insiders ≤ **0**  
- confidence ≥ **0.80** accurate / **0.72** speed (weights: mom 0.30, vol 0.25, liq 0.20, buy_pressure 0.25)  
- Optional Grok veto only (disabled)

**Risk gates:** already open; cooldown **12h** after close; `MAX_OPEN` **6** (red **1**); `MAX_ENTRIES_PER_DAY` **8**; red lock today ≤ −**$5** → entries off; daily halt ≤ −**$150**; cash ≥ ticket; desk `learning_skip(mint, conf bucket)` (key is **mint**, not symbol).

### Exit / SELL (strongest among bots)
| Rule | Threshold |
|---|---|
| Liq drop | ≥ **35%** from entry → full out |
| Hard stop | ≤ **−12%** from entry → full out |
| Model-flip | h1 mom ≤ **−6%** (before stop) |
| Ladder | **+100%** sell **50%**; **+200%** sell **25%** of original |
| Trail | after first ladder: ≥ **25%** off peak → rest out |
| Time stop | held ≥ **4h** and &lt; **+20%** → out |
| Unpriceable | HOLD (never invent price) |

Paper fill: **1%** swap fee + constant-product impact. `expand_volume` stays **false**.

### Failsafes
All facts fail-closed; daily halt $150; red lock −$5; max open 6/1; cooldown; `PAPER` must be True. Desk entry_gate applies. Stake is **flat $25** (red $10) — ignores desk stake curve.

### State written
- `positions.json` — cash ($100), open, cooldown, realized_pnl  
- `trades.csv`, `checks.csv`  
- Desk learning on full close  

### Desk override
entry_gate / pause. Own limits ($150 daily, −$5 red lock, max 6/1 open). No desk min_edge (not a Kalshi-edge bot).

---

## 5. kalshi-sized (`kalshi-sized-paper/bot.py`)

Live Tower 5: KXINXU with desk **Kelly-lite** stake (84–92¢ band), model-flip sell under 50¢, settle on result. Fallback `_sized_view()` only if the folder is missing from a checkout.

---

## Cross-bot gaps (ops-relevant)

| Gap | Detail |
|---|---|
| **Partial sells** | Kalshi S&P/sized: model-flip &lt;50¢ (fee'd) + settle. BTC: real TP + model-flip + settle. Commodity: model-flip + time-stop shadow + settle. Sports: gap-decay / scale-out / hard-stop+time-final shadows + settle. |
| **Strong sells** | Memecoin (stop −12% / ladder / trail / time / liq / model-flip). |
| **Desk-only failsafes** | Desk daily $150 / max open 12 / max risk $100 gate sports, kalshi scan, memecoin, **and BTC**. Quiet hours ≠ trade halt. Pace does not loosen edge. Floors locked 0.06/0.05/0.02. |
| **Bot vs desk mismatch** | Kalshi daily **$25** + $25 stake vs desk $150 + $20–$100 curve. Memecoin $25 flat + max 6 (red 1). BTC max-open hardcoded 12. |
| **Learning skip** | Shared desk count (≥8 settles, &lt;40% hits) — sports/kalshi/btc/meme all call it; meme key is **mint**. |
| **Double daily-loss** | Sports implements desk stop inside script; also blocked by entry_gate. Kalshi has separate $25. Memecoin $150 + −$5 red lock. BTC none local (desk gate only). |

---

## Quick reference — who can paper-buy under desk gate

| Bot | Desk `entry_gate` | Desk stake | Own daily stop | Own max open | Exit quality |
|---|---|---|---|---|---|
| sports-gap | Yes | Yes | Yes ($150 via desk cfg) | Yes (desk) | Partial (gap-decay/scale-out/shadows/settle) |
| kalshi-sp scan | Yes | No ($25) | Yes ($25) | 1/day | Partial (model-flip fee'd + settle) |
| btc15m | **Yes** | Yes | No | Hardcoded 12 | Partial (real TP + model-flip + settle) |
| memecoin | Yes | No ($25 flat) | Yes ($150 + −$5 lock) | 6 / red 1 | Strong |
| kalshi-sized | Yes | Kelly-lite | Yes ($25) | 1/day | Partial (model-flip + settle) |

---

## Sync stamp (E9 docs closeout #964)

Last re-sync after E9 chaos/doctrine observe packs (#540/#541). **No exit/fee change in that ship.** Venue floors still locked sports **0.06** / BTC+commodity **0.05** / INX+DEX **0.02** (chaos drill #979 asserts). LIVE off. Soft-max tip invent exhausted — inventory text only; no new tip chips.
