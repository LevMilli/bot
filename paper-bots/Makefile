# Living Trading Upgrade — staff smoke (paper only; floors locked).
.PHONY: living-status living-selfcheck living-floors living-seed living-test living-doctor living-ritual living-ritual-discord

living-status:
	python3 tools/staff_living_status.py

living-selfcheck:
	python3 tools/staff_living_status.py selfcheck

living-floors:
	python3 tools/staff_living_status.py floors

living-seed:
	python3 tools/staff_living_status.py seed

living-doctor:
	python3 tools/staff_living_status.py doctor

living-ritual:
	python3 tools/staff_living_ritual.py

living-ritual-discord:
	python3 tools/staff_living_ritual.py --discord

living-test:
	python3 -m unittest test_desk_living -q
