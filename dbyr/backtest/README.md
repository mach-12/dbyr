# Backtesting DBYR against an incident

For researchers testing whether DBYR would have helped in a past incident. Labs using DBYR need
none of it; they file and check records as the [root README](../../README.md) describes.

The backtest asks: **had DBYR existed during this incident, would the questions that mattered
afterwards have been answerable from the records?** The records are the answers, written in
advance by the lab. The decision points are the questions, written afterwards with hindsight. The
score is how many questions the records answer.

- **Decision points are never filed.** They are not part of the protocol. They exist only to
  measure it, and the lab never writes them.
- **Researchers write them** from the public account of the incident, ideally not the person who
  reconstructed the filings, and freeze them before scoring.
- dbyr then answers each one the same way every time: was the fact recorded before (a), checkable
  after (b), and would a declared rule have changed the decision (c)? Attributable means (a) and
  (b) both hold; (c) is reported separately.

The paper's cases are in [`benchmarks/`](../../benchmarks/), one folder per incident.

## Freezing the schema

A case records the hash `dbyr freeze` prints, taken **before any filing for the case is written**,
so a result can show which schema it was scored against. A case scored against a different schema
is void.

```bash
dbyr freeze        # sha256:<64 hex digits>
```

Put it in `decision_points.json`, either top-level or in a `freeze` block — both work:

```jsonc
"schema_hash": "sha256:5d7e..."              // flat shape, what `init` writes
"freeze": {"schema_hash": "sha256:5d7e...", "revisions": []}   // case_id/filings shape
```

`dbyr backtest init` fills this in for you. **Hand-written cases ship a placeholder**
(`sha256:REPLACE_WITH_OUTPUT_OF_DBYR_FREEZE`) that you must replace, or `score` stops with
`schema_hash must be the value dbyr freeze prints`. `check` reports a stale hash as an error and
a missing one as a warning.

## Backtest an incident, step by step

A **case** is one folder holding the incident's filings and its decision points.

**1. Create the case from the example and run it unchanged.**

```bash
dbyr backtest init cases/my-case      # copies a complete example and freezes the schema
dbyr backtest check cases/my-case     # ok (0 errors, 0 warnings)
dbyr backtest score cases/my-case     # verdicts and results tables
```

All three should succeed before you change anything. The folder holds a working example (a
synthetic safeguards-off evaluation at "Lab X", plus a system deployed on it) and a
[README](template/README.md) describing every file.

**2. Replace the example filings** — `intent_A.json`, `notice_N1.json`, `closeout_A.json`, and
`runtime_S1.json` only if a system was deployed. Use public sources only and record where every
value came from in `sources.json`. Check each with `dbyr validate` as you write it; the
[record docs](../../docs/records/README.md) list every field and check.

**3. Run the protocol over the filings.**

```bash
dbyr run cases/my-case
```

Error code `schema` means a filing is malformed: fix it. Any other error is the protocol rejecting
the filing, which for a real incident is itself a result, not something to fix.

**4. Write the decision points.** Replace the examples in `decision_points.json`, keeping `case`
and `schema_hash`. dbyr does not generate them.
**[Writing `decision_points.json`](../../docs/cases/decision_points.md)** covers every key, the
test syntax and a full example. Then `dbyr backtest check cases/my-case`.

**5. Score it.**

```bash
dbyr backtest score cases/my-case --out report/
```

The case **passes if at least half its decision points are attributable**. Every input is hashed
before and after scoring; if anything changed, or the schema is no longer the frozen one, scoring
stops. `--out` writes `report.md`, `report.html` and `metrics.json` into the folder, **and**
`results.json` and `results.md` next to each case — the pre-registered result, to commit.

**6 (optional). Add context for the tables.** Edit `annotations.json` (decision kinds, when
outsiders learned, the investigation window) and score again. Scoring never reads it; it only
fills cells that would otherwise say "not annotated".

## Command line

| Command | What it does |
|---|---|
| `dbyr freeze` | Print the schema hash a case is frozen against. |
| `dbyr backtest init DIR [--name NAME]` | Write the example case to a new folder. |
| `dbyr backtest check CASE...` | Check cases before scoring: shape, frozen hash, record keys, schema fields, placeholders. Scores nothing; exit 1 on any error. |
| `dbyr backtest score CASE... [--out DIR] [--design NAME] [--json]` | Score cases; print verdicts and tables. See step 5 for what `--out` writes. `--design` may repeat. |
| `… score CASE --mode dp_coverage [--filer_type F]` | How many decision points the filings make attributable: `{total_dp, found_dp, coverage}`. |
| `… score CASE --mode visibility_gap --dp_num DP --filer_type F [--closeout-lag DAYS]` | How much earlier an outsider would have held one decision point's material fact: `{actual_date, dbyr_date, found_early_by}`. `found_early_by` is null where no filing was due before the fact reached the outside. |

`--filer_type` is `as_believed` or `diligent`. Both `--mode`s print JSON and, with `--out`, write
`<mode>.json` there. A CASE is a folder holding `decision_points.json`, or that file itself.

**Table designs** (`--design`, default all six): `table1` attributable decision points, one row per
filer, one column per case; `table2` lead time of the outside record, one row per decision point;
`scorecard` one row per case; `question_matrix` one row per question asked after an incident;
`today_vs_dbyr` today's record against the DBYR record; `lifecycle` one row per stage of an
incident.

## Python API

```python
from dbyr import DBYR

dbyr = DBYR()
dbyr.init_case("cases/my-case")                     # step 1
print(dbyr.check_case("cases/my-case"))             # step 4: [] when ready
bt = dbyr.backtest("cases/my-case")                 # step 5
print(bt.verdicts())
bt.write("report/")                                 # report.md, report.html, metrics.json
bt.write_results()                                  # results.json, results.md per case
```

`Backtest(*cases, designs=None, strict=True).run() -> BacktestReport` loads each case, hashes every
input (including filings kept outside the case folder), scores every decision point under every
filer variant, builds the tables, and re-hashes. It raises `InputsChanged` if an input changed
during scoring, or `SchemaChanged` if a case's hash is not the current schema's. With
`strict=False` both are recorded in the report instead and the verdict reads "void".

A `BacktestReport` carries `verdicts()`, `table(design)`, `results`, `metrics`, `integrity`, and
`markdown()` / `to_json()` / `write(out)` / `write_results()`.

**Where a case's filings live** — either listed one by one, or pointed at a filing set:

```jsonc
"records": {"intent:A": "intent_A.json", "closeout:A": "closeout_A.json"}
"filings": "../../filings/lab-x/"    // a folder or manifest.json, as `dbyr run` takes
```

Paths are relative to `decision_points.json`, so the same filings can be checked with `dbyr run`
and scored with `dbyr backtest score` without copying them.

**Lower-level pieces:** `init_case(dest, name=None)`, `check_case(case)`, `Case.load(path)`,
`score(case)` (the pre-registered scoring alone), `compute_metrics(case, scored)`,
`build_table(design, metrics)`, `Fingerprint.take(folder, *more)` / `.diff(other)`, and
`apply_variant(records, variant)`.

## Layout

```
dbyr/backtest/         the engine: case, lint, scoring, metrics, tables, render, report
  template/            the example case that `dbyr backtest init` writes
docs/cases/            how to write a case's decision_points.json
benchmarks/            data only: the paper's backtest cases
```
