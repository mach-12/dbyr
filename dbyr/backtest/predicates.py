"""The predicate language decision points are written in.

A predicate tests one filing:

  {"record": KEY, "pointer": "/a/b", "equals": VALUE}
  {"record": KEY, "pointer": "/a/b", "exists": true}
  {"record": KEY, "any": "/list", "where": {FIELD: VALUE | [VALUES] | {"contains": X} | {"nonempty": true}}}
  {"all": [PREDICATE, ...]}

The evaluation is unchanged from the pre-registered scorer: `contains` tests list membership
(on a string it is always false), and a missing pointer is None.
"""

from __future__ import annotations


def get(doc, pointer: str):
    """Follow a JSON pointer; None where it does not resolve."""
    node = doc
    for part in [p for p in pointer.split("/") if p]:
        if isinstance(node, list):
            node = node[int(part)]
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def matches(item: dict, where: dict) -> bool:
    for key, want in where.items():
        have = item.get(key)
        if isinstance(want, dict):
            if "contains" in want and not (isinstance(have, list) and want["contains"] in have):
                return False
            if want.get("nonempty") and not have:
                return False
        elif isinstance(want, list):
            if have not in want:
                return False
        elif have != want:
            return False
    return True


def holds(pred: dict, records: dict) -> bool:
    if "all" in pred:
        return all(holds(p, records) for p in pred["all"])
    doc = records[pred["record"]]
    if "any" in pred:
        items = get(doc, pred["any"]) or []
        return any(matches(i, pred.get("where", {})) for i in items)
    value = get(doc, pred["pointer"])
    if "equals" in pred:
        return value == pred["equals"]
    if pred.get("exists"):
        return value is not None
    raise ValueError(f"unrecognised predicate {pred}")


def leaves(pred: dict) -> list[dict]:
    """The single-filing tests inside a predicate, in order."""
    if "all" in pred:
        return [leaf for p in pred["all"] for leaf in leaves(p)]
    return [pred]


def fields_read(pred: dict) -> list[tuple[str, str]]:
    """(record key, JSON pointer) for every field a predicate reads, including `where` keys."""
    out = []
    for leaf in leaves(pred):
        if "any" in leaf:
            out.append((leaf["record"], leaf["any"]))
            out += [(leaf["record"], f"{leaf['any']}/*/{k}") for k in leaf.get("where", {})]
        else:
            out.append((leaf["record"], leaf["pointer"]))
    return out


def first_record(pred: dict) -> str:
    return pred["record"] if "record" in pred else first_record(pred["all"][0])
