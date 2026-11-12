"""The Discord bot's handle on the trading service. Paper only.

``RemoteDesk`` looks like the ``pimp_desk`` module to ``bot.py``. Calls that
read or change the paper books go to the trading service. Pure helpers such as
``role_can``, ``auth_error``, ``public_error``, and ``confirm_reset`` run
locally from the same code, so the staff rules stay identical.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import desk_web

TIMEOUT_S = 150  # a manual sports-gap run can take 120s


def service_url() -> str:
    return str(os.environ.get("DESK_SERVICE_URL") or "").strip().rstrip("/")


class RemoteDeskError(RuntimeError):
    pass


def _request(url: str, data: bytes, key: str, content_type: str, timeout: float) -> dict:
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": content_type,
        "User-Agent": "pimp-bot",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8") or "{}")
        except Exception:  # noqa: BLE001
            body = {}
        raise RemoteDeskError(str(body.get("error") or f"Trading service answered {exc.code}.")) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RemoteDeskError("The trading service did not answer.") from None


class RemoteDesk:
    REMOTE = tuple(desk_web.CALLS)

    def __init__(self, local, url: str, key: str):
        self._local = local
        self._url = url
        self._key = key

    def _call(self, name: str, *args, **kwargs):
        payload = json.dumps({"fn": name, "args": desk_web.encode(list(args)),
                              "kwargs": desk_web.encode(kwargs)}).encode("utf-8")
        body = _request(f"{self._url}/internal/desk/call", payload, self._key, "application/json", TIMEOUT_S)
        if not body.get("ok"):
            raise RemoteDeskError(str(body.get("error") or "The trading service could not finish that."))
        return desk_web.decode(body.get("value"))

    def __getattr__(self, name):
        if name in self.REMOTE:
            return lambda *a, **k: self._call(name, *a, **k)
        if name == "backup_paper":
            # The books live on the trading service; its own volume keeps them.
            return lambda *a, **k: []
        return getattr(self._local, name)

    def push_books(self, force: bool = False) -> dict:
        """Send the bot's copy of the paper books to an empty trading service."""
        blob = desk_web.pack_books(self._local)
        url = f"{self._url}/internal/desk/import" + ("?force=1" if force else "")
        try:
            return _request(url, blob, self._key, "application/gzip", 120)
        except RemoteDeskError as exc:
            return {"ok": False, "error": str(exc)}


def wrap(local):
    """The remote desk when DESK_SERVICE_URL and DESK_SERVICE_KEY are set, else the local module."""
    url = service_url()
    key = desk_web.service_key()
    if not url:
        return local
    if len(key) < desk_web.MIN_KEY_LEN:
        raise RemoteDeskError(f"DESK_SERVICE_KEY must be at least {desk_web.MIN_KEY_LEN} characters.")
    return RemoteDesk(local, url, key)
