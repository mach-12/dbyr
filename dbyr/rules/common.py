"""Helpers shared by the rules: timestamps, durations, surfaces and monitor coverage, and the checks an
an Intent declares: monitors, pause criteria, retention and restarts."""

from __future__ import annotations

from datetime import datetime

from ..findings import Finding
from ..params import MIN_SAMPLE, OBSERVERS, RETENTION_FLOOR_MONTHS


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def months(duration: str) -> float:
    """ISO-8601 duration (PnD, PnM, PnY) or 'indefinite' -> months."""
    if duration == "indefinite":
        return float("inf")
    n, unit = int(duration[1:-1]), duration[-1]
    return {"D": n / 30.4, "M": n, "Y": 12 * n}[unit]


def surfaces(intent: dict) -> dict[str, dict]:
    return {s["surface_id"]: s for s in intent["agent_surface"]["writable_surfaces"]}


def shared_persistent(surface: dict) -> bool:
    return surface["persistence"] in ("cross_run", "permanent") and surface["tenancy"] != "run_only"


def shared_agent_surfaces(topo: dict) -> list[dict]:
    return [s for s in topo["writable_surfaces"]
            if s.get("isolation") == "shared" or s["tenancy"] in ("shared_agents", "shared_runs", "external")]


def effective_monitors(intent: dict) -> set[str]:
    """Monitor kinds that count as observers. A sampled monitor below MIN_SAMPLE, an on-alert
    monitor with no declared alert source, and aggregate reports observe nothing. [R1 S2-E4, S3-E5, S3-E6]"""
    out = set()
    for m in intent["monitoring_instruments"]:
        if m["kind"] == "aggregate_report":
            continue
        if m["coverage"] == "sampled" and m.get("sample_rate", 0) < MIN_SAMPLE:
            continue
        if m["coverage"] == "on_alert" and not m.get("alert_source"):
            continue
        out.add(m["kind"])
    return out


def observable(kind: str, monitors: set[str]) -> bool:
    obs = OBSERVERS.get(kind)
    if obs is None:
        return True
    if obs == "any":
        return bool(monitors)
    return bool(obs & monitors)


# Checks on an Intent's commitments. Each takes the record and returns its findings.

def criterion_findings(record: dict) -> list[Finding]:
    """A1: dead criteria. A criterion none of whose event kinds any declared monitor can observe
    cannot fire except by accident. [T02; worked example DP1, DP3]"""
    out = []
    monitors = effective_monitors(record)
    for n, c in enumerate(record["pause_criteria"]):
        seen = [k for k in c["matches"] if observable(k, monitors)]
        where = f"/pause_criteria/{n}"
        if not seen:
            out.append(Finding("error", "dead_criterion", where,
                               f"no declared monitor can observe {c['matches']}; criterion {c['criterion_id']!r} cannot fire"))
        elif len(seen) < len(c["matches"]):
            blind = sorted(set(c["matches"]) - set(seen))
            out.append(Finding("warning", "partly_blind_criterion", where,
                               f"criterion {c['criterion_id']!r} cannot observe {blind}"))
    return out


def monitor_findings(record: dict) -> list[Finding]:
    """Monitors must say how much they see and what feeds them. [R1 S2-E4, S3-E6]"""
    out = []
    for n, m in enumerate(record["monitoring_instruments"]):
        where = f"/monitoring_instruments/{n}"
        if m["coverage"] == "sampled" and ("sample_rate" not in m or "review_cadence" not in m):
            out.append(Finding("error", "monitor_unspecified", where, "a sampled monitor needs sample_rate and review_cadence"))
        if m["coverage"] == "on_alert" and not m.get("alert_source"):
            out.append(Finding("error", "monitor_unspecified", where, "an on-alert monitor needs an alert_source"))
        if not m.get("data_source"):
            out.append(Finding("error", "monitor_unspecified", where, "state the data_source the monitor reads"))
    return out


def retention_findings(record: dict) -> list[Finding]:
    """Retention: per class, with coverage, and long enough. [R1 S2-E9, S3-E7]"""
    out: list[Finding] = []

    def E(code: str, where: str, msg: str) -> None:
        out.append(Finding("error", code, where, msg))

    lr = record["log_retention"]
    horizon = months(lr["retain_until"].split("+", 1)[1])
    if horizon < RETENTION_FLOOR_MONTHS:
        E("retention_too_short", "/log_retention/retain_until",
          f"retain_until must be at least P{RETENTION_FLOOR_MONTHS}M after closeout")
    detail = {d["evidence_class"]: d for d in lr.get("detail", [])}
    for cls in lr["retained"]:
        d = detail.get(cls)
        if d is None:
            E("retention_detail_missing", "/log_retention/detail", f"give coverage and retention for {cls!r}")
            continue
        if d["coverage"] == "sampled" and "sample_rate" not in d:
            E("retention_detail_missing", "/log_retention/detail", f"{cls!r} is sampled; give sample_rate")
        if months(d["retention"]) < horizon:
            E("retention_class_short", "/log_retention/detail",
              f"{cls!r} is kept {d['retention']}, shorter than the declared retain_until")
    if "minimum_preserved_pct" not in lr:
        E("preservation_floor_missing", "/log_retention/minimum_preserved_pct", "declare a minimum preserved share")
    return out


def restart_findings(record: dict) -> list[Finding]:
    """Whoever pauses must not also restart."""
    if record["restart_protocol"]["approver_role"] in {c["authority_role"] for c in record["pause_criteria"]}:
        return [Finding("error", "self_approved_restart", "/restart_protocol/approver_role",
                        "the restart approver must not be a role that decides pauses [R1 S2-E11, S3-E13]")]
    return []
