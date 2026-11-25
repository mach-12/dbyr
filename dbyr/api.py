"""DBYR: one object for the common tasks.

    from dbyr import DBYR

    dbyr = DBYR()
    dbyr.schema_hash()                              # the hash to publish before a case is scored
    report = dbyr.check("filings/lab-x/")           # run the protocol over a filing set
    dbyr.validate(record)                           # one filing on its own
    dbyr.project(record, "public")                  # a disclosure view

    dbyr.init_case("cases/lab-x/")                  # start a backtest case from the example
    dbyr.check_case("cases/lab-x/")                 # check it before scoring
    bt = dbyr.backtest("cases/lab-x/")              # score; inputs are hashed before and after
    bt.verdicts(); bt.table("question_matrix"); bt.write("report/")
"""

from __future__ import annotations

from pathlib import Path

from .backtest import Backtest, BacktestReport, check_case, init_case
from .disclosure import project
from .filingset import FilingSet, load_filing_set
from .findings import Finding
from .integrity import schema_hash
from .protocol import Report, run_protocol
from .rules import validate_record


class DBYR:
    """Facade over the protocol and the backtest. Stateless; safe to share."""

    # ---------------------------------------------------------------- protocol

    def schema_hash(self) -> str:
        return schema_hash()

    def load(self, *paths: str | Path) -> FilingSet:
        return load_filing_set(*paths)

    def check(self, *paths: str | Path, views: bool = True) -> Report:
        return run_protocol(load_filing_set(*paths), views=views)

    def validate(self, record: dict) -> list[Finding]:
        return validate_record(record)

    def project(self, record: dict, tier: str) -> dict:
        view, _ = project(record, tier)
        return view

    # ---------------------------------------------------------------- backtest

    def init_case(self, dest: str | Path, name: str | None = None) -> Path:
        return init_case(dest, name)

    def check_case(self, case: str | Path) -> list[tuple[str, str]]:
        return check_case(case)

    def backtest(self, *cases: str | Path, designs: list[str] | None = None, strict: bool = True) -> BacktestReport:
        return Backtest(*cases, designs=designs, strict=strict).run()
