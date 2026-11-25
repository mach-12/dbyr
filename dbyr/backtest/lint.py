"""Check a case before scoring it: shape, record keys, schema fields and placeholders.

    problems = check_case("cases/lab-x/")       # [] when the case is ready to score

Nothing here scores anything. Each problem is (severity, message):

  error    the case cannot be scored as written (bad shape, an unknown record key)
  warning  it can be scored, but a test is likely wrong: a predicate reads a field the schema
           does not have (it will always fail), or reads a value sources.json marks placeholder
"""

from __future__ import annotations

from pathlib import Path

from ..integrity import schema_hash
from ..schema import load_schema
from .case import Case, CaseError
from .metrics import _category, _label_for, field_in_schema
from .predicates import fields_read, leaves

EVIDENCE = set(load_schema("common.schema.json")["$defs"]["evidence_class"]["enum"])


def check_case(path: str | Path) -> list[tuple[str, str]]:
    try:
        case = Case.load(path)
    except CaseError as exc:
        return [("error", str(exc))]
    out: list[tuple[str, str]] = []
    if case.frozen_hash is None:
        out.append(("warning", "no schema_hash: record the hash `dbyr freeze` prints in decision_points.json before "
                               "writing filings, so a result can show it was scored against the frozen schema"))
    elif not case.schema_matches:
        out.append(("error", f"schema_hash {case.frozen_hash} is not the current schema ({schema_hash()}); "
                             "a result scored now would be void"))
    keys = set(case.records)
    for dp in case.decision_points:
        for test in ("recorded_before", "checkable_after"):
            pred = dp[test]
            unknown = sorted({leaf["record"] for leaf in leaves(pred) if leaf.get("record") not in keys})
            if unknown:
                out.append(("error", f"{dp['id']} {test}: reads {unknown}, not among the filings {sorted(keys)}"))
                continue
            for key, pointer in fields_read(pred):
                rtype = case.records[key]["record_type"]
                if not field_in_schema(rtype, pointer):
                    out.append(("warning", f"{dp['id']} {test}: {key}{pointer} is not a field of {rtype}, "
                                           "so this test can never hold"))
                elif "/*/" not in pointer:
                    label = _label_for(case.sources, case.record_file(key), pointer)
                    if _category(label) == "placeholder":
                        out.append(("warning", f"{dp['id']} {test}: {key}{pointer} is a placeholder in "
                                               "sources.json; predicates must not use placeholder values"))
        bad = sorted(set(dp["checkable_after"].get("evidence", [])) - EVIDENCE)
        if bad:
            out.append(("error", f"{dp['id']} checkable_after: unknown evidence classes {bad}"))
    if not case.sources:
        out.append(("warning", "no sources.json: provenance cannot be reported"))
    if not case.annotations:
        out.append(("warning", "no annotations.json: table cells that need it will say 'not annotated'"))
    return out
