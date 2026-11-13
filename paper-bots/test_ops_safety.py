"""Crash safety: state files never half-written, the gateway lock never sticks after a crash."""
import json
import os
import subprocess
import sys
import time

import pytest

import kalshi_gateway as gw
import pimp_desk


def test_crash_mid_write_keeps_the_old_state(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    pimp_desk._write_json(str(path), {"bank": 100})

    real_open = open

    class Boom:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.handle.close()
            return False

        def write(self, text):
            self.handle.write(text[: len(text) // 2])
            raise OSError("power cut")

        def flush(self):
            pass

    def fake_open(file, mode="r", *a, **k):
        handle = real_open(file, mode, *a, **k)
        return Boom(handle) if "w" in mode and str(file).endswith(".tmp") else handle

    monkeypatch.setattr("builtins.open", fake_open)
    with pytest.raises(OSError):
        pimp_desk._write_json(str(path), {"bank": 999, "lots": list(range(1000))})
    monkeypatch.undo()
    assert json.loads(path.read_text()) == {"bank": 100}


def test_failed_rename_keeps_the_old_state(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    pimp_desk._write_json(str(path), {"bank": 100})

    def no_replace(a, b):
        raise OSError("disk full")
    monkeypatch.setattr(pimp_desk.os, "replace", no_replace)
    with pytest.raises(OSError):
        pimp_desk._write_json(str(path), {"bank": 5})
    monkeypatch.undo()
    assert json.loads(path.read_text()) == {"bank": 100}


HOLDER = """
import os, sys, time
sys.path.insert(0, sys.argv[1])
import kalshi_gateway as gw
with gw._Locked():
    open(os.path.join(os.environ["KALSHI_GATEWAY_DIR"], "held"), "w").close()
    time.sleep(60)
"""


@pytest.mark.skipif(gw.fcntl is None, reason="POSIX file lock only")
def test_gateway_lock_frees_when_holder_crashes(tmp_path, monkeypatch):
    folder = str(tmp_path)
    monkeypatch.setenv("KALSHI_GATEWAY_DIR", folder)
    here = os.path.dirname(os.path.abspath(gw.__file__))
    proc = subprocess.Popen([sys.executable, "-c", HOLDER, here], env={**os.environ, "KALSHI_GATEWAY_DIR": folder})
    try:
        for _ in range(200):
            if os.path.exists(os.path.join(folder, "held")):
                break
            time.sleep(0.05)
        assert os.path.exists(os.path.join(folder, "held"))
        proc.kill()  # a crash: no clean unlock
        proc.wait(5)
        start = time.monotonic()
        with gw._Locked():
            pass
        assert time.monotonic() - start < 2.0
    finally:
        if proc.poll() is None:
            proc.kill()


def test_startup_cleanup_drops_only_old_tmp_files(tmp_path, monkeypatch):
    monkeypatch.setenv("KALSHI_GATEWAY_DIR", str(tmp_path))
    old = tmp_path / "pace.json.123.tmp"
    new = tmp_path / "pace.json.456.tmp"
    keep = tmp_path / "pace.json"
    for f in (old, new, keep):
        f.write_text("{}")
    os.utime(old, (time.time() - 3600, time.time() - 3600))
    assert gw.cleanup_stale() == 1
    assert not old.exists() and new.exists() and keep.exists()
