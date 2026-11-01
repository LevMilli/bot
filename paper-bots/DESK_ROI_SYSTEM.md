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
| R2 | **Edge after costs** ≥ desk `min_edge` (or bot-equivalent buffer, e.g. BTC +0.05) | No zero/negative EV entries |
| R3 | **Desk entry_gate** blocks new entries on daily loss / max opens / open risk | Ruin control |
| R4 | **Stake** from desk curve unless a bot documents a fixed ticket (Kalshi/meme $25) | Consistency + no revenge size |
| R5 | **Exit plan before entry** — settle window and/or stop/trail/time/liq | Undefined exits destroy ROI |
| R6 | **Learning skip** on cold market×bucket (≥8 settles, &lt;40% hits) | Stop feeding losing patterns |
| R7 | **Pause honored** | Human override |
| R8 | **Quiet hours ≠ trade halt** (alerts only) — do not treat them as a risk control | Avoid false safety |
| R9 | **Pace never waives edge** | Volume ≠ edge |
| R10 | **One position key** — no duplicate game/ticker/mint | Concentration risk |
| R11 | **Snapshot path only** for city/staff — never re-parse bot files in UI | Accuracy |
| R12 | **Tower 5 absent** stays live offline until sized Kalshi lands — no substitute | Accuracy |

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
| **partial** | Path to exit before full adverse run (gap-close) + settle | Sports gap |
| **weak** | Settle-only (optional advisory TP) | Kalshi S&P, BTC 15m |
| **absent** | No script | Sized Kalshi |

**ROI system target:** no present bot may stay below **partial** without an explicit waiver in `roi_system.waivers`. Weak books must at least: (a) hard entry filters, (b) calendar/news blocks where relevant, (c) desk entry_gate, (d) invalidation logging.

---

## 5. Per-bot compliance checklist

### Sports gap → keep **partial**, push toward strong
- Buy only on edge after fee; close-game band; spread/price bounds.
- **Required:** gap-close sell + settle.
- **Next upgrade:** optional hard stop / time-to-final risk trim (separate PR).

### Kalshi S&P → **weak** allowed with waiver
- Band 80–90¢, 1/day, news calendar, −$50 day, kill ≤$400.
- Settle-only is intentional; invalidation &lt;50¢ must stay visible on monitors.
- Waiver: `settle_only_inx`.

### BTC 15m → **weak** + **must be entry_gated**
- Full signal checklist; desk stake.
- **ROI system:** `run` is an entry action → desk daily loss / open risk apply.
- Advisory TP must not be presented as an executed sell; either implement later or keep labeled print-only.

### Memecoin → **strong** reference implementation
- Facts fail-closed; stop/ladder/trail/time/liq.
- Flat $25 is an approved fixed-ticket waiver (`fixed_ticket_25`).

### Sized Kalshi → absent
- No buys until present; show offline plan only.

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
| Staff + city | PIMP-TRADING cards, PIMP-CITY monitors |
| Follow-ups | Sports hard stop; BTC real TP or drop; sized Kalshi when present |
