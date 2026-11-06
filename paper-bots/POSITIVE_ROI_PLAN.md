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

### Living Trading Upgrade (shipped slice)

| Ticket | Where |
| --- | --- |
| BTC news fail-closed | `btc15m_signal` — calendar `None` blocks buys |
| CLI entry_gate honor | `desk_living.honor_desk_entry_gate` on sports/BTC/commodity/meme |
| Meme Chicago day | `memecoin-paper/bot.today_local` → America/Chicago |
| Fee ledger gaps | sports scale-out + INX twins + meme sells |
| Feature store + Completions KPI | `desk_living` → Masters `living_upgrade` |
| Insight helpers (observe-only) | `helpers/{tip_radar,skip_historian,timer_heartbeat,empty_card_bee}` |
| Teller memory on closes | sports / BTC / INX / meme settles & sells |

### Living upgrade — EIA scout + sports calib + loser features

| Ticket | Where |
| --- | --- |
| EIA week scout | `helpers/eia_scout` — observe-only inventory horizon |
| Sports calibration board | `sports_calibration_report` / Masters `sports_calibration` |
| Feature rows on loser towers | meme + INX (sp/sized) skip/buy → living feature store |

### Living upgrade — Tier-2 insight clerks

| Ticket | Where |
| --- | --- |
| Calib nag | `helpers/calib_nag` — BTC+sports raise_Φ tickets (no silent write) |
| Hard-stop clerk | `helpers/hard_stop_clerk` — sports shadow promote readiness |
| Near-miss clerk | `helpers/near_miss_clerk` — soft z\|p promote readiness |
| Bleed clerk | `helpers/bleed_clerk` — firm bleed + misplaced capital |

### Living upgrade — ops insight clerks

| Ticket | Where |
| --- | --- |
| Distance clerk | `helpers/distance_clerk` — empty CARD + firm queue |
| Bookkeeper clerk | `helpers/bookkeeper_clerk` — Completions + fee ledger |
| Reporter clerk | `helpers/reporter_clerk` — weekly scorecard mirror |
| Quant clerk | `helpers/quant_clerk` — M3 fit + M4 latency (walk-forward) |

### Living upgrade — commodity calib + AI health

| Ticket | Where |
| --- | --- |
| Commodity calibration | `commodity_calibration_report` / Masters `commodity_calibration` |
| Living AI health | `desk_living.living_ai_health` on living board (adapt + raise_Φ) |
| Calib nag covers commodity | `helpers/calib_nag` boards include commodity |

### Living upgrade — swarm ratio + skip-twin clerk

| Ticket | Where |
| --- | --- |
| Insight≥3:1 audit | `desk_living.insight_swarm_ratio` on living board |
| Skip-twin clerk | `helpers/skip_twin_clerk` — near-miss would_pnl twin digest |

### Living upgrade — clerk pulse + skip-twin feature join

| Ticket | Where |
| --- | --- |
| Clerk pulse timer | `helpers/clerk_pulse.run_if_due` from `pimp_desk.run_scheduled` |
| Skip-twin → feature store | `desk_living.record_skip_twin_features` via `label_near_miss_outcome` |

### Living upgrade — tip radar quote-cache feed

| Ticket | Where |
| --- | --- |
| Tip radar from quote_cache | `helpers.tip_radar.games_from_quote_cache` → digests |

### Living upgrade — swarm lights + injury inbox

| Ticket | Where |
| --- | --- |
| Swarm city lights | `desk_row.swarm_lights` + Masters `swarm_lights` |
| Injury staff inbox | `helpers/injury_wire_inbox.json` via `staff_ingest` |

### Living upgrade — AI / completions HUD

| Ticket | Where |
| --- | --- |
| raise_Φ on Masters priority | `master_summary.priority` from `living_ai` |
| Completions on desk/tellers | `desk_row.completions` + teller_memory fact |

### Living upgrade — feature quiet alert + hillclimb card

| Ticket | Where |
| --- | --- |
| Feature quiet alert | `desk_living.feature_store_quiet_alert` (≥6h weekday) |
| Hillclimb lever card | living board + Masters `hillclimb_lever` status |

### Living upgrade — dual-control HUD + hillclimb CLI

| Ticket | Where |
| --- | --- |
| Dual-control on Masters/desk | `dual_control_status` on living + desk_row |
| Hillclimb staff CLI | `tools/staff_hillclimb_pick.py` + `staff_clear_hillclimb_lever` |

### Living upgrade — dual-control / ruin staff CLIs

| Ticket | Where |
| --- | --- |
| Dual-control CLI | `tools/staff_dual_control.py` |
| Ruin drill CLI + HUD | `tools/staff_ruin_drill.py` + `practiced_this_month` |

### Living upgrade — Sunday packet + skip taxonomy chip

| Ticket | Where |
| --- | --- |
| Sunday living packet | `helpers/sunday_packet` (staff draft; auto_publish=False) |
| Skip taxonomy chip | `desk_living.skip_taxonomy_chip` on desk/Masters/teller facts |

### Living upgrade — green-day / selective +1 board

| Ticket | Where |
| --- | --- |
| Green-day HUD | `desk_living.green_day_board` + Masters/desk |

### Living upgrade — firm queue chip + Sunday packet CLI

| Ticket | Where |
| --- | --- |
| Firm queue HUD | `desk_living.firm_queue_chip` on desk/Masters |
| Sunday packet CLI | `tools/staff_sunday_packet.py` |

### Living upgrade — empty CARD + near-miss chips

| Ticket | Where |
| --- | --- |
| Empty CARD chip | `desk_living.empty_card_chip` |
| Near-miss chip | `desk_living.near_miss_chip` |

### Living upgrade — timer heartbeat + helper Gate A

| Ticket | Where |
| --- | --- |
| Timer heartbeat chip | `desk_living.timer_heartbeat_chip` |
| Helper Gate A board | `desk_living.helper_gate_a_board` |

### Living upgrade — skip-regret + hard-stop chips

| Ticket | Where |
| --- | --- |
| Skip-regret chip | `desk_living.skip_regret_chip` |
| Hard-stop chip | `desk_living.hard_stop_chip` |

### Living upgrade — bleed + CLV chips

| Ticket | Where |
| --- | --- |
| Bleed chip | `desk_living.bleed_chip` |
| CLV chip | `desk_living.clv_chip` |

### Living upgrade — tip radar + calib nag chips

| Ticket | Where |
| --- | --- |
| Tip radar chip | `desk_living.tip_radar_chip` |
| Calib nag chip | `desk_living.calib_nag_chip` |

### Living upgrade — injury wire + EIA scout chips

| Ticket | Where |
| --- | --- |
| Injury wire chip | `desk_living.injury_wire_chip` |
| EIA scout chip | `desk_living.eia_scout_chip` |

### Living upgrade — city swarm vault + Discord packet

| Ticket | Where |
| --- | --- |
| City vault swarm/fills | `trading-city` Desk types + vault board |
| Sunday Discord copy | `sunday_packet.format_discord` + CLI |

### Living upgrade — skip / distance / quant chips

| Ticket | Where |
| --- | --- |
| Skip historian chip | `desk_living.skip_historian_chip` |
| Distance clerk chip | `desk_living.distance_clerk_chip` |
| Quant clerk chip | `desk_living.quant_clerk_chip` |

### Living upgrade — bookkeeper / reporter / empty-bee chips

| Ticket | Where |
| --- | --- |
| Bookkeeper chip | `desk_living.bookkeeper_chip` |
| Reporter chip | `desk_living.reporter_chip` |
| Empty-card bee chip | `desk_living.empty_card_bee_chip` |

### Next

| Ticket | Where |
| --- | --- |
| Near-miss clerk chip | labeled near-miss digest |
| Hard-stop clerk chip | shadow exits digest |
| Bleed clerk chip | firm bleed digest |

## Hard rules unchanged

- Venue floors: sports 0.06 / BTC+commodity 0.05 / INX+DEX 0.02
- Starve: n≥4, factor 0.15
- Meme red lock −$8; INX halt $460
- Kill: M3↑ with M1↓ for 2 Chicago weeks → revert lever

## Tests

```bash
python -m unittest test_positive_roi_plan_slice.py desk_roi_plan desk_master -v
```
