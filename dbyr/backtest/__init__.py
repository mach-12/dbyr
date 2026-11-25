"""Backtest DBYR against real or synthetic incidents.

    case         Case: the decision points, and the filings they score (listed, or any filing set)
    lint         check_case: check a case before scoring it
    scoring      the pre-registered scoring: (a) recorded before, (b) checkable after,
                 (c) changes decision, attributable, verdict
    metrics      further metrics for the results tables, each tagged registered or new
    tables       the four table designs: scorecard, question_matrix, today_vs_dbyr, lifecycle
    render       Markdown and HTML
    visibility   dp_coverage and visibility_gap: the two modes `dbyr backtest score` runs
    report       Backtest: run cases, verify inputs are unchanged, write the full report
    fingerprint  input hashing before and after scoring
    template/    a complete synthetic case; init_case copies it
"""

from .case import TEMPLATE, Case, CaseError, apply_variant, init_case
from .fingerprint import Fingerprint, InputsChanged, SchemaChanged
from .lint import check_case
from .metrics import compute as compute_metrics
from .report import Backtest, BacktestReport
from .scoring import score
from .tables import DESIGNS, Table, build as build_table
from .visibility import VisibilityError, dp_coverage, visibility_gap

__all__ = ["Backtest", "BacktestReport", "Case", "CaseError", "DESIGNS", "Fingerprint", "InputsChanged", "SchemaChanged",
           "TEMPLATE", "Table", "apply_variant", "build_table", "check_case", "compute_metrics", "init_case",
           "dp_coverage", "score", "visibility_gap", "VisibilityError"]
