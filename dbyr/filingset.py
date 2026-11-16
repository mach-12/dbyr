"""Load a filing set: the unit the protocol runs on.

A filing set is a folder (or a list of files and folders) holding DBYR records:
Intents and their amendments, ExceptionNotices and Closeouts.
Which files belong to it is decided, in order, by:

  manifest.json   {"description": "...", "records": {"intent:A": "intent_A.json", ...}}
                  the keys label each filing in the report
  no manifest     every *.json that carries a record_type; the key is the file name.
                  Other JSON (a backtest case's decision_points.json, sources.json,
                  results.json) is listed as skipped, not reported as a broken filing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST = "manifest.json"


class FilingSetError(ValueError):
    """The filing set cannot be read: missing file, invalid JSON, or a bad manifest."""


@dataclass
class FilingSet:
    records: dict[str, dict]
    files: dict[str, Path]
    description: str = ""
    skipped: list[Path] = field(default_factory=list)


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FilingSetError(f"{path}: no such file") from None
    except json.JSONDecodeError as exc:
        raise FilingSetError(f"{path}: not valid JSON ({exc})") from None


def _from_manifest(path: Path) -> FilingSet:
    manifest = _read(path)
    entries = manifest.get("records") if isinstance(manifest, dict) else None
    if not isinstance(entries, dict) or not entries:
        raise FilingSetError(f"{path}: a manifest needs a non-empty \"records\" object of key -> file")
    files = {key: path.parent / name for key, name in entries.items()}
    return FilingSet({key: _read(f) for key, f in files.items()}, files, manifest.get("description", ""))


def load_filing_set(*paths: str | Path) -> FilingSet:
    """Load one filing set from a manifest, a folder, or a list of files and folders."""
    paths = [Path(p) for p in paths]
    if not paths:
        raise FilingSetError("no filings given")
    if len(paths) == 1:
        only = paths[0]
        if only.is_file() and only.name == MANIFEST:
            return _from_manifest(only)
        if only.is_dir() and (only / MANIFEST).exists():
            return _from_manifest(only / MANIFEST)
    out = FilingSet({}, {})
    for p in paths:
        if not p.exists():
            raise FilingSetError(f"{p}: no such file or folder")
        for f in sorted(p.glob("*.json")) if p.is_dir() else [p]:
            doc = _read(f)
            if not (isinstance(doc, dict) and "record_type" in doc):
                out.skipped.append(f)
                continue
            key = f.name if f.name not in out.records else str(f)
            out.records[key], out.files[key] = doc, f
    if not out.records:
        raise FilingSetError("no DBYR records found (a record is a JSON object with a record_type)")
    return out
