"""The pre-registered scoring: three tests per decision point and the held-out verdict.

For each decision point and each filer variant:

  (a) recorded before   Did a field in a filing made before the event capture the material fact?
  (b) checkable after   Does the Closeout record the event, and was the evidence a V1 reconciliation
                        needs declared retained? "Partial" when the Closeout reports retention below
                        the Intent's floor for behavioural evidence.
  (c) changes decision  Would the filing have required a different action than the one taken?
                        Derived from the developer's awareness at the time and the declared criteria.

A decision point is attributable when (a) holds and (b) is not "No". A case fails if fewer than
half its decision points are attributable. This module's logic is the pre-registered scorer's,
unchanged; the result has the same shape as the committed results.json files.
"""

from __future__ import annotations

import math

from ..findings import errors
from ..integrity import schema_hash
from ..protocol import check_set
from ..rules import schema_findings, validate_record
from .case import Case
from .predicates import first_record, holds

BEHAVIOURAL = {"trajectories", "inter_agent_messages", "chain_of_thought", "tool_calls"}
UNSEEN = "criterion cannot fire on an unseen event"


def score_checkable(dp: dict, records: dict, closes: dict) -> str:
    pred = dp["checkable_after"]
    if not holds(pred, records):
        return "No"
    closeout = records[first_record(pred)]
    intent = records[closes[first_record(pred)]]
    retained = set(intent["log_retention"]["retained"])
    evidence = set(pred.get("evidence", []))
    if not evidence <= retained:
        return "No"
    floor = intent["log_retention"].get("minimum_preserved_pct")
    if floor is not None and closeout["logs_preserved_pct"] < floor and evidence & BEHAVIOURAL:
        return "Partial"
    return "Yes"


def score_decision(dp: dict, records: dict, closes: dict) -> tuple[str, str]:
    rule = dp["decision_rule"]
    if rule["rule"] == "record_obligation":
        return "Unknown", "obligation is to record, not to act"
    # A case with several runs names the Closeout the rule is scored against; default to the first.
    closeout_key = rule.get("closeout", next(iter(closes)))
    intent = records[closes[closeout_key]]
    closeout = records[closeout_key]
    criteria = [c for c in intent["pause_criteria"] if rule["event_kind"] in c["matches"]]
    if not criteria:
        return "No", "no declared criterion matches"
    aware = dp["developer_aware"]
    if aware == "no":
        return "No", UNSEEN
    if aware == "unclear":
        return "Unknown", "awareness at the time not established"
    kinds = {e["event_id"]: e["kind"] for e in closeout["security_events"]}
    ids = {c["criterion_id"]: c for c in criteria}
    for p in closeout["pause_events"]:
        cited_kind = any(kinds.get(e) == rule["event_kind"] for e in p.get("triggering_event_ids", []))
        if (p["criterion_id"] in ids or cited_kind) and p["action_taken"] == ids.get(p["criterion_id"], criteria[0])["required_action"]:
            return "No", "compliant: required action was taken and restart approved"
    return "Yes", "declared criterion required an action that was not taken"


def attributable(row: dict) -> bool:
    return row["recorded_before"] == "Yes" and row["checkable_after"] != "No"


def score(case: Case) -> dict:
    """Score every decision point under every filer variant."""
    base = case.records
    closes = case.closes

    # The reconstructed filings must be well formed (valid against the schema), or the backtest
    # scores a broken filing. The protocol's own checks are reported separately: a reconstruction
    # of a real incident may be rejected at intake, and that rejection is itself a result.
    integrity = {k: [str(f) for f in errors(schema_findings(rec))] for k, rec in base.items()}
    protocol_errors: dict[str, list[str]] = {}
    for at, f in check_set(base):
        if f.severity == "error":
            protocol_errors[at] = sorted(set(protocol_errors.get(at, [])) | {f.code})

    variants = {}
    for name in case.variants:
        recs = case.variant_records(name)
        rows = []
        for dp in case.decision_points:
            c, reason = score_decision(dp, recs, closes)
            rows.append({
                "id": dp["id"],
                "recorded_before": "Yes" if holds(dp["recorded_before"], recs) else "No",
                "checkable_after": score_checkable(dp, recs, closes),
                "changes_decision": c,
                "reason": reason,
            })
        n = len(rows)
        both = sum(attributable(r) for r in rows)
        variants[name] = {
            "rows": rows,
            "recorded_before": sum(r["recorded_before"] == "Yes" for r in rows),
            "checkable_after": sum(r["checkable_after"] != "No" for r in rows),
            "checkable_partial": sum(r["checkable_after"] == "Partial" for r in rows),
            "changes_decision_yes": sum(r["changes_decision"] == "Yes" for r in rows),
            "changes_decision_unknown": sum(r["changes_decision"] == "Unknown" for r in rows),
            "attributable": both,
            "n": n,
            "passes_heldout_criterion": both >= math.ceil(n / 2),
            "intake_errors": {k: sorted({f.code for f in errors(validate_record(r))})
                              for k, r in recs.items() if r["record_type"] == "RunIntent"},
        }
    return {
        "case": case.name,
        "is_derivation_case": case.spec["is_derivation_case"],
        "schema_hash": schema_hash(),
        "filings_well_formed": all(not v for v in integrity.values()),
        "integrity": integrity,
        "protocol_errors": protocol_errors,
        "decision_points": case.decision_points,
        "variants": variants,
    }


def needed_to_pass(n: int) -> int:
    return math.ceil(n / 2)
