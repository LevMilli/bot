"""Keep each test's paper state to itself.

Many desk helpers default to this folder as the paper root, so a test that
does not pass a temp root writes runtime files (cool-offs, ledgers, journals)
next to the bots. Those files are git-ignored, so nobody sees them, and the
next test reads them back. That made results depend on test order and on
whatever an earlier run left behind.

Around every test this fixture records the untracked files under paper-bots/,
then deletes the ones the test created and restores the ones it changed.
Tracked files and your own local paper state from before the test are kept.
Paper only. Nothing here touches the /data volume.
"""
from __future__ import annotations

import os
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
_SKIP_DIRS = {"__pycache__", ".pytest_cache", "node_modules", ".git"}


def _tracked() -> set[str] | None:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z", "--", "."],
            cwd=HERE, capture_output=True, check=True, timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return {os.path.normpath(os.path.join(HERE, p.decode())) for p in out.split(b"\0") if p}


_TRACKED = _tracked()


def _untracked_files() -> list[str]:
    found = []
    for folder, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            path = os.path.normpath(os.path.join(folder, name))
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            if path in _TRACKED:
                continue
            found.append(path)
    return found


def _read(path: str) -> bytes | None:
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


@pytest.fixture(autouse=True)
def _no_live_requote(monkeypatch):
    """Paper buys re-read the live order book before filling (strict_fill).
    Tests stay offline; test_strict_fill.py turns it on with a fake book."""
    monkeypatch.setenv("PAPER_STRICT_FILL", "0")
    yield


@pytest.fixture(autouse=True)
def _isolate_paper_state():
    if _TRACKED is None:
        # Not a git checkout: cannot tell runtime files from source. Do nothing.
        yield
        return
    before = {path: _read(path) for path in _untracked_files()}
    try:
        yield
    finally:
        for path in _untracked_files():
            if path not in before:
                try:
                    os.remove(path)
                except OSError:
                    pass
        for path, body in before.items():
            if body is None:
                continue
            if _read(path) != body:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as handle:
                    handle.write(body)


_SESSION_BEFORE: set[str] = set()


def pytest_sessionstart(session):
    if _TRACKED is not None:
        _SESSION_BEFORE.update(_untracked_files())


def pytest_sessionfinish(session, exitstatus):
    """Drop runtime files written outside a test (imports, collection)."""
    if _TRACKED is None:
        return
    for path in _untracked_files():
        if path not in _SESSION_BEFORE:
            try:
                os.remove(path)
            except OSError:
                pass
