"""Polite public GETs. Paper only, read-only.

Kalshi's public API answers "429 Too Many Requests" when one process asks for
many series back to back. The research towers used to treat that as "the
public book could not be read" and skip the whole check.

``read(url)`` keeps a small gap between requests in this process and, on 429
or a server hiccup (5xx, timeout), waits and tries again: the server's
Retry-After if it sends one, otherwise 1s, 2s, 4s. A 404 or other client
error is raised right away (a missing series is not retried).
"""
from __future__ import annotations

import os
import threading
import time
import urllib.error
import urllib.request

UA = {"User-Agent": "paper-bots/1.0 (paper-only read)"}
_LOCK = threading.Lock()
_LAST = [0.0]


def _gap():
    try:
        return max(0.0, float(os.environ.get("PUBLIC_HTTP_GAP_SECONDS", 0.15)))
    except ValueError:
        return 0.15


def _space():
    gap = _gap()
    if gap <= 0:
        return
    with _LOCK:
        wait = _LAST[0] + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _LAST[0] = time.monotonic()


def _retry_after(exc):
    try:
        value = float((exc.headers or {}).get("Retry-After"))
    except (TypeError, ValueError, AttributeError):
        return None
    return min(max(value, 0.0), 30.0)


def read(url, headers=None, timeout=10, tries=4, sleep=time.sleep):
    """GET ``url`` and return the raw body bytes."""
    last = None
    for attempt in range(max(1, int(tries))):
        _space()
        try:
            req = urllib.request.Request(url, headers=headers or UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code != 429 and exc.code < 500:
                raise
            last = exc
            wait = _retry_after(exc) if exc.code == 429 else None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
            wait = None
        if attempt == tries - 1:
            break
        sleep(wait if wait is not None else 2 ** attempt)
    raise last
