# Living Trading Upgrade — staff smoke (paper only; floors locked).
.PHONY: living-status living-selfcheck living-floors living-seed living-test living-doctor

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

living-test:
	python3 -m unittest test_desk_living -q
