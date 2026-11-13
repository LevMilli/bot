#!/usr/bin/env python3
"""IWM momentum tower: a shadow twin of QQQ momentum on IWM. Shadow paper shares only.

Same rules as QQQ momentum, run on IWM 5-minute bars (Yahoo, public). The book
lives in ../etf_momentum_book.py and reads ../qqq-momentum-paper/qqq_model.py
without changing it. Checks at HH:00 and HH:30, flat by the 16:00 close.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
if DESK_ROOT not in sys.path:
    sys.path.insert(0, DESK_ROOT)

import etf_momentum_book as book  # noqa: E402

SYMBOL = "IWM"
ID = "iwm-momentum"
NAME = "IWM momentum"


def main(argv=None, *, here=None, chart=None, now=None) -> int:
    return book.main(SYMBOL, ID, NAME, here or HERE, argv, chart=chart, now=now)


if __name__ == "__main__":
    raise SystemExit(main())
