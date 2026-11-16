"""ExceptionNotices: each notice on its own, and the notices a Closeout's events require."""

from __future__ import annotations

from datetime import timedelta

from ..findings import Finding
from ..params import NOTICE_HOURS, REPORTABLE
from .common import ts


def check_notice(notice: dict) -> list[Finding]:
    if ts(notice["filed_at"]) < ts(notice["detected_at"]):
        return [Finding("error", "notice_before_detection", "/filed_at", "notice filed before detection")]
    return []


def check_notices(intent: dict, closeout: dict, notices: list[dict]) -> list[Finding]:
    """Every detected event matching a declared criterion, and every third-party compromise,
    needs an ExceptionNotice filed within NOTICE_HOURS of detection. [T09]"""
    out: list[Finding] = []
    # The duty follows a fixed list of reportable kinds, not the criteria the filer chose, so declaring
    # criteria no likely event would match does not remove it. [R1 S2-E2, S3-E3]
    mine = [n for n in notices if n.get("run_id") == closeout.get("run_id")]
    for e in closeout["security_events"] + closeout.get("integrity_events", []):
        if "detected_at" not in e:
            continue
        if e["kind"] not in REPORTABLE:
            continue
        citing = [n for n in mine if e["event_id"] in n["event_ids"]]
        where = f"/security_events/{e['event_id']}"
        if not citing:
            out.append(Finding("error", "notice_missing", where,
                               f"{e['kind']!r} detected {e['detected_at']} has no ExceptionNotice"))
            continue
        first = min(ts(n["filed_at"]) for n in citing)
        if first - ts(e["detected_at"]) > timedelta(hours=NOTICE_HOURS):
            out.append(Finding("conduct", "notice_late", where,
                               f"first notice filed {first.isoformat()}, more than {NOTICE_HOURS} hours after detection"))
    listed = set(closeout.get("notice_ids", []))
    for n in mine:
        if listed and n["notice_id"] not in listed:
            out.append(Finding("error", "notice_not_listed", "/notice_ids",
                               f"notice {n['notice_id']!r} was filed but the closeout does not list it"))
    return out
