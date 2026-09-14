"""Side-effect-free predicate evaluation for DBYR pause criteria.

A pause criterion's ``match`` is a small declarative expression over an event
record. Keeping it declarative rather than executable is deliberate: a register
must be able to evaluate a filed criterion without running developer-supplied
code, and an auditor must be able to read the rule without a debugger.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

COMBINATORS = ("all_of", "any_of", "none_of")
LEAF_OPS = ("eq", "ne", "in", "not_in", "contains", "gte", "lte", "exists", "regex")


class PredicateError(ValueError):
    """Raised when a predicate is structurally invalid."""


def _resolve(event: Mapping[str, Any], path: str) -> Any:
    """Resolve a dotted path against an event, returning None if absent."""
    cur: Any = event
    for part in path.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _leaf(pred: Mapping[str, Any], event: Mapping[str, Any]) -> bool:
    field, op = pred["field"], pred["op"]
    actual = _resolve(event, field)
    expected = pred.get("value")

    if op == "exists":
        return (actual is not None) == (True if expected is None else bool(expected))
    if actual is None:
        return False
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "in":
        return actual in (expected or [])
    if op == "not_in":
        return actual not in (expected or [])
    if op == "contains":
        return expected in actual if isinstance(actual, (list, str, tuple)) else False
    if op == "gte":
        return actual >= expected
    if op == "lte":
        return actual <= expected
    if op == "regex":
        return bool(re.search(str(expected), str(actual)))
    raise PredicateError(f"unknown op: {op}")


def evaluate(pred: Mapping[str, Any] | None, event: Mapping[str, Any]) -> bool:
    """Evaluate ``pred`` against a single event record.

    A criterion with no ``match`` is not machine-checkable and never fires
    automatically; it is reported separately by the replay harness so that
    non-checkable criteria are visible rather than silently inert.
    """
    if pred is None:
        return False
    if not isinstance(pred, Mapping):
        raise PredicateError("predicate must be an object")

    keys = [k for k in pred if k in COMBINATORS]
    if keys:
        if len(keys) > 1 or len(pred) > 1:
            raise PredicateError("a combinator node takes exactly one key")
        key = keys[0]
        children = pred[key]
        if not isinstance(children, list) or not children:
            raise PredicateError(f"{key} requires a non-empty list")
        results = (evaluate(c, event) for c in children)
        if key == "all_of":
            return all(results)
        if key == "any_of":
            return any(results)
        return not any(results)

    if "field" not in pred or "op" not in pred:
        raise PredicateError(f"leaf predicate requires 'field' and 'op': {pred!r}")
    return _leaf(pred, event)


def describe(pred: Mapping[str, Any] | None) -> str:
    """Render a predicate as a single human-readable line for audit output."""
    if pred is None:
        return "(not machine-checkable)"
    for key in COMBINATORS:
        if key in pred:
            joiner = {"all_of": " AND ", "any_of": " OR ", "none_of": " NOR "}[key]
            return "(" + joiner.join(describe(c) for c in pred[key]) + ")"
    val = pred.get("value")
    return f"{pred['field']} {pred['op']} {val!r}" if val is not None else f"{pred['field']} {pred['op']}"
