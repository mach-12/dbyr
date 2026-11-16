# RunIntent

The Intent is filed before the first optimisation step, or before the first safeguards-off
evaluation, of a covered model. It turns "we were careful" into specific promises that can be
checked: what agents could reach, which safeguards were off, what would have stopped the run and
who decides, and what evidence will be kept to prove it. Its fields fall into nine groups:

| # | Group | What it answers |
|---|---|---|
| 1 | [Identity](#1-identity) | Who is filing, and for which run? |
| 2 | [What the run is](#2-what-the-run-is) | What kind of run, why DBYR covers it ([trigger basis](README.md#trigger-basis)), when, and at what scale? |
| 3 | [Capability forecast](#3-capability-forecast) | What does the developer expect the model to be able to do, and how will that be tested? |
| 4 | [Safeguards](#4-safeguards) | Which production safeguards are relaxed or off? |
| 5 | [Environment](#5-environment) | What can agents reach, write to, do and read? |
| 6 | [Monitoring](#6-monitoring) | How is the run watched? |
| 7 | [Pause criteria and restarts](#7-pause-criteria-and-restarts) | What stops the run, who decides, and how does it restart? |
| 8 | [Evidence retention](#8-evidence-retention) | What evidence is kept, so the filing can be checked later? |
| 9 | [People and investigations](#9-people-and-investigations) | Who holds each role, and what may an investigator do? |

**When:** at least 3 days before `start_window.start`, so intake review can happen. When a declared
fact changes, file an amendment: a new Intent with the same `run_id`, `amends` set to the ledger
sequence number of the Intent it amends, and `changes` saying what changed and why. Every version
is kept, and each Closeout is checked against the version in force when it was filed.

**Example:** [`dbyr/backtest/template/intent_A.json`](../../dbyr/backtest/template/intent_A.json),
a safeguards-off cyber evaluation that passes every check.

## Fields

Generated from [`run_intent.schema.json`](../../dbyr/schema/run_intent.schema.json).
Required "yes" means the schema requires it; the checks below require more. Nested fields are
written `parent.child`, and `parent[].child` for each item of a list. Types are Python type hints;
see [Field types](README.md#field-types).

<!-- fields:start -->
### 1. Identity

Who is filing, and for which run.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `schema_version` | yes | public | The schema version the filing is written against. | `Literal["0.1.0"]` |
| `record_type` | yes | public | The record type. It fixes which schema and which checks apply. | `Literal["RunIntent"]` |
| `run_id` | yes | public | Identifier of the run. Every later filing for the run (amendments, notices, closeouts) uses it. | `str` |
| `developer` | yes | public | The organisation running the training or evaluation. | `str` |
| `filed_at` | yes | public | When the Intent was filed. A first Intent must be filed at least the intake period (default 3 days) before the start. | `datetime` |
| `signer` | yes | public | Who signs the filing. | `dict` |
| `signer.role_id` | yes | public | The signing role, declared in the roles of the Intent. | `str` |
| `signer.organisation` | yes | public | The organisation the signer acts for. | `str` |
| `amends` | no | public | Ledger sequence number of the Intent this filing amends, if any. At least 0. | `int` |
| `changes` | no | public | For an amendment: what changed and why. | `list[str]` |
| `amendments_allowed` | no | public | Whether the filer may amend this Intent during the run. | `bool` |

### 2. What the run is

What kind of run it is, why DBYR covers it, when and at what scale.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `run_kind` | no | public | What the run is. training: a run that trains a model; evaluation: a run that tests a model already trained, one Intent per evaluation of at most 31 days; training_with_evaluation: one run that trains and evaluates within the same job; internal_deployment: a model used inside the developer. Required by the adequacy profile. A rolling, open-ended window is allowed only for training. | `Literal["training", "evaluation", "training_with_evaluation", "internal_deployment"]` |
| `trigger_basis` | yes | public | T1 compute threshold; T2 covered-developer status; T3 predicted high/critical capability crossing; T4 safeguards-off evaluation. | `list[Literal["T1", "T2", "T3", "T4"]]` |
| `start_window` | yes | public | When the run may operate. A Closeout period outside the window is a conduct finding. | `dict` |
| `start_window.start` | yes | public | First day of the window. | `date` |
| `start_window.end` | no | public | null means open-ended: a rolling training run. Closeouts are then due every 30 days. | `date \| None` |
| `compute_band` | yes | public | A band, never a value. Band edges are a schema parameter set by the operator. null means the filer withheld or did not know the band. | `Literal["<1e24", "1e24-1e25", "1e25-1e26", "1e26-1e27", ">=1e27", None]` |
| `run_scale` | no | restricted | How large the run is. | `dict` |
| `run_scale.concurrent_agents` | yes | restricted | The most agents running at once, at least 1. null means the filer withheld or did not know the count. | `int \| None` |
| `run_scale.human_users` | no | restricted | How many people interact with the agents. At least 0. | `int` |
| `data_classes` | no | restricted | Classes of training or evaluation data the run uses. | `list[str]` |
| `reward_design` | no | restricted | How rewards or grades are computed and where graders run. Required by the adequacy profile when run_kind is training or training_with_evaluation. | `str` |

### 3. Capability forecast

What the developer expects the model to be able to do, and how that will be tested.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `predicted_capability_band` | yes | public | The filer's forecast, per risk domain, of the capability the run will reach. A high or critical forecast requires T3; any forecast above low requires an eval_plan. | `dict` |
| `predicted_capability_band.cyber` | yes | public | Forecast band for offensive cyber capability. | `Literal["low", "medium", "high", "critical"]` |
| `predicted_capability_band.cbrn` | yes | public | Forecast band for chemical, biological, radiological and nuclear uplift. | `Literal["low", "medium", "high", "critical"]` |
| `predicted_capability_band.autonomy` | yes | public | Forecast band for autonomous operation. | `Literal["low", "medium", "high", "critical"]` |
| `predicted_capability_band.persuasion` | yes | public | Forecast band for persuasion and manipulation. | `Literal["low", "medium", "high", "critical"]` |
| `forecast_basis` | no | restricted | Evidence for predicted_capability_band. | `str` |
| `eval_plan` | no | restricted | Evaluations that test the capability forecast, required when any band is above low. | `list[dict]` |
| `eval_plan[].eval_id` | yes | restricted | Identifier of the evaluation. | `str` |
| `eval_plan[].evaluator` | yes | restricted | Whether the developer or an outside party runs it. | `Literal["internal", "external"]` |
| `eval_plan[].domain` | no | restricted | The risk domain it tests. | `str` |

### 4. Safeguards

Which production safeguards are relaxed or off.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `safeguards_disabled` | yes | public | The state of the production safeguards for this run. Any safeguard relaxed or off makes it a safeguards-off run, which must list T4. | `dict` |
| `safeguards_disabled.disabled` | yes | public | True if any checklist item is relaxed or off. 'Relaxed' counts. | `bool` |
| `safeguards_disabled.relaxed` | if `disabled` is `true` | restricted | The safeguards relaxed or off, required when disabled is true. | `list[str]` |
| `safeguards_disabled.signer_role` | if `disabled` is `true` | public | The role that authorised disabling them, required when disabled is true. | `str` |
| `safeguards_disabled.checklist` | no | public | State of every production safeguard (adequacy profile: all six, each once). | `list[dict]` |
| `safeguards_disabled.checklist[].safeguard` | yes | public | model_output_filters: production classifiers on outputs; refusal_behaviour: trained refusals; per_episode_reset: sandbox state wiped between episodes; network_isolation: no route to systems outside the declared paths; identity_separation: agents act under their own identity, never a human's; least_privilege_access: agents can read only what the task needs; cot_monitoring: the production chain-of-thought monitor runs on agent reasoning (optional item). | `Literal["model_output_filters", "refusal_behaviour", "per_episode_reset", "network_isolation", "identity_separation", "least_privilege_access", "cot_monitoring"]` |
| `safeguards_disabled.checklist[].state` | yes | public | relaxed: weakened in any way from the production configuration. | `Literal["on", "relaxed", "off"]` |
| `safeguards_disabled.checklist[].change` | no | restricted | What was changed, required unless state is on. | `str` |

### 5. Environment

What agents can reach, write to, do and read.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `agent_surface` | yes | restricted | What agents can reach and write to: the environment, network paths, credentials, writable surfaces and other runs that share them. | `dict` |
| `agent_surface.environment` | yes | restricted | Whether agents act on a replica (digital_twin), on real systems (live), or both (mixed). | `Literal["digital_twin", "live", "mixed"]` |
| `agent_surface.permitted_paths` | yes | restricted | Network paths agents may use. An empty array means no network access at all. | `list[dict]` |
| `agent_surface.permitted_paths[].path_id` | yes | restricted | Identifier of the path. A writable surface names it in via_path. | `str` |
| `agent_surface.permitted_paths[].via` | yes | restricted | What the path goes through, such as a proxy or gateway. | `str` |
| `agent_surface.permitted_paths[].enforcement` | yes | restricted | How the path's limits are enforced. none is not allowed in a safeguards-off (T4) run. | `Literal["physical_separation", "packet_filter", "proxy_allowlist", "none"]` |
| `agent_surface.permitted_paths[].agent_writable` | no | restricted | Whether agents can write through this path. Required by the adequacy profile; a writable path must be backed by a declared writable surface. | `bool` |
| `agent_surface.credential_scope` | yes | restricted | Credentials agents hold or can reach. | `dict` |
| `agent_surface.credential_scope.held_by_agents` | yes | restricted | Credentials agents are given. | `list[str]` |
| `agent_surface.credential_scope.admin_credentials_reachable` | yes | restricted | Whether agents can reach administrator credentials. | `bool` |
| `agent_surface.inter_agent_comms_permitted` | yes | restricted | True if any surface lets one agent read what another wrote, whether or not that is intended. A factual statement about the environment, not a policy choice. | `bool` |
| `agent_surface.writable_surfaces` | yes | restricted | Surfaces agents can write to, characterised rather than exhaustively enumerated. | `list[dict]` |
| `agent_surface.writable_surfaces[].surface_id` | yes | restricted | Identifier of the surface. Keep it the same across runs for the same physical surface: lineage checks match on it. | `str` |
| `agent_surface.writable_surfaces[].kind` | yes | restricted | What sort of surface it is. | `Literal["package_proxy", "artifact_store", "shared_filesystem", "cache", "database", "web_endpoint", "other"]` |
| `agent_surface.writable_surfaces[].direction` | yes | restricted | Who writes to the surface and who reads from it. | `dict` |
| `agent_surface.writable_surfaces[].direction.writers` | yes | restricted | Who can write to it: agents, runs or other parties. | `list[str]` |
| `agent_surface.writable_surfaces[].direction.readers` | yes | restricted | Who can read from it: agents, runs or other parties. | `list[str]` |
| `agent_surface.writable_surfaces[].persistence` | yes | restricted | How long writes survive: one episode (ephemeral), the run, across runs (cross_run), or permanently. | `Literal["ephemeral", "run", "cross_run", "permanent"]` |
| `agent_surface.writable_surfaces[].tenancy` | yes | restricted | run_only: nothing outside this run reads it AND agents within the run cannot read each other's writes; shared_agents: agents in this run can read each other's writes; shared_runs: other runs can read it; external: parties outside the developer can read it. | `Literal["run_only", "shared_runs", "shared_agents", "external"]` |
| `agent_surface.writable_surfaces[].detail` | no | sealed | Host names, paths and versions. Sealed: maps the attack surface. | `str` |
| `agent_surface.writable_surfaces[].via_path` | no | restricted | path_id of the permitted path through which agents reach this surface, if any. | `str` |
| `agent_surface.writable_surfaces[].isolation` | no | restricted | shared: an agent can read what another agent (in this or any run) wrote. | `Literal["per_episode", "shared"]` |
| `agent_surface.shared_surface_lineage` | yes | restricted | Other runs that can reach the same persistent surface. Reconciliation runs over linked runs. | `list[dict]` |
| `agent_surface.shared_surface_lineage[].surface_id` | yes | restricted | A surface listed in writable_surfaces. | `str` |
| `agent_surface.shared_surface_lineage[].run_id` | yes | restricted | Another run that reaches the same surface. | `str` |
| `agent_surface.inherited_exceptions` | no | restricted | Open containment exceptions on a shared surface that this run inherits. Must be cited. | `list[dict]` |
| `agent_surface.inherited_exceptions[].run_id` | yes | restricted | The run whose Closeout recorded the exception. | `str` |
| `agent_surface.inherited_exceptions[].exception_id` | yes | restricted | The exception's identifier in that Closeout. | `str` |
| `agent_capabilities` | no | restricted | Every tool or action agents can take (code execution, database queries, posting, editing). | `list[str]` |
| `readable_sources` | no | restricted | Every data source agents can read. | `list[str]` |

### 6. Monitoring

How the run is watched.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `monitoring_instruments` | yes | restricted | An empty array is a declared absence of monitoring, not an omission. | `list[dict]` |
| `monitoring_instruments[].kind` | yes | restricted | aggregate_report: counts or volume summaries; observes no individual event. | `Literal["cot_monitor", "reward_seeking_monitor", "trajectory_review", "environment_integrity_check", "access_log_review", "network_alerting", "inter_agent_message_monitor", "write_audit", "aggregate_report"]` |
| `monitoring_instruments[].coverage` | yes | restricted | How much the monitor sees: everything, a sample, or only what an alert raises. | `Literal["all", "sampled", "on_alert"]` |
| `monitoring_instruments[].review_cadence` | no | restricted | How often the monitor's output is reviewed, required when coverage is sampled. | `str` |
| `monitoring_instruments[].sample_rate` | no | restricted | Share of episodes or records reviewed, required when coverage is sampled. Range 0–1. | `float` |
| `monitoring_instruments[].alert_source` | no | restricted | What raises the alert, required when coverage is on_alert. | `str` |
| `monitoring_instruments[].data_source` | no | restricted | The log or stream the monitor reads. | `str` |

### 7. Pause criteria and restarts

What stops the run, who decides, and how it restarts.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `pause_criteria` | yes | restricted | Records an allocation the developer has already made under its own framework. Confers no authority. | `list[dict]` |
| `pause_criteria[].criterion_id` | yes | restricted | Identifier that pause events and notices cite. | `str` |
| `pause_criteria[].description` | no | restricted | The criterion in words. | `str` |
| `pause_criteria[].matches` | yes | restricted | Event kinds (see Closeout security_events[].kind) that trigger this criterion. | `list[EventKind]` |
| `pause_criteria[].adjudication` | yes | restricted | Whether a person or an automated check decides that the criterion has fired. | `Literal["human", "machine"]` |
| `pause_criteria[].authority_role` | yes | restricted | The role that decides a pause. It may not also approve restarts. | `str` |
| `pause_criteria[].required_action` | yes | restricted | What the filer commits to do when the criterion fires. pause, pause_and_review and halt_and_amend_intent count as pausing; notify_only does not. | `Literal["pause", "pause_and_review", "halt_and_amend_intent", "notify_only"]` |
| `restart_protocol` | yes | restricted | How a paused run is restarted. | `dict` |
| `restart_protocol.approver_role` | yes | restricted | The role that approves a restart. It must differ from every pause authority_role. | `str` |
| `restart_protocol.evidence_required` | yes | restricted | What must be shown before a restart is approved. | `list[str]` |
| `restart_protocol.intent_amendment_required` | yes | restricted | Whether a restart requires amending the Intent first. | `bool` |
| `containment_plan` | no | restricted | What the filer will do if containment fails. | `dict` |
| `containment_plan.on_detected_subversion` | no | restricted | The response when an agent is found subverting controls. | `str` |
| `containment_plan.full_offline_conditions` | no | restricted | When the run is taken fully offline. | `str` |

### 8. Evidence retention

What evidence is kept, so the filing can be checked later.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `log_retention` | yes | public | What evidence is kept, for how long, and how it is reviewed. | `dict` |
| `log_retention.retained` | yes | public | Evidence classes kept for the run. | `list[EvidenceClass]` |
| `log_retention.retain_until` | yes | public | Default closeout+P24M (ISO 8601 duration after closeout). Matches `^closeout\+P[0-9]+[YM]$`. | `str` |
| `log_retention.review_method` | yes | public | How retained evidence is reviewed. | `str` |
| `log_retention.minimum_preserved_pct` | no | public | The least share of generated evidence the filer commits to keep. A Closeout reporting less is a conduct finding. Range 0–100. | `float` |
| `log_retention.detail` | no | public | One entry per retained evidence class. | `list[dict]` |
| `log_retention.detail[].evidence_class` | yes | public | The class this entry describes. | `EvidenceClass` |
| `log_retention.detail[].coverage` | yes | public | Whether every record of the class is kept, or a sample. | `Literal["complete", "sampled"]` |
| `log_retention.detail[].sample_rate` | no | public | Share of records kept, required when coverage is sampled. Range 0–1. | `float` |
| `log_retention.detail[].retention` | yes | public | How long this class is actually kept after it is written. Matches `^(P[0-9]+[DMY]\|indefinite)$`. | `str` |

### 9. People and investigations

Who holds each role, and what a post-incident investigator may do.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `roles` | yes | public | Titles are public; contacts restricted; identities sealed and recoverable only under legal hold. | `list[dict]` |
| `roles[].role_id` | yes | public | Identifier other fields use to name the role. | `str` |
| `roles[].title` | yes | public | The role's title. | `str` |
| `roles[].organisation` | yes | public | The organisation the role belongs to. | `str` |
| `roles[].contact_channel` | no | restricted | How to reach the role holder. | `str` |
| `roles[].id_hash` | no | sealed | Hash of the role holder's identity, recoverable only under legal hold. | `str` |
| `investigator_scope_expansion` | yes | public | Standing right for a post-incident investigator to extend scope on stated grounds; extensions and refusals are logged. | `dict` |
| `investigator_scope_expansion.committed` | yes | public | Always true: the filer grants the standing right. | `Literal[True]` |
| `investigator_scope_expansion.refusals_logged` | yes | public | Always true: every refusal is logged in the Closeout. | `Literal[True]` |
| `investigator_scope_expansion.model_access_committed` | no | public | Whether an investigator may also access the model. | `bool` |
<!-- fields:end -->

## Checks on this filing

These run when the Intent is filed. An error stops it being lodged.

### Consistency

| Code | Severity | Fires when | Why |
|---|---|---|---|
| `unknown_role` | error | A role named in `safeguards_disabled.signer_role`, a criterion's `authority_role`, `restart_protocol.approver_role` or `signer.role_id` is not declared in `roles`. | Every decision must trace to a declared role. |
| `t4_missing` | error | `safeguards_disabled.disabled` is true but `trigger_basis` does not list `T4`. | A safeguards-off run carries the T4 duties whatever else covers it. |
| `lineage_unknown_surface` | error | `shared_surface_lineage` names a surface that is not in `writable_surfaces`. | |
| `shared_surface_without_lineage` | warning | A surface persists across runs and is shared, but no other run is listed for it. | Confirm this is the first run to reach it. |
| `no_monitoring_declared` | warning | `monitoring_instruments` is empty. | A Closeout attesting no events then carries little weight. |
| `trajectories_not_retained` | warning | `log_retention.retained` does not include `trajectories`. | Behavioural events cannot be checked afterwards. |

### Coverage

Whether the declared monitors and criteria can actually catch what they promise to.

| Code | Severity | Fires when | Why |
|---|---|---|---|
| `t3_missing` | error | A capability band is forecast `high` or `critical` but `trigger_basis` does not list `T3`. | The forecast and the trigger cannot disagree. |
| `no_monitoring_t4` | error | A safeguards-off (T4) run declares no monitor that observes anything. | [T07] |
| `unenforced_path_t4` | error | A safeguards-off run declares a network path with `enforcement: none`. | [T08] |
| `writability_undeclared` | error | A permitted path does not state `agent_writable`. | [T01] |
| `writable_path_without_surface` | error | A path is agent-writable but no writable surface names it in `via_path`. | What agents can write through must be declared as a surface. [T01] |
| `dead_criterion` | error | No declared monitor can observe any of a pause criterion's event kinds, so the criterion cannot fire. | A criterion nothing can see is a promise that costs nothing. [T02] |
| `partly_blind_criterion` | warning | No declared monitor can observe some of a criterion's event kinds. | |
| `core_kind_uncovered` | error | A safeguards-off run has no observable, pausing criterion for one of the core kinds: `sandbox_escape`, `privilege_escalation`, `third_party_compromise`, and `inter_agent_comms` unless communication is permitted (then the three checks below apply). | [T03, T04] |
| `comms_channel_undeclared` | error | Inter-agent communication is permitted but no surface is shared between agents or runs. | Coordination must run over a declared channel. [T06] |
| `comms_not_retained` | error | Inter-agent communication is permitted but `inter_agent_messages` is not retained. | [T06] |
| `comms_unmonitored` | error | Inter-agent communication is permitted but neither an `inter_agent_message_monitor` nor `trajectory_review` watches it. | [T06] |
| `run_kind_undeclared` | error | `run_kind` is missing. | Run kind cannot be inferred from the trigger basis: an evaluation can also carry T3. [T05] |
| `standing_intent` | error | An evaluation has no end date, or its window is longer than 31 days. | One Intent per evaluation, not a standing filing. [T05] |

### Completeness

Whether the facts a later investigation needs are stated.

| Code | Severity | Fires when | Why |
|---|---|---|---|
| `safeguard_checklist_missing` | error | `safeguards_disabled.checklist` is missing. | Relaxing a safeguard counts as disabling it, so every safeguard's state must be stated. [R1 S2-E1, S3-E9] |
| `safeguard_checklist_incomplete` | error | The checklist does not name each of the six safeguards exactly once. | [R1 S2-E1, S3-E9] |
| `disabled_inconsistent` | error | `disabled` is not true exactly when some checklist item is `relaxed` or `off`. | Calling a weakening a relaxation cannot escape the T4 duties. [R1 S2-E1, S3-E9] |
| `safeguard_change_missing` | error | A safeguard that is not `on` does not say what was changed. | |
| `monitor_unspecified` | error | A sampled monitor lacks `sample_rate` or `review_cadence`, an on-alert monitor lacks `alert_source`, or any monitor lacks `data_source`. | A monitor must say how much it sees and what feeds it. [R1 S2-E4, S3-E6] |
| `isolation_undeclared` | error | A writable surface does not state `isolation`. | [R1 S2-E3] |
| `tenancy_mislabelled` | error | A surface agents share (`isolation: shared`) is labelled `run_only`. | |
| `comms_flag_inconsistent` | error | A surface lets agents read each other's writes but `inter_agent_comms_permitted` is false. | The duty follows the surface, so denying communication does not remove it. [R1 S2-E3] |
| `shared_surface_floor` | error | A run with a surface agents share has no observable, pausing criterion for `environment_tampering`, or no observable criterion for `inter_agent_comms`. | [R1 S2-E3] |
| `kind_uncriteried` | error | A safeguards-off run has a reportable event kind that no criterion matches (`notify_only` is enough beyond the core kinds). | Classifying an event as a different kind cannot route it around every duty. [R1 S3-E3, S3-E4] |
| `retention_too_short` | error | `retain_until` is less than 12 months after closeout. | [R1 S2-E9, S3-E7] |
| `retention_detail_missing` | error | A retained evidence class has no `detail` entry, or a sampled class has no `sample_rate`. | Retention is stated per class, with its coverage. [R1 S2-E9, S3-E7] |
| `retention_class_short` | error | A class is kept for less time than `retain_until`. | [R1 S2-E9, S3-E7] |
| `preservation_floor_missing` | error | `log_retention.minimum_preserved_pct` is missing. | The Closeout's preservation is checked against it. |
| `field_missing` | error | `agent_capabilities`, `readable_sources`, `run_scale` or `forecast_basis` is missing, or a training run has no `reward_design`. | [R1 S2-E10, S2-E12, S3-E8, S3-E14, S3-E15] |
| `eval_plan_missing` | error | A capability band is forecast above `low` but there is no `eval_plan`. | A forecast must be tested. |
| `end_undeclared` | error | `start_window` has no `end` (null is allowed, for an open-ended training run), or an evaluation or deployment has a null end. | [R1 S2-E10] |
| `no_intake_time` | error | A first Intent is filed less than 3 days before the start. | Intake review needs time. [R1] |
| `amendment_without_changes` | error | An amendment has no `changes`. | [R1 S3-E2] |
| `self_approved_restart` | error | `restart_protocol.approver_role` is also a role that decides pauses. | Whoever pauses a run must not also restart it. [R1 S2-E11, S3-E13] |

## Checks across filings

### Versions

Run over every version of a run's Intent.

| Code | Severity | Fires when | Why |
|---|---|---|---|
| `standing_intent` | error | The versions of an evaluation or deployment Intent together cover more than 31 days. | Chaining date-only amendments cannot turn an evaluation into a standing filing. [R1 judge item 9; S3-E2] |

### Lineage

Run over every Intent in the set, and the Closeouts filed before each.

| Code | Severity | Fires when | Why |
|---|---|---|---|
| `lineage_not_cited` | error | An earlier run reaches the same persistent shared surface and this Intent does not cite it in `shared_surface_lineage`. | Runs that share a surface are reconciled together. |
| `inherited_exception_not_cited` | error | A containment exception on a surface this run reaches was on record, and still open, when this Intent was filed, but it is not cited in `inherited_exceptions`. | A run must not inherit a known breach silently. |
| `tenancy_conflict` | error | Two runs declare the same surface, one as `run_only` and the other as shared. | They cannot both be right. [T13] |
