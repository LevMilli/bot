#!/usr/bin/env python3
"""Champions League — paper shadow. Logs only. Buys nothing.

The series is read from the public API. An open book is logged.
If the public API does not list it, the card says so and this skips.
No stake. No desk risk share. Never LIVE.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
if DESK not in sys.path:
    sys.path.insert(0, DESK)

import shadow_missing


def main(argv=None) -> int:
    return shadow_missing.main('champions-league', argv)


if __name__ == "__main__":
    raise SystemExit(main())
