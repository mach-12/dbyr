"""Canonical JSON, digests and the schema hash.

Every hash in DBYR (ledger entries, commitments, the schema hash) is taken over
the same canonical form, so two parties holding the same record compute the
same digest. The schema hash fixes the schema before a case is scored: publish
it first, recompute it at scoring time, and they must match. Reformatting a
schema file does not change the hash; any change to its content does.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .schema import SCHEMA_VERSION, schema_files


def canonical_bytes(value: Any) -> bytes:
    """Sorted keys, no insignificant whitespace, UTF-8, no NaN/Infinity."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(value: Any) -> str:
    """Prefixed SHA-256 digest of a JSON value's canonical form."""
    return "sha256:" + sha256_hex(canonical_bytes(value))


def schema_bundle() -> dict:
    return {p.name: json.loads(p.read_text(encoding="utf-8")) for p in schema_files()}


def schema_hash() -> str:
    return digest({"schema_version": SCHEMA_VERSION, "files": schema_bundle()})
