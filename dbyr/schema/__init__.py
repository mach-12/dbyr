"""The DBYR JSON Schemas: load them, and build validators that resolve cross-file $refs."""

from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

SCHEMA_DIR = Path(__file__).parent
SCHEMA_VERSION = "0.1.0"

RECORD_SCHEMAS = {
    "RunIntent": "run_intent.schema.json",
    "RunCloseout": "run_closeout.schema.json",
    "ExceptionNotice": "exception_notice.schema.json",
}

_format_checker = FormatChecker()


@_format_checker.checks("date-time", raises=ValueError)
def _is_datetime(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must carry a UTC offset")
    return True


@_format_checker.checks("date", raises=ValueError)
def _is_date(value: Any) -> bool:
    if isinstance(value, str):
        date.fromisoformat(value)
    return True


def schema_files() -> list[Path]:
    return sorted(SCHEMA_DIR.glob("*.schema.json"))


@lru_cache(maxsize=None)
def load_schema(filename: str) -> dict:
    return json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def registry() -> Registry:
    resources = []
    for path in schema_files():
        contents = load_schema(path.name)
        resources.append((contents["$id"], Resource.from_contents(contents)))
    return Registry().with_resources(resources)


@lru_cache(maxsize=None)
def validator_for(record_type: str) -> Draft202012Validator:
    if record_type not in RECORD_SCHEMAS:
        raise KeyError(f"unknown record_type {record_type!r}")
    schema = load_schema(RECORD_SCHEMAS[record_type])
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, registry=registry(), format_checker=_format_checker)


def root(record_type: str):
    """Return (schema, resolver) for a record type, for schema-guided traversal."""
    schema = load_schema(RECORD_SCHEMAS[record_type])
    return schema, registry().resolver(base_uri=schema["$id"])


def deref(node: dict, resolver):
    """Follow $ref chains. Returns (target node, resolver scoped to its document)."""
    while isinstance(node, dict) and "$ref" in node:
        resolved = resolver.lookup(node["$ref"])
        node, resolver = resolved.contents, resolved.resolver
    return node, resolver
