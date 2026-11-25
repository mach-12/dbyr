"""Declare Before You Run (DBYR)

    filingset   load a filing set (a folder, a manifest.json, or record files)
    protocol    run every stage over a filing set: check_set, run_protocol
    rules/      every check, by what is checked (intent, closeout, notice, reconcile, versions, lineage)
    params      the deadlines, floors and fixed lists the checks apply
    schema/     the JSON Schemas and their validators
    disclosure  public / restricted / sealed views with salted commitments
    ledger      the signed, hash-chained record
    integrity   canonical JSON, digests and the schema hash
    findings    Finding and its three severities
    backtest/   score DBYR against incident cases and build the results tables
    api         DBYR, one object for the common tasks
"""

from .disclosure import all_views, check_opening, project
from .filingset import FilingSet, FilingSetError, load_filing_set
from .findings import Finding, conduct, errors
from .integrity import schema_hash
from .ledger import Ledger
from .protocol import Report, check_set, run_protocol
from .rules import check_lineage, check_notices, linked_groups, reconcile, validate_record
from .schema import SCHEMA_VERSION
from .api import DBYR  # noqa: E402  (imported last: it builds on everything above)

__all__ = [
    "DBYR",
    "SCHEMA_VERSION",
    "FilingSet",
    "FilingSetError",
    "Finding",
    "Ledger",
    "Report",
    "all_views",
    "check_lineage",
    "check_notices",
    "check_opening",
    "check_set",
    "conduct",
    "errors",
    "linked_groups",
    "load_filing_set",
    "project",
    "reconcile",
    "run_protocol",
    "schema_hash",
    "validate_record",
]
