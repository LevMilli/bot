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

### Skip-regret weekly review

| Ticket | Where |
| --- | --- |
| Weekly twin card | `desk_roi_plan.skip_regret_weekly_card` (`auto_promote=False`) |
| Masters wire | `desk_master.master_summary` → `roi_plan.skip_regret_weekly` |

### Sports hard-stop staff promote

| Ticket | Where |
| --- | --- |
| Promote readiness (n≥30, shadow EV≥0) | `sports_hard_stop_shadow_summary.promote_ready` |
| Staff arm/disarm live sells | `staff_set_sports_hard_stop_live` → promote JSON |
| Runtime live check | `sports_hard_stop_is_live` (gap_bot); code `SPORTS_HARD_STOP_LIVE` stays False |

### Daily R budget

| Ticket | Where |
| --- | --- |
| Per-tower R budgets (sports 1.5R …) | `desk_roi_plan.DAILY_R_BUDGET` / `daily_r_blocks` |
| Fee-clear bots settle-only after target | sports / BTC / commodity buy loops |
| Masters board | `roi_plan.daily_r` via `capture_daily_r_board` |

### Anti-revenge cool

| Ticket | Where |
| --- | --- |
| Same-market block after stop/flip | `record_anti_revenge` / `anti_revenge_blocks` (30m) |
| Wired on exits + buys | sports / BTC / commodity |

### INX band staff promote

| Ticket | Where |
| --- | --- |
| Promote-ready after research leader n≥20 | `inx_band_promote_status` |
| Staff arm/clear artifact | `staff_promote_inx_band` / `staff_clear_inx_band_promote` |
| Bots honor promote | `effective_inx_ask_band` in kalshi-sp / sized |

### Correlation matrix + series haircut

| Ticket | Where |
| --- | --- |
| Firm matrix board | `desk_profit.correlation_matrix` → Masters `roi_plan.correlation` |
| BTC↔INX hard veto | existing `correlation_pairs` (unchanged) |
| WTI↔Brent 0.5× haircut | `series_corr_haircut` in commodity `paper_buy` |

### Incubation lane

| Ticket | Where |
| --- | --- |
| New series settle counter | `record_incubation_settle` (n≥50) |
| Staff graduate | `staff_graduate_incubation` (`auto_promote=False`) |
| Masters board | `incubation_board` → `roi_plan.incubation` |

### Ruin drill UX

| Ticket | Where |
| --- | --- |
| Soft / hard / nuclear levels | `set_ruin_drill` / `clear_ruin_drill` |
| Entry gate blocks on active drill | `pimp_desk.entry_gate` via `ruin_drill_blocks_entries` |
| Hard/nuclear pauses all bots | uses existing `set_pause(all_bots=True)` |

### Tax / fee ledger

| Ticket | Where |
| --- | --- |
| Fee + 1¢ fill-tax rows | `record_fee_ledger` / `estimate_kalshi_fee` |
| Completeness ≥80% vs closes | `fee_ledger_completeness` |
| Wired on exits/settles | sports / BTC / commodity |
| Masters board | `roi_plan.fee_ledger` + `fee_ledger_completeness` |

### Clock-skew / stale-world skip

| Ticket | Where |
| --- | --- |
| Loop latency bars | sports 90s / 15m 40s (`STALE_LOOP_SEC`) |
| Quote / clock skew max | 30s (`CLOCK_SKEW_MAX_SEC`) |
| Entry skip API | `stale_world_blocks` / `stale_world_status` |
| Wired on buys | sports / BTC / commodity |
| Masters board | `roi_plan.stale_world` |

### Helper Gate A

| Ticket | Where |
| --- | --- |
| Helper-attributed fills | `record_helper_fill` (BTC tags `calendar_scanner`) |
| Taxed EV Gate A | `helper_gate_a` (n≥20, EV≥0) |
| Staff autonomy arm | `staff_set_helper_autonomy` (`auto_promote=False`) |
| Place-alone block | `helper_autonomy_blocks` / `helpers.may_place_alone` |
| Masters board | `roi_plan.helper_gate_a` |

### Weekly cold harvest

| Ticket | Where |
| --- | --- |
| 30–50% of green week PnL | `capture_cold_harvest` (default 40%) |
| Cold ledger total | `cold_harvest_status` → `desk_cold_harvest.json` |
| Masters board | `roi_plan.cold_harvest` (daily refresh) |
| Distinct from profit-lock | size 0.5× stays on profit-lock; cold is habit ledger |

### Hillclimb lever allowlist

| Ticket | Where |
| --- | --- |
| Allowlist | `VOL_SAFE` / `HIT_FOR_BIG` / `venue_min_edge_btc` / `min_cushion_btc` / `kelly_fraction` |
| One per Chicago week | `staff_pick_hillclimb_lever` (midweek thrash banned) |
| Raise-only floors | BTC edge/cushion reject soften proposals |
| Sunday demote | `staff_demote_hillclimb_lever` |
| Kill card uses active | `capture_hillclimb_week` reads active lever |
| Masters board | `roi_plan.hillclimb_lever` |

### Dual-control + quarterly re-baseline

| Ticket | Where |
| --- | --- |
| Live checklist stub | `dual_control_status` / `staff_sign_dual_control` |
| Two-staff confirm | primary ≠ secondary required for `arm_ready_paper` |
| Hard live lock | `LIVE_ORDERS_ENABLED=False` (stub never arms create-order) |
| Quarterly W-baseline | `capture_quarterly_rebaseline` / `quarterly_rebaseline_status` |
| Masters board | `roi_plan.dual_control` + `quarterly_rebaseline` |

### Capital OS barbell + alerts

| Ticket | Where |
| --- | --- |
| Barbell audit | meme ≤15% desk cap; fee-clear ≥70% of open (`barbell_status`) |
| Share clamp | `effective_tower_shares` caps meme at 15% even when green |
| Midday util alert | util &lt;20% + EDGE-heavy skips (`midday_util_alert`) |
| Zero-buy alert | ≥6h weekday fee-clear quiet + BUDGET skips |
| Masters board | `roi_plan.capital_os` |

### Opportunity-cost clock + idea review

| Ticket | Where |
| --- | --- |
| Pending high-edge | `note_pending_high_edge` (sports budget/max-buys skips) |
| Flush on buy | `flush_opp_cost_on_buy` when wait ≥90s + higher edge |
| Opp-cost board | `opp_cost_summary` → Masters |
| Idea register/close | `staff_register_idea` / `staff_close_idea` |
| 90d stale flag | `idea_review_status` |
| Masters board | `roi_plan.opp_cost` + `idea_review` |

### Sports green_boost + green-or-gone

| Ticket | Where |
| --- | --- |
| Sports +1 gate | `sports_green_boost_status` — 2w M1≥0 + CLV≥52% n≥20 |
| Runtime boost | `gap_bot` uses `sports_green_boost()` (default 0) |
| Green-or-gone flags | `green_or_gone_status` — red+risk / loser Gate A |
| Masters board | `roi_plan.sports_green_boost` + `green_or_gone` |

### BTC calibration report

| Ticket | Where |
| --- | --- |
| p-bucket vs hit rate | `btc_calibration_report` |
| Hi-p miscalibration | labeled ≥80% with hit &lt;70% (n≥20) → `raise_phi` |
| Daily capture | `capture_btc_calibration` |
| Masters board | `roi_plan.btc_calibration` |

### Cross-tower firm rank queue

| Ticket | Where |
| --- | --- |
| Shared offer book | `offer_firm_candidates` (sports+btc+commodity) |
| Rank + allocate | `rebuild_firm_queue` via `desk_brain.rank_desk_queue` / `allocate_risk` |
| Soft defer gate | `firm_queue_blocks` — deferred tickets skip new entries |
| Runtime wire | `gap_bot` / `btc15m_signal` / `commodity-15m` offer → rebuild → gate |
| Masters board | `roi_plan.firm_queue` |

### Parallel book prefetch + empty CARD &lt;3s

| Ticket | Where |
| --- | --- |
| Shared parallel map | `desk_more.prefetch_map` |
| Commodity books | `prefetch_commodity_books` + `evaluate(..., book=)` |
| Empty CARD log | `record_empty_card` / `empty_card_status` (bar 3s) |
| Runtime | commodity empty fast-exit; BTC logs empty CARD latency |
| Masters board | `roi_plan.empty_card` |

### Near-miss soft-gate staff promote

| Ticket | Where |
| --- | --- |
| Label shadow outcomes | `label_near_miss_outcome` (would_pnl) |
| Promote ready | n≥30 labeled + shadow EV ≥ 0 → `near_miss_promote_status` |
| Staff arm z\|p only | `staff_promote_near_miss_soft` / `staff_clear_near_miss_promote` |
| Paper relax | `effective_near_miss_relax` — z−0.05 / p−0.02; **edge forever 0** |
| Runtime | BTC `evaluate_window` applies relax when staff-armed |
| Masters board | `roi_plan.near_miss_promote` |

### Next

| Ticket | Where |
| --- | --- |
| Observe / staff hillclimb | Chicago weeks; one allowlist lever when ready |

## Hard rules unchanged

- Venue floors: sports 0.06 / BTC+commodity 0.05 / INX+DEX 0.02
- Starve: n≥4, factor 0.15
- Meme red lock −$8; INX halt $460
- Kill: M3↑ with M1↓ for 2 Chicago weeks → revert lever

## Tests

```bash
python -m unittest test_positive_roi_plan_slice.py desk_roi_plan desk_master -v
```
