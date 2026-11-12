"""The desk's "Next check" is the earliest slot by time, not by text."""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pimp_desk  # noqa: E402


def test_next_check_sorts_by_time_not_text(tmp_path):
    bots = [
        {"id": "a", "next_run": "November 12, 2026, 10:41 AM Central", "next_run_at": "2026-11-12T16:41:00+00:00"},
        {"id": "b", "next_run": "November 12, 2026, 5:15 AM Central", "next_run_at": "2026-11-12T11:15:00+00:00"},
        {"id": "c", "next_run": "Paused"},
    ]
    row = pimp_desk._desk_row(bots, [], [], "", "", dict(pimp_desk.DEFAULTS), str(tmp_path))
    assert row["next_check"] == "November 12, 2026, 5:15 AM Central"
    assert "Next check November 12, 2026, 5:15 AM Central" in row["status_line"]


def test_next_at_matches_next_text(tmp_path):
    import datetime as dt

    now = dt.datetime(2026, 11, 12, 11, 0, tzinfo=dt.timezone.utc)
    at = pimp_desk._next_at("calibration-lab", str(tmp_path), now)
    assert at is not None
    assert pimp_desk._next_for("calibration-lab", str(tmp_path), now) == pimp_desk.central_text(at)
