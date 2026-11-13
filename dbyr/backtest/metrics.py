"""Metrics over a scored case, for the results tables.

Two kinds of metric, kept apart in every output:

  registered   computed by the pre-registered scorer (scoring.py): the three tests, attributable,
               the verdict and intake errors.
  new          added after scoring, for secondary analysis. Each reads only the case's own files:
               the decision points, the filings, sources.json and annotations.json. A metric whose
               input a case does not have is reported as unavailable rather than guessed.

Nothing here changes a registered number.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..protocol import check_set
from ..rules.common import ts
from ..schema import deref, root
from .case import DECISION_KINDS, Case
from .predicates import fields_read, holds
from .scoring import UNSEEN, attributable, needed_to_pass

# Why a decision point is not attributable. Codes are stable; labels are what tables print.
ESCAPE_LABELS = {
    "no_field": "the form has no field for it",
    "not_filed": "no record was filed for it",
    "filer_unaware": "the filer did not know it",
    "not_declared": "the filing does not state it",
    "evidence_not_kept": "the evidence to check it was not kept",
    "not_in_report": "the report afterwards does not show it",
    "check_flaw": "our scoring check missed it",
}
OUTCOMES = ("attributable", "uncheckable", "unrecorded")
KIND_LABELS = {
    "setup": "Setting up the run",
    "deploy": "Deploying the system",
    "respond": "Responding during the run",
    "tell": "Telling those affected",
    "investigate": "Investigating afterwards",
}
PROVENANCE = ("first-party", "required", "forced-choice", "hindsight", "placeholder", "unknown")


# ------------------------------------------------------------------ schema fields

def field_in_schema(record_type: str, pointer: str) -> bool:
    """Whether the schema for a record type has a field at this pointer ('*' = any list item)."""
    try:
        node, resolver = root(record_type)
    except KeyError:
        return False
    for part in [p for p in pointer.split("/") if p]:
        candidates = [deref(node, resolver)]
        expanded = []
        while candidates:
            n, r = candidates.pop()
            expanded.append((n, r))
            for combo in ("allOf", "anyOf", "oneOf"):
                candidates += [deref(sub, r) for sub in n.get(combo, [])]
        found = None
        for n, r in expanded:
            if part == "*" or part.isdigit():
                if "items" in n:
                    found = (n["items"], r)
                    break
            elif part in n.get("properties", {}):
                found = (n["properties"][part], r)
                break
        if found is None:
            return False
        node, resolver = found
    return True


def _missing_fields(case: Case, pred: dict) -> list[str]:
    out = []
    for key, pointer in fields_read(pred):
        rtype = case.records[key]["record_type"]
        if not field_in_schema(rtype, pointer):
            out.append(f"{key}{pointer}")
    return out


# ------------------------------------------------------------------ provenance

def _label_for(sources: dict, file: str, pointer: str) -> str | None:
    """The sources.json label that best covers a pointer: exact match, else the longest prefix."""
    entries = sources.get(file)
    if not isinstance(entries, dict):
        return None
    best = None
    for key, label in entries.items():
        base = key.split(" ")[0]  # keys such as '/pause_criteria (C-tamper, ...)' annotate a pointer
        if pointer == base or pointer.startswith(base.rstrip("/") + "/") or base.startswith(pointer + "/"):
            if best is None or len(base) > len(best[0]):
                best = (base, label)
    return best[1] if best else None


def _category(label: str | None) -> str:
    if not label:
        return "unknown"
    head = label.split(":")[0].strip().lower()
    if head.startswith("first-party"):
        return "first-party"
    if head.startswith("forced-choice"):
        return "forced-choice"
    if head.startswith("placeholder"):
        return "placeholder"
    if "required" in head:
        return "required"
    return "unknown"


def provenance_of(case: Case, dp: dict) -> str:
    """What the recorded-before test of a decision point rests on. annotations.provenance overrides.
    With several fields, the weakest wins (placeholder < hindsight < forced-choice < required < first-party)."""
    override = case.annotations.get("provenance", {}).get(dp["id"])
    if override:
        return override
    rank = ["placeholder", "unknown", "hindsight", "forced-choice", "required", "first-party"]
    cats = [_category(_label_for(case.sources, case.record_file(k), p))
            for k, p in fields_read(dp["recorded_before"]) if "/*/" not in p]
    return min(cats, key=rank.index) if cats else "unknown"


# ------------------------------------------------------------------ timing

def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    t = ts(value if "T" in value else value + "T00:00:00Z")
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _hours(a: datetime, b: datetime) -> float:
    return round((b - a).total_seconds() / 3600, 1)


def _span(values: list[float]) -> dict | None:
    return {"min": min(values), "max": max(values), "count": len(values)} if values else None


def timeliness(case: Case) -> dict:
    events, notices, notes = {}, [], []
    for rec in case.records.values():
        if rec["record_type"] == "RunCloseout":
            for e in rec.get("security_events", []) + rec.get("integrity_events", []):
                events[e["event_id"]] = e
            notes += rec.get("third_party_notifications", [])
        elif rec["record_type"] == "ExceptionNotice":
            notices.append(rec)
    detect = [_hours(_when(e["at"]), _when(e["detected_at"]))
              for e in events.values() if e.get("at") and e.get("detected_at")]
    notice = [_hours(_when(n["detected_at"]), _when(n["filed_at"])) for n in notices if n.get("detected_at")]
    notify = []
    for n in notes:
        detected = [_when(events[i]["detected_at"]) for i in n.get("affected_by", [])
                    if i in events and events[i].get("detected_at")]
        if n.get("notified_at") and detected:
            notify.append(_hours(min(detected), _when(n["notified_at"])))
    first_detect = min((_when(e["detected_at"]) for e in events.values() if e.get("detected_at")), default=None)
    first_notice = min((_when(n["filed_at"]) for n in notices), default=None)
    outside = [(_when(x["date"]), x) for x in case.annotations.get("first_outside_account", [])]
    first_outside = min(outside, key=lambda t: t[0]) if outside else None
    return {
        "detect_hours": _span(detect),
        "notice_hours": _span(notice),
        "notify_hours": _span(notify),
        "outside_today_hours": _hours(first_detect, first_outside[0]) if first_detect and first_outside else None,
        "outside_today_what": first_outside[1]["what"] if first_outside else None,
        "outside_dbyr_hours": _hours(first_detect, first_notice) if first_detect and first_notice else None,
    }


def affected_parties(case: Case) -> dict:
    affected, told, dated = set(), set(), set()
    for rec in case.records.values():
        if rec["record_type"] != "RunCloseout":
            continue
        for e in rec.get("security_events", []) + rec.get("integrity_events", []):
            affected |= set(e.get("affected_parties", []))
        for n in rec.get("third_party_notifications", []):
            told.add(n["party"])
            if n.get("notified_at") or n.get("delay_reason") or n.get("not_notified_reason"):
                dated.add(n["party"])
    parties = affected | told
    return {"parties": len(parties), "with_record": len(parties & told), "with_date_or_reason": len(parties & dated),
            "without_record": sorted(parties - told)}


def investigation(case: Case) -> dict | None:
    inv = case.annotations.get("investigation")
    if not inv:
        return None
    (a0, a1), (b0, b1) = ([_when(x) for x in inv["incident_window"]], [_when(x) for x in inv["review_window"]])
    days = lambda s, e: (e - s).days + 1
    overlap = max(0, days(max(a0, b0), min(a1, b1))) if min(a1, b1) >= max(a0, b0) else 0
    return {"incident_days": days(a0, a1), "review_days_inside": overlap,
            "share": round(overlap / days(a0, a1), 3), "note": inv.get("note", "")}


def deployment(case: Case) -> dict | None:
    """The hand-off from runs to deployed systems, from the protocol's deployment checks. None when the
    case has no SystemRuntimeRecord."""
    systems = [r for r in case.records.values() if r["record_type"] == "SystemRuntimeRecord"]
    if not systems:
        return None
    found = [f for at, f in check_set(case.records) if at == "deployment"]
    count = lambda code: sum(f.code == code for f in found)  # noqa: E731
    return {"systems": len(systems), "base_runs": sum(len(s["base_run_ids"]) for s in systems),
            "unknown_runs": count("base_run_unknown"), "uncleared": count("deployed_uncleared"),
            "open_incidents": count("deployed_over_open_incident"), "untested_tools": count("untested_tools")}


# ------------------------------------------------------------------ per case


# ------------------------------------------------------------------ the two design tables

def design_table_1(case: Case, scored: dict) -> dict:
    """Attributable decision points, per filer, for section 6.

    Baselines are listed but not scored: this repository holds no baseline mapping, and an
    empty row says so where a missing row would not.
    """
    filers = {}
    for name, variant in scored["variants"].items():
        n, found = variant["n"], variant["attributable"]
        filers[name] = {"attributable": found, "n": n,
                        "pct": round(100 * found / n) if n else 0,
                        "changed": variant["changes_decision_yes"]}
    return {"filers": filers, "n": next(iter(scored["variants"].values()))["n"],
            "in_sample": case.is_derivation_case}


def design_table_2(case: Case, lag: int | None) -> list[dict]:
    """Lead time of the outside record, one entry per decision point, for section 7.

    The full per-decision-point list section 7 asks for in an appendix. Entries the record
    cannot support carry the reason instead of a number.
    """
    from .visibility import VisibilityError, visibility_gap
    filer, out = case.primary_variant, []
    for dp in case.decision_points:
        entry = {"id": dp["id"], "decision": dp["decision"],
                 "carried_by": (dp.get("outside_record") or {}).get("carried_by", "")}
        try:
            gap = visibility_gap(case, dp["id"], filer, lag)
            entry.update(actual=gap["actual_date"], dbyr=gap["dbyr_date"], lead=gap["found_early_by"],
                         lead_range=gap.get("found_early_by_range"), bound=gap.get("bound"),
                         note=gap.get("note"))
        except VisibilityError as exc:
            entry.update(actual=None, dbyr=None, lead=None, lead_range=None, bound=None,
                         note=str(exc).split(": ", 1)[-1])
        out.append(entry)
    return out


def compute(case: Case, scored: dict) -> dict:
    """Every metric for one scored case, for its primary variant unless stated."""
    primary = case.primary_variant
    rows = {r["id"]: r for r in scored["variants"][primary]["rows"]}
    others = {name: {r["id"]: r for r in v["rows"]} for name, v in scored["variants"].items() if name != primary}
    recs = case.variant_records(primary)
    kinds = case.annotations.get("decision_kinds", {})
    overrides = case.annotations.get("escape_reasons", {})

    filed_deployment = any(r["record_type"] == "SystemRuntimeRecord" for r in case.records.values())
    per_dp = []
    for dp in case.decision_points:
        row = rows[dp["id"]]
        if attributable(row):
            outcome, escape = "attributable", None
        elif row["recorded_before"] == "No":
            outcome = "unrecorded"
            if kinds.get(dp["id"]) == "deploy" and not filed_deployment:
                escape = "not_filed"
            elif _missing_fields(case, dp["recorded_before"]):
                escape = "no_field"
            elif any(o[dp["id"]]["recorded_before"] == "Yes" for o in others.values()):
                escape = "filer_unaware"
            else:
                escape = "not_declared"
        else:
            outcome = "uncheckable"
            escape = "evidence_not_kept" if holds(dp["checkable_after"], recs) else "not_in_report"
        if dp["id"] in overrides and outcome != "attributable":
            escape = overrides[dp["id"]]
        per_dp.append({
            "id": dp["id"], "decision": dp["decision"], "date": dp.get("date", ""),
            "kind": kinds.get(dp["id"]), "aware": dp["developer_aware"],
            "recorded_before": row["recorded_before"], "checkable_after": row["checkable_after"],
            "changes_decision": row["changes_decision"], "reason": row["reason"],
            "outcome": outcome, "escape": escape, "unseen": row["reason"] == UNSEEN,
            "provenance": provenance_of(case, dp) if outcome == "attributable" else None,
        })

    def tally(items):
        return {"n": len(items), "attributable": sum(x["outcome"] == "attributable" for x in items)}

    awareness = {a: tally([x for x in per_dp if x["aware"] == a]) for a in ("yes", "no", "unclear")}
    escapes = {}
    for x in per_dp:
        if x["escape"]:
            escapes[x["escape"]] = escapes.get(x["escape"], 0) + 1
    by_kind = ({k: tally([x for x in per_dp if x["kind"] == k]) for k in DECISION_KINDS}
               if kinds and all(x["kind"] for x in per_dp) else None)
    prov = {}
    for x in per_dp:
        if x["provenance"]:
            prov[x["provenance"]] = prov.get(x["provenance"], 0) + 1

    registered = {}
    for name, v in scored["variants"].items():
        registered[name] = {"n": v["n"], "attributable": v["attributable"], "needed": needed_to_pass(v["n"]),
                            "passes": v["passes_heldout_criterion"], "recorded_before": v["recorded_before"],
                            "checkable_after": v["checkable_after"], "changes_yes": v["changes_decision_yes"],
                            "intake_errors": v["intake_errors"]}
    return {
        "case": case.name, "label": case.label, "title": case.title,
        "is_derivation_case": case.is_derivation_case, "primary_variant": primary,
        "table1": design_table_1(case, scored),
        "table2": design_table_2(case, case.spec.get("closeout_filing_lag_days")),
        "closeout_lag": case.spec.get("closeout_filing_lag_days"),
        "void": case.schema_matches is False, "frozen_schema_hash": case.frozen_hash,
        "registered": registered,
        "decision_points": per_dp,
        "outcomes": {o: sum(x["outcome"] == o for x in per_dp) for o in OUTCOMES},
        "awareness": awareness,
        "unseen": sum(x["unseen"] for x in per_dp),
        "changed": sum(x["changes_decision"] == "Yes" for x in per_dp),
        "escapes": escapes,
        "by_kind": by_kind,
        "provenance": prov or None,
        "first_party_only": prov.get("first-party", 0) if prov else None,
        "timeliness": timeliness(case),
        "affected_parties": affected_parties(case),
        "investigation": investigation(case),
        "deployment": deployment(case),
        "today": case.annotations.get("today", {}),
        "available": {
            "decision_kinds": by_kind is not None,
            "sources": bool(case.sources),
            "outside_account": bool(case.annotations.get("first_outside_account")),
            "investigation": "investigation" in case.annotations,
            "deployment": filed_deployment,
        },
    }
