"""Tower saves land on the Railway volume through the desk's symlinks.

Regression: the shared shadow engine, Coinbase spot and BTC carry replaced the
symlink with a plain file. The desk's next re-link (every snapshot/run) put the
old volume copy back, so cash and positions reset and the same contract was
bought twice.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import kalshi_shadow_tower as engine  # noqa: E402
import pimp_desk  # noqa: E402


def _load(folder):
    spec = importlib.util.spec_from_file_location(f"_vl_{folder.replace('-', '_')}", os.path.join(HERE, folder, "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _linked(tmp_path, name="paper_account.json", body=None):
    vol = tmp_path / "vol"
    vol.mkdir()
    remote = vol / name
    remote.write_text(json.dumps(body or {"paper_only": True}))
    app = tmp_path / "app"
    app.mkdir()
    local = app / name
    os.symlink(remote, local)
    return local, remote


def test_engine_write_follows_link(tmp_path):
    local, remote = _linked(tmp_path)
    engine.write_json(str(local), {"cash": 475.0})
    assert os.path.islink(local)
    assert json.loads(remote.read_text())["cash"] == 475.0


def test_coinbase_and_carry_writes_follow_link(tmp_path):
    for i, folder in enumerate(("coinbase-spot-paper", "btc-carry-paper")):
        sub = tmp_path / str(i)
        sub.mkdir()
        local, remote = _linked(sub)
        _load(folder)._write_json(str(local), {"cash": 499.25})
        assert os.path.islink(local), folder
        assert json.loads(remote.read_text())["cash"] == 499.25, folder


def test_shadow_tower_buy_survives_the_desk_relink(tmp_path):
    """A buy, then the desk re-links (as every snapshot does): cash and the position stay."""
    volume = tmp_path / "volume"
    root = tmp_path / "app" / "paper-bots"
    tower = root / "nasdaq-paper"
    tower.mkdir(parents=True)
    (tower / "config.json").write_text(json.dumps({"paper_only": True}))
    (tower / "paper_account.json").write_text(json.dumps({"paper_only": True}))
    old = pimp_desk.SETTLEMENT_FILES
    pimp_desk.SETTLEMENT_FILES = ("nasdaq-paper/paper_account.json",)
    try:
        pimp_desk.keep_closed_settlements(str(root), durable=str(volume))
        spec = {"id": "nasdaq", "name": "Nasdaq", "floor": 0.02, "max_open": 2, "max_edge": 0.15}
        quote = {"ticker": "KXNASDAQ100U-X", "event": "KXNASDAQ100U-E", "side": "yes",
                 "ask": 0.40, "bid": 0.38, "fair": 0.50, "label": "NDX test"}
        now = dt.datetime(2026, 11, 12, 15, tzinfo=dt.timezone.utc)
        engine.run_tower(spec, str(tower), lambda c, n: ([quote], ""), now=now, fetch=lambda t: {})
        pimp_desk.keep_closed_settlements(str(root), durable=str(volume))
        state = json.loads((tower / "paper_account.json").read_text())
        assert len(state["open"]) == 1 and state["cash"] < 500
        # A second check must not buy the same market again.
        engine.run_tower(spec, str(tower), lambda c, n: ([quote], ""), now=now, fetch=lambda t: {})
        pimp_desk.keep_closed_settlements(str(root), durable=str(volume))
        state = json.loads((tower / "paper_account.json").read_text())
        assert len(state["open"]) == 1
    finally:
        pimp_desk.SETTLEMENT_FILES = old


def test_desk_atomic_write_uses_unique_tmp(tmp_path, monkeypatch):
    seen = []
    real = os.replace

    def spy(src, dst):
        seen.append(src)
        return real(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    pimp_desk._atomic_write(str(tmp_path / "pimp-good.json"), "{}\n")
    assert seen and seen[0] != str(tmp_path / "pimp-good.json") + ".tmp"
    assert str(os.getpid()) in seen[0]
