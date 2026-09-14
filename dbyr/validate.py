"""Validation of DBYR records: JSON Schema plus the checks a schema cannot express.

Schema validity is necessary but not sufficient. The semantic layer enforces the
properties the standard actually turns on: that every pause criterion names an
authority, that a safeguards-off run does not silently permit inter-agent
communication, that a closeout's pause events reference criteria that were
declared in advance, and that retention meets the floor.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .predicates import PredicateError, evaluate

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"
SCHEMA_FILES = {
    "TrainingRunIntent": "training-run-intent.schema.json",
    "TrainingRunCloseout": "training-run-closeout.schema.json",
    "SystemRuntimeRecord": "system-runtime-record.schema.json",
}
RETENTION_FLOOR_MONTHS = 24


@dataclass
class Report:
    """Outcome of validating one record."""

    record_type: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        lines = [f"{self.record_type}: {'PASS' if self.ok else 'FAIL'}"]
        lines += [f"  ERROR   {e}" for e in self.errors]
        lines += [f"  WARNING {w}" for w in self.warnings]
        return "\n".join(lines)


def load_schema(record_type: str) -> dict[str, Any]:
    try:
        name = SCHEMA_FILES[record_type]
    except KeyError:
        raise ValueError(f"unknown record_type: {record_type}") from None
    return json.loads((SCHEMA_DIR / name).read_text())


def validate(record: dict[str, Any], intent: dict[str, Any] | None = None) -> Report:
    """Validate one record. Pass the matching Intent to cross-check a Closeout."""
    record_type = record.get("record_type", "<missing>")
    report = Report(record_type=record_type)

    if record_type not in SCHEMA_FILES:
        report.errors.append(f"record_type must be one of {sorted(SCHEMA_FILES)}")
        return report

    validator = Draft202012Validator(load_schema(record_type))
    for err in sorted(validator.iter_errors(record), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.path) or "<root>"
        report.errors.append(f"{loc}: {err.message}")

    checker = {
        "TrainingRunIntent": _check_intent,
        "TrainingRunCloseout": _check_closeout,
        "SystemRuntimeRecord": _check_runtime,
    }[record_type]
    checker(record, intent, report)
    return report


def _check_intent(rec: dict[str, Any], _: dict[str, Any] | None, rep: Report) -> None:
    criteria = rec.get("pause_criteria", [])
    ids = [c.get("id") for c in criteria]
    if len(ids) != len(set(ids)):
        rep.errors.append("pause_criteria: ids must be unique")

    for c in criteria:
        cid = c.get("id", "?")
        if not c.get("authority_role"):
            rep.errors.append(f"pause_criteria/{cid}: no role holds unilateral pause authority")
        if c.get("machine_checkable") and "match" not in c:
            rep.errors.append(f"pause_criteria/{cid}: declared machine_checkable but has no match rule")
        if "match" in c:
            try:
                evaluate(c["match"], {})
            except PredicateError as exc:
                rep.errors.append(f"pause_criteria/{cid}: invalid predicate ({exc})")
        if not c.get("machine_checkable"):
            rep.warnings.append(f"pause_criteria/{cid}: not machine-checkable; will not fire in replay")

    functions = {r.get("function") for r in rec.get("roles", [])}
    if "pause_authority" not in functions:
        rep.errors.append("roles: no entry with function=pause_authority")
    declared_roles = {r.get("title") for r in rec.get("roles", [])}
    for c in criteria:
        role = c.get("authority_role")
        if role and role not in declared_roles:
            rep.warnings.append(f"pause_criteria/{c.get('id')}: authority_role '{role}' is not in roles[]")

    cs = rec.get("containment_spec", {})
    safeguards_off = rec.get("safeguards_disabled", {}).get("disabled")
    if safeguards_off and cs.get("inter_agent_comms_permitted"):
        rep.warnings.append(
            "containment_spec: inter-agent communication permitted with safeguards disabled "
            "(the ExploitGym configuration); justify explicitly or set false"
        )
    if safeguards_off and cs.get("egress_policy") == "open":
        rep.errors.append("containment_spec: egress_policy=open is not permissible with safeguards disabled")
    if safeguards_off and "safeguards_off_evaluation" not in rec.get("trigger_basis", []):
        rep.errors.append("trigger_basis: safeguards_disabled=true requires the safeguards_off_evaluation trigger")

    surfaces = cs.get("shared_writable_surfaces", [])
    if not surfaces:
        rep.warnings.append(
            "containment_spec: no shared writable surfaces declared; the 8 May failure was an "
            "undeclared surface, so an empty list is an affirmative claim that none exist"
        )
    surface_ids = [s.get("surface_id") for s in surfaces]
    if len(surface_ids) != len(set(surface_ids)):
        rep.errors.append("containment_spec: surface_ids must be unique")
    if any(s.get("readable_across_runs") for s in surfaces) and not cs.get("inter_agent_comms_permitted"):
        rep.warnings.append(
            "containment_spec: a cross-run readable surface is declared while inter-agent "
            "communication is prohibited; this is the channel that compounded across generations"
        )

    if not rec.get("restart_protocol", {}).get("approval_role"):
        rep.errors.append("restart_protocol: no named approval authority")

    retention = rec.get("log_retention", {})
    months = retention.get("retention_months_after_closeout", 0)
    if months < RETENTION_FLOOR_MONTHS:
        rep.errors.append(f"log_retention: {months} months is below the {RETENTION_FLOOR_MONTHS}-month floor")
    if not all(retention.get(k) for k in ("retain_trajectories", "retain_cot", "retain_tool_calls")):
        rep.warnings.append("log_retention: partial retention; investigators could not reconstruct the run")

    tpa = rec.get("third_party_access_commitment", {})
    if tpa.get("covers_training_time_events") is False:
        rep.warnings.append(
            "third_party_access_commitment: excludes training-time events, the exclusion that "
            "narrowed the July 2026 independent review"
        )
    if tpa.get("model_access") == "none":
        rep.warnings.append("third_party_access_commitment: no model access; reviewers could not query the instigating model")


def _check_closeout(rec: dict[str, Any], intent: dict[str, Any] | None, rep: Report) -> None:
    if rec.get("logs_preserved_pct", 100) < 100 and not rec.get("intent_amendments"):
        rep.warnings.append(
            f"logs_preserved_pct={rec.get('logs_preserved_pct')} with no amendment explaining the loss"
        )
    for pe in rec.get("pause_events", []):
        if pe.get("decision") == "continued_with_override" and not pe.get("override_authority"):
            rep.errors.append(f"pause_events/{pe.get('criterion_id')}: override with no named authority")
        restart = pe.get("restart_approval") or {}
        if pe.get("decision") == "halted" and restart and not restart.get("approved_by_role"):
            rep.errors.append(f"pause_events/{pe.get('criterion_id')}: restart with no approving role")
    for ce in rec.get("containment_exceptions", []):
        if ce.get("kind") == "undeclared_surface" and not ce.get("amendment_filed"):
            rep.errors.append(f"containment_exceptions/{ce.get('date')}: undeclared surface with no Intent amendment")
    for ev in rec.get("security_events", []):
        affected = set(ev.get("third_parties_affected", []))
        notified = set(ev.get("third_parties_notified", []))
        missing = affected - notified
        if missing:
            rep.warnings.append(
                f"security_events/{ev.get('event_id')}: affected but not notified: {sorted(missing)} "
                "(v0.1 has no notification clock; see Future Work)"
            )
    for inv in rec.get("external_investigations", []):
        if inv.get("covers_training_time_events") is False:
            rep.warnings.append(f"external_investigations/{inv.get('investigator')}: training-time events excluded from scope")
        req, grant = inv.get("transcript_weeks_requested"), inv.get("transcript_weeks_granted")
        if req and grant and grant < req:
            rep.warnings.append(
                f"external_investigations/{inv.get('investigator')}: {grant} of {req} transcript weeks granted"
            )

    if intent is None:
        return
    if intent.get("run_id") != rec.get("run_id"):
        rep.errors.append("run_id does not match the supplied Intent")
    declared = {c.get("id") for c in intent.get("pause_criteria", [])}
    for pe in rec.get("pause_events", []):
        if pe.get("criterion_id") not in declared:
            rep.errors.append(f"pause_events: criterion {pe.get('criterion_id')} was never declared in the Intent")
    declared_surfaces = {s.get("surface_id") for s in intent.get("containment_spec", {}).get("shared_writable_surfaces", [])}
    for ce in rec.get("containment_exceptions", []):
        if ce.get("kind") == "undeclared_surface" and ce.get("surface") in declared_surfaces:
            rep.warnings.append(f"containment_exceptions: surface '{ce.get('surface')}' was in fact declared")
    floor = intent.get("log_retention", {}).get("retention_months_after_closeout")
    if floor and not rec.get("logs_retention_confirmed"):
        rep.errors.append("logs_retention_confirmed is false but the Intent committed to retention")


def _check_runtime(rec: dict[str, Any], intent: dict[str, Any] | None, rep: Report) -> None:
    if rec.get("deployment_context") == "internal_production" and rec.get("oversight_mode") == "none":
        rep.warnings.append("internal production deployment with no oversight mode")
    if rec.get("inter_agent_comms_permitted") and rec.get("user_exposure") in ("limited_external", "general"):
        rep.warnings.append("inter-agent communication permitted under external exposure")
    if intent and intent.get("run_id") not in rec.get("base_run_ids", []):
        rep.warnings.append("base_run_ids does not reference the supplied Intent")
