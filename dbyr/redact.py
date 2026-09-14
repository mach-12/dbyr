"""Three views of one document.

A filing is authored once. The register derives the public, restricted and sealed
views from the per-field tier annotations carried in the schema, so the tiers
cannot drift apart the way three separately drafted documents would.

Every withheld field is replaced by a SHA-256 commitment over its canonical
encoding, and the commitments are folded into a Merkle root published with the
public view. A developer can therefore be challenged later on a sealed field
without disclosing it now: they reveal the value, anyone recomputes the leaf, and
the root either matches or it does not.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .validate import load_schema

TIERS = ("public", "restricted", "sealed")
_ORDER = {t: i for i, t in enumerate(TIERS)}


def canonical(value: Any) -> bytes:
    """Deterministic encoding: sorted keys, no insignificant whitespace, UTF-8."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def leaf_hash(path: str, value: Any) -> str:
    """Domain-separated commitment; the path is bound in so leaves cannot be swapped."""
    return hashlib.sha256(b"dbyr-leaf\x00" + path.encode() + b"\x00" + canonical(value)).hexdigest()


def merkle_root(leaves: dict[str, str]) -> str:
    """Root over path-sorted leaf hashes. Odd nodes are promoted, not duplicated."""
    if not leaves:
        return hashlib.sha256(b"dbyr-empty").hexdigest()
    level = [bytes.fromhex(leaves[p]) for p in sorted(leaves)]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level) - 1, 2):
            nxt.append(hashlib.sha256(b"dbyr-node\x00" + level[i] + level[i + 1]).digest())
        if len(level) % 2:
            nxt.append(level[-1])
        level = nxt
    return level[0].hex()


def _commit(commitments: dict[str, str], path: str, value: Any) -> str:
    """Commit a whole node and drop any commitments already made for its children."""
    for child in [k for k in commitments if k.startswith(path + "/")]:
        del commitments[child]
    commitments[path] = leaf_hash(path, value)
    return commitments[path]


def _annotation(schema: dict[str, Any] | None) -> dict[str, Any]:
    return (schema or {}).get("x-dbyr", {}) or {}


def _project(value: Any, schema: dict[str, Any] | None, view: str, inherited: str, path: str,
             commitments: dict[str, str]) -> tuple[Any, bool]:
    """Return (projected_value, include). Records commitments for anything withheld."""
    ann = _annotation(schema)
    tier = ann.get("tier", inherited)
    visible = _ORDER[tier] <= _ORDER[view]

    if isinstance(value, dict) and schema and "properties" in schema:
        kept: dict[str, Any] = {}
        withheld: list[str] = []
        for key, sub in value.items():
            sub_schema = schema["properties"].get(key)
            projected, include = _project(sub, sub_schema, view, tier, f"{path}/{key}", commitments)
            if include:
                kept[key] = projected
            else:
                withheld.append(key)
        if kept:
            if withheld:
                kept["_dbyr_withheld"] = sorted(withheld)
            return kept, True
        if not visible:
            _commit(commitments, path, value)
            if ann.get("public_projection") == "exists":
                return {"_dbyr_present": True, "_dbyr_commitment": commitments[path]}, True
            return None, False
        return kept, True

    if isinstance(value, list) and schema and isinstance(schema.get("items"), dict):
        item_schema = schema["items"]
        if visible:
            out = []
            for i, item in enumerate(value):
                projected, include = _project(item, item_schema, view, tier, f"{path}/{i}", commitments)
                if include:
                    out.append(projected)
            return out, True
        # Not visible at this view: try to promote any child fields that are.
        promoted = []
        for i, item in enumerate(value):
            projected, include = _project(item, item_schema, view, tier, f"{path}/{i}", commitments)
            if include and projected not in (None, {}, []):
                promoted.append(projected)
        _commit(commitments, path, value)
        if promoted:
            return promoted, True
        if ann.get("public_projection") == "count":
            return {"_dbyr_count": len(value), "_dbyr_commitment": commitments[path]}, True
        if ann.get("public_projection") == "exists":
            return {"_dbyr_present": bool(value), "_dbyr_commitment": commitments[path]}, True
        return None, False

    if visible:
        return value, True
    _commit(commitments, path, value)
    if ann.get("public_projection") == "exists":
        return {"_dbyr_present": value is not None, "_dbyr_commitment": commitments[path]}, True
    return None, False


def project(record: dict[str, Any], view: str = "public") -> dict[str, Any]:
    """Derive one tier view of a record, with commitments over everything withheld."""
    if view not in TIERS:
        raise ValueError(f"view must be one of {TIERS}")
    schema = load_schema(record["record_type"])
    commitments: dict[str, str] = {}
    default_tier = record.get("disclosure_tier_default", "restricted")
    projected, _ = _project(record, schema, view, default_tier, "", commitments)

    return {
        "_dbyr_view": view,
        "_dbyr_merkle_root": merkle_root(commitments),
        "_dbyr_withheld_count": len(commitments),
        "record": projected or {},
    }


def verify_disclosure(record_fragment: Any, path: str, claimed_root: str,
                      commitments: dict[str, str]) -> bool:
    """Check a later-revealed field against a previously published Merkle root.

    This is the challenge path: the developer reveals one sealed field, the
    challenger recomputes its leaf and the root over the published commitment
    set, and a mismatch is evidence the filing was altered after the fact.
    """
    recomputed = dict(commitments)
    recomputed[path] = leaf_hash(path, record_fragment)
    return merkle_root(recomputed) == claimed_root


def commitments_for(record: dict[str, Any], view: str = "public") -> dict[str, str]:
    """The path to leaf-hash map withheld at ``view``. Published beside the root."""
    schema = load_schema(record["record_type"])
    commitments: dict[str, str] = {}
    _project(record, schema, view, record.get("disclosure_tier_default", "restricted"), "", commitments)
    return commitments
