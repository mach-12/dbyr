"""Project one filing into the three disclosure views.

A field whose x-tier is above the viewer's tier is replaced by a salted
commitment. The viewer therefore sees that the field exists and can later check
an opening, but learns nothing about its value. Salts matter: without them a
low-entropy field (a boolean, a role title) could be recovered by hashing every
candidate value.

    public      sees public fields; commitments for restricted and sealed
    restricted  sees public and restricted; commitments for sealed
    sealed      sees everything (the developer's own copy)
"""

from __future__ import annotations

import copy
import hmac
import os
from typing import Any

from .integrity import canonical_bytes, sha256_hex
from .schema import deref, root

RANK = {"public": 0, "restricted": 1, "sealed": 2}


def commit(value: Any, salt: bytes) -> str:
    return "sha256:" + sha256_hex(salt + canonical_bytes(value))


def check_opening(commitment: str, value: Any, salt_hex: str) -> bool:
    return hmac.compare_digest(commitment, commit(value, bytes.fromhex(salt_hex)))


def project(record: dict, view: str, salts: dict[str, str] | None = None) -> tuple[dict, dict[str, str]]:
    """Return (projected record, openings).

    openings maps JSON pointer -> salt hex for every committed field. The
    developer keeps it with the sealed copy; a party later shown the value and
    salt for a pointer can check it against the public commitment.

    Pass the salts returned by an earlier call to make two views consistent
    (the restricted view's commitments to sealed fields then equal the public
    view's).
    """
    if view not in RANK:
        raise ValueError(f"view must be one of {sorted(RANK)}")
    schema, resolver = root(record["record_type"])
    salts = dict(salts or {})
    openings: dict[str, str] = {}

    def walk(value: Any, node: dict, res, pointer: str) -> Any:
        tier = node.get("x-tier") if isinstance(node, dict) else None
        node, res = deref(node, res)
        if tier is None and isinstance(node, dict):
            tier = node.get("x-tier")
        if tier is not None and RANK[tier] > RANK[view]:
            salt_hex = salts.get(pointer) or os.urandom(16).hex()
            salts[pointer] = salt_hex
            openings[pointer] = salt_hex
            return {"$commitment": commit(value, bytes.fromhex(salt_hex)), "$tier": tier}
        if isinstance(value, dict):
            props = node.get("properties", {}) if isinstance(node, dict) else {}
            return {k: walk(v, props.get(k, {}), res, f"{pointer}/{k}") for k, v in value.items()}
        if isinstance(value, list):
            items = node.get("items", {}) if isinstance(node, dict) else {}
            return [walk(v, items, res, f"{pointer}/{n}") for n, v in enumerate(value)]
        return copy.deepcopy(value)

    projected = walk(record, schema, resolver, "")
    return projected, openings


def all_views(record: dict) -> dict[str, dict]:
    """Public, restricted and sealed views with mutually consistent commitments."""
    public, openings = project(record, "public")
    restricted, restricted_openings = project(record, "restricted", salts=openings)
    # The developer must be able to open every commitment in either view, including
    # sealed fields nested inside objects that the public view commits to as a whole.
    openings = {**openings, **restricted_openings}
    return {"public": public, "restricted": restricted, "sealed": copy.deepcopy(record), "openings": openings}
