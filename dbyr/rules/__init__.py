"""Every check DBYR applies, organised by what is checked.

  validate_record   one filing: schema, then the checks for its record type
  reconcile         a Closeout against the Intent it closes
  check_notices     the ExceptionNotices a Closeout's events require
  version_rules     every version of a run's Intent, and Closeout cadence
  check_lineage     runs that share a persistent surface
"""

from __future__ import annotations

from ..findings import Finding
from ..schema import validator_for
from .closeout import check_closeout
from .intent import check_intent
from .lineage import check_lineage, linked_groups
from .notice import check_notice, check_notices
from .reconcile import reconcile
from .versions import in_force, version_rules

CHECKS = {
    "RunIntent": check_intent,
    "RunCloseout": check_closeout,
    "ExceptionNotice": check_notice,
}


def schema_findings(record: dict) -> list[Finding]:
    record_type = record.get("record_type")
    try:
        validator = validator_for(record_type)
    except KeyError:
        return [Finding("error", "unknown_record_type", "/record_type", f"{record_type!r} is not a DBYR record type")]
    findings = []
    for err in sorted(validator.iter_errors(record), key=lambda e: list(e.absolute_path)):
        pointer = "/" + "/".join(str(p) for p in err.absolute_path)
        findings.append(Finding("error", "schema", pointer, err.message))
    return findings


def validate_record(record: dict) -> list[Finding]:
    """Schema, then every check for the record's type."""
    findings = schema_findings(record)
    if any(f.code in ("schema", "unknown_record_type") for f in findings):
        return findings  # cross-field rules assume a well-formed record
    return findings + CHECKS[record["record_type"]](record)


__all__ = ["check_closeout", "check_intent", "check_lineage", "check_notice", "check_notices",
           "in_force", "linked_groups", "reconcile", "schema_findings",
           "validate_record", "version_rules"]
