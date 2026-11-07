# Living Trading Upgrade — staff smoke (paper only; floors locked; never auto-post).
.PHONY: living-status living-selfcheck living-floors living-floors-discord living-seed living-test living-doctor living-doctor-discord living-ritual living-ritual-discord living-ritual-observe living-gaps-discord living-ruin-discord living-l7 living-l7-discord

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

living-gaps-discord:
	python3 tools/staff_living_status.py gaps --discord

living-ruin-discord:
	python3 tools/staff_living_status.py ruin --discord

living-test:
	python3 -m unittest test_desk_living -q

living-l7:
	python3 -c "import desk_living; h=desk_living.living_self_check(); print(h.get('l7_observe_label')); print('ok' if h.get('l7_observe_ok') else 'missing='+str(h.get('l7_observe_missing'))); raise SystemExit(0 if h.get('l7_observe_ok') else 2)"

living-l7-discord:
	python3 -c "import desk_living; d=desk_living.living_doctor(record=False); print(d.get('soft_copy') or d.get('l7_observe_label') or 'L7 observe'); print('(staff paste · never auto-posts)')"
