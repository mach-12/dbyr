"""Hash every input of a case before scoring and check none changed after.

Scoring must never alter what it scores. A fingerprint is taken when a case is loaded and
taken again once scoring is done; any difference stops the run. It covers the case folder (the
decision points, sources.json, annotations.json) and, when the decision points point at filings
kept elsewhere, that filing set too. Files the scorer writes itself (results, reports) are
excluded, as are cache folders.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..integrity import schema_hash

# Files a scorer or report writes. They are outputs, not inputs.
OUTPUT_NAMES = {"results.json", "results.md", "metrics.json", "report.md", "report.html"}
IGNORED_PARTS = {"__pycache__", ".git", ".ipynb_checkpoints"}


class InputsChanged(RuntimeError):
    """A case's inputs differ between the start and the end of scoring."""


class SchemaChanged(RuntimeError):
    """A case records a frozen schema hash that is not the current schema's."""


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(p for p in root.rglob("*")
                  if p.is_file() and p.name not in OUTPUT_NAMES and not IGNORED_PARTS & set(p.parts))


def _name(path: Path, base: Path) -> str:
    """A path relative to the case folder where possible, else absolute."""
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


@dataclass(frozen=True)
class Fingerprint:
    schema_hash: str
    roots: tuple[str, ...]      # the folders or files hashed; the first is the case folder
    files: dict[str, str]       # path (relative to the case folder where possible) -> sha256

    @classmethod
    def take(cls, base: str | Path, *more: str | Path) -> "Fingerprint":
        base = Path(base)
        roots = [base] + [Path(m) for m in more]
        files = {}
        for root in roots:
            for p in _files(root):
                files[_name(p, base)] = _sha256(p)
        return cls(schema_hash(), tuple(str(r) for r in roots), files)

    def again(self) -> "Fingerprint":
        """A new fingerprint over the same folders."""
        return Fingerprint.take(*self.roots)

    def diff(self, other: "Fingerprint") -> list[str]:
        """Human-readable differences; empty when the two fingerprints match."""
        out = []
        if self.schema_hash != other.schema_hash:
            out.append(f"schema hash changed: {self.schema_hash} -> {other.schema_hash}")
        for name in sorted(self.files.keys() | other.files.keys()):
            before, after = self.files.get(name), other.files.get(name)
            if before is None:
                out.append(f"added: {name}")
            elif after is None:
                out.append(f"removed: {name}")
            elif before != after:
                out.append(f"modified: {name}")
        return out

    def to_json(self) -> dict:
        return {"schema_hash": self.schema_hash, "roots": list(self.roots), "files": dict(self.files)}
