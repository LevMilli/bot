# Living Trading Upgrade — staff smoke (paper only; floors locked; never auto-post).
.PHONY: living-status living-selfcheck living-floors living-floors-discord living-seed living-test living-doctor living-doctor-discord living-ritual living-ritual-discord living-ritual-observe living-ritual-observe-json living-ritual-live living-ritual-live-discord living-gaps-discord living-ruin-discord living-l7 living-l7-discord living-sunday living-sunday-discord living-export living-teller living-priority living-priority-discord living-hud living-hud-discord living-help living-money living-rules living-rules-discord living-surfaces living-surfaces-discord living-smoke living-smoke-discord living-paste living-paste-discord living-paper living-paper-discord living-makefile living-makefile-discord living-venues living-venues-discord living-chicago living-chicago-discord living-starve living-starve-discord living-hard-rules living-hard-rules-discord living-swarm living-swarm-discord living-expand-tip living-expand-tip-discord living-quiet-tip living-quiet-tip-discord living-timer-tip living-timer-tip-discord living-export-tip living-export-tip-discord living-doctor-tip living-doctor-tip-discord living-inventory-tip living-inventory-tip-discord living-dual-tip living-dual-tip-discord living-hillclimb-tip living-hillclimb-tip-discord living-ruin-tip living-ruin-tip-discord

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
	@echo "  make living-hillclimb-tip / living-ruin-tip"
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
