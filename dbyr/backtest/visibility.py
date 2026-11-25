"""The two questions the backtest answers about one case.

    dp_coverage      of the decisions that shaped the incident, how many could an outsider
                     have traced to a prior record and then checked?
    visibility_gap   for one decision point, how much earlier would a party outside the
                     developer have held the material fact?

The gap measures visibility, not the length of an incident. A filing in a registry stops
nothing by itself, so it is never "days saved".

Both read the scored result; neither changes it. `coverage` is the attributable count the
pre-registered scorer produces, expressed as a share. The gap reads `outside_record` on each
decision point, which the scorer never sees.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from ..params import INTAKE_DAYS, NOTICE_HOURS
from .case import Case
from .predicates import first_record, holds
from .scoring import attributable, score

THIRD_PARTY = "third_party_compromise"


class VisibilityError(Exception):
    pass


def _day(value: str) -> date:
    return date.fromisoformat(value[:10])


def dp_coverage(case: Case, filer: str | None = None) -> dict:
    """How many decision points the filings would have made attributable."""
    result = score(case)
    name = filer or case.primary_variant
    if name not in result["variants"]:
        raise VisibilityError(f"no filer {name!r}; have {sorted(result['variants'])}")
    rows = result["variants"][name]["rows"]
    found = sum(attributable(row) for row in rows)
    total = len(rows)
    return {"total_dp": total, "found_dp": found,
            "coverage": round(found / total, 4) if total else 0.0,
            "filer_type": name, "case": case.name}


# ---------------------------------------------------------------- the DBYR date

def _detection(dp: dict, records: dict) -> tuple[date, dict, str]:
    rule = dp["decision_rule"]
    kind, key = rule.get("event_kind"), rule.get("closeout")
    if not kind or key not in records:
        raise VisibilityError(f"{dp['id']}: carried by a notice, but the decision point names no event "
                              f"kind and closeout to take the detection date from")
    dated = [(_day(e["detected_at"]), e) for e in records[key].get("security_events", [])
             if e["kind"] == kind and e.get("detected_at")]
    if not dated:
        raise VisibilityError(f"{dp['id']}: no {kind} event with a detected_at in {key}")
    when, event = min(dated, key=lambda pair: pair[0])
    return when, event, key


def _dbyr_date(dp: dict, case: Case, records: dict, lag: int | None,
               detected: date | None = None) -> tuple[date | None, str]:
    """The date the carrying filing would have been due. Always the deadline, never the
    earliest date the filer could have managed."""
    record = dp.get("outside_record") or {}
    carrier = record.get("carried_by")
    if not carrier:
        raise VisibilityError(f"{dp['id']}: no outside_record.carried_by, so there is nothing to measure")

    if carrier == "none":
        return None, "no filing was due"

    if carrier == "intent":
        if not holds(dp["recorded_before"], records):
            raise VisibilityError(
                f"{dp['id']}: carried_by is 'intent', but the fact is not declared before the run for this "
                f"filer, so no Intent carries it")
        key = first_record(dp["recorded_before"])
        start = _day(records[key]["start_window"]["start"])
        return start - timedelta(days=INTAKE_DAYS), f"{key}, due {INTAKE_DAYS} days before the run starts"

    if carrier == "notice":
        when, event, key = _detection(dp, records)
        when = detected or when
        declared = {m for c in records[case.closes[key]]["pause_criteria"] for m in c["matches"]}
        if event["kind"] not in declared and event["kind"] != THIRD_PARTY:
            raise VisibilityError(f"{dp['id']}: {event['kind']} matches no declared criterion and is not a "
                                  f"third-party compromise, so no notice was due")
        return when + timedelta(hours=NOTICE_HOURS), \
            f"{event['event_id']} detected {when}, notice due within {NOTICE_HOURS}h"

    if carrier == "closeout":
        if lag is None:
            raise VisibilityError(f"{dp['id']}: carried by a closeout, so closeout_lag is required; the filing "
                                  f"lag is not set by the protocol and must be stated")
        key = first_record(dp["checkable_after"])
        end = _day(records[key]["period_end"])
        return end + timedelta(days=lag), f"{key}, period ends {end} plus a {lag}-day filing lag"

    raise VisibilityError(f"{dp['id']}: carried_by {carrier!r} is not one of intent, notice, closeout, none")


def visibility_gap(case: Case, dp_num: str, filer: str, lag: int | None = None) -> dict:
    """How much earlier an outsider would have held one decision point's material fact.

    found_early_by is None where the fact reached the outside before any filing was due: the
    protocol added no visibility there, and a negative figure would read as if it had.
    """
    points = {dp["id"]: dp for dp in case.decision_points}
    key = dp_num if dp_num in points else f"DP{dp_num}"
    if key not in points:
        raise VisibilityError(f"no decision point {dp_num!r}; have {sorted(points)}")
    if filer not in case.variants:
        raise VisibilityError(f"no filer {filer!r}; have {sorted(case.variants)}")
    dp = points[key]
    record = dp.get("outside_record") or {}
    if "first_reached_outside" not in record:
        raise VisibilityError(f"{key}: outside_record has no first_reached_outside, so there is no actual date")

    records = case.variant_records(filer)
    actual = _day(record["first_reached_outside"])
    when, basis = _dbyr_date(dp, case, records, lag)
    days = 0 if when is None else (actual - when).days

    out = {"actual_date": actual.isoformat(),
           "dbyr_date": when.isoformat() if when else None,
           "found_early_by": None if days < 0 else days,
           "decision_point": key, "filer_type": filer,
           "carried_by": record.get("carried_by"), "basis": basis}

    contested = record.get("contested_detection")
    if contested and record.get("carried_by") == "notice":
        ends = []
        for edge in ("earliest", "latest"):
            try:
                edge_date, _ = _dbyr_date(dp, case, records, lag, detected=_day(contested[edge]))
                ends.append((actual - edge_date).days)
            except VisibilityError:
                pass
        if len(ends) == 2:
            low, high = sorted(ends)
            out["found_early_by"] = None if high < 0 else low
            out["found_early_by_range"] = [low, high]
            out["note"] = "Detection date is contested; the gap is a range, not a point estimate."
    if record.get("bound"):
        out["bound"] = record["bound"]
        out.setdefault("note", f"A {record['bound']} bound, not an estimate.")
    if record.get("carried_by") == "none":
        out["note"] = record.get("note", "No filing was due, so the protocol added no visibility here.")
    return out
