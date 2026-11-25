"""Checks on one RunCloseout.

Three groups, run in this order:
  consistency   attested absence, the period, affected parties and notifications, exceptions, scope
  timeliness    detection times and the third-party notification deadline
  completeness  attested absence and its basis, classifications, integrity events, internal incidents,
                preservation per evidence class, mid-run changes and resets
"""

from __future__ import annotations

from datetime import timedelta

from ..findings import Finding
from ..params import NOTIFY_HOURS
from .common import ts


def check_closeout(closeout: dict) -> list[Finding]:
    return consistency(closeout) + timeliness(closeout) + completeness(closeout)


def consistency(closeout: dict) -> list[Finding]:
    out: list[Finding] = []
    events = closeout.get("security_events", [])
    if closeout.get("attested_absence") and events:
        out.append(Finding("error", "absence_contradicted", "/attested_absence",
                           "attested_absence is true but security events are listed"))
    if closeout.get("period_end", "") < closeout.get("period_start", ""):
        out.append(Finding("error", "period_inverted", "/period_end", "period_end precedes period_start"))

    # Every affected external party must be accounted for in third_party_notifications.
    # Integrity events affect third parties too, so both lists count here and below.
    reportable = events + closeout.get("integrity_events", [])
    event_ids = {e["event_id"] for e in reportable}
    notified = {n["party"]: n for n in closeout.get("third_party_notifications", [])}
    for i, e in enumerate(reportable):
        where = f"/security_events/{i}" if i < len(events) else f"/integrity_events/{i - len(events)}"
        for party in e.get("affected_parties", []):
            if party not in notified:
                out.append(Finding("error", "affected_party_unaccounted", f"{where}/affected_parties",
                                   f"{party!r} was affected by {e['event_id']} but has no notification entry"))
    for i, n in enumerate(closeout.get("third_party_notifications", [])):
        for ref in n["affected_by"]:
            if ref not in event_ids:
                out.append(Finding("error", "notification_unknown_event", f"/third_party_notifications/{i}/affected_by",
                                   f"event {ref!r} is not a reported event"))
        if n.get("notified") and n.get("notified_at"):
            first = min((ts(e["at"]) for e in reportable if e["event_id"] in n["affected_by"]), default=None)
            if first and ts(n["notified_at"]) < first:
                out.append(Finding("error", "notified_before_event", f"/third_party_notifications/{i}/notified_at",
                                   "notification predates the event it reports"))

    for i, x in enumerate(closeout.get("containment_exceptions", [])):
        if not x["declared_surface"]:
            out.append(Finding("warning", "undeclared_surface", f"/containment_exceptions/{i}",
                               f"surface {x['surface_id']!r} was not declared in the Intent "
                               "(the expected completeness failure); amend the Intent"))
        if x["status"] == "closed" and "closed_at" not in x:
            out.append(Finding("error", "closed_without_time", f"/containment_exceptions/{i}", "closed exception needs closed_at"))
    for i, s in enumerate(closeout.get("scope_requested_vs_granted", [])):
        req, gr = s["requested"], s["granted"]
        narrowed = gr["start"] > req["start"] or (req.get("end") or "9999") > (gr.get("end") or "9999")
        if narrowed and not s["refusals"]:
            out.append(Finding("error", "silent_scope_narrowing", f"/scope_requested_vs_granted/{i}",
                               "granted scope is narrower than requested but no refusal is logged"))
    return out


def timeliness(closeout: dict) -> list[Finding]:
    out: list[Finding] = []
    events = {e["event_id"]: e for e in closeout["security_events"] + closeout.get("integrity_events", [])}
    for eid, e in events.items():
        if "detected_at" not in e:
            out.append(Finding("error", "detection_time_missing", f"/security_events/{eid}",
                               "each event needs detected_at; it starts the notice and notification clocks"))
        elif ts(e["detected_at"]) < ts(e["at"]):
            out.append(Finding("error", "detected_before_event", f"/security_events/{eid}", "detected_at precedes the event"))

    # Notification deadline. [T10]
    for n, note in enumerate(closeout["third_party_notifications"]):
        detections = [ts(events[i]["detected_at"]) for i in note["affected_by"] if i in events and "detected_at" in events[i]]
        if note.get("notified") and note.get("notified_at") and detections:
            delay = ts(note["notified_at"]) - min(detections)
            if delay > timedelta(hours=NOTIFY_HOURS) and not note.get("delay_reason"):
                out.append(Finding("error", "late_notification", f"/third_party_notifications/{n}",
                                   f"notified {delay.days} days after detection; a delay_reason is required "
                                   f"beyond {NOTIFY_HOURS} hours"))
    return out


def completeness(closeout: dict) -> list[Finding]:
    out: list[Finding] = []

    def E(code: str, where: str, msg: str) -> None:
        out.append(Finding("error", code, where, msg))

    events = closeout["security_events"] + closeout.get("integrity_events", [])
    ids = {e["event_id"] for e in events}

    # Completeness is attested, not implied by an empty list. [R1 S2-E6]
    if "attested_absence" not in closeout:
        E("absence_not_attested", "/attested_absence", "state attested_absence explicitly")
    elif not events and not closeout.get("absence_basis"):
        # An empty list must be explained either way: a basis for attesting absence, or the reason
        # absence cannot be attested (for example, monitoring too weak to support the claim), so that a
        # weakly monitored run can still lodge an honest closeout.
        E("absence_basis_missing", "/absence_basis",
          "no events are listed: state the basis for attesting absence, or why it cannot be attested")
    elif not events and not closeout["attested_absence"]:
        out.append(Finding("warning", "absence_not_supportable", "/attested_absence",
                           "no events are listed and absence is not attested; the stated basis explains why"))
    if closeout.get("attested_absence") and not closeout.get("absence_basis"):
        E("absence_basis_missing", "/absence_basis", "say which monitors support the absence claim")
    # Classification is the filer's choice, so it must be argued. [R1 S3-E3]
    for e in events:
        if not e.get("classification_rationale"):
            E("classification_rationale_missing", f"/events/{e['event_id']}",
              f"say why {e['event_id']} is {e['kind']!r} and not a neighbouring kind")
    if "integrity_events" not in closeout:
        E("field_missing", "/integrity_events", "integrity_events is required (may be empty) [R1 S2-E5, S3-E10]")
    for e in closeout.get("integrity_events", []):
        if "detected_at" not in e:
            E("detection_time_missing", f"/integrity_events/{e['event_id']}", "each event needs detected_at")

    # Every internal incident is mapped to an event or explained. [R1 S2-E5, S3-E10]
    if "internal_incidents" not in closeout:
        E("field_missing", "/internal_incidents", "list every internal incident opened about the run (may be empty)")
    for n, inc in enumerate(closeout.get("internal_incidents", [])):
        refs = inc.get("event_ids", [])
        if not refs and not inc.get("not_an_event_reason"):
            E("incident_unmapped", f"/internal_incidents/{n}", "map the incident to events or state not_an_event_reason")
        for r in refs:
            if r not in ids:
                E("incident_unknown_event", f"/internal_incidents/{n}", f"event {r!r} is not listed")

    # Preservation per class; the headline figure is the weakest class. [R1 S2-E7, S3-E12]
    pres = closeout.get("preservation")
    if not pres:
        E("preservation_missing", "/preservation", "give preservation per evidence class")
    else:
        weakest = min(p["sample_rate"] * p["preserved_pct"] for p in pres)
        if closeout["logs_preserved_pct"] > weakest + 1e-9:
            E("preservation_overstated", "/logs_preserved_pct",
              f"{closeout['logs_preserved_pct']} exceeds the weakest class ({weakest:.2f}); see the field definition")

    # Mid-run changes, and no evidence destroyed while an incident is open. [R1 S2-E8]
    for f in ("config_changes", "surface_resets"):
        if f not in closeout:
            E("field_missing", f"/{f}", f"{f} is required (may be empty)")
    for n, r in enumerate(closeout.get("surface_resets", [])):
        at = ts(r["at"])
        open_inc = [i for i in closeout.get("internal_incidents", [])
                    if ts(i["opened_at"]) <= at and ("closed_at" not in i or at < ts(i["closed_at"]))]
        if open_inc and not r["snapshot_retained"]:
            out.append(Finding("conduct", "evidence_destroyed", f"/surface_resets/{n}",
              f"surface {r['surface_id']!r} reset without a snapshot while incident {open_inc[0]['incident_id']!r} was open"))
    for n, c in enumerate(closeout.get("config_changes", [])):
        if not c["intent_amended"]:
            out.append(Finding("warning", "change_without_amendment", f"/config_changes/{n}",
                               "a configuration change without an Intent amendment; confirm it changes no declared fact"))
    return out
