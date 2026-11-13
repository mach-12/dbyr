"""Run a backtest over any number of cases and write the full report.

    report = Backtest("cases/a", "cases/b/decision_points.json").run()
    report.verdicts()                      # pre-registered pass/fail per case and variant
    report.table("table2")                 # one of the designs
    report.write("out/")                   # report.md, report.html, metrics.json
    report.write_results()                 # results.json and results.md next to each case

Every case's inputs are hashed when it is loaded and again after scoring; if any input changed,
the run stops with InputsChanged. Outputs are written only where you ask.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..integrity import schema_hash
from .case import Case
from .fingerprint import InputsChanged, SchemaChanged
from .metrics import compute
from .render import report_html, report_markdown, results_markdown
from .scoring import score
from .tables import DESIGNS, Table, build


@dataclass
class BacktestReport:
    schema_hash: str
    results: dict[str, dict]            # case name -> pre-registered scoring output (results.json shape)
    metrics: list[dict]                 # one per case, in the order given
    tables: list[Table]
    integrity: dict[str, dict] = field(default_factory=dict)
    folders: dict[str, Path] = field(default_factory=dict)   # case name -> case folder

    def verdicts(self) -> dict[str, dict[str, dict]]:
        return {m["case"]: {name: {"attributable": r["attributable"], "n": r["n"], "needed": r["needed"],
                                   "passes": r["passes"], "derivation_case": m["is_derivation_case"]}
                            for name, r in m["registered"].items()}
                for m in self.metrics}

    def table(self, design: str) -> Table:
        return next((t for t in self.tables if t.id == design), None) or build(design, self.metrics)

    def to_json(self) -> dict:
        """The tables' values, and what is needed to show they came from unchanged inputs."""
        return {"schema_hash": self.schema_hash,
                "cases": {name: {"unchanged": c["unchanged"], "files": len(c["files"]),
                                 "schema_matches": c["schema_matches"]}
                          for name, c in self.integrity.items()},
                "tables": [{"id": t.id, "title": t.title, "columns": t.columns, "rows": t.rows,
                            "notes": t.notes} for t in self.tables]}

    def markdown(self) -> str:
        return report_markdown(self)

    def write(self, out: str | Path) -> dict[str, Path]:
        """The full report: report.md, report.html and metrics.json in `out`."""
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        paths = {"report.md": out / "report.md", "report.html": out / "report.html",
                 "metrics.json": out / "metrics.json"}
        paths["report.md"].write_text(report_markdown(self), encoding="utf-8")
        paths["report.html"].write_text(report_html(self), encoding="utf-8")
        paths["metrics.json"].write_text(json.dumps(self.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return paths

    def write_results(self) -> list[Path]:
        """The pre-registered per-case outputs, results.json and results.md, next to each case's
        decision_points.json. They are outputs, so they never count as a change to the inputs."""
        written = []
        for name, result in self.results.items():
            folder = self.folders[name]
            (folder / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            (folder / "results.md").write_text(results_markdown(result), encoding="utf-8")
            written += [folder / "results.json", folder / "results.md"]
        return written


class Backtest:
    def __init__(self, *cases: str | Path, designs: list[str] | None = None, strict: bool = True):
        if not cases:
            raise ValueError("a backtest needs at least one case (a folder or a decision_points.json)")
        self.paths = [Path(c) for c in cases]
        self.designs = designs or ["table1", "table2"]
        self.strict = strict

    def run(self) -> BacktestReport:
        loaded = [Case.load(p) for p in self.paths]   # fingerprints are taken here, before scoring
        names = [c.name for c in loaded]
        if len(set(names)) != len(names):
            raise ValueError(f"two cases share a name: {names}")
        # A case scored against a schema other than the one frozen before its filings were written is
        # void. Strict runs refuse it; otherwise the result is scored and marked void.
        stale = {c.name: c.frozen_hash for c in loaded if c.schema_matches is False}
        if stale and self.strict:
            raise SchemaChanged(f"the current schema is {schema_hash()}, but these cases froze another: "
                                + json.dumps(stale))
        results, metrics = {}, []
        for case in loaded:
            scored = score(case)
            results[case.name] = scored
            metrics.append(compute(case, scored))
        tables = [build(d, metrics) for d in self.designs]
        integrity = {}
        for case in loaded:
            diff = case.verify_unchanged()
            integrity[case.name] = {"unchanged": not diff, "diff": diff, **case.fingerprint.to_json(),
                                    "frozen_schema_hash": case.frozen_hash, "schema_matches": case.schema_matches}
        changed = {n: c["diff"] for n, c in integrity.items() if not c["unchanged"]}
        if changed and self.strict:
            raise InputsChanged("inputs changed during scoring: " + json.dumps(changed))
        return BacktestReport(schema_hash(), results, metrics, tables, integrity, {c.name: c.path for c in loaded})
