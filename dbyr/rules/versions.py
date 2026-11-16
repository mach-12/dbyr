"""Every version of a run's Intent, and the Closeouts filed against them."""

from __future__ import annotations

from datetime import date, timedelta

from ..findings import Finding
from ..params import CLOSEOUT_EVERY_DAYS, MAX_EVAL_DAYS
from .common import ts


def in_force(versions: list[dict], when: str) -> dict:
    """The version in force at a time: the latest filed at or before it (else the first)."""
    filed = [v for v in versions if ts(v["filed_at"]) <= ts(when)]
    return (filed or versions)[-1]


def version_rules(run_id: str, versions: list[dict], closeouts: list[dict]) -> list[Finding]:
    """Rules that need every version of a run's Intent and every Closeout. [R1 judge item 9; S3-E2]"""
    out: list[Finding] = []
    kind = versions[-1].get("run_kind")
    starts = [date.fromisoformat(v["start_window"]["start"]) for v in versions]
    ends = [v["start_window"].get("end") for v in versions]
    # A5 across amendments: chaining date-only amendments cannot turn an evaluation into a standing filing.
    if kind in ("evaluation", "internal_deployment") and all(ends):
        span = max(date.fromisoformat(e) for e in ends) - min(starts)
        if span > timedelta(days=MAX_EVAL_DAYS):
            out.append(Finding("error", "standing_intent", run_id,
                               f"versions of this Intent together cover {span.days} days; "
                               f"an evaluation may cover at most {MAX_EVAL_DAYS}"))
    return out + cadence(run_id, versions, closeouts, "start_window", "the run", "Intent")


def cadence(owner_id: str, versions: list[dict], closeouts: list[dict], window: str, subject: str,
            record: str) -> list[Finding]:
    """Closeout cadence and coverage are conduct: a late or missing period is recorded, not refused."""
    out: list[Finding] = []
    periods = sorted(closeouts, key=lambda c: c["period_start"])
    for n, c in enumerate(periods):
        ps, pe = date.fromisoformat(c["period_start"]), date.fromisoformat(c["period_end"])
        if (pe - ps).days > CLOSEOUT_EVERY_DAYS:
            out.append(Finding("conduct", "closeout_overdue", f"{owner_id} {c['period_start']}",
                               f"one closeout covers {(pe - ps).days} days; closeouts are due every "
                               f"{CLOSEOUT_EVERY_DAYS} days"))
        if n and ps > date.fromisoformat(periods[n - 1]["period_end"]) + timedelta(days=1):
            out.append(Finding("conduct", "closeout_gap", f"{owner_id} {c['period_start']}",
                               "no closeout covers the days before this period"))
        win = in_force(versions, c["filed_at"])[window]
        if ps < date.fromisoformat(win["start"]) or (win.get("end") and pe > date.fromisoformat(win["end"])):
            out.append(Finding("conduct", "period_outside_window", f"{owner_id} {c['period_start']}",
                               f"{subject} operated outside the window declared in the {record} in force"))
    return out
