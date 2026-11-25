"""Append-only, hash-chained, signed record.

Under Layer A the evaluator holds this file; under Layer B a register does.
Each entry commits to the previous entry's hash, so deleting, reordering or
editing any filing breaks every later link. Each entry is signed with Ed25519 by
the filer, so a filing is attributable to a key that a role controls.

Entries are stored one per line (JSON Lines).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from .findings import Finding, errors
from .integrity import canonical_bytes, digest, sha256_hex
from .rules import validate_record

GENESIS = "sha256:" + "0" * 64


def key_id(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return "ed25519:" + sha256_hex(raw)[:16]


def public_key_b64(public_key: Ed25519PublicKey) -> str:
    return base64.b64encode(public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()


def _signing_payload(entry: dict) -> bytes:
    body = {k: v for k, v in entry.items() if k not in ("signature", "entry_hash")}
    return canonical_bytes(body)


@dataclass
class Ledger:
    path: Path

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def head(self) -> str:
        e = self.entries()
        return e[-1]["entry_hash"] if e else GENESIS

    def append(self, record: dict, signing_key: Ed25519PrivateKey, filed_at: str | None = None) -> dict:
        """Validate, sign and append. Rejects non-compliant filings rather than recording them."""
        problems = errors(validate_record(record))
        if problems:
            raise ValueError("filing rejected:\n  " + "\n  ".join(map(str, problems)))
        existing = self.entries()
        entry = {
            "seq": len(existing),
            "prev_hash": existing[-1]["entry_hash"] if existing else GENESIS,
            "received_at": filed_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "record_type": record["record_type"],
            "record_digest": digest(record),
            "record": record,
            "signer_key": key_id(signing_key.public_key()),
            "signer_public_key": public_key_b64(signing_key.public_key()),
        }
        entry["signature"] = base64.b64encode(signing_key.sign(_signing_payload(entry))).decode()
        entry["entry_hash"] = digest({k: v for k, v in entry.items() if k != "entry_hash"})
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
        return entry

    def verify(self, trusted_keys: dict[str, str] | None = None) -> list[Finding]:
        """Recheck every link, digest and signature.

        trusted_keys maps key_id -> base64 public key. Without it, signatures are
        checked against the key embedded in each entry, which proves integrity
        but not who holds the key.
        """
        out: list[Finding] = []
        prev = GENESIS
        for n, entry in enumerate(self.entries()):
            where = f"seq {n}"
            if entry.get("seq") != n:
                out.append(Finding("error", "seq_gap", where, f"expected seq {n}, found {entry.get('seq')}"))
            if entry.get("prev_hash") != prev:
                out.append(Finding("error", "chain_broken", where, "prev_hash does not match the previous entry"))
            if digest(entry["record"]) != entry.get("record_digest"):
                out.append(Finding("error", "record_altered", where, "record does not match its digest"))
            recomputed = digest({k: v for k, v in entry.items() if k != "entry_hash"})
            if recomputed != entry.get("entry_hash"):
                out.append(Finding("error", "entry_altered", where, "entry_hash does not match entry contents"))
            pub_b64 = (trusted_keys or {}).get(entry["signer_key"], entry["signer_public_key"])
            if trusted_keys is not None and entry["signer_key"] not in trusted_keys:
                out.append(Finding("error", "untrusted_key", where, f"{entry['signer_key']} is not a trusted key"))
            try:
                Ed25519PublicKey.from_public_bytes(base64.b64decode(pub_b64)).verify(
                    base64.b64decode(entry["signature"]), _signing_payload(entry))
            except (InvalidSignature, ValueError):
                out.append(Finding("error", "bad_signature", where, "signature does not verify"))
            prev = entry.get("entry_hash", prev)
        return out
