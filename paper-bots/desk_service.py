"""Trading desk timer that runs without the Discord bot. Paper only.

Step 1 of splitting the trading desk from the Discord bot. The loop below is the
same pass the Discord bot's ``paper_timer`` runs every 60 seconds:

    health check -> run_scheduled -> drain alerts -> daily recap

Two ways to run it:

- Inside the Discord bot (default, nothing changes). ``bot.py`` calls
  ``one_pass`` and posts the notes to the recap and audit channels.
- On its own: ``python paper-bots/desk_service.py``. Notes go to Discord
  webhooks (``PAPER_RECAP_WEBHOOK`` and ``PAPER_AUDIT_WEBHOOK``) or to the log
  when no webhook is set. Set ``PAPER_TIMER=external`` on the Discord bot so
  the two never run the same checks at the same time.

No exchange keys, no wallets, no live orders.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

log = logging.getLogger("desk_service")

INTERVAL_S = 60
WARMUP_S = 20
OPEN_LOG_EVERY_S = 300   # "desk open" line for the evening report's daily high
_last_open_log = [0.0]
REPORT_LOG_EVERY_S = 1800  # "desk report" card for the evening report (plan steps 886-925)
_last_report_log = [0.0]


def timer_mode() -> str:
    """``internal`` (Discord bot runs the timer) or ``external`` (this service does).

    A bot pointed at a trading service (``DESK_SERVICE_URL``) never runs the timer.
    """
    if str(os.environ.get("DESK_SERVICE_URL") or "").strip():
        return "external"
    raw = str(os.environ.get("PAPER_TIMER") or "").strip().lower()
    return "external" if raw in ("external", "off", "service") else "internal"


def one_pass(desk) -> dict:
    """One timer pass. Returns the notes to send. Raises on failure like the old loop."""
    out = {"audit": [], "recap": []}
    health = desk.timer_health()
    if health.get("alert"):
        out["audit"].append(str(health["alert"]))
    desk.run_scheduled()
    log_desk_open(desk)
    log_desk_report(desk)
    health_notes = []
    watchdog = getattr(desk, "tower_watchdog", None)
    if callable(watchdog):
        try:
            health_notes.extend(str(note) for note in (watchdog() or []))
        except Exception:  # noqa: BLE001 - the watchdog never stops a pass
            log.exception("Tower watchdog failed")
    ops = getattr(desk, "ops_check", None)
    if callable(ops):
        try:
            health_notes.extend(str(note) for note in (ops() or []))
        except Exception:  # noqa: BLE001 - desk-wide checks never stop a pass
            log.exception("Desk ops check failed")
    if health_notes:
        import desk_ops
        out["audit"].extend(desk_ops.group_notes(health_notes))
    for note in desk.drain_alerts() or []:
        if "outside a bot run" in str(note):
            out["audit"].append(str(note))
        else:
            out["recap"].append(str(note))
    recap = desk.take_recap()
    if recap:
        out["recap"].append(str(recap))
    return out


def log_desk_open(desk, now: float | None = None) -> str:
    """Every 5 minutes, log how many vault bets are open (out of the max-open limit).

    The evening report reads these lines to show the day's highest open count.
    Never stops a pass.
    """
    fn = getattr(desk, "desk_open_summary", None)
    now = time.time() if now is None else now
    if not callable(fn) or now - _last_open_log[0] < OPEN_LOG_EVERY_S:
        return ""
    _last_open_log[0] = now
    try:
        s = fn()
        line = "desk open " + json.dumps(s, sort_keys=True)
    except Exception:  # noqa: BLE001
        log.exception("Desk open count failed")
        return ""
    log.info(line)
    return line


def log_desk_report(desk, now: float | None = None) -> str:
    """Every 30 minutes, log the read-only desk report card as one ``desk report {json}`` line.

    The evening report can read the day's last card: tower W-L, fees, profit, health,
    50-results progress and the number check. Never stops a pass.
    """
    fn = getattr(desk, "desk_report_card", None)
    now = time.time() if now is None else now
    if not callable(fn) or now - _last_report_log[0] < REPORT_LOG_EVERY_S:
        return ""
    _last_report_log[0] = now
    try:
        import desk_report
        line = desk_report.log_line(fn())
    except Exception:  # noqa: BLE001
        log.exception("Desk report card failed")
        return ""
    log.info(line)
    return line


def _webhook(url: str, text: str, limit: int) -> bool:
    body = str(text or "")[:limit]
    if not url or not body:
        return False
    data = json.dumps({"content": body, "allowed_mentions": {"parse": []}}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": "desk-service"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception:  # noqa: BLE001 - a failed post never stops the desk
        log.warning("Webhook post failed")
        return False


def send_notes(notes: dict) -> None:
    recap_url = os.environ.get("PAPER_RECAP_WEBHOOK") or ""
    audit_url = os.environ.get("PAPER_AUDIT_WEBHOOK") or recap_url
    for text in notes.get("audit") or []:
        if not _webhook(audit_url, text, 500):
            log.info("Audit: %s", text[:500])
    for text in notes.get("recap") or []:
        if not _webhook(recap_url, text, 1900):
            log.info("Recap: %s", text[:1900])


def run_forever(desk=None, sleep=time.sleep, passes: int | None = None) -> None:
    if desk is None:
        import pimp_desk as desk
    log.info("Desk service timer on. Paper only.")
    try:
        import desk_ops
        log.info("Deploy: %s", desk_ops.build_line())
    except Exception:  # noqa: BLE001
        pass
    try:
        desk.touch_heartbeat()
    except Exception:  # noqa: BLE001
        log.exception("First heartbeat failed")
    sleep(WARMUP_S)
    done = 0
    while passes is None or done < passes:
        try:
            send_notes(one_pass(desk))
        except Exception:  # noqa: BLE001
            log.exception("Desk service pass failed")
            send_notes({"audit": ["Paper timer failed. The last loop did not finish."]})
        done += 1
        sleep(INTERVAL_S)


def serve() -> None:
    """Timer in a background thread, private desk API on PORT (default 8080)."""
    import threading

    from aiohttp import web

    import desk_web
    import pimp_desk

    pimp_desk.keep_closed_settlements()
    try:
        import kalshi_gateway
        gone = kalshi_gateway.cleanup_stale() + kalshi_gateway.prune_cache()
        if gone:
            log.info("Kalshi gateway: removed %d stale file(s) at startup.", gone)
    except Exception:  # noqa: BLE001 - cleanup never blocks startup
        log.exception("Kalshi gateway cleanup failed")
    threading.Thread(target=run_forever, args=(pimp_desk,), name="desk-timer", daemon=True).start()
    if len(desk_web.service_key()) < desk_web.MIN_KEY_LEN:
        log.warning("DESK_SERVICE_KEY is missing or short. The desk API refuses every call until it is set.")
    port = int(os.environ.get("PORT") or 8080)
    host = os.environ.get("DESK_SERVICE_HOST") or "::"
    log.info("Desk service API on %s:%s. Paper only.", host, port)
    web.run_app(desk_web.make_app(pimp_desk), host=host, port=port, print=None)


if __name__ == "__main__":
    # stdout: hosts like Railway paint every stderr line red, even INFO.
    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Locked floors: log them once and refuse to start if one is missing or lowered.
    import desk_safety
    desk_safety.startup_check(log)
    if "--timer-only" in sys.argv:
        run_forever()
    else:
        serve()
