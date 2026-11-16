# Writing `decision_points.json`

Decision points belong to the backtest, not to the DBYR protocol. **They are never filed.** A lab
using DBYR files Intents, Notices, Closeouts and runtime records, and nothing else. Decision points
are written only when someone tests the protocol against an incident: they are the questions an
investigator asks afterwards, and the backtest counts how many the lab's records would have answered.

**Who writes them.** For a past incident, researchers working from the public account of it, and
not the person who reconstructed the filings. Never the lab whose incident it is: a lab could leave
out the decisions that make it look bad. If DBYR were used to review a real incident, the
independent investigator would write them, and the lab could propose additions but not remove any.

`decision_points.json` is a case's scoring plan. **You write it; dbyr does not generate it.** It
says which decisions shaped the incident and, for each, what a filing should have recorded before
the decision and what the Closeout should show after it. dbyr then scores each decision point
against the filings.

It is pre-registered: write it before you score, and do not edit it afterwards. To keep the
scoring independent, the person who writes it should not be the person who wrote the filings.

> **Format status.** This page documents the current format, used by
> `benchmarks/openai-2026/decision_points.json` and `benchmarks/aisi-2026/decision_points.json`.
> `dbyr/backtest/case.py` normalises both this format and the previous one, so `dbyr backtest check`
> accepts a case in either. `dbyr backtest init` still writes the previous format, and its output
> needs converting by hand. The old field names are listed under
> [What changed](#what-changed) at the end.

## What counts as a decision point

> A decision point is a moment at which an identifiable actor, with an alternative actually
> available to them at that time, chose a course of action or left one unchosen, such that the
> alternative would plausibly have changed the outcome.

Four elements, and a candidate must pass all four:

| Element | Test | Fails when |
|---|---|---|
| **Actor** | Can you name the role or organisation that decided? | It was an agent's action or a system condition |
| **Time** | Can you date it, at least to a range? | It is a standing state with no moment of choice |
| **Available alternative** | Could the actor have chosen otherwise with the information and means they had *then*? | The alternative only became visible afterwards |
| **Consequence** | Would the alternative plausibly have changed the outcome? | The outcome would have been the same either way |

The third test is the one that does most of the work. It applies the *local rationality* principle
from accident investigation: judge a choice by what the person could know and do at the time, not by
what the outcome later revealed.

**A decision point is never the fact the developer did not know. It is the choice that left them not
knowing.** That a partner's environment had an open route to the internet is a condition nobody
chose knowingly, so it is not a decision point. *Running the evaluation without first validating its
network paths* is one, because checking was available at the time. The unknown fact tells you where
to look; the decision point is the choice upstream of it.

Record the definition you applied in the top-level `definition` key, so a reader can see which bar a
candidate had to clear.

### Finding them

1. Lay the public sources out as a dated timeline.
2. Work backwards from each harm, asking "what allowed this?", until the answer is a choice by a
   person or organisation rather than an agent action or a condition.
3. Apply the four tests and discard anything that fails one — recording it under
   `retired_decision_points` rather than deleting it.
4. Set `choice` to `taken` or `not_taken`.
5. Record the knowledge state in `developer_knew`: this feeds the as-believed filer.
6. Split compound candidates so each has one actor and one date; merge duplicates.
7. Stop at the planning of the run. Company-wide strategy, such as how fast to ship models, is
   outside what a run-level protocol can reach.
8. Freeze the list before reconstructing any filing.

The actor may sit outside the developer. A partner's configuration choice is a decision point with
the partner as its actor; tag it as such, so the scoring can show which decisions a developer's own
filing could reach at all.

## How to start one

Copy `benchmarks/openai-2026/decision_points.json`, delete its decision points, and replace the
`filings` map with your own. Set `freeze.schema_hash` to what `dbyr freeze` prints before you write
any filing.

`dbyr backtest init` still writes the previous format; its output needs converting by hand.

## The file at a glance

```jsonc
{
  "case_id": "my-case",                      // required: the case's name, same as its folder
  "in_sample": false,                        // true only for the case the schema was derived from
  "definition": "A decision point is …",     // the bar a candidate had to clear

  "freeze": {                                // when the plan was fixed, and what changed since
    "schema_hash": "sha256:…",
    "revisions": [
      {"on": "2026-11-13", "pre_registered": false, "reason": "…"}
    ]
  },

  "filings": {                               // required: where the filings are, and how they relate
    "intent:A":   {"file": "intent_run_a.json"},
    "closeout:A": {"file": "closeout_run_a.json", "closes": "intent:A"},
    "notice:N0":  {"file": "notice_n0.json"}
  },

  "filers": {                                // required: at least one
    "diligent":    {"description": "Declares the configuration as it was.", "role": "Upper bound.",
                    "edits": {}},
    "as_believed": {"description": "…", "role": "Headline.",
                    "edits": {"drop_writable_surfaces": {"intent:A": ["scratch-dir"]}}}
  },

  "decision_points": [ { … }, { … } ],       // required: at least one

  "retired_decision_points": [ { … } ]       // candidates excluded, each with the test it failed
}
```

## Top-level keys

| Key | Required | What it holds |
|---|---|---|
| `case_id` | yes | The case's name, used in reports and results. Keep it the same as the folder name. |
| `freeze` | recommended | `schema_hash` is what `dbyr freeze` printed before the filings were written; if the schema changes, `check` fails and `score` refuses. `revisions` is a dated log of every edit after the first freeze, each with `pre_registered: false` if it was made after scoring. |
| `filings` | yes | Each filing's key maps to an object. `file` is its path, relative to this file. You choose the keys; `intent:A`, `closeout:A`, `notice:N1` is the convention. |
| `filers` | yes | The filer types, described below. |
| `decision_points` | yes | The decision points, described below. |
| `definition` | recommended | The definition a candidate had to meet to be listed, quoted in full. See [What counts as a decision point](#what-counts-as-a-decision-point). |
| `in_sample` | recommended | `true` for the case the schema was derived from. Its scores show traceability, not validation. |
| `retired_decision_points` | recommended | Candidates considered and excluded, each with the test it failed. See [Retired decision points](#retired-decision-points). |
| `table2_selection_rule` | optional | The one rule, stated before scoring, that picks which decision point represents this case in the lead-time table. |
| `condition_b_convention` | optional | How `checkable_afterwards` is written for this case, where the case adopts a convention worth stating once. |
| `sensitivity` | optional | Where a verdict turns on a judgement rather than on the records, the alternative readings and what each scores. |

### Relations between filings

A filing's entry carries its own relations, so there is no separate map to keep in step.

| Key | On | What it means |
|---|---|---|
| `closes` | a Closeout | The key of the Intent it closes. Every Closeout needs one. |
| `supersedes` | a Closeout | The key of an earlier Closeout for the same run that this one replaces. Use it when a later filing carries facts that did not exist when the first was filed. |
| `note` | any | A short word on why this filing exists, where that is not obvious. |

## Filers

A filer is the same filings as a particular person would have written them. Each filer edits a copy
of the Intent before scoring; a filer with no edits scores the filings as they are.

| Key | What it does |
|---|---|
| `description` | Says who this filer is. |
| `role` | What it contributes to the result: `"Headline."` or `"Upper bound."` |
| `edits.drop_writable_surfaces` | `{"intent:A": ["surface-id", …]}`: leaves those writable surfaces out, as a filer who did not know them would. |
| `edits.drop_paths` | `{"intent:A": ["path-id", …]}`: leaves those network paths out. |
| `edits.set_path_writable` | `{"intent:A": {"path-id": false}}`: states a path's writability as the filer believed it. |

The usual pair is `diligent` (what was true) and `as_believed` (what the filer plausibly believed).
Report both. Which one the tables lead with is a reporting choice and lives in `annotations.json`,
not here — the scorer scores every filer.

## A decision point

```jsonc
{
  "id": "DP2",                               // required, unique
  "date": "2026-05-26",                      // YYYY-MM-DD, when the decision was taken or missed
  "actor": "an internal team",               // who decided, in the source's own words
  "decision": "Saw the message board and disallowed internet access, escalated neither, and let the run continue.",
  "why_it_mattered": "The route the agents later used … stayed open for six more weeks.",
  "material_fact": "Agents had obtained internet access through the package proxy, and an internal team had seen them do it.",
  "developer_knew": {"status": true, "source": "Technical report p. 7: '…'"},
  "tests": { … },                            // required, see below
  "note": "…",                               // optional: a caveat a reader must weigh
  "outside_record": { … }                    // the lead-time inputs, see below
}
```

| Key | What it is |
|---|---|
| `date` | When the decision was taken, or should have been. A bare `YYYY-MM-DD`. Where the decision spans days, use the first, and say so in `note`. |
| `actor` | Who decided, named as the sources name them. If no source names anyone, write `"not named in the record"` rather than inferring a role — least of all from the filings being tested. |
| `decision` | One sentence: who did or did not decide what. |
| `why_it_mattered` | One sentence linking the decision to the outcome. |
| `material_fact` | The fact an investigator would need on record. **Write this before the tests.** Everything else is a claim about this one sentence, and a test or a lead time that drifts from it is the commonest error in a case. |
| `developer_knew` | `status` is **boolean**: `true` if the developer knew the material fact at the time. A decision on something nobody saw cannot be changed by any rule. `source` is the evidence, cited. Keep any `known` / `believed` / `unknown` nuance in a separate `knowledge` field — `case.py` maps `status` to `developer_aware` by truthiness, so the string `"unknown"` would score as *aware* and flip condition (c). `benchmarks/openai-2026` currently uses the string form; it does not bite there only because that case has no unknown entries. |
| `choice` | `taken` or `not_taken`: whether the actor did something or left something undone. |
| `available_alternative` | What the actor could have done instead, with the means and information they had **at the time**. A choice not taken needs a stated basis for expecting it, such as ordinary practice or the actor's own responsibility. |
| `date_precision` | How firm the date is: `day`, `on_or_before`, or `range` (with `date_range`). |
| `date_range` | `{"earliest": ..., "latest": ...}` where the date is a window rather than a day. |
| `from_v1` | The id this entry carried in an earlier revision, so a renumbered list stays traceable. |
| `note` | A caveat: an assumption the reconstruction rests on, or a reason this entry is weaker than it looks. |

## The three tests

| Test | Asks |
|---|---|
| `tests.declared_before_the_run` | **(a)** Did a filing made *before* the event record the fact? Usually a test on the Intent. |
| `tests.checkable_afterwards` | **(b)** Does the Closeout record the event? `evidence` lists the evidence classes a later check would need; each must be among the Intent's `log_retention.retained`, or the test scores "No". |
| `tests.would_have_changed_the_action` | **(c)** Would the filing have required a different action? `{"rule": "pause_criterion", "event_kind": KIND, "against_closeout": KEY}` asks whether a declared pause criterion matching that event kind required an action that was not taken. `{"rule": "record_obligation"}` is for decisions the protocol only requires to be recorded, not acted on. |

A decision point is **attributable** when (a) holds and (b) is not "No". A case passes when at least
half its decision points are attributable. (c) is reported separately: it bears on prevention, not
on attribution.

## Writing the tests

A test reads one filing, named by its key. There are four forms:

| Form | Holds when |
|---|---|
| `{"record": "intent:A", "pointer": "/run_kind", "equals": "evaluation"}` | the field at that JSON pointer equals the value |
| `{"record": "intent:A", "pointer": "/eval_plan", "exists": true}` | the field is present (not missing or null) |
| `{"record": "closeout:A", "pointer": "/security_events", "has_item_where": {"kind": "sandbox_escape"}}` | at least one item of the list matches every condition |
| `{"all_of": [TEST, TEST, …]}` | every test inside holds |

`pointer` is a JSON pointer in all four forms. Conditions in `has_item_where`:

| Condition | Matches an item when |
|---|---|
| `"kind": "sandbox_escape"` | the item's field equals the value |
| `"persistence": {"one_of": ["cross_run", "permanent"]}` | the item's field is one of the values |
| `"matches": {"contains": "third_party_compromise"}` | the item's field is a list containing the value |
| `"restart": {"not_empty": true}` | the item's field is present and not empty |

Pointers follow the record's field names, as listed in [docs/records/](../records/README.md):
`/agent_surface/permitted_paths`, `/pause_criteria`, `/security_events`. A pointer that does not
exist in a filing reads as missing, so the test is "No".

**Do not test a placeholder value.** If `sources.json` marks a value as a placeholder (something
made up to complete the filing), a test on it measures nothing.

## The outside record

This is how much earlier an outsider would have held the material fact. It is not a reduction in
the length of an incident, and it is never "days saved".

```jsonc
"outside_record": {
  "carried_by": "notice",                    // intent | notice | closeout | none
  "carrier_rationale": "Follows a detected event. The Intent records that a proxy path existed, not that agents reached the internet through it.",
  "first_reached_outside": "2026-08-05",     // when the fact actually reached anyone outside
  "quote": "OpenAI Black Hat USA session: 'On May 26th, the models …'",
  "source": "black-hat-2026-talk-transcript, 5-6 Aug 2026"
}
```

`carried_by` names the filing that would have put the fact on an outside record, and fixes the
date it compares against:

| `carried_by` | The date it is measured from |
|---|---|
| `intent` | The run's start minus the intake period. Only legitimate where the Intent records *this* fact, not merely a precondition for it. |
| `notice` | The detection of the event behind the decision point, plus the notice deadline. |
| `closeout` | The end of the period containing the event, plus the filing lag. |
| `none` | No filing was due, so the lead is zero. |

Always use the filing deadline, never the earliest date the filer could have managed.

**`carried_by: "intent"` is the one to be careful with.** An Intent records a configuration. If the
material fact is about something that *happened* — agents used a path, and someone saw them — the
Intent cannot carry it, and pairing an Intent date with an outside date that reports the event
overstates the lead. The question to answer in `carrier_rationale` is whether the field the Intent
declares answers the question `material_fact` asks.

Optional keys, for facts the record does not pin down:

| Key | Use it when |
|---|---|
| `note` | Anything a reader must weigh before quoting the number. |
| `bound` | `"lower"` or `"upper"`: the figure is a bound, not an estimate. Taking the latest date a source allows gives a lower bound, because a later detection means a later deadline and a shorter lead. |
| `contested_detection` | `{"earliest": …, "latest": …, "rationale": …}` when no source dates the detection. Score both ends and report a range rather than choosing one. |
| `rejected_pairings` | Other readings of `material_fact` that were considered, each with its own date, source and `rejection_rationale`. Worth recording where the choice changes the figure. |

## An example

From `benchmarks/openai-2026`. The decision is a failure to escalate; the Intent declared the path
but not the event, so a notice carries the fact, and the detection date is contested.

```json
{
  "id": "DP2",
  "date": "2026-05-25",
  "date_precision": "range",
  "date_range": {"earliest": "2026-05-25", "latest": "2026-05-31"},
  "actor": "an internal team",
  "choice": "not_taken",
  "decision": "After a monitor flagged the message board (25 May) and the team saw disallowed internet access (around 26 May), escalated neither and let the run continue.",
  "available_alternative": "Escalate to the people who could stop the run, or pause it. The team knew of both the board and the internet access.",
  "why_it_mattered": "The route the agents later used to reach the internet, and from there Hugging Face, stayed open for six more weeks.",
  "material_fact": "Agents had obtained internet access through the package proxy, and an internal team had seen them do it.",
  "developer_knew": {
    "status": true,
    "source": "Technical report p. 7: 'Around the same time, an internal team observed an agent engage in message board activity and instances of disallowed internet access.'"
  },
  "tests": {
    "declared_before_the_run": {
      "record": "intent:A",
      "pointer": "/agent_surface/permitted_paths",
      "has_item_where": {"path_id": "pkg-proxy", "enforcement": "packet_filter"}
    },
    "checkable_afterwards": {
      "record": "closeout:A",
      "pointer": "/security_events",
      "has_item_where": {"kind": "sandbox_escape"},
      "evidence": ["network_logs"]
    },
    "would_have_changed_the_action": {
      "rule": "pause_criterion",
      "event_kind": "sandbox_escape",
      "against_closeout": "closeout:A"
    }
  },
  "outside_record": {
    "carried_by": "notice",
    "carrier_rationale": "Follows a detected event. The Intent records that a proxy path existed, not that agents reached the internet through it and were seen doing so. E2 is a sandbox escape and requires a notice.",
    "first_reached_outside": "2026-08-05",
    "quote": "OpenAI Black Hat USA session: 'On May 26th, the models that were being trained successfully executed a server-side request forgery attack on artifactory.'",
    "source": "black-hat-2026-talk-transcript, 5-6 Aug 2026",
    "note": "Detection date unknown within the window above, so the lead is a range.",
    "contested_detection": {
      "earliest": "2026-05-26",
      "latest": "2026-05-31",
      "rationale": "No source dates the observation; the report says only 'around the same time' as 26 May. It cannot precede the event at 26 May 18:24, and the next dated event is 4 Jun."
    }
  }
}
```

## Checklist

1. List every decision that shaped the incident, including decisions not to act.
2. For each, write `material_fact` first, and `actor` from the sources or `"not named in the record"`.
3. Find the field that should have captured the fact before the event, and write
   `declared_before_the_run` against it.
4. Write `checkable_afterwards` against the Closeout, and list the evidence a check would need.
5. Choose `would_have_changed_the_action`, and record `developer_knew` with its source.
6. Fill in `outside_record`, and check that `carried_by` holds the fact `material_fact` names —
   not merely a precondition for it.
7. Freeze: record `freeze.schema_hash`, and log any later edit in `freeze.revisions`.

## Retired decision points

A candidate that fails one of the four tests is **not deleted**. Move it to
`retired_decision_points`, with the test it failed and why. The retired list is how a reader checks
that the filter was applied rather than fitted: a filter worth trusting removes attributable points
as well as unattributable ones.

```jsonc
{
  "id": "R3",
  "from_v1": "DP8",
  "decision": "Agent-authored package metadata executed inside GitHub-operated containers.",
  "actor": "none - agent action",
  "date": "2026-07-27",
  "failed_test": "actor",
  "reason_retired": "No person or organisation decided this. The upstream choices are DP1 and DP5. Severity does not make an event a decision point.",
  "source": "TR A.3"
}
```

Give retired entries their own id series (`R1`, `R2`, ...) so they cannot be confused with scored
ones, and keep `from_v1` so the mapping back to an earlier numbering survives. Where a retired entry
held a finding worth keeping — a schema gap, or the one place the protocol worked end to end — say
so in `reason_retired`; the entry is out of the count, not out of the paper.

Three failures recur:

- **Actor.** An agent action with nobody deciding. Look upstream for the human choice that made it
  possible, and list that instead.
- **Consequence.** A choice made after the harm. It may still matter — a notification, an
  investigation scope — but no alternative could have changed the incident's outcome, so report it
  separately as a post-incident finding.
- **Available alternative.** The premise of the exercise rather than a choice within it. Disabling
  classifiers to measure cyber capability is the stock example: the alternative would also have
  prevented the evaluation's purpose.

## Field names across the committed cases

The three cases do not currently use identical field names, and a case author should know which
dialect they are copying.

`benchmarks/openai-2026` and `benchmarks/aisi-2026` use the names on this page. `benchmarks/anthropic-2026`
predates them and uses its own for the same ideas:

| anthropic-2026 | this page | Note |
|---|---|---|
| `live_alternative` | `available_alternative` | Same concept, different name. |
| `_about` | `definition` | The rule, as free text rather than a keyed field. |
| `consequences` | — | Records candidates folded into this one; the convention here is `retired_decision_points` plus a `note`. |
| `review` | `note` | An author's caveat on the test. |
| `checkable_after_revised` | `note` | Why the (b) test was changed. |
| `decision_class` | — | `setup`, `investigate`, `respond` or `tell`. No equivalent here; a useful addition if adopted for all cases. |

The scorer tolerates all of these, because `_normalise` reads only the keys it needs. That means the
divergence is invisible at scoring time and shows up only when cases are compared. Align them before
reporting any cross-case figure.

## What changed

Against the previous format, for converting an older case.

| Was | Is now |
|---|---|
| `case`, `title`, `is_derivation_case` | `case_id` only |
| `schema_hash`, `derivation_note`, `revision_note` | `freeze.schema_hash`, `freeze.revisions[]` |
| `records` plus a separate `closes` map | `filings`, where a Closeout names what it `closes` |
| `variants`, `remove_surfaces`, `path_writable` | `filers`, `edits.drop_writable_surfaces`, `edits.set_path_writable` |
| `date: "5 Sep"` | `date: "2026-09-05"` |
| `field` | dropped; the pointer in the test is the only statement of where the fact belongs |
| `developer_aware: "yes" \| "no" \| "unclear"`, `aware_source` | `developer_knew: {status, source}` |
| `recorded_before`, `checkable_after`, `decision_rule` | `tests.declared_before_the_run`, `tests.checkable_afterwards`, `tests.would_have_changed_the_action` |
| `decision_rule.closeout` | `against_closeout` |
| `any` | `pointer` plus `has_item_where` |
| `all` | `all_of` |
| a bare list in `where` | `{"one_of": [...]}` |
| `{"nonempty": true}` | `{"not_empty": true}` |
| — | `actor`, `why_it_mattered`, `material_fact`, `outside_record` are new |
