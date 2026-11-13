"""Desk ops checks: run stats, slow towers, daily summary, disk, memory, clock, backups, health."""
import datetime as dt
import json
import os
import tarfile
import types
import urllib.request

import pytest

import desk_ops as ops
import desk_service

NOW = dt.datetime(2026, 11, 13, 18, 0, tzinfo=dt.timezone.utc)  # 12:00 CT


def _desk(runs, root=None, paused=(), settle=None):
    return types.SimpleNamespace(
        AUTO=({"id": "fed-watch", "action": "run", "every_sec": 300},
              {"id": "gdp", "action": "run", "every_sec": 600},
              {"id": "kalshi-sp", "action": "brief", "at_ct": "08:00"}),
        BOTS=({"id": "fed-watch", "name": "Fed watch"}, {"id": "gdp", "name": "GDP nowcast"},
              {"id": "kalshi-sp", "name": "Kalshi S&P"}),
        _load_runs=lambda root: runs,
        bot_paused=lambda root, bot_id: bot_id in paused,
        settlement_dir=lambda: settle,
    )


def _row(when, ok=True, summary="SIGNAL: no trade", secs=3.0):
    row = {"at": when.strftime("%Y-%m-%d %H:%M:%S UTC"), "ok": ok, "summary": summary}
    if secs is not None:
        row["secs"] = secs
    return row


def _quiet(**extra):
    base = {"fetch": lambda: (NOW.timestamp(), NOW.timestamp()), "mem_reader": lambda: {},
            "usage": lambda p: (100, 10, 90), "background": False}
    base.update(extra)
    return base


# ------------------------------------------------------------ run stats

def test_each_finished_check_counts_once_and_losses_of_cleanliness_count(tmp_path):
    runs = {"fed-watch": _row(NOW, secs=2.0)}
    desk = _desk(runs)
    root = str(tmp_path)
    ops.record_runs(desk, root, NOW)
    ops.record_runs(desk, root, NOW)  # same row, not counted again
    runs["fed-watch"] = _row(NOW + dt.timedelta(minutes=5), ok=False, summary="Traceback\nKeyError: 'x'", secs=4.0)
    ops.record_runs(desk, root, NOW)
    runs["fed-watch"] = _row(NOW + dt.timedelta(minutes=10), ok=False, summary="Stopped after 60s.\nmore", secs=60.0)
    stats = ops.record_runs(desk, root, NOW)
    day = ops.tower_day(stats, "fed-watch", "2026-11-13")
    assert day["runs"] == 3 and day["ok"] == 1 and day["fails"] == 1 and day["timeouts"] == 1
    assert day["success_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert day["avg_secs"] == pytest.approx(22.0)
    assert day["last_error"] == "Stopped after 60s."


def test_day_boundary_is_central_time(tmp_path):
    late = dt.datetime(2026, 11, 14, 5, 30, tzinfo=dt.timezone.utc)  # 11:30 PM CT on the 13th
    stats = ops.record_runs(_desk({"gdp": _row(late)}), str(tmp_path), late)
    assert "2026-11-13" in stats["days"] and "2026-11-14" not in stats["days"]


def test_rows_without_seconds_still_count(tmp_path):
    stats = ops.record_runs(_desk({"gdp": _row(NOW, secs=None)}), str(tmp_path), NOW)
    day = ops.tower_day(stats, "gdp", "2026-11-13")
    assert day["runs"] == 1 and day["avg_secs"] is None


def test_stats_keep_fourteen_days(tmp_path):
    root = str(tmp_path)
    runs = {}
    desk = _desk(runs)
    for back in range(20):
        when = NOW - dt.timedelta(days=back)
        runs["gdp"] = _row(when)
        stats = ops.record_runs(desk, root, when)
    assert len(stats["days"]) == ops.KEEP_DAYS


def _stats_with(base_secs, today_secs, base_runs=30, today_runs=6):
    days = {}
    for back in range(1, 4):
        day = (NOW - dt.timedelta(days=back)).astimezone(ops.CT).date().isoformat()
        days[day] = {"gdp": {"runs": base_runs // 3, "ok": base_runs // 3, "timed": base_runs // 3,
                             "secs": base_secs * (base_runs // 3)}}
    days["2026-11-13"] = {"gdp": {"runs": today_runs, "ok": today_runs, "timed": today_runs,
                                  "secs": today_secs * today_runs}}
    return {"seen": {}, "days": days}


def test_slow_tower_note_once_per_day():
    state = {}
    desk = _desk({})
    notes = ops.slow_notes(desk, _stats_with(10, 25), state, NOW)
    assert len(notes) == 1 and "GDP nowcast is slow today" in notes[0] and "10s" in notes[0]
    assert ops.slow_notes(desk, _stats_with(10, 25), state, NOW) == []


def test_slow_needs_enough_history_and_real_time():
    desk = _desk({})
    assert ops.slow_notes(desk, _stats_with(10, 19), {}, NOW) == []          # under 2x
    assert ops.slow_notes(desk, _stats_with(10, 25, base_runs=9), {}, NOW) == []  # thin history
    assert ops.slow_notes(desk, _stats_with(1, 4), {}, NOW) == []            # tiny runs


def test_daily_summary_names_failures_and_missing_towers(tmp_path):
    stats = {"days": {"2026-11-12": {
        "fed-watch": {"runs": 100, "ok": 97, "fails": 2, "timeouts": 1},
    }}}
    line = ops.daily_summary(_desk({}), str(tmp_path), stats, "2026-11-12", NOW)
    assert line.startswith("Ops daily for 2026-11-12: 1 of 2 timed towers ran (100 checks, 97.0% clean).")
    assert "Not clean: Fed watch 3." in line and "No finished check: GDP nowcast." in line


def test_daily_summary_all_ran_and_paused_towers_skip(tmp_path):
    stats = {"days": {"2026-11-12": {"fed-watch": {"runs": 4, "ok": 4}}}}
    line = ops.daily_summary(_desk({}, paused=("gdp",)), str(tmp_path), stats, "2026-11-12", NOW)
    assert line == "Ops daily for 2026-11-12: all 1 timed towers ran (4 checks, 100.0% clean)."


def test_check_posts_summary_once_on_a_new_day(tmp_path):
    root = str(tmp_path)
    runs = {"fed-watch": _row(NOW - dt.timedelta(days=1))}
    desk = _desk(runs)
    assert ops.check(desk, root, NOW - dt.timedelta(days=1), **_quiet()) == []  # first start
    notes = ops.check(desk, root, NOW, **_quiet())
    assert len(notes) == 1 and notes[0].startswith("Ops daily for 2026-11-12")
    assert ops.check(desk, root, NOW, **_quiet()) == []


# ------------------------------------------------------------ disk, memory, clock

def test_disk_alert_at_eighty_and_clear_under_seventy_five():
    state = {}
    assert ops.disk_notes("/x", state, lambda p: (100, 79, 21)) == []
    notes = ops.disk_notes("/x", state, lambda p: (100, 81, 19))
    assert len(notes) == 1 and "81% full" in notes[0]
    assert ops.disk_notes("/x", state, lambda p: (100, 90, 10)) == []
    assert ops.disk_notes("/x", state, lambda p: (100, 77, 23)) == []
    assert ops.disk_notes("/x", state, lambda p: (100, 60, 40)) == ["Ops: the data disk is back to 60% full."]


def test_memory_needs_three_high_passes():
    state = {}
    high = lambda: {"used": 850, "limit": 1000, "frac": 0.85}  # noqa: E731
    assert ops.memory_notes(state, NOW, high) == []
    assert ops.memory_notes(state, NOW, lambda: {"used": 500, "limit": 1000, "frac": 0.5}) == []  # streak resets
    assert ops.memory_notes(state, NOW, high) == []
    assert ops.memory_notes(state, NOW, high) == []
    notes = ops.memory_notes(state, NOW, high)
    assert len(notes) == 1 and "85%" in notes[0] and "3 passes" in notes[0]
    assert ops.memory_notes(state, NOW, high) == []
    assert ops.memory_notes(state, NOW, lambda: {"used": 600, "limit": 1000, "frac": 0.6}) == [
        "Ops: memory is back to 60% of the limit."]


def test_memory_samples_hourly_for_graphs():
    state = {}
    reader = lambda: {"used": 400e6, "limit": 1000e6, "frac": 0.4}  # noqa: E731
    for minutes in range(0, 180, 3):
        ops.memory_notes(state, NOW + dt.timedelta(minutes=minutes), reader)
    assert len(state["mem_samples"]) == 3


def test_memory_reader_handles_cgroup_v2_and_no_limit(tmp_path):
    (tmp_path / "memory.current").write_text("500\n")
    (tmp_path / "memory.max").write_text("1000\n")
    assert ops.memory_use(str(tmp_path)) == {"used": 500, "limit": 1000, "frac": 0.5}
    (tmp_path / "memory.max").write_text("max\n")
    assert ops.memory_use(str(tmp_path)) == {}


def test_clock_drift_alert_hourly_and_clear():
    state = {}
    assert ops.clock_notes(state, NOW, lambda: (100.0, 101.0)) == []
    assert state["clock_drift_s"] == 1.0
    assert ops.clock_notes(state, NOW + dt.timedelta(minutes=30), lambda: (100.0, 110.0)) == []  # not due
    notes = ops.clock_notes(state, NOW + dt.timedelta(minutes=61), lambda: (100.0, 103.5))
    assert len(notes) == 1 and "3.5s ahead of" in notes[0]
    notes = ops.clock_notes(state, NOW + dt.timedelta(minutes=125), lambda: (100.0, 100.2))
    assert notes == ["Ops: the server clock is back within 0.2s of public time."]


def test_clock_source_down_is_quiet():
    def boom():
        raise OSError("down")
    assert ops.clock_notes({}, NOW, boom) == []


def test_public_time_parses_trace(monkeypatch):
    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=-1):
            return b"fl=1\nts=1794600000.250\nip=x\n"
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=5: R())
    server, local = ops.public_time()
    assert server == 1794600000.25 and local > 0


# ------------------------------------------------------------ backups

def _books(tmp_path):
    src = tmp_path / "data" / "paper-bots"
    (src / "more-15m-paper").mkdir(parents=True)
    (src / "more-15m-paper" / "state.json").write_text(json.dumps({"bank": 1234.5}))
    (src / "pimp-runs.json").write_text("{}")
    (src / "half.json.tmp").write_text("{bad")
    return src


def test_backup_packs_verifies_and_restores(tmp_path):
    src = _books(tmp_path)
    dest = tmp_path / "data" / "backups"
    result = ops.make_backup(str(src), str(dest), NOW)
    assert result["ok"] and result["files"] == 2 and result["bad_json"] == []
    with tarfile.open(result["path"]) as tar:
        assert not any(n.endswith(".tmp") for n in tar.getnames())
    out = tmp_path / "restore"
    back = ops.restore_backup(result["path"], str(out))
    assert back["ok"]
    assert json.loads((out / "paper-bots" / "more-15m-paper" / "state.json").read_text()) == {"bank": 1234.5}
    assert not ops.restore_backup(result["path"], str(out))["ok"]  # never over a full folder


def test_backup_keeps_thirty(tmp_path):
    src = _books(tmp_path)
    dest = tmp_path / "backups"
    for back in range(32, -1, -1):
        ops.make_backup(str(src), str(dest), NOW - dt.timedelta(days=back))
    names = ops.list_backups(str(dest))
    assert len(names) == 30 and names[-1] == "paper-books-2026-11-13.tar.gz"


def test_backup_refuses_folder_inside_books(tmp_path):
    src = _books(tmp_path)
    assert not ops.make_backup(str(src), str(src / "backups"), NOW)["ok"]


def test_bad_json_fails_verify(tmp_path):
    src = _books(tmp_path)
    (src / "broken.json").write_text("{not json")
    result = ops.make_backup(str(src), str(tmp_path / "b"), NOW)
    assert not result["ok"] and result["bad_json"] == ["paper-bots/broken.json"]
    assert ops.list_backups(str(tmp_path / "b")) == []


def test_nightly_backup_runs_once_after_three_ct(tmp_path, monkeypatch):
    src = _books(tmp_path)
    monkeypatch.setenv("PAPER_BACKUP_DIR", str(tmp_path / "backups"))
    root = tmp_path / "desk"
    root.mkdir()
    desk = _desk({}, settle=str(src))
    early = dt.datetime(2026, 11, 13, 8, 0, tzinfo=dt.timezone.utc)  # 2 AM CT
    ops.check(desk, str(root), early, **_quiet())
    assert ops.list_backups() == []
    ops.check(desk, str(root), NOW, **_quiet())
    assert ops.list_backups() == ["paper-books-2026-11-13.tar.gz"]
    state = json.loads((root / ops.OPS_FILE).read_text())
    assert state["backup_last"]["ok"] and state["backup_day"] == "2026-11-13"
    os.remove(tmp_path / "backups" / "paper-books-2026-11-13.tar.gz")
    ops.check(desk, str(root), NOW + dt.timedelta(hours=1), **_quiet())
    assert ops.list_backups() == []  # one per day


def test_failed_backup_posts_next_pass(tmp_path, monkeypatch):
    src = _books(tmp_path)
    monkeypatch.setenv("PAPER_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(ops, "make_backup", lambda *a, **k: {"ok": False, "error": "Disk said no."})
    root = tmp_path / "desk"
    root.mkdir()
    desk = _desk({}, settle=str(src))
    ops.check(desk, str(root), NOW, **_quiet())
    notes = ops.check(desk, str(root), NOW + dt.timedelta(minutes=3), **_quiet())
    assert notes == ["Ops: the nightly backup did not finish. Disk said no."]
    assert ops.check(desk, str(root), NOW + dt.timedelta(minutes=6), **_quiet()) == []


def test_no_volume_no_backup(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_BACKUP_DIR", str(tmp_path / "backups"))
    ops.check(_desk({}), str(tmp_path), NOW, **_quiet())
    assert not (tmp_path / "backups").exists()


# ------------------------------------------------------------ grouping, hook, health

def test_group_notes_one_message_for_many():
    assert ops.group_notes(["a", "b"]) == ["a", "b"]
    many = [f"Watchdog: Tower {i} failed 2 checks in a row. Last line: KeyError 'yes_ask'" for i in range(30)]
    grouped = ops.group_notes(many)
    assert grouped[0].startswith("Desk health: 30 notes this pass.")
    assert all(len(g) <= ops.NOTE_LIMIT for g in grouped)
    assert len(grouped) < 10
    assert sum(g.count("\n- ") for g in grouped) == 30  # nothing dropped


def test_one_pass_groups_watchdog_and_ops_notes():
    class Desk:
        def timer_health(self):
            return {}

        def run_scheduled(self):
            pass

        def tower_watchdog(self):
            return ["w1", "w2"]

        def ops_check(self):
            return ["o1"]

        def drain_alerts(self):
            return []

        def take_recap(self):
            return ""
    out = desk_service.one_pass(Desk())
    assert out["audit"] == ["Desk health: 3 notes this pass.\n- w1\n- w2\n- o1"]


def test_one_pass_survives_ops_failure():
    class Desk:
        def timer_health(self):
            return {}

        def run_scheduled(self):
            pass

        def ops_check(self):
            raise RuntimeError("boom")

        def drain_alerts(self):
            return []

        def take_recap(self):
            return ""
    assert desk_service.one_pass(Desk())["audit"] == []


def test_check_never_raises(tmp_path):
    desk = types.SimpleNamespace(BOTS=(), AUTO=())  # missing everything
    assert ops.check(desk, str(tmp_path), NOW, **_quiet()) == []


def test_build_info_reads_pr_number():
    env = {"RAILWAY_GIT_COMMIT_SHA": "2256d39abcdef0123", "RAILWAY_GIT_COMMIT_MESSAGE":
           "Log desk open count for the evening report (#708)\n\nCo-authored-by: x"}
    info = ops.build_info(env)
    assert info == {"sha": "2256d39abcde", "pr": 708, "title": "Log desk open count for the evening report (#708)"}
    assert ops.build_line(env).startswith("build 2256d39abcde (PR #708)")
    assert ops.build_info({}) == {"sha": "", "pr": None, "title": ""}


def test_health_shows_last_pass_and_no_paths(tmp_path):
    beat = tmp_path / "beat.json"
    beat.write_text(json.dumps({"at": "2026-11-13 17:58:00 UTC"}))
    desk = types.SimpleNamespace(
        _read_json=lambda p: json.loads(open(p).read()),
        heartbeat_path=lambda root=None: str(beat),
        _root=lambda root=None: str(tmp_path),
    )
    out = ops.health(desk, now=NOW)
    assert out["last_pass_age_s"] == 120 and out["last_pass_at"].startswith("2026-11-13T17:58:00")
    assert "kalshi_gateway" in out and "build" in out
    assert str(tmp_path) not in json.dumps(out)


def test_real_pimp_desk_run_rows_carry_seconds():
    import inspect

    import pimp_desk
    src = inspect.getsource(pimp_desk)
    assert '"secs": round(time.monotonic() - started, 2)' in src
    assert callable(pimp_desk.ops_check)


def test_ops_files_survive_a_redeploy_and_write_through_the_link(tmp_path):
    import pimp_desk
    assert "pimp-run-stats.json" in pimp_desk.SETTLEMENT_FILES
    assert "pimp-ops.json" in pimp_desk.SETTLEMENT_FILES
    volume = tmp_path / "volume.json"
    volume.write_text("{}")
    link = tmp_path / "pimp-ops.json"
    os.symlink(volume, link)
    ops._save(str(link), {"a": 1})
    assert os.path.islink(link) and json.loads(volume.read_text()) == {"a": 1}
