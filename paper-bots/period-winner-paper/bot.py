#!/usr/bin/env python3
"""Period winner — paper shadow. Logs only. Buys nothing.

The series ticker is read from the repo. If it is not named, this records
that and skips. No stake. No desk risk share. Never LIVE.
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
    return shadow_missing.main('period-winner', argv)


if __name__ == "__main__":
    raise SystemExit(main())
