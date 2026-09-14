"""DBYR v0.1 — reference implementation of the Declare Before You Run filing standard.

Modules
-------
validate   JSON Schema validation plus the semantic checks a schema cannot express
redact     public / restricted / sealed views derived from one authored document
envelope   signed envelopes and an append-only, hash-chained register
predicates declarative match rules for machine-checkable pause criteria
replay     backtest harness: replay an Intent against an incident event stream
interop    emitters to SB 53, EU Code of Practice and FRONTIER Act artefacts
"""

__version__ = "0.1.0"

# Convenience aliases are deliberately not named after their modules, so that
# `dbyr.validate` and `dbyr.replay` remain the modules rather than functions.
from . import envelope, interop, predicates, redact, replay, validate  # noqa: F401
from .envelope import Register, sign, verify
from .interop import coverage_report, emit_eu_cop_incident, emit_frontier_audit_index, emit_sb53_incident
from .predicates import evaluate
from .redact import commitments_for, merkle_root, project, verify_disclosure
from .replay import counterfactual, load_events, to_markdown
from .replay import replay as replay_events
from .validate import validate as validate_record

__all__ = [
    "validate_record", "project", "commitments_for", "merkle_root", "verify_disclosure",
    "sign", "verify", "Register", "evaluate", "replay_events", "load_events",
    "counterfactual", "to_markdown", "coverage_report", "emit_sb53_incident",
    "emit_eu_cop_incident", "emit_frontier_audit_index",
    "validate", "replay", "redact", "envelope", "interop", "predicates",
]
