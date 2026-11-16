# DBYR records

DBYR has three records. A developer files them; the protocol checks each one when it is filed and
checks them against each other as the set grows.

| Record | Filed | What it says | Doc |
|---|---|---|---|
| RunIntent | before the run starts, at least 3 days ahead; again as an amendment when a declared fact changes | what the run will do, what it can reach, how it is watched, and what will pause it | [intent.md](intent.md) |
| ExceptionNotice | within 72 hours of detecting a reportable event | what was detected, when, and what was done | [notice.md](notice.md) |
| RunCloseout | when the run ends or is aborted, and at least every 30 days while it runs | what actually happened in the period: events, pauses, containment failures, evidence kept | [closeout.md](closeout.md) |

The deadlines are the defaults in [`dbyr/params.py`](../../dbyr/params.py) (see [Parameters](#parameters)).

## How the records link

- **`run_id`** ties an Intent to its notices and Closeouts.
- **Amendments:** an amendment is another Intent with the same `run_id`, an `amends` field and a
  `changes` list. The protocol keeps every version. Each Closeout is checked against the version in
  force when the Closeout was filed.
- **Event ids:** a Notice's `event_ids` are the ids the run's Closeout gives the same events, and a
  Closeout lists its notices in `notice_ids`.
- **Surfaces:** runs that reach the same persistent shared surface (the same `surface_id`) must
  cite each other in `shared_surface_lineage`. They are reconciled as one group.

## How filings are checked

`dbyr run FOLDER` (or `dbyr.check(...)` in Python) runs these stages in order:

| Stage | Checks | Documented in |
|---|---|---|
| records | each filing on its own: the schema, then the checks for its record type | each record's doc, *Checks on this filing* |
| versions | every version of a run's Intent; Closeout cadence | [intent.md](intent.md#checks-across-filings), [closeout.md](closeout.md#checks-across-filings) |
| reconcile | each Closeout against the Intent version in force | [closeout.md](closeout.md#checks-across-filings) |
| notices | the notices each Closeout's events require | [notice.md](notice.md#checks-across-filings) |
| lineage | runs that share a persistent surface | [intent.md](intent.md#checks-across-filings) |

The checks test what a filing commits to, not whether it is true. A false filing that is specific
enough passes. Catching it needs a later check against the retained evidence, which is why the
Intent must say what evidence is kept.

### Severity

| Severity | Meaning |
|---|---|
| error | The filing is defective. A filing with an error in its own checks is not lodged, and any error fails the set. |
| conduct | The filing lodges, but it records a breach of the filer's own commitments, such as a late notice or a matched criterion with no pause. It goes to adjudication. Breaches are recorded rather than refused, so that admitting one is never costlier than hiding it. |
| warning | The filing lodges. A reviewer should look here. |

### Checks that apply to every record

| Code | Severity | Fires when | Why |
|---|---|---|---|
| `schema` | error | The filing does not match its record's schema. The message names the field. No other check runs on a filing that fails the schema. | The other checks assume a well-formed record. |
| `unknown_record_type` | error | `record_type` is not one of the three records. | |
| `intent_missing` | error | A Closeout's `run_id` has no Intent in the set. | A Closeout can only be reconciled against an Intent. |
| `unreconcilable` | error | A cross-filing stage could not run because a filing it needs is malformed. The filing's own errors say why. | |

### Citations

The *Why* column cites the evasion that motivated a check: `[T..]` is a scenario from the scripted
tabletop, and `[R1 ..]` an evasion found in round 1 of the independent tabletop.

## Disclosure tiers

Every field has a tier, shown in each record's field table. A field without its own tier takes its
parent's. Each filing is projected into three views; where a view may not show a field, it holds a
salted hash of the value instead, so a reader sees that the field exists and can later check it
against the value when it is opened.

| Tier | Shown in |
|---|---|
| public | every view |
| restricted | the restricted and sealed views; a hash in the public view |
| sealed | only the sealed view, the developer's own copy, opened under legal hold; a hash in the others |

## Shared types

### Trigger basis

The Intent's `trigger_basis` lists why DBYR covers the run: one or more of the four triggers. A run
covered for several reasons lists each. T3 and T4 cannot be left out when they apply, and T4 brings
the strictest checks.

| Trigger | Covers a run when | Must be listed when | What it adds |
|---|---|---|---|
| `T1` | its training compute is above the threshold the operator sets | the filer declares it | no checks beyond those every Intent gets |
| `T2` | the developer is a covered developer | the filer declares it | no checks beyond those every Intent gets |
| `T3` | it is forecast to reach a high or critical capability | any `predicted_capability_band` is `high` or `critical` (`t3_missing`) | no further checks; the forecast is tested through `eval_plan`, which any band above `low` needs, with or without T3 (`eval_plan_missing`) |
| `T4` | any production safeguard is relaxed or off | `safeguards_disabled.disabled` is true (`t4_missing`) | at least one working monitor (`no_monitoring_t4`); no unenforced network path (`unenforced_path_t4`); an observable, pausing criterion for each core kind (`core_kind_uncovered`); a criterion for every reportable kind (`kind_uncriteried`) |

Checks named here are described in [intent.md](intent.md#coverage).

### Other shared types

**Event kinds.** Every kind except `monitor_alert` is reportable: it must be listed in the
Closeout and needs an ExceptionNotice. An event kind can only fire a pause criterion if a declared
monitor can observe it:

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

**Evidence classes:** `trajectories` full agent transcripts; `chain_of_thought` reasoning traces;
`tool_calls` every tool invocation with its arguments; `network_logs` network flows leaving the
sandbox; `access_logs` authentication and authorisation records on reachable systems;
`inter_agent_messages` every write to a surface another agent can read, with its author;
`config_snapshots` environment, permission and surface state at each change.

**Safeguards** (Intent `safeguards_disabled.checklist`, each stated exactly once):
`model_output_filters` production classifiers on outputs; `refusal_behaviour` trained refusals;
`per_episode_reset` sandbox state wiped between episodes; `network_isolation` no route outside the
declared paths; `identity_separation` agents act under their own identity, never a person's;
`least_privilege_access` agents read only what the task needs. Optionally, `cot_monitoring` the
production chain-of-thought monitor runs on agent reasoning; at most once, not required. Each is `on`,
`relaxed` (weakened in any way) or `off`.

**Roles:** every role a filing names (pause authorities, the restart approver, signers) must be
declared in the Intent's `roles`.

### Field types

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

## Keeping these docs current

The field tables are generated from the schemas in [`dbyr/schema/`](../../dbyr/schema/), so a
field's meaning is written once, in the schema's `description`. After changing a schema, run:

```bash
dbyr docs              # rewrites the field tables in docs/records/
dbyr docs --check      # exit code 1 if a table is out of date
```

The check tables are written by hand. The tests fail if a check code exists in `dbyr/rules/` but
not here, or here but not in the code, or if a severity differs.
