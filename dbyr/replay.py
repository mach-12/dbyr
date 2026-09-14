"""Backtest harness: replay a filed Intent against an incident event stream.

The question the harness answers is the one Table 1 asks. For each decision point
in the record, would some field of the filed Intent have bound, converting a
discretionary choice into a recorded one? Binding is not the same as preventing:
a criterion can fire and a named authority can still override it. What changes is
that the override is attributable.

Circumstantial threads are excluded from scoring by default, matching the paper's
rule that nothing scored depends on the wiki or RubyGems attributions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from .predicates import describe, evaluate

# Event classes that constitute use of a shared writable surface. A surface seen
# here but absent from containment_spec is an undeclared surface: the 8 May failure.
SURFACE_USE = {"undeclared_surface_write", "inter_agent_comms_established", "sandbox_egress"}


@dataclass
class Binding:
    date: str
    event_class: str
    description: str
    field_bound: str
    rule: str
    action: str
    authority: str
    kind: str  # "pause_criterion" | "containment_spec" | "restart_protocol" | "access_commitment"

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ReplayResult:
    run_id: str
    events_scored: int
    events_excluded: int
    bindings: list[Binding] = field(default_factory=list)
    inert_criteria: list[str] = field(default_factory=list)
    decision_points: list[dict[str, Any]] = field(default_factory=list)

    @property
    def first_binding(self) -> Binding | None:
        return self.bindings[0] if self.bindings else None

    @property
    def bound_count(self) -> int:
        return sum(1 for dp in self.decision_points if dp["bound"] == "Yes")

    @property
    def partial_count(self) -> int:
        return sum(1 for dp in self.decision_points if dp["bound"] == "Partial")


def load_events(path: str | Path, first_party_only: bool = True) -> tuple[list[dict], int]:
    """Load a JSONL event stream, returning (scored_events, excluded_count)."""
    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    rows.sort(key=lambda r: (r["date"], r.get("openai_item") or ""))
    if not first_party_only:
        return rows, 0
    kept = [r for r in rows if r.get("first_party")]
    return kept, len(rows) - len(kept)


def _declared_surfaces(intent: dict[str, Any]) -> set[str]:
    spec = intent.get("containment_spec", {})
    return {s.get("surface_id") for s in spec.get("shared_writable_surfaces", [])}


def _authority_for(intent: dict[str, Any], function: str) -> str:
    for role in intent.get("roles", []):
        if role.get("function") == function:
            return role.get("title", "unnamed")
    return "unnamed"


def _bindings_for_event(intent: dict[str, Any], ev: dict[str, Any]) -> list[Binding]:
    out: list[Binding] = []
    spec = intent.get("containment_spec", {})
    declared = _declared_surfaces(intent)

    for crit in intent.get("pause_criteria", []):
        if not crit.get("machine_checkable") or "match" not in crit:
            continue
        if evaluate(crit["match"], ev):
            out.append(Binding(
                date=ev["date"], event_class=ev["event_class"], description=ev["description"],
                field_bound=f"pause_criteria/{crit['id']}", rule=describe(crit["match"]),
                action=crit.get("action", "halt"), authority=crit.get("authority_role", "unnamed"),
                kind="pause_criterion",
            ))

    surface = ev.get("surface")
    if ev["event_class"] in SURFACE_USE and surface and surface not in declared:
        out.append(Binding(
            date=ev["date"], event_class=ev["event_class"], description=ev["description"],
            field_bound="containment_spec/shared_writable_surfaces",
            rule=f"surface '{surface}' in use but not declared",
            action="halt_and_amend", authority=_authority_for(intent, "pause_authority"),
            kind="containment_spec",
        ))

    if ev["event_class"] == "inter_agent_comms_established" and not spec.get("inter_agent_comms_permitted", False):
        out.append(Binding(
            date=ev["date"], event_class=ev["event_class"], description=ev["description"],
            field_bound="containment_spec/inter_agent_comms_permitted",
            rule="inter_agent_comms_permitted = false, violated",
            action="halt_and_notify", authority=_authority_for(intent, "pause_authority"),
            kind="containment_spec",
        ))

    if ev["event_class"] == "new_run_start" and ev.get("inherits_channel"):
        out.append(Binding(
            date=ev["date"], event_class=ev["event_class"], description=ev["description"],
            field_bound="trigger_basis/new Intent required",
            rule="a new run inheriting an open containment exception must file its own Intent citing it",
            action="file_or_halt", authority=_authority_for(intent, "training_owner"),
            kind="containment_spec",
        ))

    if ev["event_class"] == "restart":
        protocol = intent.get("restart_protocol", {})
        if protocol.get("approval_role") and not ev.get("restart_approval_recorded", False):
            out.append(Binding(
                date=ev["date"], event_class=ev["event_class"], description=ev["description"],
                field_bound="restart_protocol",
                rule=(f"resumption requires approval by {protocol['approval_role']} against a stated evidence bar"
                      + (" and an Intent amendment" if protocol.get("intent_amendment_required") else "")),
                action="block_restart_until_recorded", authority=protocol["approval_role"],
                kind="restart_protocol",
            ))

    if ev["event_class"] == "external_review_scoped":
        tpa = intent.get("third_party_access_commitment", {})
        if tpa:
            detail = (f"scope fixed in advance: {tpa.get('scope_summary', 'n/a')}; "
                      f"training-time events covered={tpa.get('covers_training_time_events')}; "
                      f"transcripts={tpa.get('transcript_coverage')}")
            out.append(Binding(
                date=ev["date"], event_class=ev["event_class"], description=ev["description"],
                field_bound="third_party_access_commitment + log_retention",
                rule=detail, action="scope_is_pre_agreed",
                authority=_authority_for(intent, "security_owner"), kind="access_commitment",
            ))
    return out


def _score_decision_point(ev: dict[str, Any], bindings: list[Binding]) -> str:
    """Yes if a field binds and closes the gap; Partial if it binds incompletely."""
    if not bindings:
        return "No"
    affected = set(ev.get("third_parties_affected", []))
    notified = set(ev.get("third_parties_notified", []))
    if affected - notified:
        # v0.1 fixes investigation scope and retention in advance but has no
        # affected-third-party notification clock. Flagged in Future Work.
        return "Partial"
    return "Yes"


def replay(intent: dict[str, Any], events: Iterable[dict[str, Any]], excluded: int = 0) -> ReplayResult:
    events = list(events)
    result = ReplayResult(
        run_id=intent.get("run_id", "<unknown>"),
        events_scored=len(events),
        events_excluded=excluded,
    )
    result.inert_criteria = [
        c["id"] for c in intent.get("pause_criteria", []) if not c.get("machine_checkable")
    ]

    for ev in events:
        bindings = _bindings_for_event(intent, ev)
        result.bindings.extend(bindings)
        if ev.get("decision_point"):
            result.decision_points.append({
                "date": ev["date"],
                "label": ev.get("dp_label", ev["description"]),
                "fields": sorted({b.field_bound for b in bindings}),
                "rules": [b.rule for b in bindings],
                "bound": _score_decision_point(ev, bindings),
            })
    return result


def counterfactual(result: ReplayResult, events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Compare the first binding against the date the developer actually detected."""
    detection = next((e["date"] for e in events if e["event_class"] == "detection"), None)
    first = result.first_binding
    if not (first and detection):
        return {"first_binding": first.date if first else None, "detection": detection}
    d0 = date.fromisoformat(first.date)
    d1 = date.fromisoformat(detection)
    return {
        "first_binding": first.date,
        "first_binding_field": first.field_bound,
        "actual_detection": detection,
        "days_earlier": (d1 - d0).days,
    }


def to_markdown(result: ReplayResult, cf: dict[str, Any]) -> str:
    """Regenerate Table 1 from the replay rather than asserting it by hand."""
    lines = [
        f"### Backtest: {result.run_id}",
        "",
        f"Events scored: {result.events_scored} (first-party). "
        f"Excluded as circumstantial: {result.events_excluded}.",
        "",
        "| Date | Decision point | DBYR field that binds | Bound? |",
        "|---|---|---|---|",
    ]
    for dp in result.decision_points:
        fields = "; ".join(dp["fields"]) or "—"
        lines.append(f"| {dp['date']} | {dp['label']} | {fields} | {dp['bound']} |")
    lines += [
        "",
        f"**{result.bound_count} of {len(result.decision_points)} decision points bind fully"
        f"{f', {result.partial_count} partially' if result.partial_count else ''}.** "
        "Pre-registered success criterion: 3.",
        "",
    ]
    if cf.get("days_earlier") is not None:
        lines.append(
            f"First binding on {cf['first_binding']} via `{cf['first_binding_field']}`, "
            f"**{cf['days_earlier']} days** before the developer's own alert fired on {cf['actual_detection']}."
        )
    if result.inert_criteria:
        lines.append("")
        lines.append(f"Criteria filed but not machine-checkable (never fire in replay): {', '.join(result.inert_criteria)}.")
    return "\n".join(lines)
