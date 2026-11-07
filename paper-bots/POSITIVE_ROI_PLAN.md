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
| Batch / CLI | `staff_batch_arm_promotes` · `make living-hard-stop-promote` |

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
| Staff arm | `staff_set_sports_green_boost` → `desk_sports_green_boost_promote.json` |
| Runtime boost | `gap_bot` uses `sports_green_boost()` (ready **or** staff arm; default 0) |
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

### Living upgrade — near-miss / hard-stop / bleed clerk chips

| Ticket | Where |
| --- | --- |
| Near-miss clerk chip | `desk_living.near_miss_clerk_chip` |
| Hard-stop clerk chip | `desk_living.hard_stop_clerk_chip` |
| Bleed clerk chip | `desk_living.bleed_clerk_chip` |

### Living upgrade — skip-twin / CLV closer / timer digest chips

| Ticket | Where |
| --- | --- |
| Skip-twin clerk chip | `desk_living.skip_twin_clerk_chip` |
| CLV closer chip | `desk_living.clv_closer_chip` |
| Timer digest chip | `desk_living.timer_digest_chip` |

### Living upgrade — calendar / EIA blackout / compact card

| Ticket | Where |
| --- | --- |
| Calendar scanner chip | `desk_living.calendar_scanner_chip` |
| EIA blackout chip | `desk_living.eia_blackout_chip` |
| Compact living card | `desk_living.living_compact_card` |

### Living upgrade — pulse / dual-control / ruin chips

| Ticket | Where |
| --- | --- |
| Clerk pulse chip | `desk_living.clerk_pulse_chip` |
| Dual-control chip | `desk_living.dual_control_chip` |
| Ruin drill chip | `desk_living.ruin_drill_chip` |

### Living upgrade — priority trim + status CLI + quiet pager

| Ticket | Where |
| --- | --- |
| Priority trim | `desk_master.finalize_living_priority` (max 16) |
| Staff living status | `tools/staff_living_status.py` |
| Feature quiet pager | `desk_living.feature_quiet_pager` |

### Living upgrade — injury ingest CLI + completions chip

| Ticket | Where |
| --- | --- |
| Injury ingest CLI | `tools/staff_injury_ingest.py` |
| Completions chip | `desk_living.completions_chip` + teller fact |

### Living upgrade — calib tickets CLI + self_check + vault color

| Ticket | Where |
| --- | --- |
| Calib tickets CLI | `tools/staff_calib_tickets.py` |
| Living self_check | `desk_living.living_self_check` |
| Swarm vault color | city vault green/amber from pass |

### Living upgrade — dual gaps / hillclimb / digest inventory

| Ticket | Where |
| --- | --- |
| Dual-control gaps page | `desk_living.dual_control_gaps_page` + CLI `gaps` |
| Hillclimb chip | `desk_living.hillclimb_chip` + CLI `hillclimb` |
| Digest inventory | `desk_living.digest_inventory` + CLI `inventory` |

### Living upgrade — ruin page / export / digest seed

| Ticket | Where |
| --- | --- |
| Ruin drill page | `desk_living.ruin_drill_page` + CLI `ruin` |
| Living board export | `desk_living.living_board_export` + CLI `export` |
| Digest seed | `desk_living.seed_missing_digests` + CLI `seed` |

### Living upgrade — staff map + pulse CLI

| Ticket | Where |
| --- | --- |
| Staff map | `paper-bots/LIVING_UPGRADE.md` |
| Pulse force refresh | `staff_living_status.py pulse` |

### Living upgrade — teller chip + floors assert + Sunday note

| Ticket | Where |
| --- | --- |
| Teller living chip | `desk_living.teller_living_chip` |
| Fee floors assert | `desk_living.fee_floors_assert` + CLI `floors` |
| Sunday draft note | `LIVING_UPGRADE.md` (no auto publish) |

### Living upgrade — vault teller/floors + chip catalog

| Ticket | Where |
| --- | --- |
| City vault teller/floors | trading-city vault board rows |
| Floors CLI exit 2 | `staff_living_status.py floors` |
| Chip catalog | `living_self_check.chip_catalog` |

### Living upgrade — smoke Makefile + betting expand gate

| Ticket | Where |
| --- | --- |
| Smoke Makefile | `paper-bots/Makefile` living-* targets |
| Betting expand gate | `desk_living.betting_expand_gate` + CLI `expand` |

### Living upgrade — vault expand + gaps exit + living keys test

| Ticket | Where |
| --- | --- |
| Expand on city vault | trading-city vault `expand` row |
| Living keys unit | master teller/swarm/expand keys |
| Gaps CLI exit 2 | `staff_living_status.py gaps` |

### Living upgrade — doctor + size guard + expand teller fact

| Ticket | Where |
| --- | --- |
| Living doctor | `desk_living.living_doctor` + CLI/make |
| Board size guard | `living_board_size_guard` soft max 64 |
| Expand teller fact | remember mistake when blocked |

### Living upgrade — vault doctor + weekly ritual

| Ticket | Where |
| --- | --- |
| Doctor on city vault | trading-city vault `doctor` row |
| Weekly ritual script | `tools/staff_living_ritual.py` + make |

### Living upgrade — prune + ritual Discord + doctor age

| Ticket | Where |
| --- | --- |
| Living chip prune pass | `finalize_living_priority` family prefixes + clerk twin trim |
| Ritual Discord copy | `staff_living_ritual.py --discord` + make |
| Desk doctor age chip | `doctor_age_chip` + vault/Masters stale rail |

### Living upgrade — sunday ritual + tip feed + pulse warn

| Ticket | Where |
| --- | --- |
| Sunday ritual cross-link | sunday packet Discord + checklist |
| Living tip-feed vault row | tip radar on city vault |
| Clerk pulse age soft warn | soft WARN before STALE hard insert |

### Living upgrade — AI vault + quiet tint + gaps Discord

| Ticket | Where |
| --- | --- |
| Living AI vault row | raise_Φ ticket count on vault |
| Feature quiet vault tint | quiet amber on vault |
| Dual gaps Discord shortcut | `staff_living_status.py gaps --discord` |

### Living upgrade — ruin Discord + compact vault + expand copy

| Ticket | Where |
| --- | --- |
| Ruin Discord shortcut | `status ruin --discord` |
| Living compact vault row | one-line compact on vault |
| Expand gate soft copy | blocked reason in status / `--discord` |

### Living upgrade — floors/doctor Discord + inventory vault

| Ticket | Where |
| --- | --- |
| Floors Discord soft assert | `status floors --discord` |
| Doctor Discord one-liner | `status doctor --discord` |
| Inventory thin vault tint | digest inventory on vault |

### Living upgrade — hillclimb/gaps vault + ritual make pulse

| Ticket | Where |
| --- | --- |
| Hillclimb vault row | active lever on vault |
| Dual gaps vault tint | unsigned gaps amber |
| Living ritual Makefile note | README pulse + make *-discord targets |

### Living upgrade — completions/green/bleed vault tints

| Ticket | Where |
| --- | --- |
| Completions vault tint | eligible=0 amber on fills |
| Green-day vault strip | green_n / red_n observe |
| Bleed hot vault tint | bleed fail red |

### Living upgrade — CLV / calib / timer vault

| Ticket | Where |
| --- | --- |
| CLV vault row | sports CLV completeness |
| Calib nag vault tint | raise_Φ tickets amber |
| Timer dead vault tint | timer heartbeat DEAD |

### Living upgrade — tip labels + empty/near-miss vault

| Ticket | Where |
| --- | --- |
| Tip-force vs tip-feed polish | clarify tip labels on vault |
| Empty-card vault tint | empty CARD slow amber |
| Near-miss promote vault | promote_ready observe only |

### Living upgrade — skip-regret / hard-stop / injury vault

| Ticket | Where |
| --- | --- |
| Skip-regret vault row | green_twin soft review |
| Hard-stop vault tint | sports promote_ready |
| Injury wire vault row | inbox headlines observe |

### Living upgrade — EIA scout / calendar / blackout vault

| Ticket | Where |
| --- | --- |
| EIA scout vault row | next inventory ETA |
| Calendar vault tint | events n>0 amber |
| EIA blackout vault | ACTIVE red |

### Living upgrade — firm queue / Gate A / quiet pager vault

| Ticket | Where |
| --- | --- |
| Firm queue vault row | queue depth observe |
| Helper Gate A vault | promote_ready helpers |
| Feature quiet pager vault | pager copy soft |

### Living upgrade — skip taxonomy / distance / quant vault

| Ticket | Where |
| --- | --- |
| Skip taxonomy vault | top skip codes observe |
| Distance empty vault | empty_card_pass fail |
| Quant fit vault tint | fit_pass fail amber |

### Living upgrade — bookkeeper / reporter / empty-bee vault

| Ticket | Where |
| --- | --- |
| Bookkeeper vault row | fee ledger gaps |
| Reporter vault tint | auto_publish False assert |
| Empty-card bee vault | breaches amber |

### Living upgrade — near-miss / hard-stop / bleed clerk vault

| Ticket | Where |
| --- | --- |
| Near-miss clerk vault | twin promote_ready |
| Hard-stop clerk vault | clerk promote_ready |
| Bleed clerk vault tint | clerk bleed hot |

### Living upgrade — skip-twin / CLV closer / timer digest vault

| Ticket | Where |
| --- | --- |
| Skip-twin clerk vault | promote_ready twin |
| CLV closer vault row | closer digest |
| Timer digest vault tint | digest dead |

### Living upgrade — dual / ruin chips + expand soft_copy vault

| Ticket | Where |
| --- | --- |
| Dual-control chip vault | signed checklist |
| Ruin drill chip vault | active practice |
| Expand gate vault polish | soft_copy on blocked |

### Living upgrade — sunday packet / export json / vault scroll

| Ticket | Where |
| --- | --- |
| Sunday packet vault row | packet present observe |
| Living export CLI note | doctor_age in status json |
| Vault board scroll polish | dense row + sticky toolbar |

### Living upgrade — doctor_age text / compact quiet / ritual observe

| Ticket | Where |
| --- | --- |
| Staff status doctor_age text | text status line |
| Living compact include quiet | compact parts quiet label |
| Ritual exit note on vault | ritual_ok observe chip |

### Living upgrade — ritual priority / sunday text / compact expand

| Ticket | Where |
| --- | --- |
| Ritual observe Masters priority | stale ritual rail insert |
| Living status sunday text | sunday packet line |
| Compact include expand | expand blocked in compact |

### Living upgrade — ritual observe CLI / selfcheck

| Ticket | Where |
| --- | --- |
| Living selfcheck ritual_observe | include in selfcheck payload |
| Staff ritual --observe flag | print ritual_observe only |
| Priority family ritual unit | assert ritual dedupe |

### Living upgrade — doctor ritual check / status ritual_ok / vault hint

| Ticket | Where |
| --- | --- |
| Living doctor include ritual | doctor checks ritual_observe |
| Status json ritual_ok top-level | flatten ritual_ok |
| City vault ritual sticky note | short make living-ritual hint |

### Living upgrade — doctor soft_copy ritual / export ritual_ok / status flag

| Ticket | Where |
| --- | --- |
| Doctor soft_copy ritual line | failed ritual in discord |
| Living export ritual_ok | export top-level |
| Staff status ritual_ok flag | text ritual_ok= |

### Living upgrade — compact ritual / Masters soft_copy / ritual CLI json

| Ticket | Where |
| --- | --- |
| Compact card ritual_ok | compact parts ritual= |
| Masters ritual soft_copy | priority discord ritual |
| Ritual CLI --json ritual_ok | flatten exit fields |

### Living upgrade — vault ritual draft / compact order / observe tip

| Ticket | Where |
| --- | --- |
| Vault ritual_soft_copy row | city Masters ritual draft |
| Compact quiet+ritual order | HUD part order tweak |
| Ritual observe Makefile note | LIVING_UPGRADE tip |

### Living upgrade — status ritual draft / doctor link / vault compact

| Ticket | Where |
| --- | --- |
| Status export ritual draft | status --json ritual_soft_copy |
| Doctor soft_copy Masters link | cross-link ritual draft |
| Vault compact ritual order | city compact HUD mirror |

### Living upgrade — vault paste tip / sunday ritual_ok / teller nag

| Ticket | Where |
| --- | --- |
| Ritual draft copy button note | vault hint paste path |
| Sunday packet ritual_ok | packet observe field |
| Teller memory ritual nag | teller_living ritual line |

### Living upgrade — status ritual_nag / vault sunday tint / export compact ritual

| Ticket | Where |
| --- | --- |
| Status text ritual_nag | teller line in status |
| Vault sunday ritual_ok | city sunday row tint |
| Compact export ritual_ok | export compact.ritual_ok |

### Living upgrade — compact doctor_fresh / ritual CLI flags / teller tint

| Ticket | Where |
| --- | --- |
| Doctor age + ritual HUD | compact doctor_fresh part |
| Ritual CLI text exit_ok | plain text exit flags |
| City vault teller ritual_nag | teller row tint |

### Living upgrade — compact doctor tint / export doctor_fresh / status doctor

| Ticket | Where |
| --- | --- |
| Compact tint doctor stale | vault compact doctor color |
| Export doctor_fresh flat | living_board_export |
| Status text doctor= | staff status doctor_fresh |

### Living upgrade — status json doctor_fresh / soft_copy doctor / vault row order

| Ticket | Where |
| --- | --- |
| Status json doctor_fresh | flatten status --json |
| Doctor soft_copy doctor= | discord doctor_fresh line |
| Vault doctor_age near compact | row order nudge |

### Living upgrade — compact doctor status / ritual under doc age / export doctor soft

| Ticket | Where |
| --- | --- |
| Compact+doc age HUD pair | status text compact doctor |
| Ritual vault after doc age | row order ritual under doc |
| Export doctor_line soft | export soft_copy twin |

### Living upgrade — doctor_soft_copy json / vault doctor draft / Masters doctor_fresh

| Ticket | Where |
| --- | --- |
| Status json doctor_soft_copy | flatten draft twin |
| Vault AI after ritual block | keep HUD cluster tight |
| Masters priority doctor_fresh | stale doctor rail |

### Living upgrade — status doctor draft / compact json flats / ritual observe tip

| Ticket | Where |
| --- | --- |
| Status text doctor draft | staff text doctor_soft hint |
| Compact doctor_fresh export json | status --json compact flats |
| Ritual CLI doctor_soft note | observe tip line |

### Living upgrade — vault doctor hint / doctor_age soft alias / desk verify

| Ticket | Where |
| --- | --- |
| Vault hint doctor draft | toolbar paste path |
| Doctor age soft in status json | alias doctor_soft_copy |
| Masters doctor_soft on desk | desk_row already wired verify |

### Living upgrade — quiet+doctor status / ritual discord doctor_fresh / draft tint

| Ticket | Where |
| --- | --- |
| Compact quiet+doctor status | one-liner staff HUD |
| Ritual discord doctor_fresh | format_discord line |
| City doctor draft tint | stale color on draft row |

### Living upgrade — quiet_doctor json / ritual floors_ok header / ritual draft tint

| Ticket | Where |
| --- | --- |
| Status json quiet_doctor | flatten quiet+doctor line |
| Ritual discord floors_ok | flags in draft header |
| Vault ritual draft tint | exit_ok false color |

### Living upgrade — export quiet_doctor / status floors_ok / doctor draft badge

| Ticket | Where |
| --- | --- |
| Export quiet_doctor | living_board_export field |
| Status text floors_ok | ritual flags line |
| Vault doctor draft label | stale badge text |

### Living upgrade — quiet_doctor age / ritual CLI floors / ritual draft badge

| Ticket | Where |
| --- | --- |
| Compact export quiet bit | quiet in quiet_doctor age |
| Ritual CLI floors in text | full ritual plain flags |
| City ritual draft badge | exit_ok badge text |

### Living upgrade — status quiet age / observe floors / draft badge CSS

| Ticket | Where |
| --- | --- |
| Status text quiet age | quiet+doctor age= |
| Ritual observe floors line | observe plain floors_ok |
| Vault draft badge CSS | EXIT/SOFT class |

### Living upgrade — doctor draft STALE CSS / quiet_age always / observe doctor_fresh

| Ticket | Where |
| --- | --- |
| Doctor draft badge CSS | STALE class twin |
| Status json quiet_age always | mirror text n/a |
| Ritual CLI doctor_fresh observe | observe end flag |

### Living upgrade — compact quiet_age / ritual discord quiet / status quiet_age

| Ticket | Where |
| --- | --- |
| Compact HUD quiet_age chip | city compact age |
| Ritual discord quiet hint | optional quiet line |
| Staff status quiet_age field | text quiet_age= |

### Living upgrade — compact quiet_age export / ritual json / vault tint

| Ticket | Where |
| --- | --- |
| Compact quiet_age export | export compact.quiet_age |
| Ritual json quiet_age | ritual --json field |
| Vault compact quiet tint | age-based color |

### Living upgrade — status compact_quiet_age / observe quiet_age / Masters soft rail

| Ticket | Where |
| --- | --- |
| Status json compact_quiet_age | flatten status --json |
| Ritual observe quiet_age text | observe plain age |
| Masters quiet_age priority | soft quiet rail |

### Living upgrade — always quiet_age part / discord quiet line / vault quiet_age row

| Ticket | Where |
| --- | --- |
| Compact quiet_age in parts | always quiet_age= part |
| Ritual discord age=n/a | always quiet line |
| Vault quiet_age chip row | dedicated vault row |

### Living upgrade — status quiet_age_label / ritual quiet_line / vault order

| Ticket | Where |
| --- | --- |
| Status text quiet_age_label | compact quiet_age_label |
| Ritual json always quiet line | --json feature_quiet + quiet_line |
| Vault quiet_age near ritual | quiet age before ritual |

### Living upgrade — status quiet_line / Masters label rail / vault tip

| Ticket | Where |
| --- | --- |
| Status json quiet_line twin | flatten quiet_line |
| Masters quiet_age_label rail | priority soft label |
| Vault quiet+ritual cluster tip | tip under quiet age |

### Living upgrade — export quiet_line / observe text / sunday label

| Ticket | Where |
| --- | --- |
| Export quiet_line field | living_board_export |
| Ritual observe quiet_line text | observe plain |
| Sunday packet quiet_age_label | soft sunday line |

### Living upgrade — status quiet_line / vault sunday quiet / export label

| Ticket | Where |
| --- | --- |
| Status text quiet_line twin | print quiet_line |
| Vault sunday quiet_age chip | city sunday quiet row |
| Compact export quiet_age_label | export flatten (landed) |

### Living upgrade — status sunday quiet / teller nag / ritual tip

| Ticket | Where |
| --- | --- |
| Status json sunday quiet_age | flatten sunday quiet |
| Teller quiet_age_label nag | teller living line |
| Ritual discord sunday quiet tip | optional tip line |

### Living upgrade — vault teller tint / export sunday / Masters rail

| Ticket | Where |
| --- | --- |
| Vault teller quiet nag tint | city teller row |
| Export sunday_quiet_age_label | living_board_export |
| Masters sunday quiet soft rail | priority observe |

### Living upgrade — status/ritual/vault sunday quiet batch

| Ticket | Where |
| --- | --- |
| Status text sunday quiet line | print sunday quiet |
| Ritual observe sunday quiet | observe plain + --json tip |
| Vault Masters sunday quiet | city masters sunday row |
| Status text teller quiet nag | teller_quiet_nag line |
| Status json masters sunday hit | flatten masters_sunday_quiet |
| Compact sunday quiet twin | compact.sunday_quiet_age* |
| Vault toolbar sunday quiet hint | ritual hint extend |

### Living upgrade — export masters / discord always / teller·sunday

| Ticket | Where |
| --- | --- |
| Export masters_sunday_quiet | living_board_export (landed) |
| Discord sunday quiet always | ritual tip always on |
| Teller vault sunday quiet link | tip under teller |

### Living upgrade — discord always / teller·sunday / masters text

| Ticket | Where |
| --- | --- |
| Discord sunday quiet always | ritual tip always on |
| Teller vault sunday quiet link | tip under teller |
| Status text masters sunday | print masters sunday |
| Ritual json sunday tip always | --json + plain sunday_quiet_tip |

### Living upgrade — sunday packet masters / status tip / teller link

| Ticket | Where |
| --- | --- |
| Sunday packet masters line | sunday discord |
| Status json sunday_quiet_tip | flatten tip |
| Teller·sunday vault link | under teller |

### Living upgrade — export sunday_quiet_tip (this batch)

| Ticket | Where |
| --- | --- |
| Export sunday_quiet_tip | living_board_export |

### Living upgrade — expand/compact/observe masters sunday

| Ticket | Where |
| --- | --- |
| Vault expand sunday quiet | expand row hint |
| Compact masters sunday part | masters_sunday= part |
| Ritual observe masters sunday | observe plain + --json |

### Living upgrade — masters sunday flatten + compact tint

| Ticket | Where |
| --- | --- |
| Status json masters_sunday_label | flatten compact |
| Export masters_sunday_label | living_board_export |
| Vault compact masters sunday | city compact show |

### Living upgrade — masters sunday text/discord (this batch)

| Ticket | Where |
| --- | --- |
| Status text masters_sunday= part | print compact part |
| Ritual discord masters sunday | discord line |

### Living upgrade — compact part order (this batch)

| Ticket | Where |
| --- | --- |
| Compact part order assert | quiet_age→masters_sunday→ritual |

### Living upgrade — doctor/expand sunday quiet batch

| Ticket | Where |
| --- | --- |
| Vault doctor sunday quiet | doctor row hint |
| Status json expand sunday bit | flatten expand_sunday_quiet |
| Ritual observe expand sunday | observe plain + --json |

### Living upgrade — expand sunday export/discord/text (this batch)

| Ticket | Where |
| --- | --- |
| Export expand_sunday_quiet | living_board_export |
| Ritual discord expand sunday | discord line |
| Status text expand sunday | print line |

### Living upgrade — floors/compact/doctor sunday batch

| Ticket | Where |
| --- | --- |
| Vault floors sunday quiet | floors row hint |
| Compact expand sunday twin | compact.expand_sunday_quiet |
| Doctor soft_copy sunday bit | soft_copy + export tip |

### Living upgrade — compact expand / dual / floors observe (this batch)

| Ticket | Where |
| --- | --- |
| Status json compact expand sunday | flatten |
| Vault dual sunday quiet | dual row hint |
| Ritual observe floors sunday | observe plain + --json |

### Living upgrade — floors sunday export/text (this batch)

| Ticket | Where |
| --- | --- |
| Export floors_sunday_quiet | living_board_export |
| Status text floors sunday | print line |

### Living upgrade — ruin/floors sunday batch

| Ticket | Where |
| --- | --- |
| Vault ruin sunday quiet | ruin row hint |
| Ritual discord floors sunday | discord line |
| Compact floors sunday twin | compact.floors_sunday_quiet |
| Status/export floors sunday twin | flatten compact |

### Living upgrade — gaps/ruin sunday (this batch)

| Ticket | Where |
| --- | --- |
| Vault gaps sunday quiet | gaps row hint |
| Ritual observe ruin sunday | observe tip |
| Status text ruin sunday | print line |

### Living upgrade — ruin sunday discord/export/compact (auto-roll)

| Ticket | Where |
| --- | --- |
| Ritual discord ruin sunday | discord line |
| Export ruin_sunday_quiet | living_board_export |
| Compact ruin sunday twin | compact.ruin_sunday_quiet |
| Status flatten ruin sunday | status --json |

### Living upgrade — hill/swarm/gaps sunday (auto-roll)

| Ticket | Where |
| --- | --- |
| Vault hill sunday quiet | hill row hint |
| Vault swarm sunday quiet | swarm row hint |
| Ritual discord gaps sunday | discord line |
| Compact/export hill+swarm+gaps | sunday twins |

### Living upgrade — digests/fills/gaps observe (auto-roll)

| Ticket | Where |
| --- | --- |
| Vault digests sunday quiet | digests row hint |
| Vault fills sunday quiet | fills row hint |
| Ritual observe gaps sunday | observe plain + --json |

### Living upgrade — green/bleed/digests sunday (auto-roll)

| Ticket | Where |
| --- | --- |
| Vault green sunday quiet | green row hint |
| Vault bleed sunday quiet | bleed row hint |
| Ritual discord digests sunday | discord line |

### Living upgrade — CLV/timer/digests observe (auto-roll)

| Ticket | Where |
| --- | --- |
| Vault CLV sunday quiet | CLV row hint |
| Vault timer sunday quiet | timer row hint |
| Ritual observe digests sunday | observe plain + --json |

### Living upgrade — calib/pulse/timer sunday (auto-roll)

| Ticket | Where |
| --- | --- |
| Vault calib sunday quiet | calib row hint |
| Vault pulse sunday quiet | pulse row hint |
| Ritual discord timer sunday | discord line |

### Living upgrade — queue/Gate A/AI sunday (auto-roll)

| Ticket | Where |
| --- | --- |
| Vault queue sunday quiet | queue row hint |
| Vault Gate A sunday quiet | Gate A row hint |
| Vault AI sunday quiet | AI row hint |

### Living upgrade — tip/blackout/injury sunday (auto-roll)

| Ticket | Where |
| --- | --- |
| Vault tip feed sunday quiet | tip feed row hint |
| Vault blackout sunday quiet | blackout row hint |
| Vault injury sunday quiet | injury row hint |

### Living upgrade — empty/EIA/pager sunday vault pass (auto-roll)

| Ticket | Where |
| --- | --- |
| Vault empty/near-miss sunday | empty + near-miss hints |
| Vault EIA/calendar sunday | EIA + calendar hints |
| Vault pager/books sunday | pager + books hints |

### Living upgrade — digests/fills sunday twins (auto-roll)

| Ticket | Where |
| --- | --- |
| Compact digests+fills sunday | living_compact_card twins |
| Export/status digests+fills sunday | board export + status text/json |
| Ritual Discord hill/swarm/fills | discord lines |
| Ritual observe fills sunday | observe plain + --json |

### Living upgrade — green/bleed/CLV sunday twins (auto-roll)

| Ticket | Where |
| --- | --- |
| Compact green+bleed sunday | living_compact_card twins |
| Export/status green+bleed/CLV | board export + status flatten |
| Ritual Discord green/bleed/CLV/calib | discord lines |
| Compact CLV+timer+calib sunday | living_compact_card twins |

### Living upgrade — queue/GateA/AI/tip sunday twins (auto-roll)

| Ticket | Where |
| --- | --- |
| Compact queue+GateA+AI sunday | living_compact_card twins |
| Export/status queue/GateA/AI | board export + status flatten |
| Ritual Discord queue/GateA/AI/tip | discord lines |
| Compact tip/blackout/injury sunday | living_compact_card twins |

### Living upgrade — empty/EIA/pager/pulse/dual sunday twins (auto-roll)

| Ticket | Where |
| --- | --- |
| Compact empty+near-miss sunday | living_compact_card twins |
| Compact EIA+calendar+pager+books | living_compact_card twins |
| Compact pulse+dual sunday | living_compact_card twins |
| Export/status/ritual empty…dual | export + status + Discord/observe |

### Living upgrade — skip-reg/clerks sunday twins (auto-roll)

| Ticket | Where |
| --- | --- |
| Compact skip-reg+hard-stop sunday | living_compact_card twins |
| Compact distance+quant+report+bee | living_compact_card twins |
| Compact clerk twins (nm/hs/bleed/skip-twin/CLV/t-digest) | living_compact_card twins |
| Vault+ritual+status skip-reg/clerks sunday | App vault + Discord/observe + status |

### Living upgrade — meta vault sunday quiet pass (auto-roll)

| Ticket | Where |
| --- | --- |
| Vault skips/budgets/adapt/tip-force sunday | App vault ops rows |
| Vault compact/doc/quiet/ritual/teller sunday | App vault living rows |
| Compact skips/teller/doc/quiet/ritual twins | living_compact_card + export |
| Ritual/status meta sunday lines | Discord/observe + status |

### Living upgrade — vault sunday leftovers (auto-roll)

| Ticket | Where |
| --- | --- |
| Vault skip-taxonomy + sunday packet | App vault rows |
| Vault quiet age / quiet·ritual / drafts | App vault rows |
| Vault stopbleed + fill tax sunday | App vault rows |

### Living upgrade — L7 digest/journal/monday observe (auto-roll)

| Ticket | Where |
| --- | --- |
| Digest freshness chip | `desk_living.digest_freshness_chip` |
| Journal coverage chip | fit+latency age/coverage observe |
| Monday pulse chip | timer alive + digest freshness |
| Vault/status/ritual/export surfaces | App + staff CLIs + compact twins |

### Living upgrade — L7 toxic/adapt/SLA observe (auto-roll)

| Ticket | Where |
| --- | --- |
| Toxic fill detector chip | `desk_living.toxic_fill_chip` |
| Weekly adapt A/B summary chip | `desk_living.adapt_ab_chip` |
| Staff SLA raise_Φ age surface | `desk_living.raise_phi_sla_chip` (never auto-writes Φ) |
| Vault/status/ritual/export surfaces | App + staff CLIs + compact twins |

### Living upgrade — L7 feature/catalog/phase2 observe (auto-roll)

| Ticket | Where |
| --- | --- |
| Feature coverage chip | `desk_living.feature_coverage_chip` |
| Chip catalog soft-max chip | `desk_living.chip_catalog_chip` |
| Phase 2 pulse chip | `desk_living.phase2_pulse_chip` (gap-decay/scale-out) |
| Vault/status/ritual/export surfaces | App + staff CLIs + compact twins |

### Living upgrade — L7 selfcheck/doctor pulse (auto-roll)

| Ticket | Where |
| --- | --- |
| Selfcheck L7 keys | `living_self_check.l7_observe_*` |
| Doctor soft_copy L7 line | `living_doctor` soft_copy + fields |
| Makefile `living-l7` | observe exit 2 on missing L7 chips |
| Ritual/status L7 pulse | Discord/observe + status text |

### Living upgrade — L7 pulse surfaces (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `l7_observe_summary` helper | surface-only (not a board chip) |
| Compact/export L7 sunday twin | `l7_observe_sunday_quiet` |
| Vault l7 pulse row | App vault |
| `make living-l7-discord` | staff paste draft · never auto-posts |

### Living upgrade — L7 status CLI surfaces (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `staff_living_status.py l7` | JSON + exit 2 if missing |
| `l7 --discord` draft | staff paste · never auto-posts |
| Makefile living-l7 / living-l7-discord | wire to status CLI |
| Priority inserts L7 miss | staff priority JSON |

### Living upgrade — feature store + skip historian sunday (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| Feature store sunday twin | compact/export `feature_store_sunday_quiet` |
| Skip historian sunday twin | compact/export `skip_historian_sunday_quiet` |
| Vault/status/ritual surfaces | App + staff CLIs |

### Living upgrade — sunday export + live discord labels (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| Export keep feature_store + skip_historian | `living_board_export` |
| Ritual discord live L7/store/historian labels | `format_discord` |
| `sunday_twin_coverage` + status `sunday` | surface audit CLI |
| Makefile living-sunday* | staff paste · never auto-posts |

### Living upgrade — ritual Discord live labels (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `ritual_live_labels` helper | surface-only label map from board |
| Ritual Discord sunday lines | live chip labels with static fallbacks |
| Coverage test | draft contains live swarm/toxic labels |

### Living upgrade — export keep clerks/helpers (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| Export keep clerks/helpers/gates | `living_board_export` keep list |
| Export surface audits | ritual_live_labels / sunday_twin_coverage / l7_observe |
| Makefile `living-export` | staff_living_status export |

### Living upgrade — sunday twin doctor/status/vault (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| Doctor soft_copy sunday twins line | `living_doctor` |
| Status text/json sunday twins | staff_living_status |
| Vault sunday twins row | App vault (from export flat) |

### Living upgrade — status sunday twins flatten (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| Status JSON auto-flatten `*_sunday_quiet` | staff_living_status json |
| Status text swarm/hill/gaps sunday | _text lines |
| Export `sunday_twins` map | living_board_export |

### Living upgrade — observe live + selfcheck twins (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| Ritual `--observe` plain driven by `ritual_live_labels` | staff_living_ritual |
| Ritual `--observe --json` live + sunday twin flats | staff_living_ritual |
| Selfcheck `sunday_twin_*` fields | `living_self_check` |
| Vault sunday twins map n | App vault row |

### Living upgrade — timer + status ritual live (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `timer_label` on ritual_live_labels | desk_living |
| Ritual observe timer sunday row | staff_living_ritual |
| Status text timer/ritual live/twins sunday | staff_living_status |
| Selfcheck `ritual_live_*` | living_self_check |

### Living upgrade — doctor/vault timer live (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| Doctor soft_copy ritual live + timer sunday | `living_doctor` |
| Status JSON `ritual_live_*` + timer sunday | staff_living_status json |
| Vault timer prefers live/twin labels | App vault row |

### Living upgrade — vault ritual live row (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| Vault ritual live n/digests/fills/timer | App vault row |

### Living upgrade — compact ritual live sunday twin (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| Compact/export `ritual_live_sunday_quiet` | living_compact_card / export |

### Living upgrade — ritual live status/discord (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| Discord Ritual live + Sunday twins sunday | format_discord |
| Discord Timer prefers `timer_label` | format_discord |
| Observe/status ritual live sunday twin | ritual + status |
| Selfcheck/doctor `ritual_live_sunday_quiet` | living_self_check / doctor |

### Living upgrade — teller ritual live (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| Teller memory_line `ritual live n=` | teller_living_chip |
| Status teller ritual live line | staff_living_status |

### Living upgrade — ritual live batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| Makefile `living-ritual-live` / observe-json / teller | Makefile |
| Status CLI `ritual-live` (+ discord) | staff_living_status |
| Compact/export `teller_ritual_live_sunday_quiet` | living_compact_card / export |
| Export `ritual_live_n` / `ritual_live_ok` | living_board_export |
| Vault ritual·live + teller·live rows | App vault |
| Status teller ritual live sunday twin line | staff_living_status _text |

### Living upgrade — observe/priority ritual live batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| Priority flags thin ritual live + teller | staff_living_status priority |
| Makefile `living-priority` | Makefile |
| Observe teller ritual live sunday line | staff_living_ritual --observe |
| Discord Teller ritual live sunday | format_discord |
| Doctor soft_copy teller ritual live + audit cmd | living_doctor |
| Status JSON teller/ritual live flats | staff_living_status json |

### Living upgrade — export/HUD priority batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `living_priority_snapshot` surface helper | desk_living |
| Compact/export `priority_sunday_quiet` | compact / export |
| Export priority_lines + living_memory_line | living_board_export |
| Status priority --discord + text/json flats | staff_living_status |
| Makefile `living-priority-discord` | Makefile |
| Vault priority row | App vault |
| Selfcheck/doctor priority label | living_self_check / doctor |

### Living upgrade — priority observe/pulse batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| Ritual observe priority sunday line | staff_living_ritual --observe |
| Discord Priority sunday | format_discord |
| Ritual payload priority snapshot | staff_living_ritual |
| Pulse JSON priority + ritual_live_n | staff_living_status pulse |

### Living upgrade — HUD surfaces batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `living_hud_summary` surface helper | desk_living |
| Compact/export `hud_sunday_quiet` | compact / export |
| Status CLI `hud` (+ discord) | staff_living_status |
| Makefile `living-hud` / `living-hud-discord` | Makefile |
| Vault hud row | App vault |
| Observe/Discord HUD sunday | ritual observe / format_discord |
| Selfcheck/export hud fields | living_self_check / export |

### Living upgrade — help/selfcheck/money-path batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| Makefile `living-help` / `living-money` | Makefile |
| README living Makefile index | README.md |
| Status CLI `help` / `money` (+ discord) | staff_living_status |
| `living_money_path_tip` + `money_path_sunday_quiet` | desk_living / compact / export |
| Export `selfcheck_ok` / `selfcheck_label` | living_board_export |
| Vault selfcheck + money-path rows | App vault |

### Living upgrade — guardrails / surfaces batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `living_guardrails_tip` + `guardrails_sunday_quiet` | desk_living / compact / export |
| `living_surface_index` + `surfaces_sunday_quiet` | desk_living / compact / export |
| Status CLI `rules` / `surfaces` (+ discord) | staff_living_status |
| Makefile `living-rules` / `living-surfaces` | Makefile |
| Ritual observe + Discord money/guardrails/surfaces | staff_living_ritual |
| Vault guardrails + surfaces rows | App vault |
| README living index | README.md |

### Living upgrade — staff smoke batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `living_staff_smoke` + `smoke_sunday_quiet` | desk_living / compact / export |
| Status CLI `smoke` (+ discord) | staff_living_status |
| Makefile `living-smoke` | Makefile |
| Doctor/pulse/ritual smoke flats | doctor soft_copy / pulse / ritual |
| Vault smoke row | App vault |
| LIVING_UPGRADE / README index | docs |

### Living upgrade — Discord paste index batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `living_discord_paste_tip` + `paste_sunday_quiet` | desk_living / compact / export |
| Status CLI `paste` (+ discord) | staff_living_status |
| Makefile `living-paste` | Makefile |
| Ritual observe/Discord paste line | staff_living_ritual |
| Vault paste row | App vault |
| README index | README.md |

### Living upgrade — paper-live / makefile batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `living_paper_live_tip` + `paper_live_sunday_quiet` | desk_living / compact / export |
| `living_makefile_index` + `makefile_sunday_quiet` | desk_living / compact / export |
| Status CLI `paper` / `makefile` (+ discord) | staff_living_status |
| Makefile `living-paper` / `living-makefile` | Makefile |
| Ritual observe/Discord paper+makefile | staff_living_ritual |
| Vault paper-live + makefile rows | App vault |
| README index | README.md |

### Living upgrade — venues / chicago batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `living_venues_tip` + `venues_sunday_quiet` | desk_living / compact / export |
| `living_chicago_tip` + `chicago_sunday_quiet` | desk_living / compact / export |
| Status CLI `venues` / `chicago` (+ discord) | staff_living_status |
| Makefile `living-venues` / `living-chicago` | Makefile |
| Ritual observe/Discord venues+chicago | staff_living_ritual |
| Vault venues + chicago rows | App vault |
| README index | README.md |

### Living upgrade — starve / hard-rules batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `living_starve_tip` + `starve_sunday_quiet` | desk_living / compact / export |
| `living_hard_rules_tip` + `hard_rules_sunday_quiet` | desk_living / compact / export |
| Status CLI `starve` / `hard-rules` (+ discord) | staff_living_status |
| Makefile `living-starve` / `living-hard-rules` | Makefile |
| Ritual observe/Discord starve+hard-rules | staff_living_ritual |
| Vault starve + hard-rules rows | App vault |
| README index | README.md |


### Living upgrade — swarm/expand/quiet/timer tip batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `living_swarm_tip` + `swarm_tip_sunday_quiet` | desk_living / compact / export |
| `living_expand_tip` + `expand_tip_sunday_quiet` | desk_living / compact / export |
| `living_quiet_tip` + `quiet_tip_sunday_quiet` | desk_living / compact / export |
| `living_timer_tip` + `timer_tip_sunday_quiet` | desk_living / compact / export |
| Status CLI swarm/expand-tip/quiet-tip/timer-tip | staff_living_status |
| Makefile living-swarm / expand-tip / quiet-tip / timer-tip | Makefile |
| Ritual observe/Discord tip lines | staff_living_ritual |
| Vault tip rows | App vault |

### Living upgrade — export/doctor tip batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `living_export_tip` + `export_tip_sunday_quiet` | desk_living / compact / export |
| `living_doctor_tip` + `doctor_tip_sunday_quiet` | desk_living / compact / export |
| Status CLI `export-tip` / `doctor-tip` | staff_living_status |
| Makefile `living-export-tip` / `living-doctor-tip` | Makefile |
| Ritual + vault tip rows | ritual / App |

### Living upgrade — inventory/dual/hillclimb/ruin tip batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `living_inventory_tip` + `inventory_sunday_quiet` | desk_living / compact / export |
| `living_dual_tip` + `dual_tip_sunday_quiet` | desk_living / compact / export |
| `living_hillclimb_tip` + `hillclimb_tip_sunday_quiet` | desk_living / compact / export |
| `living_ruin_tip` + `ruin_tip_sunday_quiet` | desk_living / compact / export |
| Status CLI `inventory-tip` / `dual-tip` / `hillclimb-tip` / `ruin-tip` | staff_living_status |
| Makefile living-inventory-tip / dual-tip / hillclimb-tip / ruin-tip | Makefile |
| Ritual + vault tip rows | ritual / App |

### Living upgrade — near-miss/helper/hard-stop/skip-regret tip batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `living_near_miss_tip` + `near_miss_tip_sunday_quiet` | desk_living / compact / export |
| `living_helper_tip` + `helper_tip_sunday_quiet` | desk_living / compact / export |
| `living_hard_stop_tip` + `hard_stop_tip_sunday_quiet` | desk_living / compact / export |
| `living_skip_regret_tip` + `skip_regret_tip_sunday_quiet` | desk_living / compact / export |
| Status CLI near-miss-tip / helper-tip / hard-stop-tip / skip-regret-tip | staff_living_status |
| Makefile living-near-miss-tip / helper-tip / hard-stop-tip / skip-regret-tip | Makefile |
| Ritual + vault tip rows | ritual / App |

### Living upgrade — eia/injury/completions/toxic tip batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `living_eia_tip` + `eia_tip_sunday_quiet` | desk_living / compact / export |
| `living_injury_tip` + `injury_tip_sunday_quiet` | desk_living / compact / export |
| `living_completions_tip` + `completions_tip_sunday_quiet` | desk_living / compact / export |
| `living_toxic_tip` + `toxic_tip_sunday_quiet` | desk_living / compact / export |
| Status CLI eia-tip / injury-tip / completions-tip / toxic-tip | staff_living_status |
| Makefile living-eia-tip / injury-tip / completions-tip / toxic-tip | Makefile |
| Ritual + vault tip rows | ritual / App |

### Living upgrade — calib/clv/clerk/bookkeeper tip batch (auto-roll, no new chips)

| Ticket | Where |
| --- | --- |
| `living_calib_tip` + `calib_tip_sunday_quiet` | desk_living / compact / export |
| `living_clv_tip` + `clv_tip_sunday_quiet` | desk_living / compact / export |
| `living_clerk_tip` + `clerk_tip_sunday_quiet` | desk_living / compact / export |
| `living_bookkeeper_tip` + `bookkeeper_tip_sunday_quiet` | desk_living / compact / export |
| Status CLI calib-tip / clv-tip / clerk-tip / bookkeeper-tip | staff_living_status |
| Makefile living-calib-tip / clv-tip / clerk-tip / bookkeeper-tip | Makefile |
| Ritual + vault tip rows | ritual / App |

### Positive ROI — exit_plan stamp on fee-clear buys (Phase 3)

| Ticket | Where |
| --- | --- |
| `default_exit_plan` / `exit_plan_coverage` | `desk_roi_plan` (not a board chip) |
| Sports / commodity / BTC stamp `exit_plan` at buy | `gap_bot` / commodity bot / `btc15m_signal` |
| Masters `roi_plan.exit_plans` | `desk_master.master_summary` |

### Positive ROI — exit_plan stamp on INX + meme opens

| Ticket | Where |
| --- | --- |
| INX S&P / sized `exit_plan` at open | `kalshi-*-paper/paper_sim.open_position` |
| Memecoin `exit_plan` (stop/flip/ladder) | `memecoin-paper/bot.py` |
| Coverage tracks fee-clear + loser towers | `exit_plan_coverage` |

### Surface backlog (soft-max — no new board chips until catalog headroom)

| Optional later surface | Notes |
| --- | --- |
| *(exhausted useful soft-max invent — pause until chip headroom or staff asks)* | Prefer money-path tickets over thin tip aliases |

Raising chip soft-max / inventing new board chips is out of scope until staff opens catalog headroom (52/64). Soft-max still binds.

### Positive ROI — Chicago bleed-week observe

| Ticket | Where |
| --- | --- |
| `capture_bleed_week` / `latest_bleed_week` | `desk_roi_plan` (not a board chip) |
| Masters `roi_plan.bleed_week` | `desk_master.master_summary` |
| Target \|red\|/\|green\| &lt; 0.5 + misplaced $ | observe only; never softens floors |

### Staff promote batch (gate lifted)

| Ticket | Where |
| --- | --- |
| Hard-stop live arm (force) | `staff_set_sports_hard_stop_live(..., force=True)` · `make living-hard-stop-promote` |
| Green_boost arm (force) | `staff_set_sports_green_boost(..., force=True)` · `make living-green-boost-arm` |
| INX band staff lock 80–90 | `staff_promote_inx_band("80_90", force=True)` · `make living-inx-band-promote` |
| Batch helper | `staff_batch_arm_promotes` · `make living-staff-promote-batch` |
| Committed artifacts | `desk_sports_hard_stop_promote.json` / `desk_sports_green_boost_promote.json` / `desk_inx_band_promote.json` |

Code default `SPORTS_HARD_STOP_LIVE` stays False. Fee floors stay 0.06 / 0.05 / 0.02. Soft-max chip catalog still 52/64.

### Near-miss soft-z staff arm + hard-stop CSV packet

| Ticket | Where |
| --- | --- |
| Soft-z force arm (edge relax forever 0) | `staff_promote_near_miss_soft("z", force=True)` · `make living-near-miss-promote` |
| Committed artifact | `desk_near_miss_promote.json` |
| Hard-stop shadow CSV export | `export_sports_hard_stop_shadow_csv` · `make living-hard-stop-export` |

### Skip-regret staff review (non-fee only)

| Ticket | Where |
| --- | --- |
| Non-fee candidate filter | `skip_regret_candidates` |
| Accept/defer log | `staff_log_skip_regret_decision` (never auto-loosens) |
| CLI | `make living-skip-regret` |
| Masters | `roi_plan.skip_regret_candidates` + `skip_regret_decisions` |

### Money-path pulse CLI (non-tip)

| Ticket | Where |
| --- | --- |
| Firm queue status | `make living-firm-queue` |
| Completions eligible | `make living-completions` |
| Feature-store coverage + quiet | `make living-feature-store` |
| Combined pulse | `make living-money-pulse` |

### Feature-store densify + completions/firm-queue observe (non-tip)

| Ticket | Where |
| --- | --- |
| Dense schema v1 (null-coded keys) | `FEATURE_DENSE_KEYS` · `densify_feature_row` · `record_decision_features` |
| Densify coverage board | `feature_store_coverage.densify_pct` / `densify_pass` (≥90%) |
| Completions eligible by tower | `completions_summary.eligible_by_bot` |
| Firm-queue observe samples | `firm_queue_status` deferred/accepted samples · `observe_only` |
| Pulse includes densify | `make living-money-pulse` → `feature_densify` |

### Sports desk-wide open-risk (E1 #116)

| Ticket | Where |
| --- | --- |
| Headroom helper | `desk_open_risk_headroom` / `desk_open_risk_blocks` |
| Sports buy + firm-queue remaining | `sports-gap-paper/gap_bot.py` uses desk-wide used/remaining |

### E1 #118–#120 regression guards

| Ticket | Where |
| --- | --- |
| #118 exits-before-entries | `test_e1_exits_stake_mint.SportsExitsBeforeEntries` |
| #119 INX stake shrink both bots | `test_e1_exits_stake_mint.InxStakeContractsShrink` |
| #120 meme learning_skip mint key | `test_e1_exits_stake_mint.MemeLearningSkipMintKey` |

### Sticky-open SLA entry block (E1 #136/#137)

| Ticket | Where |
| --- | --- |
| Sticky detect + exit_priority | `desk_more.sticky_positions` / `sticky_sla_status` |
| Red-day speculative entry block | `sticky_entry_blocks` on sports / BTC / commodity |
| Masters | `roi_plan.sticky_sla` |

### INX research evidence thin (keep 80–90)

| Ticket | Where |
| --- | --- |
| Evidence-thin board | `inx_band_promote_status.evidence_thin` / `keep_live_band` / `n_to_promote` |
| Research report flags | `run_inx_band_research.evidence_thin` |
| CLI | `make living-inx-research` / `living-inx-status` |
| Rule | Keep live **80–90** until leader n≥20 beats live EV — no force on money-path CLI |

### Near-miss soft-p second arm (after z holds M1)

| Ticket | Where |
| --- | --- |
| M1 hold helper | `near_miss_m1_holds` |
| Soft-p readiness | `near_miss_soft_p_status` (z armed + M1 + promote_ready) |
| Staff arm (no force) | `staff_promote_near_miss_soft("p")` · `make living-near-miss-soft-p` |
| Masters | `roi_plan.near_miss_soft_p` |

### E2 exit-quality observe / selective after M1

| Ticket | Where |
| --- | --- |
| Sports exit kind hit rates | `sports_exit_quality_board` |
| Combined observe | `exit_quality_observe` · `make living-exit-quality` |
| Selective throughput after M1 | `selective_throughput_observe` |
| Money pulse | `make living-money-pulse` includes exit_quality |
| Masters | `roi_plan.exit_quality` + `selective_throughput` |

### Hard-stop shadow evidence observe (n→30)

| Ticket | Where |
| --- | --- |
| Evidence-thin board | `sports_hard_stop_shadow_summary.evidence_thin` / `n_to_promote` / `label` |
| Observe CLI | `make living-hard-stop-status` |
| No-force promote when ready | `make living-hard-stop-promote-ready` (force=False) |

### BTC + commodity exit-quality observe parity

| Ticket | Where |
| --- | --- |
| Fee-clear exit kinds | `fee_clear_exit_quality_board` (TP / flip / settle) |
| Combined observe | `exit_quality_observe.fee_clear_exits` |

### Green_boost evidence-thin observe (no-force when ready)

| Ticket | Where |
| --- | --- |
| Evidence-thin board | `sports_green_boost_status.evidence_thin` / `missing` / `label` |
| Observe CLI | `make living-green-boost-status` |
| No-force arm when ready | `make living-green-boost-arm-ready` (force=False) |

### Edge08 + Helper Gate A evidence-thin observe

| Ticket | Where |
| --- | --- |
| Edge08 distance board | `btc_edge08_shadow_status.evidence_thin` / `n_to_promote` / `label` |
| No-force promote when ready | `make living-edge08-promote-ready` (force=False) |
| Helper Gate A thin board | `helper_gate_a` / `helper_promote_status.evidence_thin` / `label` |

### Near-miss evidence-thin observe + no-force z

| Ticket | Where |
| --- | --- |
| Distance board | `near_miss_promote_status.evidence_thin` / `n_to_promote` / `label` |
| Soft-p thin label | `near_miss_soft_p_status.evidence_thin` |
| Observe CLI | `make living-near-miss-status` |
| No-force soft-z when ready | `make living-near-miss-promote-ready` (force=False) |

### Promote-distance combined observe

| Ticket | Where |
| --- | --- |
| Combined board | `promote_distance_observe` · `make living-promote-distance` |
| Money pulse | `make living-money-pulse` includes `promote_distance` |
| Masters | `roi_plan.promote_distance` |

### TC-151 hillclimb lever process observe

| Ticket | Where |
| --- | --- |
| Process board | `hillclimb_lever_status` — `process_only` / `needs_staff_pick` / `label` |
| Observe CLI | `make living-hillclimb-lever` (never auto-picks) |

### Firm-health observe (Phase 2/7 pulse)

| Ticket | Where |
| --- | --- |
| Combined board | `firm_health_observe` · `make living-firm-health` |
| Bleed / daily R / opp-cost / profit-lock CLIs | `living-bleed-week` / `living-daily-r` / `living-opp-cost` / `living-profit-lock` |
| Money pulse | `make living-money-pulse` includes `firm_health` + capital OS |
| Masters | `roi_plan.firm_health` |

### Ops observe (incubation / ruin / cold / graduation / BTC calib)

| Ticket | Where |
| --- | --- |
| Combined board | `ops_observe` · `make living-ops-observe` |
| Split CLIs | `living-incubation` / `living-ruin-drill-status` / `living-cold-harvest` / `living-graduation` / `living-btc-calib` |
| Dual-control | observe-only status inside `ops_observe` (LIVE_ORDERS still deferred) |
| Money pulse / Masters | `ops` on pulse + `roi_plan.ops` |

### Guardrails observe (empty CARD / stale / adverse / anti-revenge)

| Ticket | Where |
| --- | --- |
| Combined board | `guardrails_observe` · `make living-guardrails` |
| Adverse / anti-revenge status | `adverse_cool_status` / `anti_revenge_status` |
| Split CLIs | `living-adverse-cool` / `living-anti-revenge` / `living-empty-card` / `living-stale-world` |
| Money pulse / Masters | `guardrails` on pulse + `roi_plan.guardrails` |

### Review observe (ideas / quarterly / corr)

| Ticket | Where |
| --- | --- |
| Combined board | `review_observe` · `make living-review-observe` |
| Split CLIs | `living-idea-review` / `living-quarterly` / `living-corr-matrix` |
| Money pulse / Masters | `review` on pulse + `roi_plan.review` |

### Calib + CLV + flow observe

| Ticket | Where |
| --- | --- |
| Combined board | `calib_clv_observe` · `make living-calib-clv` |
| Tower calibs / raise_Φ log | `living-sports-calib` / `living-commodity-calib` / `living-btc-calib` / `living-raise-phi-log` |
| CLV / sticky / green-or-gone / selective | `living-clv-status` / `living-sticky-sla` / `living-green-or-gone` / `living-selective` |
| Money pulse / Masters | `calib_clv` on pulse + `roi_plan.calib_clv` |
| Never auto-writes Φ | `auto_write_phi=False` |

### Baseline + fee-ledger observe (Phase 0)

| Ticket | Where |
| --- | --- |
| Combined board | `baseline_fee_observe` · `make living-baseline-fee` |
| Capture W0 | `make living-baseline-capture` |
| Fee ledger completeness | `make living-fee-ledger` |
| Money pulse / Masters | `baseline_fee` on pulse + `roi_plan.baseline_fee` |

### Commodity time-stop shadow (Phase 3 P0)

| Ticket | Where |
| --- | --- |
| Hit rule | ≤3m to close + underwater mark PnL → `commodity_time_stop_hit` |
| Shadow log | `record_commodity_time_stop_shadow` (code `COMMODITY_TIME_STOP_LIVE=False`) |
| Promote board | `commodity_time_stop_shadow_summary` · `make living-commodity-tstop-status` |
| No-force arm when ready | `make living-commodity-tstop-promote-ready` |
| Runtime | `commodity-15m-paper/bot.py` shadows; live sell only if staff-armed |
| Exit plan stamp | `model_flip+time_stop_shadow+settle` |
| Masters / promote-distance | `roi_plan.commodity_time_stop` + gate on distance board |

### Sports time-to-final trim shadow (Phase 3 P1)

| Ticket | Where |
| --- | --- |
| Hit rule | ≤5m regulation left + underwater mark → `sports_time_final_hit` |
| Clock helper | `sports_minutes_remaining` (league period map) |
| Shadow log | `record_sports_time_final_shadow` (code `SPORTS_TIME_FINAL_LIVE=False`) |
| Promote board | `sports_time_final_shadow_summary` · `make living-sports-tfinal-status` |
| No-force arm when ready | `make living-sports-tfinal-promote-ready` |
| Runtime | `sports-gap-paper/gap_bot.py` shadows; live sell only if staff-armed |
| Exit plan stamp | `…+time_final_shadow+settle` |
| Masters / promote-distance | `roi_plan.sports_time_final` + gate on distance board |

### Doc-truth inventory / README (Phase 0 honesty)

| Ticket | Where |
| --- | --- |
| Floors / cadence / exits match code | `BUY_SELL_FAILSAFE_INVENTORY.md` |
| BTC TP not print-only | root `README.md` |
| Pin test | `test_doc_truth.py` (floors 0.06/0.05/0.02; AUTO 180/60/90/180) |

### Exit-regret KPIs (Phase 3 E2 densify)

| Ticket | Where |
| --- | --- |
| Sports settle losers with prior shadow | `exit_regret_observe.sports_shadow_share` |
| BTC settle vs TP giveback (¢) | `btc_tp_giveback_avg` |
| INX flip save vs wipe | `inx_flip_save_usd` |
| Meme exit histogram | `meme_exit_histogram` |
| Wired | `exit_quality_observe.exit_regret` · Masters `roi_plan.exit_regret` |

### Next

| Ticket | Where |
| --- | --- |
| Staff pick hillclimb lever this Chicago week | TC-151 (process — external) |
| Dual-control / LIVE_ORDERS (deferred) | staff gate |
| Force-armed evidence catch-up (deferred) | hard-stop / near-miss / INX n bars |

### INX research no-force path

| Ticket | Where |
| --- | --- |
| History from kalshi-sp/sized bots | `inx_history_from_bots` |
| Research run | `run_inx_band_research` · `make living-inx-research` |
| Promote-ready board | `inx_band_promote_status` · `make living-inx-status` |
| Leader promote (no force) | `staff_promote_inx_leader` · `make living-inx-band-promote` |
| Green_boost evidence catch-up — 2 Chicago weeks M1≥0 + CLV≥52% | `sports_green_boost_status.ready` (staff already armed) |
| Hard-stop shadow n≥30 EV≥0 — drop force dependency | `sports_hard_stop_shadow_summary.promote_ready` |
| Near-miss labeled n≥30 EV≥0 — drop force; optional soft-p second | `near_miss_promote_status` → `staff_promote_near_miss_soft("p")` |
| Dual-control / LIVE_ORDERS stay off until separate staff gate | paper-only forever until staff |

### Helper Gate A staff arm CLI

| Ticket | Where |
| --- | --- |
| Gate A board | `helper_promote_status` · `make living-helper-gate-a` |
| Staff arm (ready only; no force on CLI) | `staff_set_helper_autonomy` · `make living-helper-arm` |
| Default | `may_place_alone=False` until Gate A + staff |

### BTC edge08 shadow promote (raise-only)

| Ticket | Where |
| --- | --- |
| Promote-ready board | `btc_edge08_shadow_status` (n≥30 EV≥0.5) |
| Staff promote | `staff_promote_btc_edge08` · `make living-edge08-promote` |
| Runtime | `pimp_desk.promote_shadow` writes venue_edge **0.08** (above 0.05 floor) |
| Masters | `roi_plan.btc_edge08_shadow` |

### BTC raise_Φ staff decision log

| Ticket | Where |
| --- | --- |
| Accept/defer log + before/after hit rates | `staff_log_raise_phi_decision` / `raise_phi_decision_log` |
| CLI | `tools/staff_calib_tickets.py accept\|defer\|decisions` |
| Masters | `roi_plan.raise_phi_decisions` |
| Never writes Φ | `auto_write_phi=False` forever |

## Hard rules unchanged

- Venue floors: sports 0.06 / BTC+commodity 0.05 / INX+DEX 0.02
- Starve: n≥4, factor 0.15
- Meme red lock −$5; INX halt $460
- Kill: M3↑ with M1↓ for 2 Chicago weeks → revert lever

## Tests

```bash
python -m unittest test_positive_roi_plan_slice.py desk_roi_plan desk_master -v
```
