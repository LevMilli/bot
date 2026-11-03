# Positive ROI plan — shipped slice

Paper only. No profit guarantee. Fee floors stay locked.

Full narrative (store): `docs/positive-roi-master-plan.md` on the agent store.
Interactive: Positive ROI Master Plan canvas.

## Shipped

### #104 — P0–P3 starter

| Ticket | Where |
| --- | --- |
| M3 fit→buy journals | `desk_roi_plan.record_fit` / `fit_buy_rate` → `desk_master` M3 |
| M4 latency timers | `desk_roi_plan.record_latency` / `latency_p50` → `desk_master` M4 |
| Firm bleed + capital misplaced | `desk_master.master_summary` → `bleed`, `capital_misplaced`, `roi_plan` |
| W0 baseline auto-capture | first `master_summary` with bots writes `desk_roi_baseline.json` |
| Near-miss weekly card | `desk_roi_plan.near_miss_weekly_card` (`auto_promote=False`) |
| Sports CLV completeness | `clv_row_complete` / `clv_completeness` + tests |
| INX band research harness | `run_inx_band_research` — **does not** change live 80–90¢ band |
| Commodity model-flip exits | `commodity-15m-paper/bot.py` `manage_model_flips` |
| BTC real take-profit | `btc15m_signal.manage_take_profits` (no longer print-only) |

### #105 — sports exit quality

| Ticket | Where |
| --- | --- |
| Sports M4 latency | `gap_bot.run` → `record_latency(sports-gap)` |
| Sports M3 fit journals | buy/block → `record_fit` |
| Sports hard-stop **shadow** | bid ≤ entry − 12¢ logs would-stop; `SPORTS_HARD_STOP_LIVE=False` |

### #106 — INX twin / macro

| Ticket | Where |
| --- | --- |
| Anti-double sized vs S&P | `desk_inx.anti_double_blocks` in sized `step_scan` |
| Twin edge ≥ venue + 1¢ | `desk_inx.twin_edge_blocks` |
| Pre-FOMC calm / post-print +30m | `desk_inx.inx_entry_blocks` on both INX bots |

### #108 — learn v2 / adverse cool

| Ticket | Where |
| --- | --- |
| Learning skip v2 | `pimp_desk.learning_skip(..., side, hour_ct)` |
| Adverse cool-off | `desk_roi_plan.record_adverse_fill` / `adverse_cool_blocks` |
| Weekly scorecard API | `desk_roi_plan.capture_weekly_scorecard` |

### Scorecard wire — daily Masters board

| Ticket | Where |
| --- | --- |
| Chicago-day scorecard on master | `desk_master.master_summary` → `roi_plan.weekly_scorecard` |
| Public latest reader | `desk_roi_plan.latest_weekly_scorecard` |

### Master graduation + meme retirement

| Ticket | Where |
| --- | --- |
| M5 util + M7 Gate B on tower rows | `desk_master.tower_master_row` (v3) |
| Graduation checklist (2 Chicago weeks) | `desk_roi_plan.capture_graduation_week` / `graduation_board` |
| Meme 20d retirement clock | `desk_roi_plan.meme_retirement_clock` — recommend pause, never auto-retire |

### Hillclimb kill detector

| Ticket | Where |
| --- | --- |
| Firm M1 proxy | `desk_roi_plan.firm_taxed_m1` |
| Kill rule M3↑ M1↓ × 2 weeks | `capture_hillclimb_week` / `hillclimb_kill_status` — flag only, no auto param write |
| Masters wire | `desk_master.master_summary` → `hillclimb_kill` |

### Profit-lock harvest

| Ticket | Where |
| --- | --- |
| Chicago-week firm PnL ledger | `desk_roi_plan.capture_profit_lock` |
| Safe-mode 0.5× after $40 target | `profit_lock_size_mult` / `profit_lock_status` |
| Masters wire | `desk_master.master_summary` → `profit_lock` |
| Kelly path applies 0.5× | `pimp_desk.stake_dollars_for` notes `profit_lock_mult` |

### Next

| Ticket | Where |
| --- | --- |
| Sports hard-stop promote after n≥30 | staff gate; `SPORTS_HARD_STOP_LIVE` stays False |
| INX band promote | only after research-week artifact |
| Skip-regret twin weekly review | wire into scorecard |
| Daily R budget per tower | settle-only after budget |

## Hard rules unchanged

- Venue floors: sports 0.06 / BTC+commodity 0.05 / INX+DEX 0.02
- Starve: n≥4, factor 0.15
- Meme red lock −$8; INX halt $460
- Kill: M3↑ with M1↓ for 2 Chicago weeks → revert lever

## Tests

```bash
python -m unittest test_positive_roi_plan_slice.py desk_roi_plan desk_master -v
```
