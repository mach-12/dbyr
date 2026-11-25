"""A Closeout checked against the Intent it closes, or a deployed system's Closeout against its
its Intent: the criteria, roles, restart protocol and retention it declared.

This is the V0 half of a V1 reconciliation: it checks the filings agree with each
other; a V1 auditor then checks them against retained logs.
"""

from __future__ import annotations

from ..findings import Finding
from ..params import CORE_KINDS_T4
from .common import effective_monitors, observable


def reconcile(intent: dict, closeout: dict) -> list[Finding]:
    """Check a Closeout against the Intent it closes. This is the V0 half of a V1 reconciliation:
    it checks the filings agree with each other; a V1 auditor then checks them against retained logs."""
    out: list[Finding] = []
    if intent.get("run_id") != closeout.get("run_id"):
        return [Finding("error", "run_mismatch", "/run_id", "closeout does not close this intent")]

    role_ids = {r["role_id"] for r in intent["roles"]}
    criteria = {c["criterion_id"]: c for c in intent["pause_criteria"]}
    events = {e["event_id"]: e for e in closeout["security_events"]}
    surfaces = {s["surface_id"] for s in intent.get("agent_surface", {}).get("writable_surfaces", [])}

    # Did any event match a declared criterion without a pause event being recorded?
    triggered = {eid for p in closeout["pause_events"] for eid in p.get("triggering_event_ids", [])}
    for eid, e in events.items():
        matching = [c for c in criteria.values() if e["kind"] in c["matches"]]
        if matching and eid not in triggered:
            out.append(Finding("conduct", "criterion_matched_no_pause_event", f"/security_events/{eid}",
                               f"event kind {e['kind']!r} matches criteria "
                               f"{[c['criterion_id'] for c in matching]} but no pause event cites it"))
        for cls in e["evidence"]:
            if cls not in intent["log_retention"]["retained"]:
                out.append(Finding("warning", "evidence_not_retained", f"/security_events/{eid}/evidence",
                                   f"{cls!r} is cited as evidence but was not declared retained"))

    for i, p in enumerate(closeout["pause_events"]):
        c = criteria.get(p["criterion_id"])
        where = f"/pause_events/{i}"
        if c is None:
            out.append(Finding("error", "unknown_criterion", where, f"{p['criterion_id']!r} is not in the Intent"))
            continue
        if p["triggered_by_role"] not in role_ids:
            out.append(Finding("error", "unknown_role", where, f"{p['triggered_by_role']!r} not declared"))
        if p["action_taken"] != c["required_action"]:
            out.append(Finding("warning", "action_differs", where,
                               f"declared action {c['required_action']!r}, recorded {p['action_taken']!r}"))
        r = p.get("restart")
        if r:
            if r["approved_by_role"] != intent["restart_protocol"]["approver_role"]:
                out.append(Finding("conduct", "restart_wrong_approver", where,
                                   f"restart approved by {r['approved_by_role']!r}, protocol names "
                                   f"{intent['restart_protocol']['approver_role']!r}"))
            if intent["restart_protocol"]["intent_amendment_required"] and not r.get("intent_amended"):
                out.append(Finding("conduct", "restart_without_amendment", where,
                                   "restart protocol requires an Intent amendment"))

    for i, x in enumerate(closeout["containment_exceptions"]):
        if x["declared_surface"] != (x["surface_id"] in surfaces):
            out.append(Finding("error", "declared_flag_wrong", f"/containment_exceptions/{i}/declared_surface",
                               "declared_surface does not match the Intent's writable_surfaces"))

    floor = intent["log_retention"].get("minimum_preserved_pct")
    if floor is not None and closeout["logs_preserved_pct"] < floor:
        out.append(Finding("conduct", "retention_below_floor", "/logs_preserved_pct",
                           f"{closeout['logs_preserved_pct']}% preserved, Intent declared at least {floor}%"))
    return out + monitoring_support(intent, closeout) + preservation(intent, closeout)


def monitoring_support(intent: dict, closeout: dict) -> list[Finding]:
    out: list[Finding] = []
    monitors = effective_monitors(intent)
    # Attested absence is only as strong as the monitoring behind it. [T19]
    # Applies whatever the trigger basis, not only under T4. [R1 S2-E6]
    if closeout.get("attested_absence"):
        blind = [k for k in CORE_KINDS_T4 if not observable(k, monitors)]
        if blind:
            out.append(Finding("error", "absence_unsupported", "/attested_absence",
                               f"absence of events is attested, but no declared monitor could observe {blind}"))
    return out


def preservation(intent: dict, closeout: dict) -> list[Finding]:
    out: list[Finding] = []
    if closeout.get("preservation"):
        covered = {p["evidence_class"] for p in closeout["preservation"]}
        missing = [c for c in intent["log_retention"]["retained"] if c not in covered]
        if missing:
            out.append(Finding("error", "preservation_incomplete", "/preservation", f"no preservation entry for {missing}"))
    if (closeout["status"] == "rolling" and intent["record_type"] == "RunIntent"
            and intent.get("run_kind") not in ("training", "training_with_evaluation")):
        out.append(Finding("error", "rolling_not_training", "/status", "only training runs may be rolling [R1 S3-E2]"))
    # (retention below the declared floor is a conduct finding in validate.reconcile, not a lodging error)
    return out
