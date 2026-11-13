# Backtest: openai-2026

**Derivation case.** (a) and (b) are traceability, not validation.

Schema hash: `sha256:5d7ed0105e75a8cea3729adc4af8b78f45f9a6cee212e31b1ffe3bd567c348f8`
Reconstructed filings well formed: True

## Filer variant: diligent

| DP | (a) recorded before | (b) checkable after | (c) changes decision | why |
|---|---|---|---|---|
| DP1 | Yes | Partial | No | criterion cannot fire on an unseen event |
| DP2 | Yes | Yes | Yes | declared criterion required an action that was not taken |
| DP3 | Yes | Partial | Yes | declared criterion required an action that was not taken |
| DP4 | Yes | Yes | No | criterion cannot fire on an unseen event |
| DP5 | Yes | Yes | No | compliant: required action was taken and restart approved |
| DP6 | Yes | Yes | Unknown | obligation is to record, not to act |
| DP7 | Yes | Yes | Yes | declared criterion required an action that was not taken |

Intake review of the reconstructed Intents: intent:A: accepted; intent:B: comms_unmonitored, dead_criterion, shared_surface_floor; intent:C: comms_unmonitored, dead_criterion, shared_surface_floor; intent:D: comms_unmonitored, dead_criterion, shared_surface_floor

Attributable on 7 of 7; passes the held-out criterion (needs 4).

## Filer variant: as_believed

| DP | (a) recorded before | (b) checkable after | (c) changes decision | why |
|---|---|---|---|---|
| DP1 | No | Partial | No | criterion cannot fire on an unseen event |
| DP2 | Yes | Yes | Yes | declared criterion required an action that was not taken |
| DP3 | No | Partial | Yes | declared criterion required an action that was not taken |
| DP4 | Yes | Yes | No | criterion cannot fire on an unseen event |
| DP5 | Yes | Yes | No | compliant: required action was taken and restart approved |
| DP6 | Yes | Yes | Unknown | obligation is to record, not to act |
| DP7 | Yes | Yes | Yes | declared criterion required an action that was not taken |

Intake review of the reconstructed Intents: intent:A: accepted; intent:B: core_kind_uncovered, dead_criterion; intent:C: core_kind_uncovered, dead_criterion; intent:D: core_kind_uncovered, dead_criterion

Attributable on 5 of 7; passes the held-out criterion (needs 4).
