"""The city snapshot schema (GET /api/pimp-trading.json), versioned.

The APEX-CITY page (trading-city/src/types.ts ``Snapshot``) reads these
top-level keys. The desk may add new keys at any time: the city ignores keys
it does not know, so an old city build keeps working when a new field
appears. Renaming or removing a key the city reads is a breaking change and
needs a new ``SCHEMA_VERSION`` plus a matching ``FIELDS_BY_VERSION`` row.

Read only. Nothing here changes what a tower does.
"""
from __future__ import annotations

SCHEMA_VERSION = 1

# Top-level keys of the TypeScript ``Snapshot`` type, per schema version.
FIELDS_BY_VERSION = {
    1: ("paper_only", "banner", "desk", "bots", "limits", "roi_system", "health", "timer", "ok", "error",
        "schema_version"),
}
FIELDS = FIELDS_BY_VERSION[SCHEMA_VERSION]
# Keys the desk always sends (``ok`` and ``error`` only appear on a failure).
ALWAYS = ("paper_only", "banner", "desk", "bots", "limits", "roi_system", "health", "timer", "schema_version")
# Every tower card needs these.
BOT_REQUIRED = ("id", "name")


def problems(snap, *, require_version: bool = False) -> list[str]:
    """Plain list of what is wrong with a snapshot for the city. Empty = fine.

    Unknown keys are never a problem (forward compatible). A snapshot without
    ``schema_version`` is an old desk build (version 0) and still valid unless
    ``require_version`` is set.
    """
    out: list[str] = []
    if not isinstance(snap, dict):
        return ["snapshot is not an object"]
    version = snap.get("schema_version")
    if version is None:
        if require_version:
            out.append("schema_version missing")
    elif not isinstance(version, int) or isinstance(version, bool) or version < 1:
        out.append(f"schema_version {version!r} is not a positive whole number")
    if snap.get("paper_only") is not True:
        out.append("paper_only must be true")
    bots = snap.get("bots")
    if not isinstance(bots, list):
        out.append("bots[] missing")
        return out
    seen = set()
    for i, bot in enumerate(bots):
        if not isinstance(bot, dict):
            out.append(f"bots[{i}] is not an object")
            continue
        for key in BOT_REQUIRED:
            if not isinstance(bot.get(key), str) or not bot.get(key):
                out.append(f"bots[{i}].{key} missing")
        if bot.get("id") in seen:
            out.append(f"bots[{i}].id {bot.get('id')!r} repeated")
        seen.add(bot.get("id"))
    if "desk" in snap and not isinstance(snap.get("desk"), (dict, type(None))):
        out.append("desk is not an object")
    return out
