# Backtest case

A backtest tests the DBYR protocol itself. It asks, for each decision that shaped an incident: **had
DBYR existed, was the fact written down before the run, and could it be checked afterwards?** A case
holds the filings the lab would have made, and the decision points they are scored on.

**If you only want to file DBYR records and check them, you do not need a case:** write the filings
and run `dbyr run`. Decision points are never filed. They are the questions an investigator asks
after an incident, written by researchers (never by the lab whose incident it is), and they exist
only to measure the protocol.

This folder is a complete, working example: a synthetic safeguards-off cyber evaluation at a
fictional "Lab X", and a system later deployed on it. It passes every check. Start from it and
replace its contents with your own.

## What is in a case

| File | Written by | What it is |
|---|---|---|
| `intent_A.json` | you | RunIntent: the run's commitments, filed before it starts |
| `notice_N1.json` | you | ExceptionNotice: filed within 72 hours of detecting an event |
| `closeout_A.json` | you | RunCloseout: what happened, filed at the end (and every 30 days) |
| `decision_points.json` | you (`init` copies an example and fills in `case` and `schema_hash`) | the scoring plan: which decisions to score, and what each is tested against |
| `sources.json` | you, optional | where each value in the filings came from |
| `annotations.json` | you, optional | context for the results tables, added after scoring; never read by the scoring |

Every field and every check of the four filings is documented in `docs/records/` in the DBYR
repository.

## Steps

### 1. Create the case and try it unchanged

```bash
dbyr backtest init cases/my-case      # copies this example and freezes the schema
dbyr backtest check cases/my-case     # should print: ok (0 errors, 0 warnings)
dbyr backtest score cases/my-case     # should print the verdicts and tables
```

`init` records the current schema hash as `schema_hash` in `decision_points.json`. Do not change
it. If the schema changes later, the case is void: `check` reports an error and `score` refuses.

### 2. Replace the filings with your own

Write one Intent per run, one Notice per reportable event, one Closeout per run (and per 30-day
period), and a runtime record if a system was deployed. Records are linked by `run_id` (or
). An amendment is another Intent with the same `run_id`, plus
`amends` and `changes`.

The filings may live in this folder or anywhere else (see `records` and `filings` below).

### 3. Run the protocol over the filings

```bash
dbyr run cases/my-case
```

- An error with the code `schema` means a filing is malformed: fix it.
- Any other error is the protocol rejecting the filing. For a real incident, that rejection is a
  result to report, not something to fix.

### 4. Replace the decision points with your own

Edit `decision_points.json`: dbyr does not generate it. Keep `case` and `schema_hash`; replace
everything else. The full format, the test syntax and a worked example are in
`docs/cases/decision_points.md` in the DBYR repository.

| Key | What to write |
|---|---|
| `records` or `filings` | where the filings are: `records` lists each file (`{"intent:A": "intent_A.json"}`); `filings` points at a folder or `manifest.json` anywhere, the same thing `dbyr run` takes |
| `closes` | each Closeout's key, mapped to its Intent's key |
| `variants` | the filer variants to score, usually `diligent` (states what was true) and `as_believed` (states what the filer believed). Each edits a copy of the Intent with `remove_surfaces`, `remove_paths` or `path_writable` |
| `decision_points` | one entry per decision, described below |

Each decision point has:

| Key | What it is |
|---|---|
| `id`, `decision`, `field` | a name, what was decided, and the filing field that should have captured it |
| `developer_aware` | `yes`, `no` or `unclear`, with `aware_source` |
| `recorded_before` | a test on a filing made before the event: `pointer` with `equals` or `exists`, `any` with `where`, or `all` |
| `checkable_after` | a test on the Closeout, plus the `evidence` classes a later check needs kept |
| `decision_rule` | `pause_criterion` with an `event_kind`, or `record_obligation` |

### 5. Check and score

```bash
dbyr backtest check cases/my-case
dbyr backtest score cases/my-case --out report/ --write-results
```

Each decision point is scored on (a) recorded before, (b) checkable after, and (c) whether the
filing would have changed the decision. A case **passes if at least half its decision points
satisfy (a) and (b)**. Report both variants. Every input is hashed before and after scoring; if
anything changed, the run stops.

### 6. Optional: add context for the tables

`annotations.json` adds what the tables need but the scoring never reads. Write it after scoring.

| Key | What it holds |
|---|---|
| `label` | the case's column heading |
| `primary_variant` | the variant the tables report (default `as_believed`) |
| `decision_kinds` | per decision point: `setup`, `deploy`, `respond`, `tell` or `investigate` |
| `first_outside_account` | dated accounts from outside the organisation: `date`, `what`, `source` |
| `investigation` | `incident_window` and `review_window`, each `[start, end]` |
| `today` | per question, what the organisation's own accounts show |
| `escape_reasons`, `provenance` | corrections to the automatic classification, with the reason in `_notes` |

## What dbyr writes

| Command | Writes | Used for |
|---|---|---|
| `dbyr backtest init` | a copy of this example case, with `case` and `schema_hash` filled in | a starting point: you replace the filings and the decision points |
| `dbyr run --out DIR` | `report.json`, `report.md`, `views/` | the protocol's findings on the filings, and their public, restricted and sealed views |
| `dbyr backtest score --out DIR` | `report.md`, `report.html`, `metrics.json` | the full report with all four tables, and the same as data |
| `dbyr backtest score --write-results` | `results.json`, `results.md` in the case folder | the case's pre-registered result, to commit |

## Rules for an honest case

- Freeze the schema before writing filings, and publish the hash.
- For a real incident, use public sources only. Keep snapshots in `sources/`, and mark every value
  in `sources.json` as `first-party`, `forced-choice` or `placeholder`.
- Never test a placeholder value in a decision point; `check` warns if one does.
- The person who writes the decision points should not be the person who wrote the filings.
- Do not edit `decision_points.json` after scoring.

## Reading findings

- **error**: the filing is defective and is not lodged; any error fails the set.
- **conduct**: the filing lodges, but records a breach of the filer's own commitments (a late
  notice, a matched criterion with no pause). It goes to adjudication.
- **warning**: for the reviewer's attention.
