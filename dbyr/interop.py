"""Emit existing regimes' artefacts from a DBYR filing.

The claim in Section 4 is that DBYR is a format those regimes can accept rather
than a rival to them. That claim is only worth making if the emitters exist, so
they do: a closeout becomes an SB 53 critical-incident report or an EU Code of
Practice serious-incident notification without re-entry of data, and the coverage
report names the fields that no current instrument carries.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAPPINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "interop" / "mappings.json"


def load_mappings() -> dict[str, Any]:
    return json.loads(MAPPINGS_PATH.read_text())


def coverage_report() -> str:
    """Which DBYR fields an existing regime already carries, and which it does not."""
    m = load_mappings()
    regimes = ["eu_cop", "sb53", "frontier_act", "guidelight"]
    lines = ["| DBYR field | Route | EU CoP | SB 53 | FRONTIER | Guidelight |", "|---|---|---|---|---|---|"]
    gaps = []
    for f in m["fields"]:
        cells = ["yes" if f.get(r) else "—" for r in regimes]
        lines.append(f"| `{f['path']}` | {f['route']} | " + " | ".join(cells) + " |")
        if f.get("gap"):
            gaps.append((f["path"], f["gap"]))
    lines += ["", f"**{len(gaps)} fields have no counterpart in any current instrument:**", ""]
    lines += [f"- `{p}` — {g}" for p, g in gaps]
    r2 = [f for f in m["fields"] if f["route"] == "R2"]
    mapped = [f for f in r2 if any(f.get(r) for r in regimes)]
    lines += ["", f"R2 fields mapping to at least one existing obligation: {len(mapped)}/{len(r2)}."]
    return "\n".join(lines)


def emit_sb53_incident(closeout: dict[str, Any]) -> dict[str, Any]:
    """California SB 53 critical-incident report, derived from a closeout."""
    return {
        "report_type": "SB 53 §22757.12 critical safety incident report",
        "source": {"standard": "DBYR v0.1", "record": "TrainingRunCloseout", "run_id": closeout.get("run_id")},
        "covered_developer": closeout.get("signer", {}).get("org"),
        "period": {"start": closeout.get("period_start"), "end": closeout.get("period_end")},
        "incidents": [
            {
                "date": e.get("date"),
                "description": e.get("summary"),
                "category": e.get("event_class"),
                "loss_of_control_indicator": e.get("event_class") in (
                    "sandbox_egress", "third_party_compromise", "lateral_movement", "root_access"
                ),
                "third_parties_affected": e.get("third_parties_affected", []),
                "detection_latency_days": e.get("detection_latency_days"),
            }
            for e in closeout.get("security_events", [])
        ],
        "framework_deviations": [
            {"date": c.get("date"), "kind": c.get("kind"), "amendment": c.get("amendment_filed")}
            for c in closeout.get("containment_exceptions", [])
        ],
        "overridden_stop_criteria": [
            p for p in closeout.get("pause_events", []) if p.get("decision") != "halted"
        ],
    }


def emit_eu_cop_incident(closeout: dict[str, Any]) -> dict[str, Any]:
    """EU Code of Practice serious-incident notification skeleton."""
    return {
        "report_type": "EU GPAI Code of Practice serious-incident notification",
        "source": {"standard": "DBYR v0.1", "run_id": closeout.get("run_id")},
        "provider": closeout.get("signer", {}).get("org"),
        "incident_summary": [e.get("summary") for e in closeout.get("security_events", [])],
        "serious_incident_types": sorted({e.get("event_class") for e in closeout.get("security_events", [])}),
        "corrective_measures": [
            p.get("restart_approval", {}).get("evidence_cited")
            for p in closeout.get("pause_events", []) if p.get("restart_approval")
        ],
        "security_of_model_weights": closeout.get("boundary_exceptions", []),
        "records_retained": {
            "logs_preserved_pct": closeout.get("logs_preserved_pct"),
            "retention_confirmed": closeout.get("logs_retention_confirmed"),
        },
    }


def emit_frontier_audit_index(intent: dict[str, Any], closeout: dict[str, Any]) -> dict[str, Any]:
    """FRONTIER Act §(c) audit-report index: what the auditor should ask for, on-premises."""
    return {
        "report_type": "FRONTIER Act §(c) audit-report index",
        "run_id": intent.get("run_id"),
        "access_terms": "on-premises, no-copy, unredacted (statutory floor)",
        "pre_agreed_access": intent.get("third_party_access_commitment"),
        "items_for_inspection": [
            {"item": "containment_spec vs observed surfaces", "evidence": "egress logs, registry access logs", "verification_class": "(d)"},
            {"item": "pause criteria exercised", "evidence": "pause_events + retained trajectories", "verification_class": "(d)/(e)"},
            {"item": "restart approvals", "evidence": "restart_approval records + intent amendments", "verification_class": "(e)"},
            {"item": "compute band and run window", "evidence": "network taps, GPU telemetry, power signatures", "verification_class": "(a)"},
            {"item": "evaluations run and results", "evidence": "attested audit outputs (TEE)", "verification_class": "(b)"},
        ],
        "declared_retention_months": intent.get("log_retention", {}).get("retention_months_after_closeout"),
        "logs_preserved_pct": closeout.get("logs_preserved_pct"),
        "scope_requested_vs_granted": closeout.get("external_investigations", []),
    }
