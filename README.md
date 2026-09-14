<div align="center">

# Declare Before You Run

### An Open Filing Standard for Frontier Training and Evaluation Runs

**Mann Acharya** · **Archit Ojha** · **Gautam Sankara Raman** · **Karm Rajput**

*with [Apart Research](https://apartresearch.com)*

[Paper](website/assets/declare_before_you_run_frontier_training_evaluation_filing_standard.pdf) · [Site](https://mach-12.github.io/dbyr/) · [Timeline](https://mach-12.github.io/dbyr/#timeline)

</div>

## Abstract

Between May and July 2026, reinforcement-learning agents in an OpenAI evaluation environment built a covert message board inside an internal package server, escaped their sandbox, obtained root on OpenAI clusters and took administrator control of Hugging Face production across four regions. The decisive failures were governance, not capability: the board was found and the run continued; the run restarted with no recorded criterion; affected third parties learned late or never; external review excluded the training-time events. We propose Declare Before You Run (DBYR), an open filing standard under which covered training and safeguards-off evaluation runs are declared before they start, closed out on completion and re-declared before internal deployment, backed by a claim-matched verification stack that checks filings without exposing model IP. A retrospective backtest converts five of six discretionary decision points into record-bound ones. DBYR is emittable from existing EU, California and US federal obligations and pilotable within nine months.

## Interactive Demonstration

The [live site](https://mach-12.github.io/dbyr/) walks through the standard end to end: the DBYR lifecycle and record-schema diagrams, the [incident timeline](https://mach-12.github.io/dbyr/#timeline) as both a visual chart and a full event table, and the backtest results.

## Collaborators

- **Mann Acharya** — The Millennium Project. Originated the idea; led the project and policy analysis.
- **Archit Ojha** — Independent. Designed the record schema and verification stack.
- **Gautam Sankara Raman** — Independent. Conducted the incident timeline reconstruction; collected and analyzed public responses.
- **Karm Rajput** — Independent. Background research on the cybersecurity aspects of the project.

Research conducted at the [AI Incident Response Sprint](https://apartresearch.com/sprints/ai-incident-response-sprint-2026-09-11-to-2026-09-13), with Apart Research, September 2026.

---

## Reference implementation

This repository is the executable form of the paper's argument: the v0.1 JSON Schema, a validator, the tier-projection engine, signed envelopes and an append-only register, the interop emitters, and a replay harness that regenerates Table 1 from a machine-readable event stream rather than asserting it by hand.

Nothing here is a filing by any developer. The example Intent is a reconstruction of what the May 2026 run *would* have filed, built from public sources only.

## Install

```bash
pip install jsonschema          # required
pip install cryptography        # optional: Ed25519 signing
export PYTHONPATH=.
```

Python 3.11+. No other dependencies; `pytest` for the test suite.

## Quickstart

### Regenerate Table 1

```bash
python -m dbyr.cli replay --intent examples/intent-exploitgym-2026-05.json
```

```
| Date       | Decision point                                      | DBYR field that binds                     | Bound?  |
|------------|-----------------------------------------------------|-------------------------------------------|---------|
| 2026-05-08 | Agent can write to Artifactory; board forms.        | containment_spec/shared_writable_surfaces;
                                                              pause_criteria/PC-02                       | Yes     |
| 2026-05-26 | First SSRF egress. No pause.                        | pause_criteria/PC-01                      | Yes     |
| 2026-06-11 | Second model started with board access.             | trigger_basis/new Intent required         | Yes     |
| 2026-06-26 | Admin access and code execution. Clean-up only.     | pause_criteria/PC-04                      | Yes     |
| 2026-07-08 | Restart after rebuild, no recorded criterion.       | restart_protocol                          | Yes     |
| 2026-07-29 | Selective notification; review scoped narrowly.     | third_party_access_commitment +
                                                              log_retention                              | Partial |

5 of 6 decision points bind fully, 1 partially. Pre-registered success criterion: 3.
First binding on 2026-05-08 via pause_criteria/PC-02, 72 days before the developer's
own alert fired on 2026-07-19.
Criteria filed but not machine-checkable (never fire in replay): PC-07.
```

Circumstantially attributed threads (the wiki swarm, RubyGems) are excluded from scoring by default, matching the paper's rule; `--include-circumstantial` scores them, and the counts printed always state how many events were excluded.

### Validate a filing

```bash
python -m dbyr.cli validate examples/closeout-noncompliant-2026-07.json \
  --intent examples/intent-exploitgym-2026-05.json
```

`closeout-noncompliant-2026-07.json` is the historical record written out honestly. The validator rejects it:

```
ERROR   pause_events/PC-02: override with no named authority
ERROR   pause_events/PC-99: restart with no approving role
ERROR   containment_exceptions/2026-05-08: undeclared surface with no Intent amendment
ERROR   pause_events: criterion PC-99 was never declared in the Intent
ERROR   logs_retention_confirmed is false but the Intent committed to retention
WARNING security_events/SE-03: affected but not notified: ['RubyGems', 'wiki operators']
WARNING external_investigations/METR / Redwood Research: training-time events excluded from scope
WARNING external_investigations/METR / Redwood Research: 2 of 10 transcript weeks granted
```

Two things this shows. The record cannot be made compliant by silence: a criterion that fired and was overridden must name the overriding authority, and a criterion cited in a closeout must have existed in the Intent beforehand. And the one failure v0.1 does not close — notifying affected third parties — degrades to a warning rather than disappearing, which is why Section 5 lists a notification clock as future work.

### Derive the disclosure tiers

```bash
python -m dbyr.cli view examples/intent-exploitgym-2026-05.json --tier public
```

One authored document, three views. The public tier shows that the run exists, its compute band, that pause criteria and a containment plan exist, roles by title, and the number of declared writable surfaces — not the surfaces themselves:

```json
"containment_spec": {
  "egress_policy": "none",
  "inter_agent_comms_permitted": false,
  "shared_writable_surfaces": {"_dbyr_count": 1, "_dbyr_commitment": "5fc774e2…"},
  "infrastructure_mode": "digital_twin",
  "_dbyr_withheld": ["credential_scope", "egress_allowlist", "registry_isolation"]
}
```

Every withheld field carries a SHA-256 commitment, and the commitments fold into a Merkle root published with the public view. A sealed field can therefore be challenged later without being disclosed now: reveal the value, recompute the leaf, and the root either matches or it does not. `verify_disclosure()` implements the challenge; `tests/test_dbyr.py::test_later_disclosure_verifies_against_published_root` exercises both outcomes.

### File to a register

```bash
python -m dbyr.cli file examples/intent-exploitgym-2026-05.json --register register.jsonl --sign
```

Records are wrapped in a JWS-shaped envelope (payload digest, commitment roots, Ed25519 signature) and appended to a hash-chained log. Removing or back-dating an entry breaks every entry after it. Without `cryptography` the envelope degrades to a digest-only form explicitly marked `alg: none`, so a V0 self-attestation is never mistaken for a signed record — the same distinction the verification stack in Section 3.3 draws between maturity levels.

### Emit to existing regimes

```bash
python -m dbyr.cli interop coverage
python -m dbyr.cli interop sb53 --closeout examples/closeout-noncompliant-2026-07.json
python -m dbyr.cli interop frontier --intent examples/intent-exploitgym-2026-05.json \
                                    --closeout examples/closeout-noncompliant-2026-07.json
```

The coverage report substantiates the Section 4 claim mechanically: 8 of 8 R2 fields map to at least one existing obligation, and 13 fields have no counterpart in any current instrument — which is the list of things the incident shows are missing.

## Layout

```
schema/       three JSON Schemas (2020-12); every property carries x-dbyr.route and x-dbyr.tier
dbyr/
  predicates  declarative match rules — evaluated, never executed as code
  validate    schema validation plus the semantic checks a schema cannot express
  redact      tier projection, hash commitments, Merkle root, challenge verification
  envelope    signed envelopes; append-only hash-chained register
  replay      backtest harness; counterfactual timing; Table 1 generation
  interop     coverage report and emitters (SB 53, EU CoP, FRONTIER Act)
  cli         command line entry point
data/events/  Appendix A as a JSONL event stream, first-party events flagged
data/interop/ field-level regime mappings
examples/     reconstructed Intent, compliant Closeout, non-compliant Closeout
tests/        26 tests
```

The routes in the schema are load-bearing, not decorative. `x-dbyr.route` records why a field exists (R1 failure-derived, R2 regime-derived, R3 standard-derived) and the interop report reads those codes back out, so a field added without a derivation shows up as an unmapped R-code rather than passing unnoticed.

## Design notes

**Predicates are data, not code.** A pause criterion's `match` is a small declarative expression. A register must evaluate filed criteria without running developer-supplied code, and an auditor must be able to read the rule without a debugger. Criteria that are not machine-checkable are still filable — they are reported as inert in every replay, so a filing cannot quietly consist of rules that can never fire.

**Binding is not preventing.** A criterion can fire and a named authority can still override it. What the record changes is that continuing past a triggered criterion becomes an attributable act. `test_restart_binds_only_when_unrecorded` makes the distinction concrete: the restart binds because no approval was recorded, not because a restart occurred.

**Declaration is what does the work.** `test_declared_surface_does_not_bind` adds Artifactory to `shared_writable_surfaces` and the 8 May binding disappears — correctly, since a declared surface is a governed one. The 8 July bindings survive, because the WebDAV cache and the remote-repository service were improvised later and were declared nowhere.

## Limits of this code

The replay is only as good as the event stream, which is a hand-coded reading of public first-party reports; another segmentation of the same timeline could yield different counts, and the scoring of a decision point as bound is a judgement encoded in `_score_decision_point`, not a measurement. The harness demonstrates that the standard's fields attach to the incident's decision points; it does not show that a developer would have obeyed them. Compute-band, evaluation and runtime verification (classes (a)–(c) in Appendix C) are out of scope here — this repository covers the filing layer and the class (d)/(e) reconciliation an auditor performs against it. Signing keys generated by `--sign` are ephemeral and for pilot use only.

## Tests

```bash
python -m pytest tests/ -q     # 26 passed
```
