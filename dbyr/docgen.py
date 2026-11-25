"""The field tables in docs/records/, generated from the schemas.

Each record's doc holds its field table between two markers. sync() rewrites what is between them
and leaves the hand-written text around it alone; with check=True it only reports stale files.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .schema import RECORD_SCHEMAS, SCHEMA_DIR

START, END = "<!-- fields:start -->", "<!-- fields:end -->"
DOCS = {
    "RunIntent": "intent.md",
    "ExceptionNotice": "notice.md",
    "RunCloseout": "closeout.md",
}
# Shared types from common.schema.json as Python types. EventKind and EvidenceClass are the
# Literal aliases docs/records/README.md defines.
TYPE_NAMES = {
    "timestamp": "datetime",
    "date": "date",
    "id": "str",
    "role_ref": "str",
    "evidence_class": "EvidenceClass",
    "event_kind": "EventKind",
}


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _resolve(node: dict, doc: str) -> tuple[dict, str, str | None]:
    """Follow $ref to the node it names. Returns the node, the file it lives in and the name of the
    first def on the way that docs/records/README.md names (else the last def)."""
    name = None
    while "$ref" in node:
        file, _, frag = node["$ref"].partition("#")
        doc = file or doc
        target = _load(doc)
        for part in frag.strip("/").split("/"):
            target = target[part]
        if name not in TYPE_NAMES:
            name = frag.rsplit("/", 1)[-1]
        node = target
    return node, doc, name


def _py(value: Any) -> str:
    """A JSON value written as a Python literal."""
    return repr(value) if isinstance(value, (bool, type(None))) else json.dumps(value)


def _type(node: dict, doc: str) -> str:
    """The field's type as a Python type hint, as the JSON would be parsed."""
    target, doc, name = _resolve(node, doc)
    if name in TYPE_NAMES:
        return TYPE_NAMES[name]
    if "const" in target:
        return f"Literal[{_py(target['const'])}]"
    if "enum" in target:
        return "Literal[" + ", ".join(_py(v) for v in target["enum"]) + "]"
    if "oneOf" in target:
        alts = [_type(alt, doc) for alt in target["oneOf"]]
        return " | ".join(sorted(alts, key=lambda a: a == "None"))  # None last, as in X | None
    t = target.get("type")
    if t == "array":
        return f"list[{_type(target.get('items', {}), doc)}]"
    return {"object": "dict", "null": "None", "number": "float", "integer": "int",
            "boolean": "bool", "string": "str"}.get(t, "Any")


def _constraint(node: dict, doc: str) -> str:
    """Limits on a value that its Python type cannot show, in words. Shared types are explained once,
    in docs/records/README.md, not on every field."""
    target, _, name = _resolve(node, doc)
    if name in TYPE_NAMES:
        return ""
    lo, hi = target.get("minimum"), target.get("maximum")
    if lo is not None and hi is not None:
        return f"Range {lo}–{hi}."
    if lo is not None:
        return f"At least {lo}."
    if "pattern" in target:
        return f"Matches `{target['pattern']}`."
    return ""


def _conditions(node: dict) -> dict[str, str]:
    """Fields an if/then/else, or a oneOf of alternatives, makes required, with the condition in words."""
    out: dict[str, str] = {}
    alternatives = [alt["required"][0] for alt in node.get("oneOf", []) if len(alt.get("required", [])) == 1]
    for f in alternatives:
        others = " or ".join(f"`{o}`" for o in alternatives if o != f)
        out[f] = f"yes, unless {others} is given"
    cond = node.get("if", {}).get("properties", {})
    if len(cond) != 1:
        return out
    (field, test), = cond.items()
    value = json.dumps(test.get("const"))
    for f in node.get("then", {}).get("required", []):
        out[f] = f"if `{field}` is `{value}`"
    for f in node.get("else", {}).get("required", []):
        out[f] = f"if `{field}` is not `{value}`"
    return out


def _children(node: dict, doc: str) -> tuple[dict, str] | None:
    """The object whose properties a field's rows continue into, if any."""
    target, doc, _ = _resolve(node, doc)
    if target.get("type") == "array":
        return _children(target.get("items", {}), doc)
    for alt in target.get("oneOf", []):
        found = _children(alt, doc)
        if found:
            return found
    return (target, doc) if "properties" in target else None


def fields(record_type: str) -> list[dict]:
    """Every field of a record, depth first: path, required, tier, type, description."""
    rows: list[dict] = []

    def walk(obj: dict, doc: str, prefix: str, tier: str) -> None:
        required = set(obj.get("required", []))
        when = _conditions(obj)
        for name, node in obj["properties"].items():
            own = node.get("x-tier", tier)
            target, _, _ = _resolve(node, doc)
            path = prefix + name
            rows.append({
                "path": path,
                "required": "yes" if name in required else when.get(name, "no"),
                "tier": own,
                "type": _type(node, doc),
                "description": node.get("description") or target.get("description", "") if "$ref" not in node
                               else node.get("description", ""),
                "constraint": _constraint(node, doc),
            })
            sub = _children(node, doc)
            if sub:
                inner, inner_doc = sub
                array = _resolve(node, doc)[0].get("type") == "array"
                walk(inner, inner_doc, path + ("[]." if array else "."), own)

    walk(_load(RECORD_SCHEMAS[record_type]), RECORD_SCHEMAS[record_type], "", "public")
    return rows


# Records whose fields are shown in groups: (heading, what the group answers, top-level fields).
# Every top-level field must be in exactly one group.
GROUPS = {
    "RunIntent": [
        ("Identity", "Who is filing, and for which run.",
         ["schema_version", "record_type", "run_id", "developer", "filed_at", "signer",
          "amends", "changes", "amendments_allowed"]),
        ("What the run is", "What kind of run it is, why DBYR covers it, when and at what scale.",
         ["run_kind", "trigger_basis", "start_window", "compute_band", "run_scale", "data_classes", "reward_design"]),
        ("Capability forecast", "What the developer expects the model to be able to do, and how that will be tested.",
         ["predicted_capability_band", "forecast_basis", "eval_plan"]),
        ("Safeguards", "Which production safeguards are relaxed or off.",
         ["safeguards_disabled"]),
        ("Environment", "What agents can reach, write to, do and read.",
         ["agent_surface", "agent_capabilities", "readable_sources"]),
        ("Monitoring", "How the run is watched.",
         ["monitoring_instruments"]),
        ("Pause criteria and restarts", "What stops the run, who decides, and how it restarts.",
         ["pause_criteria", "restart_protocol", "containment_plan"]),
        ("Evidence retention", "What evidence is kept, so the filing can be checked later.",
         ["log_retention"]),
        ("People and investigations", "Who holds each role, and what a post-incident investigator may do.",
         ["roles", "investigator_scope_expansion"]),
    ],
    "ExceptionNotice": [
        ("Identity", "Who is filing, and for which run.",
         ["schema_version", "record_type", "notice_id", "run_id", "filed_at", "signer"]),
        ("What was detected", "What happened, and when the developer found out.",
         ["detected_at", "event_ids", "kinds", "summary"]),
        ("What it touches", "Which of the Intent's pause criteria it matched, and who outside was affected.",
         ["criterion_ids", "affected_parties"]),
        ("Response", "What the developer did about it.",
         ["action_taken"]),
    ],
    "RunCloseout": [
        ("Identity and period", "Who is filing, for which run, which days it covers, and its state.",
         ["schema_version", "record_type", "run_id", "filed_at", "signer", "period_start", "period_end",
          "status"]),
        ("Events", "What was detected in the period, or why nothing was.",
         ["security_events", "integrity_events", "attested_absence", "absence_basis", "internal_incidents",
          "notice_ids"]),
        ("Pauses", "What the run did each time a pause criterion fired.",
         ["pause_events"]),
        ("Containment and changes", "Where containment failed, and what changed mid-run.",
         ["containment_exceptions", "config_changes", "surface_resets"]),
        ("Third parties", "Who outside was affected, and whether and when they were told.",
         ["third_party_notifications"]),
        ("Evidence", "How much of the evidence the Intent promised to keep is still held.",
         ["preservation", "logs_preserved_pct", "logs_retention_confirmed"]),
        ("Investigations", "What post-incident investigators asked for, and what they were given.",
         ["scope_requested_vs_granted"]),
        ("Outcome", "Which evaluations ran, what risk remains, and whether the model may be deployed.",
         ["evals_planned_vs_run", "residual_risk", "cleared_for_system_integration"]),
    ],
}


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def _table(rows: list[dict]) -> str:
    lines = ["| Field | Required | Tier | Meaning | Type |", "|---|---|---|---|---|"]
    for r in rows:
        meaning = " ".join(x for x in (r["description"], r["constraint"]) if x)
        lines.append(f"| `{r['path']}` | {r['required']} | {r['tier']} | {_cell(meaning)} | `{_cell(r['type'])}` |")
    return "\n".join(lines)


def _top(path: str) -> str:
    return path.split(".", 1)[0].split("[", 1)[0]


def field_table(record_type: str) -> str:
    rows = fields(record_type)
    groups = GROUPS.get(record_type)
    if groups is None:
        return _table(rows)
    top = list(dict.fromkeys(_top(r["path"]) for r in rows))
    grouped = [f for _, _, names in groups for f in names]
    if sorted(grouped) != sorted(top):
        raise ValueError(f"{record_type}: GROUPS must list each top-level field once; "
                         f"ungrouped {sorted(set(top) - set(grouped))}, unknown {sorted(set(grouped) - set(top))}")
    parts = []
    for n, (heading, about, names) in enumerate(groups, 1):
        order = {name: i for i, name in enumerate(names)}
        mine = sorted((r for r in rows if _top(r["path"]) in order), key=lambda r: order[_top(r["path"])])
        parts.append(f"### {n}. {heading}\n\n{about}\n\n{_table(mine)}")
    return "\n\n".join(parts)


def sync(folder: str | Path, check: bool = False) -> list[Path]:
    """Rewrite the field table in each record doc in `folder`. Returns the docs that were (or, with
    check=True, would be) changed."""
    changed = []
    for record_type, name in DOCS.items():
        path = Path(folder) / name
        text = path.read_text(encoding="utf-8")
        if text.count(START) != 1 or text.count(END) != 1:
            raise ValueError(f"{path}: needs exactly one {START} and one {END}")
        head, rest = text.split(START)
        _, tail = rest.split(END)
        new = f"{head}{START}\n{field_table(record_type)}\n{END}{tail}"
        if new != text:
            changed.append(path)
            if not check:
                path.write_text(new, encoding="utf-8")
    return changed
