# RunCloseout

The Closeout says what actually happened in a period of the run: every reportable event detected,
every pause, every containment failure, who was told, what investigators asked for and were given,
and how much of the evidence is still held. It is then checked against the Intent, so a gap between
what was declared and what happened shows up as a finding.

**When:** when the run completes or is aborted, and at least every 30 days while it runs.
Consecutive Closeouts must leave no gap between periods.

**Clearing a run for downstream use:** a run's latest Closeout states, in
`cleared_for_system_integration`, whether the model it produced may be built on.

**Completeness:** `security_events` and `integrity_events` list every event of a reportable kind
detected in the period. An empty list is a statement that none was detected, so the Closeout must
also say whether absence is attested (`attested_absence`) and on what basis (`absence_basis`).

Its fields fall into eight groups:

| # | Group | What it answers |
|---|---|---|
| 1 | [Identity and period](#1-identity-and-period) | Who is filing, for which run, which days does it cover, and what state is it in? |
| 2 | [Events](#2-events) | What was detected in the period, or why was nothing? |
| 3 | [Pauses](#3-pauses) | What did the run do each time a pause criterion fired? |
| 4 | [Containment and changes](#4-containment-and-changes) | Where did containment fail, and what changed mid-run? |
| 5 | [Third parties](#5-third-parties) | Who outside was affected, and were they told in time? |
| 6 | [Evidence](#6-evidence) | How much of the promised evidence is still held? |
| 7 | [Investigations](#7-investigations) | What did investigators ask for, and what were they given? |
| 8 | [Outcome](#8-outcome) | Which evaluations ran, what risk remains, and may the model be deployed? |

**Example:** [`dbyr/backtest/template/closeout_A.json`](../../dbyr/backtest/template/closeout_A.json).

## Fields

Generated from [`run_closeout.schema.json`](../../dbyr/schema/run_closeout.schema.json).
Required "yes" means the schema requires it; the checks below require more. Nested fields are
written `parent.child`, and `parent[].child` for each item of a list. Types are Python type hints;
see [Field types](README.md#field-types).

<!-- fields:start -->
### 1. Identity and period

Who is filing, for which run, which days it covers, and its state.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `schema_version` | yes | public | The schema version the filing is written against. | `Literal["0.1.0"]` |
| `record_type` | yes | public | The record type. It fixes which schema and which checks apply. | `Literal["RunCloseout"]` |
| `run_id` | yes | public | The run this Closeout closes. It must match the Intent's run_id. | `str` |
| `filed_at` | yes | public | When the Closeout was filed. It is checked against the Intent version in force at this time. | `datetime` |
| `signer` | yes | public | Who signs the filing. | `dict` |
| `signer.role_id` | yes | public | The signing role, declared in the roles of the Intent. | `str` |
| `signer.organisation` | yes | public | The organisation the signer acts for. | `str` |
| `period_start` | yes | public | First day the Closeout covers. | `date` |
| `period_end` | yes | public | Last day the Closeout covers. One Closeout may cover at most 30 days (default). | `date` |
| `status` | yes | public | The run's state at the end of the period. Only training runs may be rolling. | `Literal["completed", "aborted", "paused", "rolling"]` |

### 2. Events

What was detected in the period, or why nothing was.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `security_events` | yes | restricted | Every event of a reportable kind (any event_kind except monitor_alert) that the developer detected in the period. Completeness is required: an empty list is a statement that none was detected. | `list[dict]` |
| `security_events[].event_id` | yes | restricted | Identifier of the event. Notices, pause events and notifications cite it. | `str` |
| `security_events[].at` | yes | restricted | When the event happened. | `datetime` |
| `security_events[].kind` | yes | restricted | What kind of event it was. | `EventKind` |
| `security_events[].description` | yes | restricted | What happened. | `str` |
| `security_events[].evidence` | yes | restricted | Evidence classes a V1 reconciliation would check this event against. | `list[EvidenceClass]` |
| `security_events[].affected_parties` | no | restricted | External organisations affected. Each must appear in third_party_notifications. | `list[str]` |
| `security_events[].detected_at` | no | restricted | When the developer detected the event. Starts the interim-notice and notification clocks. Required by the adequacy profile. | `datetime` |
| `security_events[].classification_rationale` | no | restricted | Why this kind and not a neighbouring one. | `str` |
| `integrity_events` | no | restricted | Events of kind environment_tampering or integrity_incident; same completeness duty as security_events. | `list[dict]` |
| `integrity_events[].event_id` | yes | restricted | Identifier of the event. Notices, pause events and internal incidents cite it. | `str` |
| `integrity_events[].at` | yes | restricted | When the event happened. | `datetime` |
| `integrity_events[].kind` | yes | restricted | What kind of event it was. | `EventKind` |
| `integrity_events[].description` | yes | restricted | What happened. | `str` |
| `integrity_events[].evidence` | yes | restricted | Evidence classes a V1 reconciliation would check this event against. | `list[EvidenceClass]` |
| `integrity_events[].affected_parties` | no | restricted | External organisations affected. Each must appear in third_party_notifications. | `list[str]` |
| `integrity_events[].detected_at` | no | restricted | When the developer detected the event. Starts the interim-notice and notification clocks. Required by the adequacy profile. | `datetime` |
| `integrity_events[].classification_rationale` | no | restricted | Why this kind and not a neighbouring one. | `str` |
| `attested_absence` | no | public | Required by the adequacy profile. True asserts that no reportable event was detected; then absence_basis is required. | `bool` |
| `absence_basis` | no | public | Which monitors, at what coverage, support the absence claim. | `str` |
| `internal_incidents` | no | restricted | Every internal incident ticket opened about the run, mapped to events or explained. | `list[dict]` |
| `internal_incidents[].incident_id` | yes | restricted | The internal ticket's identifier. | `str` |
| `internal_incidents[].opened_at` | yes | restricted | When the ticket was opened. | `datetime` |
| `internal_incidents[].closed_at` | no | restricted | When the ticket was closed. | `datetime` |
| `internal_incidents[].summary` | no | restricted | What the ticket was about. | `str` |
| `internal_incidents[].event_ids` | no | restricted | The events the ticket maps to. | `list[str]` |
| `internal_incidents[].not_an_event_reason` | no | restricted | Why the ticket is not an event, required when it maps to none. | `str` |
| `notice_ids` | no | public | ExceptionNotices filed for this run during the period. | `list[str]` |

### 3. Pauses

What the run did each time a pause criterion fired.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `pause_events` | yes | restricted | Every time a pause criterion fired in the period, and what was done. | `list[dict]` |
| `pause_events[].criterion_id` | yes | restricted | The Intent criterion that fired. | `str` |
| `pause_events[].triggering_event_ids` | no | restricted | The events that triggered it. An event that matches a criterion but is cited by no pause event is a conduct finding. | `list[str]` |
| `pause_events[].triggered_at` | yes | restricted | When the criterion fired. | `datetime` |
| `pause_events[].triggered_by_role` | yes | restricted | The role that called it. | `str` |
| `pause_events[].action_taken` | yes | restricted | What was actually done. none records that the run did not pause. | `Literal["pause", "pause_and_review", "halt_and_amend_intent", "notify_only", "none"]` |
| `pause_events[].restart` | no | restricted | The restart, or null if the run did not restart. | `dict \| None` |
| `pause_events[].restart.approved_by_role` | yes | restricted | The role that approved the restart. A role other than the Intent's approver_role is a conduct finding. | `str` |
| `pause_events[].restart.approved_at` | yes | restricted | When the restart was approved. | `datetime` |
| `pause_events[].restart.evidence` | yes | restricted | What was shown to approve the restart. | `list[str]` |
| `pause_events[].restart.intent_amended` | no | restricted | Whether the Intent was amended before the restart. | `bool` |

### 4. Containment and changes

Where containment failed, and what changed mid-run.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `containment_exceptions` | yes | restricted | Every breach of declared containment in the period: network, communication, credential or write. | `list[dict]` |
| `containment_exceptions[].exception_id` | yes | restricted | Identifier of the exception. A later run reaching the same surface cites it in inherited_exceptions while it is open. | `str` |
| `containment_exceptions[].surface_id` | yes | restricted | The surface where it happened. | `str` |
| `containment_exceptions[].declared_surface` | yes | restricted | False when the surface was not in the Intent's agent_surface: the expected completeness failure. | `bool` |
| `containment_exceptions[].kind` | yes | restricted | What escaped containment. | `Literal["network", "comms", "credential", "write"]` |
| `containment_exceptions[].opened_at` | yes | restricted | When the exception opened. | `datetime` |
| `containment_exceptions[].closed_at` | no | restricted | When it closed, required when status is closed. | `datetime` |
| `containment_exceptions[].status` | yes | restricted | Whether the exception is still open. | `Literal["open", "closed"]` |
| `containment_exceptions[].linked_runs` | no | restricted | Other runs that reach the same surface. | `list[str]` |
| `config_changes` | no | restricted | Every change to the environment, permissions or surfaces during the period. | `list[dict]` |
| `config_changes[].at` | yes | restricted | When it changed. | `datetime` |
| `config_changes[].what` | yes | restricted | What changed. | `str` |
| `config_changes[].intent_amended` | yes | restricted | Whether the Intent was amended for it. | `bool` |
| `surface_resets` | no | restricted | Every reset of a writable surface during the period. | `list[dict]` |
| `surface_resets[].at` | yes | restricted | When the surface was reset. | `datetime` |
| `surface_resets[].surface_id` | yes | restricted | The surface that was reset. | `str` |
| `surface_resets[].snapshot_retained` | yes | restricted | Whether a snapshot was kept. A reset without one while an internal incident is open is a conduct finding. | `bool` |

### 5. Third parties

Who outside was affected, and whether and when they were told.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `third_party_notifications` | yes | public | One entry per affected external party: whether and when it was told, or why not. Party names are restricted (naming a victim can expose an unpatched system); the counts and timing are public. | `list[dict]` |
| `third_party_notifications[].party` | yes | restricted | The affected organisation. | `str` |
| `third_party_notifications[].affected_by` | yes | restricted | The events that affected it. | `list[str]` |
| `third_party_notifications[].notified` | yes | public | Whether it was told. | `bool` |
| `third_party_notifications[].notified_at` | if `notified` is `true` | public | When it was told. Later than the deadline (default 72 hours) after detection needs a delay_reason. | `datetime` |
| `third_party_notifications[].channel` | no | restricted | How it was told. | `str` |
| `third_party_notifications[].not_notified_reason` | if `notified` is not `true` | restricted | Why it was not told. | `str` |
| `third_party_notifications[].delay_reason` | no | restricted | Required by the adequacy profile when notification came later than the deadline after detection. | `str` |

### 6. Evidence

How much of the evidence the Intent promised to keep is still held.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `preservation` | no | public | Per evidence class: what share of what was generated is held. | `list[dict]` |
| `preservation[].evidence_class` | yes | public | The class this entry describes. | `EvidenceClass` |
| `preservation[].denominator` | yes | public | What 100% means: the records of this class the run generated. | `str` |
| `preservation[].sample_rate` | yes | public | Share of generated records that were captured. Range 0–1. | `float` |
| `preservation[].preserved_pct` | yes | public | Percentage of captured records still held. Range 0–100. | `float` |
| `preservation[].earliest_record` | no | public | When the earliest record held was written. | `datetime` |
| `logs_preserved_pct` | yes | public | The weakest class: the minimum over preservation[] of sample_rate x preserved_pct. Not an average and not a share of what the developer chose to keep. Range 0–100. | `float` |
| `logs_retention_confirmed` | no | public | Whether the filer confirms that the retention declared in the Intent is in place. | `bool` |

### 7. Investigations

What post-incident investigators asked for, and what they were given.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `scope_requested_vs_granted` | yes | public | Each post-incident investigator: the scope asked for, the scope given, and any refusals. | `list[dict]` |
| `scope_requested_vs_granted[].investigator` | yes | public | Who investigated. | `str` |
| `scope_requested_vs_granted[].requested` | yes | public | The period the investigator asked to examine. | `dict` |
| `scope_requested_vs_granted[].requested.start` | yes | public | First day of the window. | `date` |
| `scope_requested_vs_granted[].requested.end` | no | public | null means open-ended: a rolling training run. Closeouts are then due every 30 days. | `date \| None` |
| `scope_requested_vs_granted[].granted` | yes | public | The period the investigator was allowed to examine. A grant narrower than the request needs a logged refusal. | `dict` |
| `scope_requested_vs_granted[].granted.start` | yes | public | First day of the window. | `date` |
| `scope_requested_vs_granted[].granted.end` | no | public | null means open-ended: a rolling training run. Closeouts are then due every 30 days. | `date \| None` |
| `scope_requested_vs_granted[].model_access_granted` | no | public | Whether the investigator was given access to the model. | `bool` |
| `scope_requested_vs_granted[].refusals` | yes | public | Each request that was refused. | `list[dict]` |
| `scope_requested_vs_granted[].refusals[].at` | yes | public | When it was refused. | `datetime` |
| `scope_requested_vs_granted[].refusals[].what` | yes | public | What was refused. | `str` |
| `scope_requested_vs_granted[].refusals[].grounds` | yes | public | Why it was refused. | `str` |
| `scope_requested_vs_granted[].refusals[].refused_by_role` | yes | public | The role that refused it. | `str` |

### 8. Outcome

Which evaluations ran, what risk remains, and whether the model may be deployed.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `evals_planned_vs_run` | no | restricted | The Intent's eval_plan set against the evaluations actually run. | `list[dict]` |
| `residual_risk` | no | restricted | Risk that remains after the run. | `str` |
| `cleared_for_system_integration` | no | public | Whether the model this run produced is cleared to be built on downstream. | `bool` |
<!-- fields:end -->

## Checks on this filing

These run when the Closeout is filed. An error stops it being lodged.

### Consistency

| Code | Severity | Fires when | Why |
|---|---|---|---|
| `absence_contradicted` | error | `attested_absence` is true but security events are listed. | |
| `period_inverted` | error | `period_end` is before `period_start`. | |
| `affected_party_unaccounted` | error | An event names an affected party that has no entry in `third_party_notifications`. | Every affected party is either told or a reason is given. |
| `notification_unknown_event` | error | A notification's `affected_by` names an event not in `security_events`. | |
| `notified_before_event` | error | A party is recorded as told before the first event it was told about. | |
| `undeclared_surface` | warning | A containment exception is on a surface the Intent did not declare. | The expected completeness failure: amend the Intent. |
| `closed_without_time` | error | A closed containment exception has no `closed_at`. | |
| `silent_scope_narrowing` | error | An investigator was granted a narrower period than requested and no refusal is logged. | |

### Timeliness

| Code | Severity | Fires when | Why |
|---|---|---|---|
| `detection_time_missing` | error | A security or integrity event has no `detected_at`. | Detection starts the notice and notification clocks. |
| `detected_before_event` | error | `detected_at` is earlier than the event. | |
| `late_notification` | error | A party was told more than 72 hours after detection and no `delay_reason` is given. | [T10] |

### Completeness

| Code | Severity | Fires when | Why |
|---|---|---|---|
| `absence_not_attested` | error | `attested_absence` is missing. | Completeness is attested, not implied by an empty list. [R1 S2-E6] |
| `absence_basis_missing` | error | No events are listed and there is no `absence_basis`, or absence is attested without one. | The basis says which monitors support the claim, or why absence cannot be attested, so a weakly monitored run can still file honestly. [R1 S2-E6] |
| `absence_not_supportable` | warning | No events are listed and absence is not attested. | The stated basis explains why. |
| `classification_rationale_missing` | error | An event has no `classification_rationale`. | Classification is the filer's choice, so it must be argued. [R1 S3-E3] |
| `field_missing` | error | `integrity_events`, `internal_incidents`, `config_changes` or `surface_resets` is missing. Each may be empty. | [R1 S2-E5, S2-E8, S3-E10] |
| `incident_unmapped` | error | An internal incident maps to no event and gives no `not_an_event_reason`. | Every internal ticket about the run is mapped to an event or explained. [R1 S2-E5, S3-E10] |
| `incident_unknown_event` | error | An internal incident names an event that is not listed. | |
| `preservation_missing` | error | `preservation` is missing or empty. | Preservation is stated per evidence class. [R1 S2-E7, S3-E12] |
| `preservation_overstated` | error | `logs_preserved_pct` is higher than the weakest class (`sample_rate` × `preserved_pct`). | The headline figure is the weakest class, not an average. [R1 S2-E7, S3-E12] |
| `evidence_destroyed` | conduct | A surface was reset without a snapshot while an internal incident was open. | [R1 S2-E8] |
| `change_without_amendment` | warning | A configuration change was made without amending the Intent. | Confirm it changes no declared fact. |

## Checks across filings

### Reconciliation with the Intent

Each Closeout is checked against the Intent version in force when it was filed. This checks that the
filings agree with each other; an auditor then checks them against the retained evidence.

| Code | Severity | Fires when | Why |
|---|---|---|---|
| `run_mismatch` | error | The Closeout's `run_id` differs from the Intent it is checked against. | |
| `criterion_matched_no_pause_event` | conduct | An event matches a declared pause criterion but no pause event cites it. | The run did not do what its Intent committed to. |
| `evidence_not_retained` | warning | An event cites an evidence class the Intent did not declare retained. | |
| `unknown_criterion` | error | A pause event cites a criterion that is not in the Intent. | |
| `unknown_role` | error | A pause event's `triggered_by_role` is not declared in the Intent's `roles`. | |
| `action_differs` | warning | A pause event's `action_taken` differs from the criterion's `required_action`. | |
| `restart_wrong_approver` | conduct | A restart was approved by a role other than the Intent's `restart_protocol.approver_role`. | |
| `restart_without_amendment` | conduct | The restart protocol requires an Intent amendment and the restart records none. | |
| `declared_flag_wrong` | error | A containment exception's `declared_surface` disagrees with the Intent's `writable_surfaces`. | |
| `retention_below_floor` | conduct | `logs_preserved_pct` is below the Intent's `minimum_preserved_pct`. | |
| `absence_unsupported` | error | Absence of events is attested, but no declared monitor could observe one of the core kinds. | Attested absence is only as strong as the monitoring behind it. [T19; R1 S2-E6] |
| `preservation_incomplete` | error | An evidence class the Intent retains has no `preservation` entry. | |
| `rolling_not_training` | error | `status` is `rolling` but the run is not a training run. | [R1 S3-E2] |

### Cadence

Run over every Closeout of a run, against the Intent version in force for each.

| Code | Severity | Fires when | Why |
|---|---|---|---|
| `closeout_overdue` | conduct | One Closeout covers more than 30 days. | A late Closeout is recorded, not refused. [R1 judge item 9; S3-E2] |
| `closeout_gap` | conduct | No Closeout covers the days between two periods. | |
| `period_outside_window` | conduct | A period falls outside the Intent's `start_window`. | The run operated outside its declared window. |
