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
    for note in desk.drain_alerts() or []:
        if "outside a bot run" in str(note):
            out["audit"].append(str(note))
        else:
            out["recap"].append(str(note))
    recap = desk.take_recap()
    if recap:
        out["recap"].append(str(recap))
    return out


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
    threading.Thread(target=run_forever, args=(pimp_desk,), name="desk-timer", daemon=True).start()
    if len(desk_web.service_key()) < desk_web.MIN_KEY_LEN:
        log.warning("DESK_SERVICE_KEY is missing or short. The desk API refuses every call until it is set.")
    port = int(os.environ.get("PORT") or 8080)
    host = os.environ.get("DESK_SERVICE_HOST") or "::"
    log.info("Desk service API on %s:%s. Paper only.", host, port)
    web.run_app(desk_web.make_app(pimp_desk), host=host, port=port, print=None)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if "--timer-only" in sys.argv:
        run_forever()
    else:
        serve()
