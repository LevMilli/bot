#!/usr/bin/env python3
"""Commodity 15m 85c cap: practice twin (B2) of a 15-minute tower. Paper only. Shadow only.

All rules live in ../fifteen_twins.py (TWINS["commodity-15m-cap85"]); the shared engine is
../kalshi_shadow_tower.py. This folder holds only this twin's own ledger.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
if DESK_ROOT not in sys.path:
    sys.path.insert(0, DESK_ROOT)

import fifteen_twins  # noqa: E402

TWIN_ID = "commodity-15m-cap85"

if __name__ == "__main__":
    raise SystemExit(fifteen_twins.main(TWIN_ID, HERE))
