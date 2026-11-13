"""Desk operations checks. Paper only, read-only for every tower.

The tower watchdog (``desk_watchdog``) says when one tower times out, fails or
stalls. This module watches the desk as a whole, once per timer pass:

* **Run stats.** Every finished check in ``pimp-runs.json`` is counted per tower
  per Central-time day: runs, clean runs, failures, time-limit stops and run
  seconds. Kept 14 days in ``pimp-run-stats.json``.
* **Slow towers.** When a tower's average run time today is at least twice its
  7-day average, one note per tower per day.
* **Daily summary.** The first pass of a new Central day posts one line about
  yesterday: how many towers ran, clean rate, who failed, who never ran.
* **Disk.** One note when the data disk is 80% full, one when it is back under 75%.
* **Memory.** One note when the container stays over 80% of its memory limit for
  three passes in a row, one when it is back under 70%. Hourly samples are kept
  for graphs.
* **Clock.** Once an hour, compare the server clock with a public time source.
  One note when it is off by more than 2 seconds.
* **Backups.** Once a day after 3 AM Central, pack the paper books on the volume
  into ``/data/backups``, check the copy opens and every JSON file reads, and
  keep the newest 30.

Nothing here changes what a tower buys, sells, sizes or settles. A failure in
any check is logged and skipped; it never stops a timer pass. State lives in
``pimp-ops.json`` next to the other desk files.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import shutil
import tarfile
import threading
import time
import urllib.request

log = logging.getLogger("desk_ops")

OPS_FILE = "pimp-ops.json"
STATS_FILE = "pimp-run-stats.json"
KEEP_DAYS = 14
SLOW_MULT = 2.0
SLOW_MIN_RUNS = 5         # runs today before a slow note
SLOW_MIN_BASE_RUNS = 20   # runs in the prior 7 days before a slow note
SLOW_MIN_SECS = 5.0       # tiny runs never count as slow
DISK_ALERT = 0.80
DISK_CLEAR = 0.75
MEM_ALERT = 0.80
MEM_CLEAR = 0.70
MEM_STREAK = 3
MEM_SAMPLE_EVERY_S = 3600
MEM_SAMPLES = 72
CLOCK_EVERY_S = 3600
CLOCK_ALERT_S = 2.0
CLOCK_CLEAR_S = 1.0
CLOCK_URL = "https://www.cloudflare.com/cdn-cgi/trace"
BACKUP_HOUR_CT = 3
BACKUP_KEEP = 30
BACKUP_SKIP_DISK = 0.90
NOTE_LIMIT = 480          # one Discord audit note holds 500 characters

STARTED_AT = time.time()

try:
    from zoneinfo import ZoneInfo
    CT = ZoneInfo("America/Chicago")
except Exception:  # noqa: BLE001 - tzdata missing: fall back to a fixed offset
    CT = dt.timezone(dt.timedelta(hours=-6))


# ---------------------------------------------------------------- small helpers

def _now(now=None) -> dt.datetime:
    now = now or dt.datetime.now(dt.timezone.utc)
    return now if now.tzinfo else now.replace(tzinfo=dt.timezone.utc)


def ct_day(when: dt.datetime) -> str:
    return _now(when).astimezone(CT).date().isoformat()


def _load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(path: str, data: dict) -> None:
    if os.path.islink(path):  # bound to the volume: write through the link, never over it
        path = os.path.realpath(path)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def _when(text):
    import desk_watchdog
    return desk_watchdog._when(text)


def _names(desk) -> dict:
    return {b["id"]: b.get("name") or b["id"] for b in getattr(desk, "BOTS", ())}


def _last_line(summary: str) -> str:
    lines = [ln.strip() for ln in str(summary or "").splitlines() if ln.strip()]
    line = lines[-1] if lines else "no output"
    return line if len(line) <= 120 else line[:117] + "..."


def _fit(text: str, limit: int = NOTE_LIMIT) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _expected(desk, root: str, now: dt.datetime) -> list:
    """Towers on an every-N-seconds timer that are not paused."""
    import desk_watchdog
    names = _names(desk)
    out = []
    for bot_id in sorted(desk_watchdog._gaps(desk, root, now)):
        if bot_id not in names:
            continue
        try:
            if desk.bot_paused(root, bot_id):
                continue
        except Exception:  # noqa: BLE001
            pass
        out.append(bot_id)
    return out


# ---------------------------------------------------------------- run stats

def record_runs(desk, root: str, now=None) -> dict:
    """Count each newly finished check once. Returns the stats file contents."""
    now = _now(now)
    path = os.path.join(root, STATS_FILE)
    stats = _load(path)
    seen = stats.get("seen") if isinstance(stats.get("seen"), dict) else {}
    days = stats.get("days") if isinstance(stats.get("days"), dict) else {}
    runs = desk._load_runs(root) or {}
    for bot_id, row in sorted(runs.items()):
        if not isinstance(row, dict):
            continue
        at = str(row.get("at") or "")
        if not at or seen.get(bot_id) == at:
            continue
        seen[bot_id] = at
        when = _when(at)
        day = ct_day(when or now)
        tower = days.setdefault(day, {}).setdefault(bot_id, {})
        summary = str(row.get("summary") or "")
        tower["runs"] = int(tower.get("runs") or 0) + 1
        if row.get("ok"):
            tower["ok"] = int(tower.get("ok") or 0) + 1
        elif summary.startswith("Stopped after"):
            tower["timeouts"] = int(tower.get("timeouts") or 0) + 1
            tower["last_error"] = summary.splitlines()[0]
        else:
            tower["fails"] = int(tower.get("fails") or 0) + 1
            tower["last_error"] = _last_line(summary)
        secs = row.get("secs")
        if isinstance(secs, (int, float)) and not isinstance(secs, bool) and secs >= 0:
            tower["secs"] = round(float(tower.get("secs") or 0.0) + float(secs), 3)
            tower["timed"] = int(tower.get("timed") or 0) + 1
    keep = sorted(days)[-KEEP_DAYS:]
    stats = {"seen": seen, "days": {d: days[d] for d in keep}}
    _save(path, stats)
    return stats


def tower_day(stats: dict, bot_id: str, day: str) -> dict:
    """Plain numbers for one tower on one day: runs, clean rate, average seconds."""
    row = ((stats.get("days") or {}).get(day) or {}).get(bot_id) or {}
    runs = int(row.get("runs") or 0)
    ok = int(row.get("ok") or 0)
    timed = int(row.get("timed") or 0)
    return {
        "runs": runs,
        "ok": ok,
        "fails": int(row.get("fails") or 0),
        "timeouts": int(row.get("timeouts") or 0),
        "success_rate": round(ok / runs, 4) if runs else None,
        "avg_secs": round(float(row.get("secs") or 0) / timed, 2) if timed else None,
        "last_error": str(row.get("last_error") or ""),
    }


def _week_avg(stats: dict, bot_id: str, day: str):
    secs = 0.0
    timed = 0
    for other in sorted((stats.get("days") or {})):
        if other >= day:
            continue
        if (dt.date.fromisoformat(day) - dt.date.fromisoformat(other)).days > 7:
            continue
        row = stats["days"][other].get(bot_id) or {}
        secs += float(row.get("secs") or 0)
        timed += int(row.get("timed") or 0)
    return (secs / timed, timed) if timed else (None, 0)


def slow_notes(desk, stats: dict, state: dict, now=None) -> list:
    now = _now(now)
    day = ct_day(now)
    said = state.setdefault("slow_said", {})
    for old in [d for d in said if d != day]:
        said.pop(old, None)
    today_said = set(said.get(day) or [])
    names = _names(desk)
    notes = []
    for bot_id, row in sorted(((stats.get("days") or {}).get(day) or {}).items()):
        timed = int(row.get("timed") or 0)
        if bot_id in today_said or timed < SLOW_MIN_RUNS:
            continue
        avg_today = float(row.get("secs") or 0) / timed
        base, base_runs = _week_avg(stats, bot_id, day)
        if base is None or base_runs < SLOW_MIN_BASE_RUNS or avg_today < SLOW_MIN_SECS:
            continue
        if avg_today >= SLOW_MULT * base:
            notes.append(f"Ops: {names.get(bot_id, bot_id)} is slow today. Its checks average "
                         f"{avg_today:.0f}s, about {avg_today / base:.1f}x its 7-day average of {base:.0f}s.")
            today_said.add(bot_id)
    said[day] = sorted(today_said)
    return notes


def daily_summary(desk, root: str, stats: dict, day: str, now=None) -> str:
    """One plain line about a finished Central day. Every failure is counted."""
    now = _now(now)
    names = _names(desk)
    rows = (stats.get("days") or {}).get(day) or {}
    expected = _expected(desk, root, now)
    ran = [b for b in expected if int((rows.get(b) or {}).get("runs") or 0) > 0]
    missing = [b for b in expected if b not in ran]
    total = sum(int(r.get("runs") or 0) for r in rows.values())
    clean = sum(int(r.get("ok") or 0) for r in rows.values())
    rate = f"{100.0 * clean / total:.1f}% clean" if total else "no checks"
    head = (f"Ops daily for {day}: all {len(expected)} timed towers ran" if not missing
            else f"Ops daily for {day}: {len(ran)} of {len(expected)} timed towers ran")
    parts = [f"{head} ({total} checks, {rate})."]
    bad = sorted(((int(r.get("fails") or 0) + int(r.get("timeouts") or 0), b) for b, r in rows.items()),
                 key=lambda pair: (-pair[0], pair[1]))
    bad = [(n, b) for n, b in bad if n > 0]
    if bad:
        parts.append("Not clean: " + ", ".join(f"{names.get(b, b)} {n}" for n, b in bad[:8])
                     + (f" and {len(bad) - 8} more" if len(bad) > 8 else "") + ".")
    if missing:
        parts.append("No finished check: " + ", ".join(names.get(b, b) for b in missing[:8])
                     + (f" and {len(missing) - 8} more" if len(missing) > 8 else "") + ".")
    return _fit(" ".join(parts))


# ---------------------------------------------------------------- disk, memory, clock

def disk_notes(path: str, state: dict, usage=shutil.disk_usage) -> list:
    try:
        total, used, _free = usage(path)
    except OSError:
        return []
    if not total:
        return []
    frac = used / total
    state["disk"] = {"used_frac": round(frac, 4), "free_gb": round((total - used) / 1e9, 2)}
    if frac >= DISK_ALERT and not state.get("disk_said"):
        state["disk_said"] = True
        return [f"Ops: the data disk is {frac * 100:.0f}% full ({(total - used) / 1e9:.1f} GB free). "
                "Old snapshots or backups may need a cleanup."]
    if frac < DISK_CLEAR and state.get("disk_said"):
        state["disk_said"] = False
        return [f"Ops: the data disk is back to {frac * 100:.0f}% full."]
    return []


def _read_int(path: str):
    try:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read().strip()
    except OSError:
        return None
    return int(raw) if raw.isdigit() else None


def memory_use(base: str = "/sys/fs/cgroup") -> dict:
    """Container memory in use and its limit (cgroup v2, then v1). Empty when unknown."""
    used = _read_int(os.path.join(base, "memory.current"))
    limit = _read_int(os.path.join(base, "memory.max"))
    if used is None:
        used = _read_int(os.path.join(base, "memory", "memory.usage_in_bytes"))
        limit = _read_int(os.path.join(base, "memory", "memory.limit_in_bytes"))
    if not used or not limit or limit >= 1 << 60:
        return {}
    return {"used": used, "limit": limit, "frac": round(used / limit, 4)}


def memory_notes(state: dict, now=None, reader=memory_use) -> list:
    now = _now(now)
    mem = reader() or {}
    if not mem:
        return []
    frac = float(mem["frac"])
    samples = state.setdefault("mem_samples", [])
    last = _when(samples[-1]["at"]) if samples else None
    if last is None or (now - last).total_seconds() >= MEM_SAMPLE_EVERY_S:
        samples.append({"at": now.isoformat(timespec="seconds"), "frac": round(frac, 4),
                        "used_mb": round(mem["used"] / 1e6)})
        del samples[:-MEM_SAMPLES]
    state["mem"] = {"frac": round(frac, 4), "used_mb": round(mem["used"] / 1e6),
                    "limit_mb": round(mem["limit"] / 1e6)}
    state["mem_streak"] = int(state.get("mem_streak") or 0) + 1 if frac >= MEM_ALERT else 0
    if state["mem_streak"] >= MEM_STREAK and not state.get("mem_said"):
        state["mem_said"] = True
        return [f"Ops: the trading service has used {frac * 100:.0f}% of its memory for "
                f"{state['mem_streak']} passes in a row ({mem['used'] / 1e6:.0f} of {mem['limit'] / 1e6:.0f} MB)."]
    if frac < MEM_CLEAR and state.get("mem_said"):
        state["mem_said"] = False
        return [f"Ops: memory is back to {frac * 100:.0f}% of the limit."]
    return []


def public_time(url: str = CLOCK_URL, timeout: float = 5.0) -> tuple:
    """(server_ts, local_midpoint) from a public time source. Raises on failure."""
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "desk-ops-clock"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read(4096).decode("utf-8", "replace")
    t1 = time.time()
    match = re.search(r"^ts=([0-9.]+)$", body, re.M)
    if not match:
        raise ValueError("no ts in time source answer")
    return float(match.group(1)), (t0 + t1) / 2.0


def clock_notes(state: dict, now=None, fetch=public_time) -> list:
    now = _now(now)
    last = _when(state.get("clock_checked"))
    if last is not None and (now - last).total_seconds() < CLOCK_EVERY_S:
        return []
    state["clock_checked"] = now.isoformat(timespec="seconds")
    try:
        server, local = fetch()
    except Exception:  # noqa: BLE001 - the time source being down is not a desk problem
        log.info("Clock check skipped: the public time source did not answer")
        return []
    drift = local - server
    state["clock_drift_s"] = round(drift, 3)
    if abs(drift) > CLOCK_ALERT_S and not state.get("clock_said"):
        state["clock_said"] = True
        side = "ahead of" if drift > 0 else "behind"
        return [f"Ops: the server clock is {abs(drift):.1f}s {side} public time. "
                "15-minute windows and day boundaries may be off."]
    if abs(drift) <= CLOCK_CLEAR_S and state.get("clock_said"):
        state["clock_said"] = False
        return [f"Ops: the server clock is back within {abs(drift):.1f}s of public time."]
    return []


# ---------------------------------------------------------------- backups

_SKIP_SUFFIX = (".tmp", ".lock", ".keep", ".link", ".part")


def backup_dir() -> str:
    return str(os.environ.get("PAPER_BACKUP_DIR") or "/data/backups").strip()


def _tar_filter(info: tarfile.TarInfo):
    if info.issym() or info.islnk() or info.name.endswith(_SKIP_SUFFIX):
        return None
    return info


def verify_backup(path: str) -> dict:
    """Open a backup and read every JSON file in it. This is the restore test."""
    files = 0
    bad = []
    with tarfile.open(path, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            files += 1
            if member.name.endswith(".json"):
                handle = tar.extractfile(member)
                try:
                    json.loads(handle.read().decode("utf-8") or "null")
                except (ValueError, UnicodeDecodeError):
                    bad.append(member.name)
    return {"ok": not bad and files > 0, "files": files, "bad_json": bad}


def list_backups(dest: str | None = None) -> list:
    dest = dest or backup_dir()
    try:
        names = os.listdir(dest)
    except OSError:
        return []
    return sorted(f for f in names if f.startswith("paper-books-") and f.endswith(".tar.gz"))


def make_backup(src: str, dest: str, now=None, keep: int = BACKUP_KEEP) -> dict:
    """Pack ``src`` into ``dest/paper-books-<CT date>.tar.gz``, verify it, keep the newest ``keep``."""
    now = _now(now)
    src = os.path.realpath(src)
    dest = os.path.realpath(dest)
    if dest == src or dest.startswith(src + os.sep):
        return {"ok": False, "error": "The backup folder cannot sit inside the books it backs up."}
    os.makedirs(dest, exist_ok=True)
    final = os.path.join(dest, f"paper-books-{ct_day(now)}.tar.gz")
    tmp = final + ".part"
    with tarfile.open(tmp, "w:gz") as tar:
        tar.add(src, arcname="paper-bots", filter=_tar_filter)
    check = verify_backup(tmp)
    if not check["ok"]:
        os.remove(tmp)
        return {"ok": False, "error": "The new backup did not read back cleanly.", **check}
    os.replace(tmp, final)
    size = os.path.getsize(final)
    old = list_backups(dest)
    removed = []
    for extra in (old[:-keep] if keep > 0 else []):
        os.remove(os.path.join(dest, extra))
        removed.append(extra)
    return {"ok": True, "path": final, "bytes": size, "removed": removed, **check}


def restore_backup(path: str, target: str) -> dict:
    """Unpack a backup into an empty folder. Never writes over a live desk."""
    target = os.path.realpath(target)
    if os.path.isdir(target) and os.listdir(target):
        return {"ok": False, "error": "Restore into an empty folder, then swap it in by hand."}
    check = verify_backup(path)
    if not check["ok"]:
        return {"ok": False, "error": "That backup does not read back cleanly.", **check}
    os.makedirs(target, exist_ok=True)
    with tarfile.open(path, "r:gz") as tar:
        for member in tar.getmembers():
            if not (member.isfile() or member.isdir()):
                continue
            out = os.path.realpath(os.path.join(target, member.name))
            if out != target and not out.startswith(target + os.sep):
                continue
            tar.extract(member, target)
    return {"ok": True, "folder": os.path.join(target, "paper-bots"), **check}


_BACKUP_RUNNING = threading.Lock()


def backup_due(state: dict, now=None) -> bool:
    local = _now(now).astimezone(CT)
    return local.hour >= BACKUP_HOUR_CT and state.get("backup_day") != local.date().isoformat()


def _backup_job(src: str, path: str, now) -> None:
    if not _BACKUP_RUNNING.acquire(blocking=False):
        return
    try:
        try:
            result = make_backup(src, backup_dir(), now=now)
        except Exception as exc:  # noqa: BLE001
            log.exception("Nightly backup failed")
            result = {"ok": False, "error": f"{exc.__class__.__name__}."}
        log.info("Nightly backup: ok=%s files=%s bytes=%s", result.get("ok"), result.get("files"),
                 result.get("bytes"))
        latest = _load(path)
        latest["backup_last"] = {"at": _now().isoformat(timespec="seconds"),
                                 **{k: result.get(k) for k in ("ok", "files", "bytes", "error")}}
        latest["backup_result"] = {"ok": bool(result.get("ok")), "error": result.get("error") or ""}
        _save(path, latest)
    finally:
        _BACKUP_RUNNING.release()


def backup_notes(desk, root: str, state: dict, now=None, background: bool = True) -> list:
    """Start the nightly backup when due. A failed backup posts on the next pass."""
    now = _now(now)
    notes = []
    done = state.pop("backup_result", None)
    if isinstance(done, dict) and not done.get("ok"):
        notes.append(f"Ops: the nightly backup did not finish. {done.get('error') or 'Unknown error.'}")
    if not backup_due(state, now):
        return notes
    try:
        src = desk.settlement_dir()
    except Exception:  # noqa: BLE001
        src = None
    if not src or not os.path.isdir(src):
        return notes  # no volume (a laptop or a test): nothing to back up
    state["backup_day"] = now.astimezone(CT).date().isoformat()
    usage = (state.get("disk") or {}).get("used_frac")
    if isinstance(usage, (int, float)) and usage >= BACKUP_SKIP_DISK:
        notes.append(f"Ops: skipped the nightly backup because the disk is {usage * 100:.0f}% full.")
        return notes
    path = os.path.join(root, OPS_FILE)
    if background:
        threading.Thread(target=_backup_job, args=(src, path, now), name="desk-backup", daemon=True).start()
    else:
        _save(path, state)
        _backup_job(src, path, now)
        latest = _load(path)
        for key in ("backup_last", "backup_result"):
            if key in latest:
                state[key] = latest[key]
    return notes


# ---------------------------------------------------------------- grouping and the pass hook

def group_notes(notes: list, limit: int = NOTE_LIMIT) -> list:
    """One outage, one message: pack many short notes into as few audit messages as fit."""
    notes = [str(n) for n in notes if str(n or "").strip()]
    if len(notes) <= 2:
        return notes
    head = f"Desk health: {len(notes)} notes this pass."
    out = []
    cur = head
    for note in notes:
        line = "\n- " + _fit(note, limit - len(head) - 4)
        if len(cur) + len(line) > limit:
            out.append(cur)
            cur = "Desk health (more):"
        cur += line
    out.append(cur)
    return out


def check(desk, root: str, now=None, fetch=public_time, mem_reader=memory_use,
          usage=shutil.disk_usage, background: bool = True) -> list:
    """All desk-wide checks for one pass. Never raises."""
    now = _now(now)
    path = os.path.join(root, OPS_FILE)
    state = _load(path)
    notes = []
    stats = {}
    try:
        stats = record_runs(desk, root, now)
        notes.extend(slow_notes(desk, stats, state, now))
    except Exception:  # noqa: BLE001
        log.exception("Ops run stats failed")
    today = ct_day(now)
    last_day = state.get("summary_day")
    if last_day is None:
        state["summary_day"] = today  # first start: wait for a full day before summing one up
    elif last_day != today:
        try:
            notes.append(daily_summary(desk, root, stats, last_day, now))
        except Exception:  # noqa: BLE001
            log.exception("Ops daily summary failed")
        state["summary_day"] = today

    def disk():
        try:
            where = desk.settlement_dir() or root
        except Exception:  # noqa: BLE001
            where = root
        return disk_notes(where if os.path.isdir(where) else root, state, usage)

    for name, fn in (
        ("disk", disk),
        ("memory", lambda: memory_notes(state, now, mem_reader)),
        ("clock", lambda: clock_notes(state, now, fetch)),
        ("backup", lambda: backup_notes(desk, root, state, now, background)),
    ):
        try:
            notes.extend(fn())
        except Exception:  # noqa: BLE001
            log.exception("Ops %s check failed", name)
    state["last_check"] = now.isoformat(timespec="seconds")
    try:
        latest = _load(path)  # a background backup may have written its result meanwhile
        if (latest.get("backup_last") or {}).get("at") != (state.get("backup_last") or {}).get("at"):
            for key in ("backup_last", "backup_result"):
                if key in latest:
                    state[key] = latest[key]
        _save(path, state)
    except OSError:
        log.exception("Ops state save failed")
    return notes


# ---------------------------------------------------------------- build and health

def build_info(env=None) -> dict:
    """Which build is running. Reads only the commit id and title the host stamps on the deploy."""
    env = os.environ if env is None else env
    sha = str(env.get("RAILWAY_GIT_COMMIT_SHA") or env.get("GIT_COMMIT_SHA") or "").strip()[:12]
    title = str(env.get("RAILWAY_GIT_COMMIT_MESSAGE") or env.get("GIT_COMMIT_MESSAGE") or "").strip()
    title = title.splitlines()[0] if title else ""
    match = re.search(r"\(#(\d+)\)\s*$", title)
    return {"sha": sha, "pr": int(match.group(1)) if match else None, "title": title[:120]}


def build_line(env=None) -> str:
    info = build_info(env)
    pr = f"PR #{info['pr']}" if info["pr"] else "PR unknown"
    return f"build {info['sha'] or 'unknown'} ({pr}): {info['title'] or 'no title'}"


def health(desk, root: str | None = None, now=None) -> dict:
    """Extra fields for the trading service's /healthz. No secrets, no paths."""
    now = _now(now)
    out = {"build": build_info(), "uptime_s": int(time.time() - STARTED_AT)}
    try:
        beat = desk._read_json(desk.heartbeat_path(root)) or {}
        at = _when(beat.get("at"))
        out["last_pass_at"] = at.isoformat(timespec="seconds") if at else None
        out["last_pass_age_s"] = int((now - at).total_seconds()) if at else None
    except Exception:  # noqa: BLE001
        out["last_pass_at"] = None
        out["last_pass_age_s"] = None
    try:
        import kalshi_gateway
        gw = kalshi_gateway.status()
        out["kalshi_gateway"] = {k: gw.get(k) for k in ("sent", "count_429", "cooldown_left_s", "cache_hits")}
    except Exception:  # noqa: BLE001
        out["kalshi_gateway"] = {}
    try:
        state = _load(os.path.join(desk._root(root), OPS_FILE))
        out["ops"] = {k: state.get(k) for k in ("disk", "mem", "clock_drift_s", "backup_last", "last_check")}
    except Exception:  # noqa: BLE001
        out["ops"] = {}
    return out
