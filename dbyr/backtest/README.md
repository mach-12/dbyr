# Backtesting DBYR against an incident

For researchers testing whether DBYR would have helped in a past incident. Labs using DBYR need
none of this; they file and check records as the [root README](../../README.md) describes.

The question: **had DBYR existed during this incident, would the questions that mattered afterwards
have been answerable from the records?** The filings are the answers, written in advance by the lab.
The decision points are the questions, written afterwards with hindsight. The score is how many
questions the filings answer.

Decision points are never filed — they are not part of the protocol, only the measure of it.
Researchers write them from the public account, ideally not the person who reconstructed the
filings, and freeze them before scoring.

The paper's cases are in [`benchmarks/`](../../benchmarks/), one folder per incident.

## Step by step

A **case** is one folder holding an incident's filings and its decision points.

**1. Start from the example and run it unchanged.**

```bash
dbyr backtest init cases/my-case     # copies a working example and freezes the schema
dbyr backtest check cases/my-case    # ok (0 errors, 0 warnings)
dbyr backtest score cases/my-case    # verdicts and tables
```

All three must succeed before you change anything. The folder holds a synthetic safeguards-off
evaluation at "Lab X" and a [README](template/README.md) describing every file.

**2. Replace the filings** — `intent_A.json`, `notice_N1.json`, `closeout_A.json`. Use public
sources only, and record where every value came from in `sources.json`. Check each with
`dbyr validate` as you write it; the [record docs](../../docs/records/README.md) list every field.

**3. Run the protocol over them.**

```bash
dbyr run cases/my-case
```

A `schema` error means a filing is malformed — fix it. Any other error is the protocol rejecting
the filing, which for a real incident is itself a result, not something to fix.

**4. Write the decision points** in `decision_points.json`. dbyr does not generate them; see
[Writing `decision_points.json`](../../docs/cases/decision_points.md). Then
`dbyr backtest check cases/my-case`.

**5. Score it.**

```bash
dbyr backtest score cases/my-case --out report/
```

A case **passes if at least half its decision points are attributable**. Every input is hashed
before and after scoring; if anything changed, or the schema is no longer the frozen one, scoring
stops. `--out` writes `report.md`, `report.html` and `metrics.json` there, and `results.json` /
`results.md` next to each case — the result to commit.

**6 (optional).** `annotations.json` fills table cells that would otherwise say "not annotated".
Scoring never reads it.

## Freezing the schema

A case records the hash `dbyr freeze` prints, taken **before any filing for the case is written**,
so a result shows which schema it was scored against. A case scored against a different schema is
void.

```jsonc
"freeze": {"schema_hash": "sha256:5d7e…", "revisions": []}
```

`init` fills it in. `check` reports a stale hash as an error and a missing one as a warning.

## Commands

| | |
|---|---|
| `dbyr freeze` | print the schema hash a case is frozen against |
| `dbyr backtest init DIR [--name NAME]` | write the example case to a new folder |
| `dbyr backtest check CASE...` | check a case before scoring: shape, frozen hash, record keys, schema fields, placeholders |
| `dbyr backtest score CASE... [--out DIR] [--design NAME] [--json]` | score cases and print verdicts and tables |

Two narrower modes, both printing JSON:

```bash
dbyr backtest score CASE --mode dp_coverage --filer_type as_believed
dbyr backtest score CASE --mode visibility_gap --dp_num DP2 --filer_type as_believed
```

`--filer_type` is `as_believed` or `diligent`. `--design` defaults to all six: `table1`
(attributable decision points), `table2` (lead time of the outside record), `scorecard`,
`question_matrix`, `today_vs_dbyr`, `lifecycle`.

## Python

```python
from dbyr import DBYR

d = DBYR()
d.init_case("cases/my-case")
print(d.check_case("cases/my-case"))     # [] when ready
bt = d.backtest("cases/my-case")
print(bt.verdicts())
bt.write("report/")                      # report.md, report.html, metrics.json
bt.write_results()                       # results.json, results.md per case
```

`Backtest(*cases, designs=None, strict=True).run()` returns a `BacktestReport` carrying
`verdicts()`, `table(design)`, `results`, `metrics`, `integrity`, and `markdown()` / `to_json()` /
`write(out)` / `write_results()`. It raises `InputsChanged` if an input changed during scoring, or
`SchemaChanged` if a case's hash is not the current schema's; with `strict=False` both are recorded
and the verdict reads "void".

Lower-level: `init_case`, `check_case`, `Case.load`, `score` (the pre-registered scoring alone),
`compute_metrics`, `build_table`, `Fingerprint`, `apply_variant`.

A case's filings can live elsewhere — paths are relative to `decision_points.json`, so the same
filings can be checked with `dbyr run` and scored with `dbyr backtest score` without copying:

```jsonc
"filings": {"intent:A": {"file": "intent_A.json"}}   // listed one by one
"filings": "../../filings/lab-x/"                    // or a folder / manifest.json
```
