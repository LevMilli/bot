"""Tower watchdog: timeouts, two-in-a-row failures, stalls; one note each."""
import datetime as dt
import json
import types

import desk_watchdog as wd

NOW = dt.datetime(2026, 11, 12, 15, 0, tzinfo=dt.timezone.utc)


def _desk(runs, paused=()):
    return types.SimpleNamespace(
        AUTO=({"id": "fed-watch", "action": "run", "every_sec": 300},
              {"id": "kalshi-sp", "action": "brief", "at_ct": "08:00"}),
        BOTS=({"id": "fed-watch", "name": "Fed watch"}, {"id": "kalshi-sp", "name": "Kalshi S&P"}),
        _load_runs=lambda root: runs,
        bot_paused=lambda root, bot_id: bot_id in paused,
    )


def _row(minutes_ago, ok=True, summary="SIGNAL: no trade"):
    at = (NOW - dt.timedelta(minutes=minutes_ago)).strftime("%Y-%m-%d %H:%M:%S UTC")
    return {"at": at, "ok": ok, "summary": summary}


def test_timeout_posts_once_then_recovers(tmp_path):
    runs = {"fed-watch": _row(1, ok=False, summary="Stopped after 60s.\nKalshi tape: +3")}
    desk = _desk(runs)
    notes = wd.check(desk, str(tmp_path), now=NOW)
    assert len(notes) == 1 and "time limit" in notes[0] and "60s" in notes[0]
    runs["fed-watch"] = _row(0.5, ok=False, summary="Stopped after 60s.")
    assert wd.check(desk, str(tmp_path), now=NOW) == []  # deduped
    runs["fed-watch"] = _row(0.1)
    notes = wd.check(desk, str(tmp_path), now=NOW)
    assert notes == ["Watchdog: Fed watch is healthy again. Its last check finished cleanly."]
    assert wd.check(desk, str(tmp_path), now=NOW) == []


def test_two_failures_in_a_row(tmp_path):
    runs = {"fed-watch": _row(6, ok=False, summary="Traceback\nKeyError: 'yes_ask'")}
    desk = _desk(runs)
    assert wd.check(desk, str(tmp_path), now=NOW) == []  # one failure is a hiccup
    assert wd.check(desk, str(tmp_path), now=NOW) == []  # same row, not counted twice
    runs["fed-watch"] = _row(1, ok=False, summary="Traceback\nKeyError: 'yes_ask'")
    notes = wd.check(desk, str(tmp_path), now=NOW)
    assert len(notes) == 1 and "failed 2 checks in a row" in notes[0] and "KeyError" in notes[0]


def _warm(desk, root, minutes=31):
    """Watchdog has been watching for ``minutes`` (checks every 5 min)."""
    for back in range(minutes, 0, -5):
        wd.check(desk, root, now=NOW - dt.timedelta(minutes=back), timer_alive=False)


def test_stall_needs_live_timer_and_posts_once(tmp_path):
    desk = _desk({"fed-watch": _row(45)})
    _warm(desk, str(tmp_path))
    assert wd.check(desk, str(tmp_path), now=NOW, timer_alive=False) == []
    notes = wd.check(desk, str(tmp_path), now=NOW)
    assert len(notes) == 1 and "45m" in notes[0]
    assert wd.check(desk, str(tmp_path), now=NOW) == []
    saved = json.loads((tmp_path / wd.STATE_FILE).read_text())
    assert saved["fed-watch"]["said"] == ["stalled"]


def test_restart_does_not_flag_every_tower(tmp_path):
    desk = _desk({"fed-watch": _row(300)})
    assert wd.check(desk, str(tmp_path), now=NOW) == []  # just started watching
    later = NOW + dt.timedelta(minutes=5)
    assert wd.check(desk, str(tmp_path), now=later) == []
    # After a full stall window of watching, the old row is a real stall.
    for step in range(10, 40, 5):
        notes = wd.check(desk, str(tmp_path), now=NOW + dt.timedelta(minutes=step))
        if notes:
            break
    assert notes and "has not finished a check" in notes[0]


def test_recent_clean_run_is_quiet_and_paused_skipped(tmp_path):
    assert wd.check(_desk({"fed-watch": _row(3)}), str(tmp_path), now=NOW) == []
    desk = _desk({"fed-watch": _row(500, ok=False, summary="Stopped after 60s.")}, paused={"fed-watch"})
    assert wd.check(desk, str(tmp_path), now=NOW) == []


def test_one_pass_carries_watchdog_notes():
    import desk_service

    desk = types.SimpleNamespace(
        timer_health=lambda: {},
        run_scheduled=lambda: None,
        tower_watchdog=lambda: ["Watchdog: X hit its time limit"],
        drain_alerts=lambda: [],
        take_recap=lambda: "",
    )
    assert desk_service.one_pass(desk)["audit"] == ["Watchdog: X hit its time limit"]


def test_real_desk_watchdog_runs(tmp_path):
    import pimp_desk

    assert pimp_desk.tower_watchdog(str(tmp_path), now=NOW) == []
