# Living Trading Upgrade — staff smoke (paper only; floors locked; never auto-post).
.PHONY: living-status living-selfcheck living-floors living-floors-discord living-seed living-test living-doctor living-doctor-discord living-ritual living-ritual-discord living-ritual-observe living-ritual-observe-json living-ritual-live living-ritual-live-discord living-gaps-discord living-ruin-discord living-l7 living-l7-discord living-sunday living-sunday-discord living-export living-teller living-priority living-priority-discord living-hud living-hud-discord living-help living-money living-rules living-rules-discord living-surfaces living-surfaces-discord living-smoke living-smoke-discord living-paste living-paste-discord living-paper living-paper-discord living-makefile living-makefile-discord living-venues living-venues-discord living-chicago living-chicago-discord living-starve living-starve-discord living-hard-rules living-hard-rules-discord living-swarm living-swarm-discord living-expand-tip living-expand-tip-discord living-quiet-tip living-quiet-tip-discord living-timer-tip living-timer-tip-discord living-export-tip living-export-tip-discord living-doctor-tip living-doctor-tip-discord living-inventory-tip living-inventory-tip-discord living-dual-tip living-dual-tip-discord living-hillclimb-tip living-hillclimb-tip-discord living-ruin-tip living-ruin-tip-discord living-near-miss-tip living-near-miss-tip-discord living-helper-tip living-helper-tip-discord living-hard-stop-tip living-hard-stop-tip-discord living-skip-regret-tip living-skip-regret-tip-discord living-eia-tip living-eia-tip-discord living-injury-tip living-injury-tip-discord living-completions-tip living-completions-tip-discord living-toxic-tip living-toxic-tip-discord living-calib-tip living-calib-tip-discord living-clv-tip living-clv-tip-discord living-clerk-tip living-clerk-tip-discord living-bookkeeper-tip living-bookkeeper-tip-discord living-hard-stop-promote living-hard-stop-status living-hard-stop-promote-ready living-green-boost-arm living-green-boost-status living-green-boost-arm-ready living-inx-band-promote living-staff-promote-batch living-near-miss-promote living-near-miss-status living-near-miss-promote-ready living-near-miss-soft-p living-hard-stop-export living-near-miss-label living-near-miss-export living-edge08-export living-green-boost-export living-helper-backfill living-clv-repair living-clv-completeness living-shadow-catchup living-shadow-tick living-shadow-ops living-edge08-status living-edge08-promote living-edge08-promote-ready living-helper-gate-a living-helper-arm living-inx-research living-inx-status living-skip-regret living-firm-queue living-completions living-feature-store living-money-pulse living-exit-quality living-promote-distance living-hillclimb-lever living-firm-health living-bleed-week living-daily-r living-opp-cost living-profit-lock living-ops-observe living-incubation living-ruin-drill-status living-cold-harvest living-graduation living-btc-calib living-guardrails living-adverse-cool living-anti-revenge living-empty-card living-stale-world living-review-observe living-idea-review living-quarterly living-corr-matrix living-calib-clv living-clv-status living-green-or-gone living-sticky-sla living-selective living-eligible-funnel living-insight-ratio living-edge08-compare living-cadence-health living-raise-phi-log living-sports-calib living-commodity-calib living-baseline-fee living-baseline-capture living-fee-ledger living-commodity-tstop-status living-commodity-tstop-promote living-commodity-tstop-promote-ready living-latency-stage living-tip-decision-ms living-exit-risk-ms living-fill-capacity living-firm-tower-m1 living-m5-idle-budget living-distance-stance living-hillclimb-pick living-hillclimb-pick-ready living-hillclimb-pick-list living-hillclimb-pick-status living-hillclimb-clear living-staff-promote-ready-pack living-promote-ready-pack living-staff-promote-batch-ready living-disarm-thin living-staff-disarm-thin living-dual-control-status living-dual-control living-dual-gaps living-staff-dashboard living-observation-clock living-graduation-capture living-promote-sla

living-help:
	@echo "Living Trading Upgrade — paper only · floors locked · Discord never auto-posts"
	@echo "  make living-status / living-selfcheck / living-export / living-test / living-smoke"
	@echo "  make living-hud / living-hud-discord / living-priority / living-priority-discord"
	@echo "  make living-ritual-live / living-ritual-live-discord / living-ritual-observe"
	@echo "  make living-ritual / living-ritual-discord / living-doctor / living-doctor-discord"
	@echo "  make living-floors / living-floors-discord / living-teller / living-money"
	@echo "  make living-rules / living-rules-discord / living-surfaces / living-surfaces-discord"
	@echo "  make living-paste / living-paste-discord / living-paper / living-makefile"
	@echo "  make living-venues / living-venues-discord / living-chicago / living-chicago-discord"
	@echo "  make living-starve / living-starve-discord / living-hard-rules / living-hard-rules-discord"
	@echo "  make living-swarm / living-expand-tip / living-quiet-tip / living-timer-tip"
	@echo "  make living-export-tip / living-doctor-tip / living-inventory-tip / living-dual-tip"
	@echo "  make living-hillclimb-tip / living-ruin-tip / living-near-miss-tip / living-helper-tip"
	@echo "  make living-hard-stop-tip / living-skip-regret-tip / living-eia-tip / living-injury-tip"
	@echo "  make living-completions-tip / living-toxic-tip / living-calib-tip / living-clv-tip"
	@echo "  make living-clerk-tip / living-bookkeeper-tip"
	@echo "  make living-hard-stop-promote / living-green-boost-arm / living-inx-band-promote"
	@echo "  make living-staff-promote-batch / living-near-miss-promote / living-hard-stop-export"
	@echo "  make living-staff-promote-ready-pack / living-staff-promote-batch-ready (prefer over force)"
	@echo "  make living-shadow-catchup / living-shadow-tick / living-shadow-ops / living-money-pulse"
	@echo "  make living-hillclimb-pick / living-staff-dashboard / living-observation-clock"
	@echo "  make living-dual-control-status / living-graduation-capture"
	@echo "  make living-l7 / living-sunday / living-gaps-discord / living-ruin-discord"
	@echo "Staff map: LIVING_UPGRADE.md · plan: POSITIVE_ROI_PLAN.md"

living-status:
	python3 tools/staff_living_status.py

living-selfcheck:
	python3 tools/staff_living_status.py selfcheck

living-floors:
	python3 tools/staff_living_status.py floors

living-floors-discord:
	python3 tools/staff_living_status.py floors --discord

living-seed:
	python3 tools/staff_living_status.py seed

living-doctor:
	python3 tools/staff_living_status.py doctor

living-doctor-discord:
	python3 tools/staff_living_status.py doctor --discord

living-ritual:
	python3 tools/staff_living_ritual.py

living-ritual-discord:
	python3 tools/staff_living_ritual.py --discord

# Observe-only readiness (never records doctor / never auto-posts). Exit 2 if floors soft or expand blocked.
living-ritual-observe:
	python3 tools/staff_living_ritual.py --observe

living-ritual-observe-json:
	python3 tools/staff_living_ritual.py --observe --json

# Surface audit: ritual live labels + sunday twin (never softens / never auto-posts).
living-ritual-live:
	python3 tools/staff_living_status.py ritual-live

living-ritual-live-discord:
	python3 tools/staff_living_status.py ritual-live --discord

living-gaps-discord:
	python3 tools/staff_living_status.py gaps --discord

living-ruin-discord:
	python3 tools/staff_living_status.py ruin --discord

living-test:
	python3 -m unittest test_desk_living -q

living-l7:
	python3 tools/staff_living_status.py l7

living-l7-discord:
	python3 tools/staff_living_status.py l7 --discord

living-sunday:
	python3 tools/staff_living_status.py sunday

living-sunday-discord:
	python3 tools/staff_living_status.py sunday --discord

living-export:
	python3 tools/staff_living_status.py export

living-teller:
	python3 tools/staff_living_status.py teller

living-priority:
	python3 tools/staff_living_status.py priority

living-priority-discord:
	python3 tools/staff_living_status.py priority --discord

living-hud:
	python3 tools/staff_living_status.py hud

living-hud-discord:
	python3 tools/staff_living_status.py hud --discord

living-money:
	python3 tools/staff_living_status.py money

living-rules:
	python3 tools/staff_living_status.py rules

living-rules-discord:
	python3 tools/staff_living_status.py rules --discord

living-surfaces:
	python3 tools/staff_living_status.py surfaces

living-surfaces-discord:
	python3 tools/staff_living_status.py surfaces --discord

living-smoke:
	python3 tools/staff_living_status.py smoke

living-smoke-discord:
	python3 tools/staff_living_status.py smoke --discord

living-paste:
	python3 tools/staff_living_status.py paste

living-paste-discord:
	python3 tools/staff_living_status.py paste --discord

living-paper:
	python3 tools/staff_living_status.py paper

living-paper-discord:
	python3 tools/staff_living_status.py paper --discord

living-makefile:
	python3 tools/staff_living_status.py makefile

living-makefile-discord:
	python3 tools/staff_living_status.py makefile --discord

living-venues:
	python3 tools/staff_living_status.py venues

living-venues-discord:
	python3 tools/staff_living_status.py venues --discord

living-chicago:
	python3 tools/staff_living_status.py chicago

living-chicago-discord:
	python3 tools/staff_living_status.py chicago --discord

living-starve:
	python3 tools/staff_living_status.py starve

living-starve-discord:
	python3 tools/staff_living_status.py starve --discord

living-hard-rules:
	python3 tools/staff_living_status.py hard-rules

living-hard-rules-discord:
	python3 tools/staff_living_status.py hard-rules --discord

living-swarm:
	python3 tools/staff_living_status.py swarm

living-swarm-discord:
	python3 tools/staff_living_status.py swarm --discord

living-expand-tip:
	python3 tools/staff_living_status.py expand-tip

living-expand-tip-discord:
	python3 tools/staff_living_status.py expand-tip --discord

living-quiet-tip:
	python3 tools/staff_living_status.py quiet-tip

living-quiet-tip-discord:
	python3 tools/staff_living_status.py quiet-tip --discord

living-timer-tip:
	python3 tools/staff_living_status.py timer-tip

living-timer-tip-discord:
	python3 tools/staff_living_status.py timer-tip --discord

living-export-tip:
	python3 tools/staff_living_status.py export-tip

living-export-tip-discord:
	python3 tools/staff_living_status.py export-tip --discord

living-doctor-tip:
	python3 tools/staff_living_status.py doctor-tip

living-doctor-tip-discord:
	python3 tools/staff_living_status.py doctor-tip --discord

living-inventory-tip:
	python3 tools/staff_living_status.py inventory-tip

living-inventory-tip-discord:
	python3 tools/staff_living_status.py inventory-tip --discord

living-dual-tip:
	python3 tools/staff_living_status.py dual-tip

living-dual-tip-discord:
	python3 tools/staff_living_status.py dual-tip --discord

living-hillclimb-tip:
	python3 tools/staff_living_status.py hillclimb-tip

living-hillclimb-tip-discord:
	python3 tools/staff_living_status.py hillclimb-tip --discord

living-ruin-tip:
	python3 tools/staff_living_status.py ruin-tip

living-ruin-tip-discord:
	python3 tools/staff_living_status.py ruin-tip --discord

living-near-miss-tip:
	python3 tools/staff_living_status.py near-miss-tip

living-near-miss-tip-discord:
	python3 tools/staff_living_status.py near-miss-tip --discord

living-helper-tip:
	python3 tools/staff_living_status.py helper-tip

living-helper-tip-discord:
	python3 tools/staff_living_status.py helper-tip --discord

living-hard-stop-tip:
	python3 tools/staff_living_status.py hard-stop-tip

living-hard-stop-tip-discord:
	python3 tools/staff_living_status.py hard-stop-tip --discord

living-skip-regret-tip:
	python3 tools/staff_living_status.py skip-regret-tip

living-skip-regret-tip-discord:
	python3 tools/staff_living_status.py skip-regret-tip --discord

living-eia-tip:
	python3 tools/staff_living_status.py eia-tip

living-eia-tip-discord:
	python3 tools/staff_living_status.py eia-tip --discord

living-injury-tip:
	python3 tools/staff_living_status.py injury-tip

living-injury-tip-discord:
	python3 tools/staff_living_status.py injury-tip --discord

living-completions-tip:
	python3 tools/staff_living_status.py completions-tip

living-completions-tip-discord:
	python3 tools/staff_living_status.py completions-tip --discord

living-toxic-tip:
	python3 tools/staff_living_status.py toxic-tip

living-toxic-tip-discord:
	python3 tools/staff_living_status.py toxic-tip --discord

living-calib-tip:
	python3 tools/staff_living_status.py calib-tip

living-calib-tip-discord:
	python3 tools/staff_living_status.py calib-tip --discord

living-clv-tip:
	python3 tools/staff_living_status.py clv-tip

living-clv-tip-discord:
	python3 tools/staff_living_status.py clv-tip --discord

living-clerk-tip:
	python3 tools/staff_living_status.py clerk-tip

living-clerk-tip-discord:
	python3 tools/staff_living_status.py clerk-tip --discord

living-bookkeeper-tip:
	python3 tools/staff_living_status.py bookkeeper-tip

living-bookkeeper-tip-discord:
	python3 tools/staff_living_status.py bookkeeper-tip --discord

# Money-path staff promotes (paper only · floors locked · never auto).
living-hard-stop-promote:
	python3 tools/staff_living_status.py hard-stop-promote

living-hard-stop-status:
	python3 tools/staff_living_status.py hard-stop-status

living-hard-stop-promote-ready:
	python3 tools/staff_living_status.py hard-stop-promote-ready

living-green-boost-arm:
	python3 tools/staff_living_status.py green-boost-arm

living-green-boost-status:
	python3 tools/staff_living_status.py green-boost-status

living-green-boost-arm-ready:
	python3 tools/staff_living_status.py green-boost-arm-ready

living-inx-research:
	python3 tools/staff_living_status.py inx-research

living-inx-status:
	python3 tools/staff_living_status.py inx-status

living-inx-band-promote:
	python3 tools/staff_living_status.py inx-band-promote

living-staff-promote-batch:
	@echo "STAFF FORCE OVERRIDE — prefer make living-staff-promote-batch-ready"
	python3 tools/staff_living_status.py staff-promote-batch

living-near-miss-promote:
	python3 tools/staff_living_status.py near-miss-promote

living-near-miss-status:
	python3 tools/staff_living_status.py near-miss-status

living-near-miss-promote-ready:
	python3 tools/staff_living_status.py near-miss-promote-ready

living-near-miss-soft-p:
	python3 tools/staff_living_status.py near-miss-soft-p

living-hard-stop-export:
	python3 tools/staff_living_status.py hard-stop-export

living-near-miss-label:
	python3 tools/staff_living_status.py near-miss-label

living-near-miss-export:
	python3 tools/staff_living_status.py near-miss-export

living-edge08-export:
	python3 tools/staff_living_status.py edge08-export

living-green-boost-export:
	python3 tools/staff_living_status.py green-boost-export

living-helper-backfill:
	python3 tools/staff_living_status.py helper-backfill

living-clv-repair:
	python3 tools/staff_living_status.py clv-repair

living-clv-completeness:
	python3 tools/staff_living_status.py clv-completeness

living-shadow-catchup:
	python3 tools/staff_living_status.py shadow-catchup

living-shadow-tick:
	python3 tools/staff_living_status.py shadow-tick

living-shadow-ops:
	python3 tools/staff_living_status.py shadow-ops

living-edge08-status:
	python3 tools/staff_living_status.py edge08-status

living-edge08-promote:
	python3 tools/staff_living_status.py edge08-promote

living-edge08-promote-ready:
	python3 tools/staff_living_status.py edge08-promote-ready

living-helper-gate-a:
	python3 tools/staff_living_status.py helper-gate-a

living-helper-arm:
	python3 tools/staff_living_status.py helper-arm

living-skip-regret:
	python3 tools/staff_living_status.py skip-regret

living-firm-queue:
	python3 tools/staff_living_status.py firm-queue

living-completions:
	python3 tools/staff_living_status.py completions

living-feature-store:
	python3 tools/staff_living_status.py feature-store

living-money-pulse:
	python3 tools/staff_living_status.py money-pulse

living-exit-quality:
	python3 tools/staff_living_status.py exit-quality

living-promote-distance:
	python3 tools/staff_living_status.py promote-distance

living-hillclimb-lever:
	python3 tools/staff_living_status.py hillclimb-lever

living-firm-health:
	python3 tools/staff_living_status.py firm-health

living-bleed-week:
	python3 tools/staff_living_status.py bleed-week

living-daily-r:
	python3 tools/staff_living_status.py daily-r

living-opp-cost:
	python3 tools/staff_living_status.py opp-cost

living-profit-lock:
	python3 tools/staff_living_status.py profit-lock

living-ops-observe:
	python3 tools/staff_living_status.py ops-observe

living-incubation:
	python3 tools/staff_living_status.py incubation

living-ruin-drill-status:
	python3 tools/staff_living_status.py ruin-drill

living-cold-harvest:
	python3 tools/staff_living_status.py cold-harvest

living-graduation:
	python3 tools/staff_living_status.py graduation

living-btc-calib:
	python3 tools/staff_living_status.py btc-calib

living-eth-calib:
	python3 tools/staff_living_status.py eth-calib

living-guardrails:
	python3 tools/staff_living_status.py guardrails

living-adverse-cool:
	python3 tools/staff_living_status.py adverse-cool

living-anti-revenge:
	python3 tools/staff_living_status.py anti-revenge

living-empty-card:
	python3 tools/staff_living_status.py empty-card

living-stale-world:
	python3 tools/staff_living_status.py stale-world

living-review-observe:
	python3 tools/staff_living_status.py review-observe

living-idea-review:
	python3 tools/staff_living_status.py idea-review

living-quarterly:
	python3 tools/staff_living_status.py quarterly

living-corr-matrix:
	python3 tools/staff_living_status.py corr-matrix

living-calib-clv:
	python3 tools/staff_living_status.py calib-clv

living-clv-status:
	python3 tools/staff_living_status.py clv-status

living-clv-leagues:
	python3 tools/staff_living_status.py clv-leagues

living-green-or-gone:
	python3 tools/staff_living_status.py green-or-gone

living-sticky-sla:
	python3 tools/staff_living_status.py sticky-sla

living-selective:
	python3 tools/staff_living_status.py selective

living-eligible-funnel:
	python3 tools/staff_living_status.py eligible-funnel

living-insight-ratio:
	python3 tools/staff_living_status.py insight-ratio

living-edge08-compare:
	python3 tools/staff_living_status.py edge08-compare

living-cadence-health:
	python3 tools/staff_living_status.py cadence-health

living-raise-phi-log:
	python3 tools/staff_living_status.py raise-phi-log

living-sports-calib:
	python3 tools/staff_living_status.py sports-calib

living-commodity-calib:
	python3 tools/staff_living_status.py commodity-calib

living-baseline-fee:
	python3 tools/staff_living_status.py baseline-fee

living-baseline-capture:
	python3 tools/staff_living_status.py baseline-capture

living-fee-ledger:
	python3 tools/staff_living_status.py fee-ledger

.PHONY: living-half-kelly-crb living-fee-sim living-dutch-book living-sharp-lag-harvest living-fed-watch-harvest living-poly-arb living-poly-arb-harvest living-cpi-nowcast living-vol-curve living-vol-curve-harvest living-funding-twins living-macro-harvest living-line-shopper living-btc-basis-scout living-nhl-poisson-audit living-dvol-regime living-multi-ex-disagree living-funding-scout living-metals-heat living-energy-heat living-inx-band-occupancy
living-half-kelly-crb:
	python3 tools/staff_living_status.py half-kelly-crb

living-fee-sim:
	python3 tools/staff_living_status.py fee-sim

living-dutch-book:
	python3 tools/staff_living_status.py dutch-book

living-sharp-lag-harvest:
	python3 tools/staff_living_status.py sharp-lag-harvest

living-fed-watch-harvest:
	python3 tools/staff_living_status.py fed-watch-harvest

living-poly-arb:
	python3 tools/staff_living_status.py poly-arb

living-poly-arb-harvest:
	python3 tools/staff_living_status.py poly-arb-harvest

living-cpi-nowcast:
	python3 tools/staff_living_status.py cpi-nowcast

living-vol-curve:
	python3 tools/staff_living_status.py vol-curve

living-vol-curve-harvest:
	python3 tools/staff_living_status.py vol-curve-harvest

living-funding-twins:
	python3 tools/staff_living_status.py funding-twins

living-macro-harvest:
	python3 tools/staff_living_status.py macro-harvest

living-line-shopper:
	python3 tools/staff_living_status.py line-shopper

living-btc-basis-scout:
	python3 tools/staff_living_status.py btc-basis-scout

living-nhl-poisson-audit:
	python3 tools/staff_living_status.py nhl-poisson-audit

living-dvol-regime:
	python3 tools/staff_living_status.py dvol-regime

living-multi-ex-disagree:
	python3 tools/staff_living_status.py multi-ex-disagree

living-funding-scout:
	python3 tools/staff_living_status.py funding-scout

living-metals-heat:
	python3 tools/staff_living_status.py metals-heat

living-energy-heat:
	python3 tools/staff_living_status.py energy-heat

living-inx-band-occupancy:
	python3 tools/staff_living_status.py inx-band-occupancy

living-commodity-tstop-status:
	python3 tools/staff_living_status.py commodity-tstop-status

living-commodity-tstop-promote:
	python3 tools/staff_living_status.py commodity-tstop-promote

living-commodity-tstop-promote-ready:
	python3 tools/staff_living_status.py commodity-tstop-promote-ready

living-sports-tfinal-status:
	python3 tools/staff_living_status.py sports-tfinal-status

living-sports-tfinal-promote:
	python3 tools/staff_living_status.py sports-tfinal-promote

living-sports-tfinal-promote-ready:
	python3 tools/staff_living_status.py sports-tfinal-promote-ready

# Post-E3E7 money-path boards (#358) — observe only; floors locked; never tip invent.
living-latency-stage:
	python3 tools/staff_living_status.py latency-stage

living-tip-decision-ms:
	python3 tools/staff_living_status.py tip-decision-ms

living-exit-risk-ms:
	python3 tools/staff_living_status.py exit-risk-ms

living-fill-capacity:
	python3 tools/staff_living_status.py fill-capacity

living-firm-tower-m1:
	python3 tools/staff_living_status.py firm-tower-m1

living-m5-idle-budget:
	python3 tools/staff_living_status.py m5-idle-budget

living-distance-stance:
	python3 tools/staff_living_status.py distance-stance

# Staff SLA pack — observe / no-force; never LIVE; never tip invent; floors locked.
living-hillclimb-pick-list:
	python3 tools/staff_hillclimb_pick.py list

living-hillclimb-pick-status:
	python3 tools/staff_hillclimb_pick.py status

living-hillclimb-pick-ready:
	python3 tools/staff_hillclimb_pick.py pack

living-hillclimb-pick:
	@if [ -n "$(HILLCLIMB_LEVER)" ]; then \
	  python3 tools/staff_hillclimb_pick.py pick "$(HILLCLIMB_LEVER)" --note "$(NOTE)"; \
	else \
	  python3 tools/staff_living_status.py hillclimb-pick; \
	fi

living-hillclimb-clear:
	python3 tools/staff_hillclimb_pick.py clear --who "$(WHO)" --note "$(NOTE)"

living-staff-promote-ready-pack living-promote-ready-pack:
	python3 tools/staff_living_status.py promote-ready-pack

living-staff-promote-batch-ready:
	python3 tools/staff_living_status.py staff-promote-batch-ready

# Safety rollback: disarm staff promotes that are armed while evidence is still thin.
living-disarm-thin living-staff-disarm-thin:
	python3 tools/staff_living_status.py disarm-thin

living-dual-control-status living-dual-control:
	python3 tools/staff_living_status.py dual-control-status

living-dual-gaps:
	python3 tools/staff_living_status.py gaps

living-staff-dashboard:
	python3 tools/staff_living_status.py staff-dashboard

living-observation-clock:
	python3 tools/staff_living_status.py observation-clock

living-graduation-capture:
	python3 tools/staff_living_status.py graduation-capture

living-promote-sla:
	python3 tools/staff_living_status.py promote-sla
