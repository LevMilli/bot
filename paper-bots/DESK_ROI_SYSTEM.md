# Desk ROI system

Paper-only operating system every tower must follow to **protect bankroll and keep only positive-expectancy habits**. This is learning software, not financial advice — “maximize ROI” here means **discipline + edge after costs**, not guaranteed profit.

Source of truth for live numbers: `pimp_desk.snapshot()`. Policy object: `snapshot.roi_system` (from `pimp_desk.ROI_POLICY`).

Related: `BUY_SELL_FAILSAFE_INVENTORY.md` (thresholds), `TEAM_ROLES.md`.

---

## 1. North star

**Only paper-buy when edge after fees/slippage clears the desk bar, risk budget is open, and an exit plan already exists.**  
Cut repeating losers via learning skip. Never size up to “make it back.” Never invent fills.

---

## 2. Universal rules (all present bots)

| # | Rule | Why |
| --- | --- | --- |
| R1 | **Paper only** — no live keys, wallets, or real orders | Hard product constraint |
| R2 | **Edge after costs** ≥ venue `venue_min_edge` (fallback desk `min_edge`) | No zero/negative EV entries |
| R3 | **Desk entry_gate** blocks new entries on daily loss / max opens / open risk | Ruin control |
| R4 | **Stake** from Kelly-lite (capped by curve + open risk) unless a fixed ticket (Kalshi/meme $25) | Consistency + no revenge size |
| R5 | **Exit plan before entry** — model-flip and/or settle/stop/trail/time/liq | Undefined exits destroy ROI |
| R6 | **Learning skip** on cold market×bucket (≥8 settles, &lt;40% hits) | Stop feeding losing patterns |
| R7 | **Pause honored** | Human override |
| R8 | **Quiet hours ≠ trade halt** (alerts only) — do not treat them as a risk control | Avoid false safety |
| R9 | **Pace never waives edge** | Volume ≠ edge |
| R10 | **One position key** — no duplicate game/ticker/mint | Concentration risk |
| R11 | **Snapshot path only** for city/staff — never re-parse bot files in UI | Accuracy |
| R12 | **Tower 5 Sized Kalshi** is live when `kalshi-sized-paper` is present — no fake substitute | Accuracy |
| R18 | **Midnight CT** — out-of-ammo / underwater flat towers reload cash + reset P&L + log/learn; winners untouched | Bankroll |
| R13 | **Correlation veto** — paired directional factors cannot stack when the open book is as good or better | Portfolio heat |
| R14 | **Fee-aware venue bars** — sports / BTC / INX / DEX | Honest edge |
| R15 | **Model-flip exits** fire before hard stops / settle-only waits | Cut losers earlier |
| R16 | **Expectancy starve** throttles losers after enough settles | Capital allocation |
| R17 | **Shadow bots** spend no desk cash; promote only after expectancy gates | Research loop |

---

## 3. Risk budget (desk defaults)

| Control | Default | Role |
| --- | --- | --- |
| Daily loss stop | $150 | Hard stop new entries (Chicago day) |
| Max open positions | 12 | Cap concurrent risk |
| Max open risk | $100 | Cap dollars at risk |
| Stake &lt;80% prob | ~$20 | Small when uncertain |
| Stake ≥80% | $20–$100 | Size into stronger model probs |
| Learning | 8 settles / 40% hit | Skip cold buckets |

Bot-local stops that are **tighter** than desk (Kalshi −$50, meme −$50, max 4 meme opens) **win**.

---

## 4. Exit quality ladder (ROI order)

| Grade | Meaning | Desk bots today |
| --- | --- | --- |
| **strong** | Active stop + scale-out + trail/time/liq | Memecoin |
| **partial** | Path to exit before full adverse run (gap-close / model-flip / TP) + settle | Sports gap, BTC 15m (real TP + flip), commodity (flip), INX |
| **weak** | Settle-only with hard entry filters | *(avoid — upgrade)* |
| **absent** | No script | *(legacy only)* |

**Locked venue floors (cannot lower):** sports 0.06 · BTC/commodity 0.05 · INX/DEX 0.02 · Coinbase spot 0.05 (excess return after the round trip, not a probability).  
**Starve defaults:** `starve_min_n=4`, `starve_factor=0.15`. **Meme red lock:** −$8 / stop −12% / max 1 open when red. **INX drawdown halt:** cash ≤ $460.

**ROI system target:** no present bot may stay below **partial** without an explicit waiver in `roi_system.waivers`. Weak books must at least: (a) hard entry filters, (b) calendar/news blocks where relevant, (c) desk entry_gate, (d) invalidation logging.

---

## 5. Per-bot compliance checklist

### Sports gap → keep **partial**, push toward strong
- Buy only on edge after fee; close-game band; spread/price bounds.
- **Required:** gap-close sell + settle.
- **Next upgrade:** hard-stop + time-to-final shadows shipped (staff promote for live); measure n→30 EV≥0 before arming.

### Kalshi S&P → **partial** (model-flip under 50¢ + settle)
- Band 80–90¢, 1/day, news calendar, −$50 day, kill ≤$400.
- Model-flip paper-sells when side bid collapses under 50¢; else settle at 3 PM CT.
- Waiver: `fixed_ticket_25` only.

### BTC 15m → **partial** + **must be entry_gated**
- Full signal checklist; Kelly-lite stake; venue `kalshi_btc15m` edge.
- Model-flip flatten when side/fair flips against the open; else settle.
- Shadow `edge08` runs on a parallel account and never spends desk cash.

### Memecoin → **strong** reference implementation
- Facts fail-closed; stop/ladder/trail/time/liq.
- Flat $25 is an approved fixed-ticket waiver (`fixed_ticket_25`).

### Coinbase spot → **partial**, shadow only
- Public daily candles. ETH-USD and SOL-USD longs. BTC-USD research-only.
- Rule: cross above the 50-day average. Cost is the US intro taker round trip (0.90% + 0.10% slip each side).
- Buy only when that rule's own closed trades, and the latest 20 of them, have n ≥ 20, hit ≥ 40%, median net > 0, and mean net ≥ 0.05. A fat-tail average with a losing typical trade stays flat. The unfinished daily candle is ignored. After 8 paper settles the book itself must still clear that bar.
- Exits match the sample: −15% stop at the close, model-flip back under the average, 120-day time stop.
- Own $500 sleeve, fixed $25, max 1 open. No desk cash and no tower risk share until a person graduates incubation (n ≥ 50).
- Waiver: `fixed_ticket_25`, `shadow_only`.

### Sized Kalshi → **partial**
- KXINXU 84–92¢ band; desk Kelly-lite stake; model-flip under 50¢ + settle.
- Own paper bankroll; desk entry_gate + venue `kalshi_inx` edge.

---

## 6. Decision loop (every timer/manual check)

```
pause? → stop
paper mode ok? → else refuse
entry action? → entry_gate (desk) → else settle/brief only
learning skip? → skip
bot-local failsafes / edge? → else skip
open / size within stake + cash → else skip
paper fill at real public price → record
on each check: run sell plan (stop/trail/settle) before new buys when the script supports it
```

---

## 7. What “maximize positive ROI” means in practice

1. **Survive** — daily stop + open risk beat hero trades.  
2. **Select** — learning skip + edge bar remove cold garbage.  
3. **Size** — stake curve / fixed tickets, never double-up after a loss.  
4. **Exit** — prefer strong exit books; don’t romanticize settle-only.  
5. **Measure** — snapshot `plans`, `gates_hit`, `desk.ops`, `roi_system.compliance`.

There is **no** claim of live alpha. Paper results stay optimistic.

---

## 8. Implementation map

| Piece | Location |
| --- | --- |
| Policy object | `pimp_desk.ROI_POLICY` → `snapshot["roi_system"]` |
| Per-bot plans | `BOT_PLANS` / `bot_plans()` |
| Live gates | `gates_hit` / `entry_gate` |
| Staff + city | PIMP-TRADING cards, APEX-CITY monitors |
| Follow-ups | Sports hard stop; BTC real TP or drop; sized Kalshi when present |

---

## 9. Speed runbook (M4) — staff drills

Fee floors stay locked. Speed never waives edge. Cadence targets (AUTO): BTC **60s**, commodity **90s**, sports **180s** (tip windows denser without floor waive). Observe: `fee_clear_cadence_health_board` · `make living-cadence-health` · Masters `roi_plan.fee_clear_cadence`.

**M4 bars:** sports p50 ≤45s (n≥5); BTC/commodity p50 ≤20s (n≥5).

### Drill A — M4 red, M1 green
Latency is the problem, not edge. Fix perf (cache hits, prefetch, stage timers). **Do not** loosen venue floors, soft-relax edge, or raise max_buys to “catch up.”

### Drill B — M4 green, M1 red
Not a speed problem. Do not densify cadence further. Kill last volume/selective lever; starve losers; keep meme/INX capped. Wait for fee-clear EV, not faster polls.
