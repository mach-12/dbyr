"""Signed envelopes and the append-only register log.

Envelopes are JWS-shaped: a detached payload digest, an algorithm, a signer block
and a signature. Ed25519 is used when ``cryptography`` is available; otherwise the
envelope degrades to a digest-only form that is explicitly marked unsigned, so a
self-attested record can never be mistaken for a signed one.

The register log is a hash chain. Each entry commits to the previous entry, so an
entry cannot be removed or back-dated without breaking every entry after it. That
is the property that makes "the restart was recorded" checkable later.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .redact import canonical, commitments_for, merkle_root

try:  # optional dependency
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

    HAVE_ED25519 = True
except Exception:  # pragma: no cover
    HAVE_ED25519 = False


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def generate_key() -> tuple[str, str]:
    """Return (private_key_b64, key_id). Test and pilot use only."""
    if not HAVE_ED25519:
        raise RuntimeError("ed25519 unavailable; install `cryptography`")
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes_raw()
    pub = key.public_key().public_bytes_raw()
    return _b64(raw), hashlib.sha256(pub).hexdigest()[:16]


def sign(record: dict[str, Any], private_key_b64: str | None = None,
         signer: dict[str, str] | None = None) -> dict[str, Any]:
    """Wrap a record in a signed envelope carrying its tier commitment roots."""
    payload = canonical(record)
    digest = hashlib.sha256(payload).hexdigest()
    roots = {
        view: merkle_root(commitments_for(record, view))
        for view in ("public", "restricted")
    }
    envelope: dict[str, Any] = {
        "dbyr_envelope": "0.1",
        "record_type": record.get("record_type"),
        "run_id": record.get("run_id") or record.get("system_id"),
        "payload_sha256": digest,
        "commitment_roots": roots,
        "filed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "signer": signer or record.get("signer") or {},
    }
    if private_key_b64 and HAVE_ED25519:
        key = Ed25519PrivateKey.from_private_bytes(_unb64(private_key_b64))
        envelope["alg"] = "EdDSA"
        envelope["public_key"] = _b64(key.public_key().public_bytes_raw())
        envelope["signature"] = _b64(key.sign(canonical(
            {k: v for k, v in envelope.items() if k not in ("signature",)}
        )))
    else:
        envelope["alg"] = "none"
        envelope["signature"] = None
    envelope["payload"] = record
    return envelope


def verify(envelope: dict[str, Any]) -> tuple[bool, str]:
    """Check digest and, where present, the Ed25519 signature."""
    record = envelope.get("payload")
    if record is None:
        return False, "envelope carries no payload"
    if hashlib.sha256(canonical(record)).hexdigest() != envelope.get("payload_sha256"):
        return False, "payload digest mismatch: the record was altered after filing"
    if envelope.get("alg") == "none":
        return True, "digest verified; record is UNSIGNED (V0 self-attestation)"
    if not HAVE_ED25519:
        return False, "signature present but ed25519 unavailable"
    body = {k: v for k, v in envelope.items() if k not in ("signature", "payload")}
    pub = Ed25519PublicKey.from_public_bytes(_unb64(envelope["public_key"]))
    try:
        pub.verify(_unb64(envelope["signature"]), canonical(body))
    except Exception:
        return False, "signature verification failed"
    return True, "digest and Ed25519 signature verified"


class Register:
    """An append-only, hash-chained register file (JSON Lines)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _tip(self) -> str:
        if not self.path.exists():
            return "0" * 64
        last = None
        for line in self.path.read_text().splitlines():
            if line.strip():
                last = json.loads(line)
        return last["entry_hash"] if last else "0" * 64

    def append(self, envelope: dict[str, Any]) -> dict[str, Any]:
        entry = {
            "seq": self.count(),
            "prev_hash": self._tip(),
            "record_type": envelope.get("record_type"),
            "run_id": envelope.get("run_id"),
            "payload_sha256": envelope.get("payload_sha256"),
            "commitment_roots": envelope.get("commitment_roots"),
            "alg": envelope.get("alg"),
            "filed_at": envelope.get("filed_at"),
        }
        entry["entry_hash"] = hashlib.sha256(canonical(entry)).hexdigest()
        with self.path.open("a") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text().splitlines() if l.strip()]

    def count(self) -> int:
        return len(self.entries())

    def verify_chain(self) -> tuple[bool, str]:
        prev = "0" * 64
        for entry in self.entries():
            body = {k: v for k, v in entry.items() if k != "entry_hash"}
            if entry["prev_hash"] != prev:
                return False, f"entry {entry['seq']}: broken chain (an earlier entry was removed or edited)"
            if hashlib.sha256(canonical(body)).hexdigest() != entry["entry_hash"]:
                return False, f"entry {entry['seq']}: entry hash mismatch"
            prev = entry["entry_hash"]
        return True, f"chain intact over {self.count()} entries"
