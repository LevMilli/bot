#!/usr/bin/env python3
"""Deploy checklist and smoke test. Paper only, read-only.

Before a merge (on a laptop or in CI):

    python3 paper-bots/tools/deploy_check.py local            # quick checks
    python3 paper-bots/tools/deploy_check.py local --tests    # plus the full test suite

Right after a deploy (no key needed, reads public health pages only):

    python3 paper-bots/tools/deploy_check.py smoke --desk-url https://<trading service> \
        --city-url https://<discord bot>/health

``local`` checks:
  * the desk loads and every tower in BOTS has its folder and script,
  * a snapshot built from a scratch copy lists every tower (the smoke test),
  * the locked edge floors are not lower than the locked values,
  * real money is off in the defaults,
  * the city build (trading-city/dist/index.html) is there and has the offline fixture.

``smoke`` checks:
  * the trading service's /healthz answers ok, paper only, timer alive,
  * the last timer pass is under 5 minutes old,
  * the city page answers 200,
  * optional --sha: both services report the same build.

Exit code 0 means every check passed. Each line says PASS or FAIL in plain words.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
REPO = os.path.dirname(DESK)

LOCKED_FLOORS = {
    "kalshi_sports": 0.06, "kalshi_btc15m": 0.05, "kalshi_commodity15m": 0.05, "kalshi_inx": 0.02,
    "solana_dex": 0.02, "coinbase_spot": 0.05, "binance_btc_carry": 0.02, "kalshi_econ": 0.05,
    "equity_qqq": 0.02, "coinbase_btc_carry": 0.02,
}
MAX_PASS_AGE_S = 300


class Report:
    def __init__(self):
        self.failed = 0

    def check(self, ok: bool, what: str, detail: str = "") -> bool:
        print(f"{'PASS' if ok else 'FAIL'}  {what}" + (f" ({detail})" if detail else ""))
        if not ok:
            self.failed += 1
        return ok


def _import_desk():
    if DESK not in sys.path:
        sys.path.insert(0, DESK)
    import pimp_desk
    return pimp_desk


def check_towers(rep: Report, desk) -> None:
    missing = []
    for bot in desk.BOTS:
        folder = os.path.join(DESK, bot["folder"])
        script = (bot.get("run") or {}).get("argv", ("bot.py",))[0] if isinstance(bot.get("run"), dict) else None
        if not os.path.isdir(folder):
            missing.append(f"{bot['id']} folder")
        elif script and not os.path.isfile(os.path.join(folder, script)):
            missing.append(f"{bot['id']} script")
    rep.check(not missing, f"every tower has its folder and script ({len(desk.BOTS)} towers)", ", ".join(missing[:5]))


def check_snapshot(rep: Report, desk_ids: list) -> None:
    """Build a snapshot from a scratch copy so the live books are never touched."""
    scratch = tempfile.mkdtemp(prefix="deploy-check-")
    try:
        copy = os.path.join(scratch, "paper-bots")
        shutil.copytree(DESK, copy, symlinks=False, ignore=shutil.ignore_patterns(
            "__pycache__", ".kalshi_gateway", "*.tmp", "market-snapshots-paper"), ignore_dangling_symlinks=True)
        code = (
            "import json, sys; sys.path.insert(0, sys.argv[1]); import pimp_desk; "
            "s = pimp_desk.snapshot(sys.argv[1]); "
            "print(json.dumps({'ids': [b.get('id') for b in s.get('bots') or []], 'paper_only': s.get('paper_only')}))"
        )
        env = {**os.environ, "PAPER_KEEP_SETTLEMENTS": "0", "PAPER_DATA_DIR": os.path.join(scratch, "volume"),
               "KALSHI_GATEWAY_DIR": os.path.join(scratch, "gw")}
        proc = subprocess.run([sys.executable, "-c", code, copy], capture_output=True, text=True, timeout=180,
                              env=env, cwd=copy)
        if not rep.check(proc.returncode == 0, "snapshot builds", (proc.stderr or "").strip().splitlines()[-1:]
                         and (proc.stderr or "").strip().splitlines()[-1][:120] or ""):
            return
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        absent = [i for i in desk_ids if i not in set(out["ids"])]
        rep.check(not absent, f"snapshot lists every tower ({len(out['ids'])})", ", ".join(absent[:5]))
        rep.check(out.get("paper_only") is True, "snapshot says paper only")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def check_floors(rep: Report, desk) -> None:
    floors = (desk.DEFAULTS.get("venue_min_edge") or {})
    low = [f"{k} {floors.get(k)} < {v}" for k, v in LOCKED_FLOORS.items()
           if not isinstance(floors.get(k), (int, float)) or floors[k] < v]
    rep.check(not low, "locked edge floors are not lower", "; ".join(low))


def check_money_off(rep: Report, desk) -> None:
    rep.check(desk.DEFAULTS.get("paper_only") is True, "real money is off (paper_only)")


def check_city(rep: Report) -> None:
    dist = os.path.join(REPO, "trading-city", "dist")
    rep.check(os.path.isfile(os.path.join(dist, "index.html")), "city build is present (trading-city/dist)")
    rep.check(os.path.isfile(os.path.join(dist, "fixture-snapshot.json")), "city offline fixture is present")


def run_local(args) -> int:
    rep = Report()
    try:
        desk = _import_desk()
    except Exception as exc:  # noqa: BLE001
        rep.check(False, "desk loads", f"{exc.__class__.__name__}: {exc}"[:160])
        return 1
    rep.check(True, "desk loads")
    check_towers(rep, desk)
    check_floors(rep, desk)
    check_money_off(rep, desk)
    check_snapshot(rep, [b["id"] for b in desk.BOTS])
    check_city(rep)
    if args.tests:
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"],
                              cwd=DESK, timeout=1500)
        rep.check(proc.returncode == 0, "full test suite passes")
    print("All checks passed." if not rep.failed else f"{rep.failed} check(s) failed.")
    return 0 if not rep.failed else 1


def _get_json(url: str, timeout: float = 15.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "deploy-check"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def smoke(desk_url: str, city_url: str = "", sha: str = "", get_json=_get_json, get_status=None) -> int:
    rep = Report()
    try:
        body = get_json(desk_url.rstrip("/") + "/healthz")
    except Exception as exc:  # noqa: BLE001
        rep.check(False, "trading service answers /healthz", exc.__class__.__name__)
        return 1
    rep.check(body.get("ok") is True, "trading service says ok")
    rep.check(body.get("paper_only") is True, "trading service says paper only")
    rep.check(body.get("timer_alive") is True, "desk timer is alive")
    age = body.get("last_pass_age_s")
    rep.check(isinstance(age, (int, float)) and age < MAX_PASS_AGE_S, "last timer pass is recent",
              f"{age}s" if age is not None else "no pass yet")
    build = (body.get("build") or {})
    if sha:
        rep.check(str(build.get("sha") or "").startswith(sha[:7]), "trading service runs the expected build",
                  str(build.get("sha") or "unknown"))
    if city_url:
        def status(url):
            req = urllib.request.Request(url, headers={"User-Agent": "deploy-check"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status
        try:
            code = (get_status or status)(city_url)
        except Exception as exc:  # noqa: BLE001
            code = exc.__class__.__name__
        rep.check(code == 200, "city page answers", str(code))
    print("Smoke test passed." if not rep.failed else f"{rep.failed} smoke check(s) failed.")
    return 0 if not rep.failed else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    local = sub.add_parser("local", help="checks before a merge")
    local.add_argument("--tests", action="store_true", help="also run the full test suite")
    sm = sub.add_parser("smoke", help="checks right after a deploy")
    sm.add_argument("--desk-url", required=True)
    sm.add_argument("--city-url", default="")
    sm.add_argument("--sha", default="")
    args = parser.parse_args(argv)
    if args.cmd == "local":
        return run_local(args)
    return smoke(args.desk_url, args.city_url, args.sha)


if __name__ == "__main__":
    sys.exit(main())
