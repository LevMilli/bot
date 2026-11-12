"""One shared door to Kalshi's public API for every tower. Paper only, read-only.

Each tower runs as its own process and used to ask Kalshi on its own. Together
they tripped Kalshi's "429 Too Many Requests" and then each one kept retrying,
which made it worse. This module is the shared door:

* **Shared pace.** Every Kalshi GET, from any tower process, takes a turn on one
  schedule (``KALSHI_READS_PER_SEC``, default 8). A turn is reserved under a
  file lock, so two towers never send in the same slot.
* **Shared back-off.** When Kalshi answers 429, the door closes for every tower
  for the server's ``Retry-After`` (or 2s, 4s, 8s ... up to 30s). A tower that
  would have to wait longer than ``KALSHI_GATEWAY_MAX_WAIT`` (default 12s) gets
  the 429 straight back, so its own check can skip and finish on time.
* **Shared cache.** The same URL asked within ``KALSHI_CACHE_SECONDS`` (default
  10s) is answered from disk, so two towers reading one book cost one request.

State lives in ``KALSHI_GATEWAY_DIR`` (default ``<desk>/.kalshi_gateway``).
Only GETs to Kalshi's public host pass through here; any other URL goes straight
to ``urllib``. No key, no order, no account call.
"""
from __future__ import annotations

import email.message
import hashlib
import io
import json
import os
import threading
import time
import urllib.error
import urllib.request

try:  # POSIX file lock; Windows dev boxes fall back to the thread lock only.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

HERE = os.path.dirname(os.path.abspath(__file__))
KALSHI_HOSTS = ("api.elections.kalshi.com", "trading-api.kalshi.com")
_THREAD_LOCK = threading.Lock()


def _env_float(name: str, default: float, low: float = 0.0) -> float:
    try:
        return max(low, float(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default


def reads_per_sec() -> float:
    """0 turns the shared pace off (tests)."""
    return _env_float("KALSHI_READS_PER_SEC", 8.0)


def cache_seconds() -> float:
    return _env_float("KALSHI_CACHE_SECONDS", 10.0)


def max_wait() -> float:
    return _env_float("KALSHI_GATEWAY_MAX_WAIT", 12.0)


def state_dir() -> str:
    return os.environ.get("KALSHI_GATEWAY_DIR") or os.path.join(HERE, ".kalshi_gateway")


def is_kalshi(url: str) -> bool:
    text = str(url or "")
    return any(f"//{host}/" in text for host in KALSHI_HOSTS)


class GatewayBusy(urllib.error.HTTPError):
    """The shared door is closed longer than this caller may wait. Acts like a 429."""

    def __init__(self, url: str, wait: float):
        headers = email.message.Message()
        headers["Retry-After"] = str(int(max(1, round(wait))))
        super().__init__(url, 429, f"Kalshi gateway busy ({wait:.0f}s back-off)", headers, None)
        self.wait = wait


# ------------------------------------------------------------------ shared state
def _state_path() -> str:
    return os.path.join(state_dir(), "pace.json")


class _Locked:
    """Cross-process lock around pace.json."""

    def __enter__(self):
        os.makedirs(state_dir(), exist_ok=True)
        _THREAD_LOCK.acquire()
        self._fh = open(os.path.join(state_dir(), "pace.lock"), "a+")
        if fcntl is not None:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        try:
            if fcntl is not None:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            self._fh.close()
        finally:
            _THREAD_LOCK.release()
        return False


def _load() -> dict:
    try:
        with open(_state_path(), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data: dict) -> None:
    tmp = _state_path() + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    os.replace(tmp, _state_path())


def reserve(url: str = "", clock=time.time) -> float:
    """Reserve the next shared turn. Returns seconds to wait (0 = go now).

    Raises GatewayBusy (a 429) when the wait would exceed ``max_wait()``.
    """
    rate = reads_per_sec()
    with _Locked():
        data = _load()
        now = clock()
        start = max(now, float(data.get("next_free") or 0), float(data.get("cooldown_until") or 0))
        wait = start - now
        if wait > max_wait():
            raise GatewayBusy(url, wait)
        if rate > 0:
            data["next_free"] = start + 1.0 / rate
        data["sent"] = int(data.get("sent") or 0) + 1
        _save(data)
    return max(0.0, wait)


def note_429(retry_after: float | None = None, clock=time.time) -> float:
    """Close the door for every tower. Returns the back-off in seconds."""
    with _Locked():
        data = _load()
        now = clock()
        strikes = int(data.get("strikes") or 0) + 1
        if float(data.get("last_429") or 0) < now - 120:
            strikes = 1  # a quiet two minutes resets the ladder
        back = retry_after if retry_after is not None else min(30.0, 2.0 ** strikes)
        back = min(max(float(back), 1.0), 30.0)
        data.update({
            "strikes": strikes,
            "last_429": now,
            "cooldown_until": max(float(data.get("cooldown_until") or 0), now + back),
            "count_429": int(data.get("count_429") or 0) + 1,
        })
        _save(data)
    return back


def note_ok() -> None:
    """A clean answer. Strikes decay so the next 429 starts the ladder low again."""
    with _Locked():
        data = _load()
        if data.get("strikes"):
            data["strikes"] = max(0, int(data["strikes"]) - 1)
            _save(data)


def status() -> dict:
    """For the desk card: how often Kalshi said no, and whether the door is shut now."""
    data = _load()
    now = time.time()
    shut = max(0.0, float(data.get("cooldown_until") or 0) - now)
    return {
        "paper_only": True,
        "reads_per_sec": reads_per_sec(),
        "sent": int(data.get("sent") or 0),
        "count_429": int(data.get("count_429") or 0),
        "cooldown_left_s": round(shut, 1),
        "cache_hits": int(data.get("cache_hits") or 0),
    }


# ------------------------------------------------------------------ cache
def _cache_file(url: str) -> str:
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return os.path.join(state_dir(), "cache", key[:2], key + ".bin")


def _cache_get(url: str, ttl: float) -> bytes | None:
    if ttl <= 0:
        return None
    path = _cache_file(url)
    try:
        if time.time() - os.path.getmtime(path) > ttl:
            return None
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def _cache_put(url: str, body: bytes, ttl: float) -> None:
    if ttl <= 0:
        return
    path = _cache_file(url)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + f".{os.getpid()}.tmp"
        with open(tmp, "wb") as handle:
            handle.write(body)
        os.replace(tmp, path)
    except OSError:
        pass


def prune_cache(max_age: float = 600.0) -> int:
    """Drop cache files older than ``max_age``. Called now and then by ``read``."""
    root = os.path.join(state_dir(), "cache")
    gone = 0
    cutoff = time.time() - max_age
    for folder, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(folder, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    gone += 1
            except OSError:
                pass
    return gone


def _bump_hits() -> None:
    try:
        with _Locked():
            data = _load()
            data["cache_hits"] = int(data.get("cache_hits") or 0) + 1
            if data["cache_hits"] % 500 == 0:
                data["pruned"] = prune_cache()
            _save(data)
    except OSError:
        pass


# ------------------------------------------------------------------ the door
def _retry_after(exc) -> float | None:
    try:
        return float((exc.headers or {}).get("Retry-After"))
    except (TypeError, ValueError, AttributeError):
        return None


def read(url: str, headers: dict | None = None, timeout: float = 15, ttl: float | None = None,
         sleep=time.sleep) -> bytes:
    """One GET. Kalshi URLs share the pace, back-off and cache; others go straight out.

    Raises urllib's HTTPError like ``urlopen`` would (a 429 included), so each
    tower keeps its own skip rules.
    """
    req_headers = headers or {"User-Agent": "paper-bots/1.0 (paper-only read)"}
    if not is_kalshi(url):
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    ttl = cache_seconds() if ttl is None else float(ttl)
    hit = _cache_get(url, ttl)
    if hit is not None:
        _bump_hits()
        return hit
    wait = reserve(url)
    if wait > 0:
        sleep(wait)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            note_429(_retry_after(exc))
        raise
    note_ok()
    _cache_put(url, body, ttl)
    return body


class _Response(io.BytesIO):
    status = 200

    def getcode(self):
        return self.status


def urlopen(req, timeout: float = 15):
    """Drop-in for ``urllib.request.urlopen`` on GETs: ``with urlopen(req) as r: json.load(r)``."""
    if isinstance(req, str):
        url, headers = req, None
    else:
        if req.data is not None or req.get_method() != "GET":
            return urllib.request.urlopen(req, timeout=timeout)
        url, headers = req.full_url, dict(req.header_items()) or None
    if not is_kalshi(url):
        return urllib.request.urlopen(req, timeout=timeout)
    return _Response(read(url, headers=headers, timeout=timeout))
