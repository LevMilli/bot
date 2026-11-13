"""Private desk API for the trading service. Paper only.

The Discord bot keeps the staff login, the PIMP-TRADING page, and APEX-CITY.
When ``DESK_SERVICE_URL`` is set on the bot, every desk call goes here instead
of the bot's own copy of the desk. This service holds the paper books and runs
the timer.

Every call must carry ``Authorization: Bearer <DESK_SERVICE_KEY>``. Only the
functions in ``CALLS`` can run, and callers cannot pick a folder: any ``root``
argument is forced to the service's own desk.

No exchange keys, no wallets, no live orders.
"""
from __future__ import annotations

import base64
import hmac
import io
import json
import logging
import os
import shutil
import tarfile
import tempfile

log = logging.getLogger("desk_web")

MIN_KEY_LEN = 24
IMPORT_MARKER = "pimp-imported.json"
BACKUP_DIR = "pre-import-backup"
MAX_IMPORT_BYTES = 200 * 1024 * 1024

# name -> True when the first positional argument is the desk root.
CALLS = {
    "snapshot": False,
    "export_xlsx": False,
    "save_settings": False,
    "run_bot": False,
    "run_due": False,
    "set_pause": True,
    "annotate": True,
    "mark_seen": False,
    "reset_bot": False,
    "timer_health": False,
}


def service_key() -> str:
    return str(os.environ.get("DESK_SERVICE_KEY") or "").strip()


def key_ok(header: str, key: str | None = None) -> bool:
    key = service_key() if key is None else key
    if len(key) < MIN_KEY_LEN:
        return False
    want = f"Bearer {key}"
    got = str(header or "")
    return len(got) == len(want) and hmac.compare_digest(got.encode(), want.encode())


def encode(value):
    if isinstance(value, (bytes, bytearray)):
        return {"__bytes__": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, tuple):
        return {"__tuple__": [encode(v) for v in value]}
    if isinstance(value, list):
        return [encode(v) for v in value]
    if isinstance(value, dict):
        return {str(k): encode(v) for k, v in value.items()}
    return value


def decode(value):
    if isinstance(value, dict):
        if set(value) == {"__bytes__"}:
            return base64.b64decode(value["__bytes__"])
        if set(value) == {"__tuple__"}:
            return tuple(decode(v) for v in value["__tuple__"])
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value


def call(desk, name: str, args=None, kwargs=None):
    """Run one allowed desk function. Raises KeyError for anything else."""
    if name not in CALLS:
        raise KeyError(name)
    args = list(args or [])
    kwargs = dict(kwargs or {})
    kwargs.pop("root", None)
    if CALLS[name]:
        if args:
            args[0] = None
        else:
            args = [None]
    return getattr(desk, name)(*args, **kwargs)


def _has_books(desk) -> bool:
    durable = desk.settlement_dir()
    base = durable if durable and os.path.isdir(durable) else desk.ROOT
    for rel in desk.SETTLEMENT_FILES:
        path = os.path.join(base, *rel.split("/"))
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            return True
    return False


def _safe_members(tar: tarfile.TarFile):
    for member in tar.getmembers():
        name = member.name
        if name.startswith("/") or ".." in name.split("/"):
            continue
        if not (member.isfile() or member.isdir()):
            continue
        yield member


def _target(desk) -> str:
    durable = desk.settlement_dir()
    return durable or desk.ROOT


def imported(desk) -> bool:
    return os.path.isfile(os.path.join(_target(desk), IMPORT_MARKER))


def _backup_target(target: str, stamp: str) -> int:
    """Copy what the service has now aside before the bot's books replace it."""
    dest_root = os.path.join(target, BACKUP_DIR, stamp)
    n = 0
    for folder, dirs, files in os.walk(target):
        rel_folder = os.path.relpath(folder, target)
        if rel_folder.split(os.sep)[0] == BACKUP_DIR:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if not (rel_folder == "." and d == BACKUP_DIR)]
        for name in files:
            src = os.path.join(folder, name)
            if os.path.islink(src) or not os.path.isfile(src):
                continue
            dest = os.path.join(dest_root, os.path.relpath(src, target))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
            n += 1
    return n


def import_books(desk, blob: bytes, force: bool = False) -> dict:
    """Take the Discord bot's paper books once.

    The first copy wins over whatever the service wrote on its own since it
    started; those files are kept in pre-import-backup/<time>/ first. After
    that, every copy is refused unless forced, so the service's books are never
    replaced by an older copy.
    """
    if imported(desk) and not force:
        return {"ok": False, "error": "The Discord bot's books were already copied here once. Nothing was replaced."}
    target = _target(desk)
    os.makedirs(target, exist_ok=True)
    import time as _time
    stamp = _time.strftime("%Y%m%d-%H%M%S", _time.gmtime())
    count = 0
    lock = getattr(desk, "_FILE_LOCK", None)
    if lock is not None:
        lock.acquire()
    try:
        backed_up = _backup_target(target, stamp)
        count = _unpack_into(blob, target)
        with open(os.path.join(target, IMPORT_MARKER), "w", encoding="utf-8") as handle:
            json.dump({"paper_only": True, "at": stamp, "files": count, "backed_up": backed_up}, handle)
    finally:
        if lock is not None:
            lock.release()
    if desk.settlement_dir():
        desk.keep_closed_settlements()
    try:
        desk.audit(None, "desk-service", f"Imported {count} paper file(s) from the Discord bot.")
    except Exception:  # noqa: BLE001
        pass
    log.warning("Imported %s paper file(s) from the Discord bot; %s earlier file(s) kept in %s/%s.",
                count, backed_up, BACKUP_DIR, stamp)
    return {"ok": True, "files": count, "backed_up": backed_up}


def _unpack_into(blob: bytes, target: str) -> int:
    count = 0
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
            members = list(_safe_members(tar))
            tar.extractall(tmp, members=members)
        for folder, _dirs, files in os.walk(tmp):
            for name in files:
                src = os.path.join(folder, name)
                rel = os.path.relpath(src, tmp)
                dest = os.path.join(target, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                if os.path.islink(dest):
                    os.unlink(dest)
                shutil.copy2(src, dest)
                count += 1
    return count


def pack_books(desk) -> bytes:
    """Copy of this desk's paper folder (the volume copy when one is bound)."""
    durable = desk.settlement_dir()
    base = durable if durable and os.path.isdir(durable) else desk.ROOT
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        if base == desk.ROOT:
            for rel in desk.SETTLEMENT_FILES:
                path = os.path.join(base, *rel.split("/"))
                if os.path.isfile(path):
                    tar.add(os.path.realpath(path), arcname=rel)
            arch = os.path.join(base, "midnight-archive")
            if os.path.isdir(arch):
                tar.add(arch, arcname="midnight-archive")
        else:
            for name in sorted(os.listdir(base)):
                if name in (BACKUP_DIR, IMPORT_MARKER):
                    continue
                tar.add(os.path.join(base, name), arcname=name)
    return buf.getvalue()


def make_app(desk=None):
    from aiohttp import web
    import asyncio

    if desk is None:
        import pimp_desk as desk

    def guard(request):
        if not key_ok(request.headers.get("Authorization", "")):
            raise web.HTTPForbidden(text=json.dumps({"ok": False, "error": "Wrong or missing desk key."}),
                                    content_type="application/json")

    async def health(request):
        try:
            timer = desk.timer_health()
        except Exception:  # noqa: BLE001
            timer = {"alive": False}
        body = {
            "ok": True,
            "paper_only": True,
            "service": "trading-desk",
            "timer_alive": bool(timer.get("alive")),
            "has_books": _has_books(desk),
            "imported": imported(desk),
        }
        try:
            import desk_ops
            extra = desk_ops.health(desk)
            body.update({k: v for k, v in extra.items() if k not in body})
        except Exception:  # noqa: BLE001 - extra health fields never break the health page
            log.exception("desk health extras")
        return web.json_response(body)

    async def do_call(request):
        guard(request)
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            return web.json_response({"ok": False, "error": "Bad request."}, status=400)
        name = str(body.get("fn") or "")
        if name not in CALLS:
            return web.json_response({"ok": False, "error": "That desk call is not allowed."}, status=400)
        loop = asyncio.get_running_loop()
        try:
            value = await loop.run_in_executor(
                None, lambda: call(desk, name, decode(body.get("args") or []), decode(body.get("kwargs") or {})))
        except Exception as exc:  # noqa: BLE001
            log.exception("desk call %s", name)
            return web.json_response({"ok": False, "error": desk.public_error(str(exc)) or "The desk could not finish that."},
                                     status=500)
        return web.json_response({"ok": True, "value": encode(value)})

    async def do_import(request):
        guard(request)
        blob = await request.read()
        if not blob or len(blob) > MAX_IMPORT_BYTES:
            return web.json_response({"ok": False, "error": "Empty or too large."}, status=400)
        force = str(request.query.get("force") or "") == "1"
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(None, lambda: import_books(desk, blob, force=force))
        except Exception:  # noqa: BLE001
            log.exception("desk import")
            return web.json_response({"ok": False, "error": "Could not unpack the paper books."}, status=400)
        return web.json_response(result, status=200 if result.get("ok") else 409)

    app = web.Application(client_max_size=MAX_IMPORT_BYTES + 1024)
    app.add_routes([
        web.get("/healthz", health),
        web.post("/internal/desk/call", do_call),
        web.post("/internal/desk/import", do_import),
    ])
    return app
