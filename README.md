<div align="center">

# Declare Before You Run

### A disclosure protocol for frontier AI training and evaluation

</div>

Before a lab starts a covered run, it files a signed record of what the run will do, what its agents
can reach, how it is watched and what will stop it. When something goes wrong it files what
happened. An evaluator checks the two against each other.

This repository is the executable form of the paper: the JSON Schemas, the checks an evaluator runs,
the public / restricted / sealed disclosure views, and a signed hash-chained ledger.

```bash
pip install -e .
```

## The three records

| When | What | Fields |
|---|---|---|
| at least 3 days before the run starts | **RunIntent** — what the run will do, what agents can reach, how it is watched, what pauses it | [intent.md](docs/records/intent.md) |
| within 72 hours of detecting a reportable event | **ExceptionNotice** — what was detected, when, what was done | [notice.md](docs/records/notice.md) |
| when the run ends, and at least every 30 days | **RunCloseout** — what actually happened | [closeout.md](docs/records/closeout.md) |

Working examples of all three, each passing every check, are in
[`dbyr/backtest/template/`](dbyr/backtest/template/).

## Check a filing set

```bash
dbyr validate filings/lab-x/intent_A.json    # one record, as you write it
dbyr run filings/lab-x --out report/         # the whole set
```

Every finding is one of three things:

- **error** — the filing is defective and is not lodged
- **conduct** — it lodges, but records a breach of the filer's own commitments (a late notice, a
  criterion that fired with no pause). It goes to adjudication
- **warning** — for the reviewer's attention

`--out` writes `report.json`, `report.md`, and each lodged filing's three disclosure views, with the
salts that let the filer later prove a hidden value.

To sign the lodged filings into a tamper-evident record:

```bash
dbyr keygen lab.key
dbyr run filings/lab-x --ledger record.jsonl --key lab.key
dbyr verify record.jsonl        # any edit, deletion or reordering is detected
```

## In Python

```python
from dbyr import DBYR

report = DBYR().check("filings/lab-x")
print(report.ok, report.counts())       # True {'error': 0, 'conduct': 0, 'warning': 1}
```

`DBYR()` wraps the common tasks; everything is also importable directly from `dbyr`.

| | |
|---|---|
| `DBYR().check(*paths)` | run the whole protocol over a filing set |
| `DBYR().validate(record)` | check one filing on its own |
| `DBYR().load(*paths)` | load a filing set from a folder, manifest or file list |
| `DBYR().project(record, tier)` | the `public`, `restricted` or `sealed` view of a filing |
| `DBYR().schema_hash()` | the hash identifying the schema version a filing was checked against |

The underlying functions — `run_protocol`, `validate_record`, `reconcile`, `check_notices`,
`check_lineage`, `project`, `all_views`, `Ledger` — take plain dicts and return `Finding` objects.

## Command line

| | |
|---|---|
| `dbyr run PATH... [--out DIR] [--ledger FILE --key KEYFILE] [--json]` | run the protocol over a filing set; exit 1 on any error |
| `dbyr validate FILE...` | check each filing on its own |
| `dbyr project --view TIER FILE` | print one disclosure view |
| `dbyr keygen KEYFILE` | write a new Ed25519 signing key |
| `dbyr verify LEDGER` | recheck every hash link and signature |
| `dbyr freeze` | print the schema hash |
| `dbyr docs [DIR] [--check]` | rewrite the field tables in the record docs from the schemas |

## More

- [Record reference](docs/records/README.md) — every field, every check
- [Backtesting DBYR](dbyr/backtest/README.md) — how the paper measured the protocol against past
  incidents. Labs never need this
- [Writing `decision_points.json`](docs/cases/decision_points.md) — for researchers scoring a case
