# DBYR records

DBYR has three records. A developer files them; the protocol checks each one when it is filed, and
checks them against each other as the set grows.

| Record | Filed | What it says |
|---|---|---|
| [RunIntent](intent.md) | at least 3 days before the run starts; again as an amendment when a declared fact changes | what the run will do, what it can reach, how it is watched, what will pause it |
| [ExceptionNotice](notice.md) | within 72 hours of detecting a reportable event | what was detected, when, and what was done |
| [RunCloseout](closeout.md) | when the run ends or is aborted, and at least every 30 days while it runs | what actually happened: events, pauses, containment failures, evidence kept |

## How they link

- **`run_id`** ties an Intent to its notices and Closeouts.
- **Amendments** are another Intent with the same `run_id`, plus `amends` and `changes`. Every
  version is kept; each Closeout is checked against the version in force when it was filed.
- **Event ids:** a Notice's `event_ids` are the ids the run's Closeout gives the same events, and a
  Closeout lists its notices in `notice_ids`.
- **Surfaces:** runs reaching the same persistent shared surface must cite each other in
  `shared_surface_lineage`. They are reconciled as one group.

`dbyr run FOLDER` runs the checks in order: each filing alone, then Intent versions, each Closeout
against the Intent in force, notice timeliness, and lineage across runs. Each record's doc lists its
own codes.

## Severity

| | |
|---|---|
| **error** | the filing is defective and is not lodged |
| **conduct** | it lodges, but records a breach of the filer's own commitments. It goes to adjudication |
| **warning** | for the reviewer's attention |

Four codes are not specific to one record:

| Code | Severity | Fires when |
|---|---|---|
| `schema` | error | The filing does not match its schema. No other check runs on it. |
| `unknown_record_type` | error | `record_type` is not one of the three records. |
| `intent_missing` | error | A Closeout's `run_id` has no Intent in the set. |
| `unreconcilable` | error | A cross-filing stage could not run because a filing it needs is malformed. |

A bracketed tag such as `[T09]` or `[R1 S2-E3]` names the tabletop finding that motivated a check.

## Disclosure tiers

Every field has a tier, shown in each record's field table; a field without one takes its parent's.
Each filing is projected into three views. Where a view may not show a field it holds a salted hash
instead, so a reader sees the field exists and can check it later when the value is opened.

| Tier | Shown in |
|---|---|
| public | every view |
| restricted | restricted and sealed; a hash in public |
| sealed | only the sealed view, opened under legal hold; a hash in the others |

## Trigger basis

The Intent's `trigger_basis` lists why DBYR covers the run. A run covered for several reasons lists
each. T4 brings the strictest checks.

| Trigger | Covers a run when | Must be listed when | What it adds |
|---|---|---|---|
| `T1` | training compute is above the operator's threshold | the filer declares it | nothing beyond the checks every Intent gets |
| `T2` | the developer is a covered developer | the filer declares it | nothing beyond the checks every Intent gets |
| `T3` | it is forecast to reach a high or critical capability | any `predicted_capability_band` is `high` or `critical` | nothing further; the forecast is tested through `eval_plan`, which any band above `low` needs |
| `T4` | any production safeguard is relaxed or off | `safeguards_disabled.disabled` is true | a working monitor; no unenforced network path; an observable pausing criterion for each core kind; a criterion for every reportable kind |

See [intent.md](intent.md#checks-when-filed) for the codes these raise.

## Event kinds

Every kind except `monitor_alert` is reportable: it must be listed in the Closeout and needs an
ExceptionNotice. A kind can only fire a pause criterion if a declared monitor can observe it.

| Event kind | Meaning | Observed by |
|---|---|---|
| `sandbox_escape` | an agent reaches outside the sandbox | `network_alerting`, `trajectory_review` |
| `undeclared_surface_use` | an agent uses a surface the Intent did not declare | `write_audit`, `environment_integrity_check`, `trajectory_review` |
| `inter_agent_comms` | one agent reads what another wrote | `inter_agent_message_monitor`, `trajectory_review` |
| `credential_misuse` | an agent uses credentials beyond their purpose | `access_log_review`, `environment_integrity_check` |
| `privilege_escalation` | an agent gains privileges it was not given | `access_log_review`, `environment_integrity_check` |
| `remote_code_execution` | an agent runs code on a system it should not reach | `environment_integrity_check`, `access_log_review`, `trajectory_review` |
| `agent_induced_outage` | an agent takes a system down | always observable |
| `third_party_compromise` | an outside party's system is compromised | always observable (by external report) |
| `environment_tampering` | an agent alters its task, grader, reward or shared build and test inputs | `environment_integrity_check`, `write_audit`, `reward_seeking_monitor`, `trajectory_review` |
| `access_boundary_breach` | an agent reads or moves data outside its declared `readable_sources` | `access_log_review`, `trajectory_review` |
| `data_exposure` | restricted data reaches a wider audience than permitted | `access_log_review`, `write_audit`, `trajectory_review` |
| `integrity_incident` | unrequested bulk changes, propagated factual errors, or actions misattributed to a person | `write_audit`, `trajectory_review` |
| `monitor_alert` | a monitor raised an alert (not reportable) | any monitor |

A monitor counts as an observer only if it actually observes: a sampled monitor below a 1% sample
rate, an on-alert monitor with no `alert_source`, and an `aggregate_report` observe nothing.

## Field types

The *Type* column gives each field's type as a Python type hint, as the JSON is parsed:

| Type | In the JSON file |
|---|---|
| `str`, `int`, `float`, `bool` | a string, a whole number, any number, `true` or `false` |
| `datetime` | an ISO 8601 date-time string with a time zone, e.g. `"2026-07-04T09:30:00Z"` |
| `date` | an ISO 8601 date string, e.g. `"2026-07-04"` |
| `Literal["a", "b"]` | exactly one of the listed values |
| `list[X]` | an array whose items are `X` |
| `dict` | an object; its fields are the rows below it, written `parent.child` |
| `X \| None` | `X`, or `null` |
| `EventKind` | `Literal` of the event kinds in the table above |
| `EvidenceClass` | `Literal` of the evidence classes above |

Identifiers (`run_id`, `surface_id`, `criterion_id` and the like) are `str` of letters, digits and
`. _ : -`, up to 128 characters. A field naming a role (`authority_role`, `signer.role_id` and the
like) is a `str` that must be a `role_id` from the Intent's `roles`. Ranges and formats that the
type cannot show are given at the end of the field's meaning.

## Parameters

The checks use these defaults from [`dbyr/params.py`](../../dbyr/params.py). An operator may set
others; changing one changes what lodges.

| Parameter | Default | Meaning |
|---|---|---|
| `INTAKE_DAYS` | 3 | a first Intent is filed at least this many days before the run starts |
| `NOTICE_HOURS` | 72 | an ExceptionNotice is due within this many hours of detection |
| `NOTIFY_HOURS` | 72 | an affected third party is told within this many hours of detection, or a reason is given |
| `CLOSEOUT_EVERY_DAYS` | 30 | the longest period one Closeout may cover |
| `MAX_EVAL_DAYS` | 31 | the longest window one evaluation Intent may cover, across all its versions |
| `RETENTION_FLOOR_MONTHS` | 12 | the shortest retention after closeout |
| `MIN_SAMPLE` | 0.01 | a sampled monitor below this rate observes nothing |
| `CORE_KINDS_T4` | `sandbox_escape`, `privilege_escalation`, `inter_agent_comms`, `third_party_compromise` | the kinds a safeguards-off run needs an observable, pausing criterion for |
| `PAUSING` | `pause`, `pause_and_review`, `halt_and_amend_intent` | the required actions that count as pausing |

The field tables are generated: run `dbyr docs` after a schema change, or `dbyr docs --check` in CI.
