# Living Trading Upgrade — staff smoke (paper only; floors locked; never auto-post).
.PHONY: living-status living-selfcheck living-floors living-floors-discord living-seed living-test living-doctor living-doctor-discord living-ritual living-ritual-discord living-gaps-discord living-ruin-discord

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

living-gaps-discord:
	python3 tools/staff_living_status.py gaps --discord

living-ruin-discord:
	python3 tools/staff_living_status.py ruin --discord

living-test:
	python3 -m unittest test_desk_living -q
