# ExceptionNotice

An interim filing. It closes the gap between a fast incident and a Closeout that may be 30 days
away: when the developer detects a reportable event (every kind except `monitor_alert`), it says
what was detected, when, and what was done about it. It records detection; it does not detect.

**When:** within 72 hours of `detected_at`. One notice may cover several events; list each in
`event_ids`, using the ids the run's Closeout will give the same events. The Closeout lists the
notices filed in its period in `notice_ids`.

**Example:** [`notice_N1.json`](../../dbyr/backtest/template/notice_N1.json).

## Fields

Generated from [`exception_notice.schema.json`](../../dbyr/schema/exception_notice.schema.json).
See [field types](README.md#field-types) and [disclosure tiers](README.md#disclosure-tiers).

<!-- fields:start -->
### 1. Identity

Who is filing, and for which run.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `schema_version` | yes | public | The schema version the filing is written against. | `Literal["0.1.0"]` |
| `record_type` | yes | public | The record type. It fixes which schema and which checks apply. | `Literal["ExceptionNotice"]` |
| `notice_id` | yes | public | Identifier of the notice. The run's Closeout lists it in notice_ids. | `str` |
| `run_id` | yes | public | The run the events happened in. | `str` |
| `filed_at` | yes | public | When the notice was filed: within the notice deadline (default 72 hours) of detected_at. | `datetime` |
| `signer` | yes | public | Who signs the filing. | `dict` |
| `signer.role_id` | yes | public | The signing role, declared in the roles of the Intent. | `str` |
| `signer.organisation` | yes | public | The organisation the signer acts for. | `str` |

### 2. What was detected

What happened, and when the developer found out.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `detected_at` | yes | public | When the developer detected the events. | `datetime` |
| `event_ids` | yes | public | Identifiers that the run's Closeout will use for the same events. | `list[str]` |
| `kinds` | yes | public | The event kinds reported. | `list[EventKind]` |
| `summary` | no | restricted | What happened, in words. | `str` |

### 3. What it touches

Which of the Intent's pause criteria it matched, and who outside was affected.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `criterion_ids` | no | restricted | The Intent's pause criteria the events matched, if any. | `list[str]` |
| `affected_parties` | no | restricted | External organisations affected. | `list[str]` |

### 4. Response

What the developer did about it.

| Field | Required | Tier | Meaning | Type |
|---|---|---|---|---|
| `action_taken` | yes | public | What the filer did in response. none records that nothing was done. | `Literal["pause", "pause_and_review", "halt_and_amend_intent", "notify_only", "none"]` |
<!-- fields:end -->

## Checks when filed

| Code | Severity | Fires when | Why |
|---|---|---|---|
| `notice_before_detection` | error | `filed_at` is earlier than `detected_at`. | |

## Checks across filings

Run when the run's Closeout is filed: each reportable event it lists is matched to the notices for
the same run.

| Code | Severity | Fires when | Why |
|---|---|---|---|
| `notice_missing` | error | A reportable event in the Closeout, with a detection time, is cited by no notice. | The duty follows a fixed list of reportable kinds, not the criteria the filer chose, so declaring criteria no likely event would match does not remove it. [T09; R1 S2-E2, S3-E3] |
| `notice_late` | conduct | The first notice citing an event was filed more than 72 hours after detection. | [T09] |
| `notice_not_listed` | error | A notice was filed for the run but the Closeout's `notice_ids` does not list it (checked only when `notice_ids` is given). | |
