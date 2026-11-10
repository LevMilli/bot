"""Observe-only corr_clerk insight digest — E8 pack. Never LIVE / floors locked."""
from __future__ import annotations

from helpers import e8_digest_pack as pack

HELPER = "corr_clerk"
DIGEST_NAME = f"{HELPER}_digest.json"


def digest_path(root: str | None = None) -> str:
    return pack.digest_path_for(HELPER, root)


def build_digest(payload=None, *, now=None):
    return pack.BUILDERS[HELPER](payload, now=now)


def write_digest_from_desk(root: str | None = None, *, bots=None):
    return pack.write_digest_from_desk(HELPER, root, bots=bots)


if __name__ == "__main__":
    import json
    print(json.dumps(write_digest_from_desk(), indent=2, sort_keys=True, default=str))
