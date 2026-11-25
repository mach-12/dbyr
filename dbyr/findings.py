"""Findings: what every check returns.

Findings have a severity:
  error    the filing is defective and cannot be lodged until it is amended
  conduct  the filing lodges, but it truthfully records a breach of the filer's own declared
           commitments (a matched criterion with no pause, a restart approved by the wrong role,
           logs lost below the declared floor, evidence destroyed, a late notice). These are flagged
           for adjudication rather than refused, so that admitting a breach is never costlier than
           hiding it. [tabletop round 1, judge headline finding 4]
  warning  the filing lodges; a reconciler should look here
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Finding:
    severity: str  # "error" | "conduct" | "warning"
    code: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.code} at {self.where}: {self.message}"


def errors(findings: Iterable[Finding]) -> list[Finding]:
    """Findings that stop a filing being lodged."""
    return [f for f in findings if f.severity == "error"]


def conduct(findings: Iterable[Finding]) -> list[Finding]:
    """Recorded breaches: the filing lodges and the breach goes to adjudication."""
    return [f for f in findings if f.severity == "conduct"]
