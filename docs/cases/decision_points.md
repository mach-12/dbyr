# Writing `decision_points.json`

A case is reconstructed filings plus this file. The filings are what a lab would have lodged; this
file lists the questions an investigator would ask afterwards. The score is how many the filings
answer.

Decision points are never filed — they exist only to test the protocol against an incident. Write
the list before you score, and not the person who wrote the filings.

## What counts as a decision point

> A moment at which an identifiable actor, with an alternative actually available to them at that
> time, chose a course of action or left one unchosen, such that the alternative would plausibly
> have changed the outcome.

All four must hold:

| Element | Fails when |
|---|---|
| **Actor** — who decided | it was an agent's action or a system condition |
| **Time** — when, at least to a range | it is a standing state with no moment of choice |
| **Alternative** — could they have chosen otherwise, with what they knew *then* | it is only visible in hindsight |
| **Consequence** — would that have changed the outcome | the outcome would have been the same |

**It is never the fact the developer did not know; it is the choice that left them not knowing.**
An environment having an open route to the internet is a condition nobody chose. *Running the
evaluation without validating its network paths first* is the decision point.

Stop at the planning of the run.

## The file

```jsonc
{
  "case_id": "my-case",                      // same as the folder name
  "in_sample": false,                        // true only for the case the schema came from
  "definition": "A moment at which …",       // the bar you applied

  "freeze": {
    "schema_hash": "sha256:…",               // what `dbyr freeze` printed before any filing
    "revisions": [{"on": "2026-11-16", "pre_registered": false, "reason": "…"}]
  },

  "filings": {
    "intent:A":   {"file": "intent_a.json"},
    "closeout:A": {"file": "closeout_a.json", "closes": "intent:A"},
    "notice:N1":  {"file": "notice_n1.json"}
  },

  // A filer is the filings as one person would have written them.
  // Edits apply to the Intent before scoring: drop_writable_surfaces, drop_paths, set_path_writable.
  "filers": {
    "diligent":    {"description": "The configuration as it was.", "role": "Upper bound.", "edits": {}},
    "as_believed": {"description": "What the team believed.",      "role": "Headline.",
                    "edits": {"drop_writable_surfaces": {"intent:A": ["scratch-dir"]}}}
  },

  "decision_points": [{
    "id": "DP2",
    "date": "2026-05-25",
    "date_precision": "range",               // day | on_or_before | range
    "date_range": {"earliest": "2026-05-25", "latest": "2026-05-31"},
    "actor": "an internal team",             // or "not named in the record" — never inferred
    "choice": "not_taken",                   // taken | not_taken
    "decision": "Saw the message board, escalated nothing, let the run continue.",
    "available_alternative": "Escalate, or pause. The team knew of the board.",
    "why_it_mattered": "The route the agents later used stayed open for six more weeks.",

    // Write this first. Every test below is a claim about this one sentence.
    "material_fact": "Agents had reached the internet through the proxy, and a team had seen them.",

    // status is BOOLEAN. The scorer reads it by truthiness, so "unknown" would score as aware.
    "developer_knew": {"status": true, "source": "Technical report p. 7: '…'"},

    "tests": {
      "declared_before_the_run": {"record": "intent:A", "pointer": "/agent_surface/permitted_paths",
                                  "has_item_where": {"path_id": "pkg-proxy"}},
      "checkable_afterwards":    {"record": "closeout:A", "pointer": "/security_events",
                                  "has_item_where": {"kind": "sandbox_escape"},
                                  "evidence": ["network_logs"]},
      "would_have_changed_the_action": {"rule": "pause_criterion", "event_kind": "sandbox_escape",
                                        "against_closeout": "closeout:A"}
    },

    // How much earlier an outsider would have held the fact. Never "days saved".
    "outside_record": {
      "carried_by": "notice",                // intent | notice | closeout | none
      "carrier_rationale": "The Intent records that a path existed, not that agents used it.",
      "first_reached_outside": "2026-08-05",
      "quote": "…",
      "source": "black-hat-2026-talk-transcript"
    },

    "note": "A caveat a reader must weigh."
  }],

  // Candidates that failed one of the four tests. Moved, never deleted — this is how a reader
  // checks the filter was applied rather than fitted. Use a separate id series.
  "retired_decision_points": [{
    "id": "R3",
    "decision": "Agent-authored code executed inside a third party's containers.",
    "actor": "none - agent action",
    "date": "2026-07-27",
    "failed_test": "actor",
    "reason_retired": "Nobody decided this. Severity does not make an event a decision point.",
    "source": "TR A.3"
  }]
}
```

## The three conditions

**(a) `declared_before_the_run`** — did a filing made before the event record the fact? Usually the
Intent, but a Notice counts too.

**(b) `checkable_afterwards`** — does the Closeout record the event, and is every class in
`evidence` listed in the Intent's `log_retention.retained`? Always test an **event, exception or
pause** — never a re-statement of what the Intent already declares.

**(c) `would_have_changed_the_action`** — `{"rule": "pause_criterion", "event_kind": …,
"against_closeout": …}`, or `{"rule": "record_obligation"}` for a decision the protocol only
requires to be *recorded*. `record_obligation` returns `Unknown` by construction and can never be
`Yes`.

**Attributable = (a) holds and (b) is not "No".** A case passes at half its decision points. (c) is
reported separately.

## Writing a test

```jsonc
{"record": "intent:A",   "pointer": "/run_kind", "equals": "evaluation"}
{"record": "intent:A",   "pointer": "/eval_plan", "exists": true}
{"record": "closeout:A", "pointer": "/security_events", "has_item_where": {"kind": "sandbox_escape"}}
{"all_of": [ … ]}
```

Inside `has_item_where`:

| Condition | Matches when |
|---|---|
| `"kind": "sandbox_escape"` | the field equals the value |
| `"persistence": {"one_of": [...]}` | the field is one of the values |
| `"matches": {"contains": "…"}` | the field is a list containing the value |
| `"restart": {"not_empty": true}` | the field is present and not empty |

## Two traps

**A pointer that is not a field of that record** reads as missing, so the test scores No. Use it
only where you mean to register a missing field, and say so in `note`.

**A value `sources.json` marks `placeholder`** was invented to make the record validate. A test on
it measures nothing.
