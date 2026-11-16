<div align="center">

# Declare Before You Run

###  A Disclosure Protocol for Frontier AI Training and Evaluation

## The `dbyr` package

This repository is the executable form of the paper: the JSON Schemas for the three DBYR records, the checks an evaluator runs on them, the public / restricted / sealed disclosure views, and a signed hash-chained ledger.

This page is for **labs** that file the records and the **regulators or evaluators** that check them. Researchers testing whether DBYR would have helped in a past incident should read **[Backtesting DBYR](dbyr/backtest/README.md)** instead; that is how the paper measured DBYR, and labs never need it.

### Install

```bash
pip install -e .
```

### File and check the records

The lab files three kinds of record over a run's life; the evaluator checks them as a set. Examples of all three, each passing every check, are in [`dbyr/backtest/template/`](dbyr/backtest/template/): `intent_A.json`, `notice_N1.json` and `closeout_A.json`. The [record docs](docs/records/README.md) list every field and every check.

| When | The lab files | Doc |
|---|---|---|
| at least 3 days before the run starts | a RunIntent: what the run will do, what agents can reach, how it is watched, what pauses it, what evidence is kept | [intent.md](docs/records/intent.md) |
| within 72 hours of detecting a reportable event | an ExceptionNotice | [notice.md](docs/records/notice.md) |
| when the run ends, and at least every 30 days | a RunCloseout: what actually happened | [closeout.md](docs/records/closeout.md) |

**Step 1. Check each record as you write it.**

```bash
dbyr validate filings/lab-x/intent_A.json
```

**Step 2. Check the whole set.** The lab can run this before submitting; the evaluator runs it on receipt.

```bash
dbyr run filings/lab-x --out report/
```

Each finding is an **error** (the filing is defective and is not lodged), a **conduct** finding (the filing lodges, but records a breach of the lab's own commitments, such as a late notice or a criterion that fired with no pause; it goes to adjudication), or a **warning**. `--out` writes `report.json`, `report.md`, and for each lodged filing its public, restricted and sealed views in `views/`, with `openings.json`, the salts that let the lab later prove a hidden value.

**Step 3 (optional). Sign the lodged filings into a tamper-evident record.**

```bash
dbyr keygen lab.key
dbyr run filings/lab-x --ledger record.jsonl --key lab.key
dbyr verify record.jsonl                # any edit, deletion or reordering is detected
```

In Python:

```python
from dbyr import DBYR

dbyr = DBYR()
report = dbyr.check("filings/lab-x")    # step 2
print(report.ok, report.counts())       # True {'error': 0, 'conduct': 0, 'warning': 1}
```

---

## Python API

Everything below is importable from the top-level package: `from dbyr import <name>`. The backtest API is documented in [Backtesting DBYR](dbyr/backtest/README.md).

### `DBYR`: one object for the common tasks

Start here. Each method wraps one of the functions further down.

| Method | Returns | What it does |
|---|---|---|
| `DBYR().schema_hash()` | `str` | The hash of the frozen schemas, identifying the exact schema version a filing was checked against. |
| `DBYR().load(*paths)` | `FilingSet` | Load a filing set from a folder, its `manifest.json`, or a list of record files. |
| `DBYR().check(*paths, views=True)` | `Report` | Run the whole protocol over a filing set. |
| `DBYR().validate(record)` | `list[Finding]` | Check one filing on its own. |
| `DBYR().project(record, tier)` | `dict` | The `"public"`, `"restricted"` or `"sealed"` view of one filing. |

```python
from dbyr import DBYR

dbyr = DBYR()
report = dbyr.check("filings/lab-x")
for stage, at, finding in report.findings:
    print(stage, finding)
```

### Filing sets

A filing set is the unit the protocol runs on: Intents (and amendments), ExceptionNotices and Closeouts.

**`load_filing_set(*paths) -> FilingSet`**
Load from a `manifest.json` (`{"records": {"intent:A": "intent_A.json", ...}}`), a folder, or files. Without a manifest, every `*.json` with a `record_type` is a filing; other JSON is listed in `skipped`.

```python
from dbyr import load_filing_set
fs = load_filing_set("filings/lab-x")
fs.records        # {"closeout_A.json": {...}, "intent_A.json": {...}, ...}  (no manifest: keyed by file name)
fs.files          # filing key -> path on disk
fs.description    # from the manifest, if any
fs.skipped        # JSON files that are not DBYR records
```

**`FilingSet`**: the loaded set (`records`, `files`, `description`, `skipped`).
**`FilingSetError`**: raised for a missing file, invalid JSON or a bad manifest.

### Running the protocol

**`run_protocol(filings, views=True, ledger=None, signing_key=None) -> Report`**
Runs every stage in the order an evaluator meets them: each record on its own, Intent versions, reconciliation of each Closeout against the Intent in force, notice timeliness, and lineage across runs sharing a surface. Optionally projects the disclosure views and signs lodged filings into a ledger.

```python
from dbyr import load_filing_set, run_protocol
report = run_protocol(load_filing_set("filings/lab-x"))
report.ok              # False if any finding is an error
report.counts()        # {"error": 0, "conduct": 0, "warning": 1}
report.lodged          # filing keys that passed their own checks
report.views           # filing key -> public / restricted / sealed / openings
print(report.to_markdown())        # or report.to_json()
```

**`check_set(filings: dict) -> list[tuple[str, Finding]]`**
The checks alone, without views or a ledger: every finding labelled with the filing key or stage it belongs to.

**`Report`**: the result of `run_protocol` (`ok`, `counts()`, `findings`, `lodged`, `views`, `ledger_entries`, `to_json()`, `to_markdown()`).

### Checking individual records

| Function | Checks |
|---|---|
| `validate_record(record) -> list[Finding]` | One filing on its own: schema, cross-field rules and minimum content for its record type. |
| `reconcile(intent, closeout) -> list[Finding]` | A Closeout against the Intent it closes: matched criteria without a pause, restart approvals, undeclared surfaces, retention and preservation. |
| `check_notices(intent, closeout, notices) -> list[Finding]` | Every reportable event has an ExceptionNotice filed within 72 hours of detection. |
| `check_lineage(intents, closeouts) -> list[Finding]` | Runs reaching the same persistent shared surface cite each other and any exception already on record. |
| `linked_groups(intents) -> list[set[str]]` | The run ids that form one reconciliation unit because they share a surface. |

```python
import json
from dbyr import validate_record, reconcile

intent = json.load(open("filings/lab-x/intent_A.json"))
closeout = json.load(open("filings/lab-x/closeout_A.json"))
validate_record(intent)              # [] when the Intent lodges
for f in reconcile(intent, closeout):
    print(f)                          # [warning] code at /pointer: message
```

### Findings

Every check returns `Finding` objects with a `severity`, `code`, `where` (a JSON pointer) and `message`.

| Severity | Meaning |
|---|---|
| `error` | The filing is defective and is not lodged. |
| `conduct` | The filing lodges, but it records a breach of the filer's own commitments (a late notice, a matched criterion with no pause). It goes to adjudication; admitting a breach is never costlier than hiding it. |
| `warning` | For the reviewer's attention. |

**`errors(findings)`** and **`conduct(findings)`** filter a list to one severity.

### Disclosure views

Each field has a disclosure tier. A field above the viewer's tier is replaced by a salted commitment, so the viewer can see it exists and later check it without learning its value.

**`project(record, view, salts=None) -> (view, openings)`**
`view` is `"public"`, `"restricted"` or `"sealed"`. `openings` maps each committed field's JSON pointer to its salt; the filer keeps it.

**`all_views(record) -> dict`**: `{"public", "restricted", "sealed", "openings"}` in one call, with consistent salts.

**`check_opening(commitment, value, salt_hex) -> bool`**: check a revealed value against its commitment.

```python
import json
from dbyr import project, check_opening

intent = json.load(open("filings/lab-x/intent_A.json"))
public, openings = project(intent, "public")
public["monitoring_instruments"]      # {"$commitment": "sha256:...", "$tier": "restricted"}

salt = openings["/monitoring_instruments"]
check_opening(public["monitoring_instruments"]["$commitment"], intent["monitoring_instruments"], salt)  # True
```

### The ledger

**`Ledger(path)`**: an append-only, hash-chained, Ed25519-signed record of lodged filings, one entry per line. Deleting, reordering or editing any entry breaks every later link.

| Method | What it does |
|---|---|
| `append(record, signing_key, filed_at=None) -> dict` | Validate, sign and append one filing; returns the entry. |
| `verify(trusted_keys=None) -> list[Finding]` | Recheck every hash link and signature. |
| `entries()` | Every entry, in order. |
| `head()` | The hash of the last entry. |

```python
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from dbyr import Ledger

key = Ed25519PrivateKey.generate()
book = Ledger(Path("record.jsonl"))
book.append(intent, key)
book.verify()                         # [] when every link and signature holds
```

### Schema and integrity

**`schema_hash() -> str`**: the SHA-256 of the canonical form of every schema file. Reformatting a schema does not change it; any change to its content does.
**`SCHEMA_VERSION`**: the schema version label.

---

## Command line

`dbyr <command>` (or `python -m dbyr <command>`):

| Command | What it does |
|---|---|
| `dbyr run PATH... [--out DIR] [--ledger FILE --key KEYFILE] [--json]` | Run the whole protocol over one filing set. `--out` writes `report.json`, `report.md` and every disclosure view. Exit code 1 if any finding is an error. |
| `dbyr validate FILE...` | Check each filing on its own. |
| `dbyr project --view TIER FILE` | Print the public, restricted or sealed view of a filing. |
| `dbyr keygen KEYFILE` | Write a new Ed25519 signing key, for `run --ledger`. |
| `dbyr verify LEDGER` | Recheck every hash link and signature in a ledger. |
| `dbyr freeze` | Print the schema hash. |
| `dbyr docs [DIR] [--check]` | Rewrite the field tables in the record docs (default `docs/records`) from the schemas. `--check` only reports stale docs, with exit code 1. |

The `dbyr backtest` commands are documented in [Backtesting DBYR](dbyr/backtest/README.md).

---

