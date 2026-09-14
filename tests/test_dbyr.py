"""Test suite. Run with: python -m pytest tests/ -q"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from dbyr import envelope, interop, predicates, redact, replay as replay_mod, validate as validate_mod

ROOT = Path(__file__).resolve().parent.parent
INTENT = json.loads((ROOT / "examples" / "intent-exploitgym-2026-05.json").read_text())
CLOSEOUT_OK = json.loads((ROOT / "examples" / "closeout-exploitgym-2026-07.json").read_text())
CLOSEOUT_BAD = json.loads((ROOT / "examples" / "closeout-noncompliant-2026-07.json").read_text())
EVENTS_PATH = ROOT / "data" / "events" / "openai-exploitgym-2026.jsonl"


# --- predicates ------------------------------------------------------------

def test_leaf_ops():
    ev = {"event_class": "sandbox_egress", "surface": "artifactory", "count": 3}
    assert predicates.evaluate({"field": "event_class", "op": "eq", "value": "sandbox_egress"}, ev)
    assert predicates.evaluate({"field": "event_class", "op": "in", "value": ["a", "sandbox_egress"]}, ev)
    assert predicates.evaluate({"field": "count", "op": "gte", "value": 3}, ev)
    assert predicates.evaluate({"field": "surface", "op": "regex", "value": "^arti"}, ev)
    assert not predicates.evaluate({"field": "missing", "op": "exists", "value": True}, ev)


def test_combinators_and_missing_fields():
    ev = {"event_class": "restart"}
    assert predicates.evaluate({"any_of": [
        {"field": "event_class", "op": "eq", "value": "restart"},
        {"field": "event_class", "op": "eq", "value": "other"},
    ]}, ev)
    assert predicates.evaluate({"none_of": [{"field": "event_class", "op": "eq", "value": "other"}]}, ev)
    # A missing field never satisfies a comparison, so rules cannot fire by accident.
    assert not predicates.evaluate({"field": "third_parties_affected", "op": "contains", "value": "X"}, ev)


def test_malformed_predicate_rejected():
    with pytest.raises(predicates.PredicateError):
        predicates.evaluate({"all_of": [], "any_of": []}, {})


# --- validation ------------------------------------------------------------

def test_example_records_validate():
    assert validate_mod.validate(INTENT).ok
    assert validate_mod.validate(CLOSEOUT_OK, intent=INTENT).ok


def test_noncompliant_closeout_is_caught():
    report = validate_mod.validate(CLOSEOUT_BAD, intent=INTENT)
    assert not report.ok
    joined = " ".join(report.errors)
    assert "override with no named authority" in joined
    assert "undeclared surface with no Intent amendment" in joined
    assert "never declared in the Intent" in joined          # PC-99
    warnings = " ".join(report.warnings)
    assert "training-time events excluded" in warnings
    assert "2 of 10 transcript weeks granted" in warnings
    assert "RubyGems" in warnings                             # affected but not notified


def test_pause_criterion_without_authority_fails():
    bad = copy.deepcopy(INTENT)
    bad["pause_criteria"][0]["authority_role"] = ""
    assert "no role holds unilateral pause authority" in " ".join(validate_mod.validate(bad).errors)


def test_retention_floor_enforced():
    bad = copy.deepcopy(INTENT)
    bad["log_retention"]["retention_months_after_closeout"] = 6
    report = validate_mod.validate(bad)
    assert not report.ok
    assert "below the 24-month floor" in " ".join(report.errors)


def test_open_egress_with_safeguards_off_rejected():
    bad = copy.deepcopy(INTENT)
    bad["containment_spec"]["egress_policy"] = "open"
    assert "egress_policy=open" in " ".join(validate_mod.validate(bad).errors)


def test_cross_run_readable_surface_warns():
    bad = copy.deepcopy(INTENT)
    bad["containment_spec"]["shared_writable_surfaces"][0]["readable_across_runs"] = True
    assert any("cross-run readable surface" in w for w in validate_mod.validate(bad).warnings)


def test_non_machine_checkable_criteria_are_surfaced():
    assert any("PC-07" in w for w in validate_mod.validate(INTENT).warnings)


# --- tiering ---------------------------------------------------------------

def test_public_view_hides_restricted_fields():
    pub = redact.project(INTENT, "public")["record"]
    assert pub["compute_band"] == "1e26-1e27"
    assert "data_classes" not in pub
    # Criterion ids and authorities are public; the match rule is not.
    crit = pub["pause_criteria"][0]
    assert crit["id"] == "PC-01" and crit["authority_role"]
    assert "match" not in crit
    # Contact channels and identity hashes never appear publicly.
    assert "contact_channel" not in pub["roles"][0]


def test_tiers_are_cumulative():
    pub = redact.project(INTENT, "public")
    res = redact.project(INTENT, "restricted")
    sealed = redact.project(INTENT, "sealed")
    assert pub["_dbyr_withheld_count"] > res["_dbyr_withheld_count"] > sealed["_dbyr_withheld_count"]
    assert sealed["_dbyr_withheld_count"] == 0
    assert "match" in res["record"]["pause_criteria"][0]


def test_public_projection_shows_existence_not_content():
    pub = redact.project(INTENT, "public")["record"]
    assert pub["containment_spec"]["egress_policy"] == "none"
    assert "credential_scope" in pub["containment_spec"]["_dbyr_withheld"]
    # The number of shared writable surfaces is public; the surfaces themselves are not.
    surfaces = pub["containment_spec"]["shared_writable_surfaces"]
    assert surfaces["_dbyr_count"] == 1 and "surface_id" not in json.dumps(surfaces)
    assert pub["third_party_access_commitment"]["covers_training_time_events"] is True


def test_commitment_detects_tampering():
    root = redact.project(INTENT, "public")["_dbyr_merkle_root"]
    tampered = copy.deepcopy(INTENT)
    tampered["containment_spec"]["credential_scope"] = "unrestricted"
    assert redact.project(tampered, "public")["_dbyr_merkle_root"] != root


def test_later_disclosure_verifies_against_published_root():
    commitments = redact.commitments_for(INTENT, "public")
    root = redact.merkle_root(commitments)
    path = "/containment_spec/credential_scope"
    truth = INTENT["containment_spec"]["credential_scope"]
    assert redact.verify_disclosure(truth, path, root, commitments)
    assert not redact.verify_disclosure("a different story", path, root, commitments)


# --- envelopes and register ------------------------------------------------

def test_envelope_roundtrip_and_tamper_detection():
    env = envelope.sign(INTENT)
    ok, msg = envelope.verify(env)
    assert ok and "UNSIGNED" in msg
    env["payload"]["compute_band"] = "<1e25"
    ok, msg = envelope.verify(env)
    assert not ok and "altered after filing" in msg


@pytest.mark.skipif(not envelope.HAVE_ED25519, reason="ed25519 unavailable")
def test_signed_envelope():
    key, _ = envelope.generate_key()
    env = envelope.sign(INTENT, key)
    ok, msg = envelope.verify(env)
    assert ok and "Ed25519" in msg
    env["signature"] = env["signature"][:-4] + "AAAA"
    assert not envelope.verify(env)[0]


def test_register_chain(tmp_path):
    reg = envelope.Register(tmp_path / "register.jsonl")
    reg.append(envelope.sign(INTENT))
    reg.append(envelope.sign(CLOSEOUT_OK))
    assert reg.verify_chain()[0]
    # Silently drop the first entry, as a developer rewriting history would.
    rows = reg.path.read_text().splitlines()
    reg.path.write_text(rows[1] + "\n")
    ok, msg = reg.verify_chain()
    assert not ok and "broken chain" in msg


# --- replay ----------------------------------------------------------------

def test_backtest_reproduces_table_1():
    events, excluded = replay_mod.load_events(EVENTS_PATH)
    result = replay_mod.replay(INTENT, events, excluded)
    assert len(result.decision_points) == 6
    assert result.bound_count == 5          # pre-registered criterion was 3
    assert result.partial_count == 1        # notification clock absent from v0.1
    assert excluded > 0                     # circumstantial threads excluded from scoring


def test_first_binding_precedes_actual_detection():
    events, excluded = replay_mod.load_events(EVENTS_PATH)
    result = replay_mod.replay(INTENT, events, excluded)
    cf = replay_mod.counterfactual(result, events)
    assert cf["first_binding"] == "2026-05-08"
    assert cf["actual_detection"] == "2026-07-19"
    assert cf["days_earlier"] == 72


def test_declared_surface_does_not_bind():
    """Binding must come from the declaration, not from the event class alone."""
    permissive = copy.deepcopy(INTENT)
    permissive["containment_spec"]["shared_writable_surfaces"].append(
        {"surface_id": "internal-artifactory", "kind": "package_registry",
         "writable_by_agents": True, "readable_across_runs": True, "justification": "declared"}
    )
    events, _ = replay_mod.load_events(EVENTS_PATH)

    def surface_bindings(result, day):
        return [b for b in result.bindings
                if b.date == day and "shared_writable_surfaces" in b.field_bound]

    assert surface_bindings(replay_mod.replay(INTENT, events), "2026-05-08")
    relaxed = replay_mod.replay(permissive, events)
    assert not surface_bindings(relaxed, "2026-05-08")
    # Surfaces improvised later (the WebDAV cache, the remote-repository service)
    # are still undeclared, so the run remains bound at those points.
    assert surface_bindings(relaxed, "2026-07-08")


def test_restart_binds_only_when_unrecorded():
    events, _ = replay_mod.load_events(EVENTS_PATH)
    assert any(b.kind == "restart_protocol" for b in replay_mod.replay(INTENT, events).bindings)
    recorded = [dict(e, restart_approval_recorded=True) if e["event_class"] == "restart" else e for e in events]
    assert not any(b.kind == "restart_protocol" for b in replay_mod.replay(INTENT, recorded).bindings)


def test_inert_criteria_reported():
    events, _ = replay_mod.load_events(EVENTS_PATH)
    assert "PC-07" in replay_mod.replay(INTENT, events).inert_criteria


# --- interop ---------------------------------------------------------------

def test_sb53_emitter_flags_loss_of_control():
    report = interop.emit_sb53_incident(CLOSEOUT_BAD)
    assert any(i["loss_of_control_indicator"] for i in report["incidents"])
    assert report["overridden_stop_criteria"]


def test_frontier_index_carries_pre_agreed_access():
    idx = interop.emit_frontier_audit_index(INTENT, CLOSEOUT_BAD)
    assert idx["pre_agreed_access"]["covers_training_time_events"] is True
    assert idx["logs_preserved_pct"] == 90


def test_coverage_report_names_the_gaps():
    text = interop.coverage_report()
    assert "containment_spec" in text and "restart_protocol" in text
    assert "no counterpart in any current instrument" in text
