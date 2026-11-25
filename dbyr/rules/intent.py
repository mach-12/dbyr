"""Checks on one RunIntent.

Three groups, run in this order:
  consistency   roles, the T4 trigger, lineage references; warnings on monitoring and retention
  coverage      criteria a declared monitor can observe, enforced and declared paths, core coverage
                under safeguards-off, the inter-agent channel, the evaluation window
  completeness  the safeguards checklist, monitor specifications, shared surfaces, reportable kinds,
                retention, required fields, intake time and amendments

They check what a filing commits to, not whether it is true. A false filing that is
specific enough passes; catching it needs reconciliation against retained logs.
Rules cite the evasion that motivated them: [T..] the scripted tabletop, [R1 ..] round 1
of the independent tabletop.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from ..findings import Finding
from ..params import CORE_KINDS_T4, INTAKE_DAYS, MAX_EVAL_DAYS, PAUSING, REPORTABLE, SAFEGUARDS
from .common import (criterion_findings, effective_monitors, monitor_findings, observable, restart_findings,
                     retention_findings, shared_agent_surfaces, ts)


def check_intent(intent: dict) -> list[Finding]:
    return consistency(intent) + coverage(intent) + completeness(intent)


def consistency(intent: dict) -> list[Finding]:
    out: list[Finding] = []
    role_ids = {r["role_id"] for r in intent.get("roles", [])}

    def need_role(role: str | None, where: str) -> None:
        if role is not None and role not in role_ids:
            out.append(Finding("error", "unknown_role", where, f"role {role!r} is not declared in roles[]"))

    sg = intent.get("safeguards_disabled", {})
    if sg.get("disabled") and "T4" not in intent.get("trigger_basis", []):
        out.append(Finding("error", "t4_missing", "/trigger_basis",
                           "safeguards are disabled, so T4 must be listed as a trigger basis"))
    need_role(sg.get("signer_role"), "/safeguards_disabled/signer_role")

    for i, c in enumerate(intent.get("pause_criteria", [])):
        need_role(c.get("authority_role"), f"/pause_criteria/{i}/authority_role")
    need_role(intent.get("restart_protocol", {}).get("approver_role"), "/restart_protocol/approver_role")
    need_role(intent.get("signer", {}).get("role_id"), "/signer/role_id")

    topo = intent.get("agent_surface", {})
    surfaces = {s["surface_id"]: s for s in topo.get("writable_surfaces", [])}
    for i, link in enumerate(topo.get("shared_surface_lineage", [])):
        if link["surface_id"] not in surfaces:
            out.append(Finding("error", "lineage_unknown_surface", f"/agent_surface/shared_surface_lineage/{i}",
                               f"surface {link['surface_id']!r} is not among writable_surfaces"))
    for sid, s in surfaces.items():
        if s["persistence"] in ("cross_run", "permanent") and s["tenancy"] != "run_only":
            if not any(l["surface_id"] == sid for l in topo.get("shared_surface_lineage", [])):
                out.append(Finding("warning", "shared_surface_without_lineage", "/agent_surface/writable_surfaces",
                                   f"surface {sid!r} persists and is shared but no other run is listed; "
                                   "confirm this is the first run to reach it"))
    if not intent.get("monitoring_instruments"):
        out.append(Finding("warning", "no_monitoring_declared", "/monitoring_instruments",
                           "monitoring is declared absent; closeout attestations of no events carry little weight"))
    if "trajectories" not in intent.get("log_retention", {}).get("retained", []):
        out.append(Finding("warning", "trajectories_not_retained", "/log_retention/retained",
                           "trajectories are not retained, so behavioural events cannot be reconciled at V1"))
    return out


def coverage(intent: dict) -> list[Finding]:
    out: list[Finding] = []
    triggers = set(intent["trigger_basis"])
    t4 = "T4" in triggers
    topo = intent["agent_surface"]
    monitors = effective_monitors(intent)
    criteria = intent["pause_criteria"]

    # A9: a filer that forecasts a high or critical capability must list T3; the forecast and the
    # trigger cannot disagree. (A low forecast that is false is not caught here; see T17.)
    if any(b in ("high", "critical") for b in intent["predicted_capability_band"].values()) and "T3" not in triggers:
        out.append(Finding("error", "t3_missing", "/trigger_basis",
                           "a high or critical capability is forecast, so T3 must be listed"))

    # A2: no monitoring under safeguards-off. [tabletop T07]
    if t4 and not monitors:
        out.append(Finding("error", "no_monitoring_t4", "/monitoring_instruments",
                           "a safeguards-off run must declare at least one monitor"))

    # A8: no enforcement on a network path under safeguards-off. [T08]
    for n, p in enumerate(topo["permitted_paths"]):
        if t4 and p["enforcement"] == "none":
            out.append(Finding("error", "unenforced_path_t4", f"/agent_surface/permitted_paths/{n}",
                               "a safeguards-off run cannot declare an unenforced network path"))

    # A3: path writability must be declared, and a writable path needs a surface behind it. [T01]
    via = {s.get("via_path") for s in topo["writable_surfaces"]}
    for n, p in enumerate(topo["permitted_paths"]):
        where = f"/agent_surface/permitted_paths/{n}"
        if "agent_writable" not in p:
            out.append(Finding("error", "writability_undeclared", where,
                               f"path {p['path_id']!r} must state whether agents can write through it"))
        elif p["agent_writable"] and p["path_id"] not in via:
            out.append(Finding("error", "writable_path_without_surface", where,
                               f"path {p['path_id']!r} is writable but no writable surface names it as via_path"))

    out += criterion_findings(intent)

    # A4/A2: core coverage under safeguards-off. Each core kind needs a live criterion that pauses. [T03, T04]
    if t4:
        for kind in CORE_KINDS_T4:
            if kind == "inter_agent_comms" and topo["inter_agent_comms_permitted"]:
                continue  # handled by A6
            live = [c for c in criteria
                    if kind in c["matches"] and c["required_action"] in PAUSING and observable(kind, monitors)]
            if not live:
                out.append(Finding("error", "core_kind_uncovered", "/pause_criteria",
                                   f"safeguards-off run has no observable, pausing criterion for {kind!r}"))

    # A6: permitting inter-agent communication is allowed, but then the channel must be declared,
    # retained and watched, so coordination stays visible. [T06]
    if topo["inter_agent_comms_permitted"]:
        # Same predicate as comms_flag_inconsistent below, or the two checks contradict each other
        # on an external shared surface (the public internet).
        if not shared_agent_surfaces(topo):
            out.append(Finding("error", "comms_channel_undeclared", "/agent_surface/inter_agent_comms_permitted",
                               "inter-agent communication is permitted but no shared surface carries it"))
        if "inter_agent_messages" not in intent["log_retention"]["retained"]:
            out.append(Finding("error", "comms_not_retained", "/log_retention/retained",
                               "inter-agent communication is permitted, so inter_agent_messages must be retained"))
        if not ({"inter_agent_message_monitor", "trajectory_review"} & monitors):
            out.append(Finding("error", "comms_unmonitored", "/monitoring_instruments",
                               "inter-agent communication is permitted but nothing monitors it"))

    # A5: one evaluation Intent per evaluation, not a standing quarterly filing. [T05]
    # Run kind is declared, not inferred from the trigger basis: an evaluation can also carry T3.
    kind = intent.get("run_kind")
    if kind is None:
        out.append(Finding("error", "run_kind_undeclared", "/run_kind",
                           "declare whether this is a training run or an evaluation"))
    if kind == "evaluation":
        win = intent["start_window"]
        if win.get("end") is None:
            out.append(Finding("error", "standing_intent", "/start_window/end",
                               "a safeguards-off evaluation Intent must have an end date"))
        elif date.fromisoformat(win["end"]) - date.fromisoformat(win["start"]) > timedelta(days=MAX_EVAL_DAYS):
            out.append(Finding("error", "standing_intent", "/start_window",
                               f"an evaluation Intent may cover at most {MAX_EVAL_DAYS} days; file one per evaluation"))
    return out


def completeness(intent: dict) -> list[Finding]:
    out: list[Finding] = []

    def E(code: str, where: str, msg: str) -> None:
        out.append(Finding("error", code, where, msg))

    topo, sg = intent["agent_surface"], intent["safeguards_disabled"]
    criteria, triggers = intent["pause_criteria"], set(intent["trigger_basis"])
    monitors = effective_monitors(intent)

    # Safeguards checklist: every production safeguard, each with a state. "Relaxed" counts as disabled,
    # so the T4 floor cannot be escaped by calling a weakening a relaxation. [R1 S2-E1, S3-E9]
    items = sg.get("checklist")
    if items is None:
        E("safeguard_checklist_missing", "/safeguards_disabled/checklist", f"state every safeguard: {', '.join(SAFEGUARDS)}")
    else:
        named = [i["safeguard"] for i in items]
        missing = [x for x in SAFEGUARDS if x not in named]
        if missing or len(named) != len(set(named)):
            E("safeguard_checklist_incomplete", "/safeguards_disabled/checklist", f"each safeguard exactly once; missing {missing}")
        weakened = [i for i in items if i["state"] != "on"]
        if bool(weakened) != bool(sg["disabled"]):
            E("disabled_inconsistent", "/safeguards_disabled/disabled",
              "disabled must be true exactly when some checklist item is relaxed or off")
        for n, i in enumerate(items):
            if i["state"] != "on" and not i.get("change"):
                E("safeguard_change_missing", f"/safeguards_disabled/checklist/{n}", f"say what was changed in {i['safeguard']!r}")

    out += monitor_findings(intent)

    # Every shared agent-writable surface is a channel, whatever the comms flag says. The duty attaches to
    # the surface, so denying communication does not pay. [R1 S2-E3; judge finding on honesty cost]
    for n, srf in enumerate(topo["writable_surfaces"]):
        if "isolation" not in srf:
            E("isolation_undeclared", f"/agent_surface/writable_surfaces/{n}", "declare isolation: per_episode or shared")
        elif srf["isolation"] == "shared" and srf["tenancy"] == "run_only":
            E("tenancy_mislabelled", f"/agent_surface/writable_surfaces/{n}",
              "a surface agents share cannot be run_only (see the tenancy definition)")
    shared = shared_agent_surfaces(topo)
    if shared:
        if not topo["inter_agent_comms_permitted"]:
            E("comms_flag_inconsistent", "/agent_surface/inter_agent_comms_permitted",
              f"surfaces {[x['surface_id'] for x in shared]} let agents read each other's writes, so this must be true")
        for kind, need_pause in (("environment_tampering", True), ("inter_agent_comms", False)):
            ok = [c for c in criteria if kind in c["matches"] and observable(kind, monitors)
                  and (c["required_action"] in PAUSING or not need_pause)]
            if not ok:
                E("shared_surface_floor", "/pause_criteria",
                  f"a run with a shared agent-writable surface needs an observable{' pausing' if need_pause else ''} "
                  f"criterion for {kind!r}")

    # Under safeguards-off every reportable kind must appear in some criterion (notify_only allowed beyond
    # the core kinds), so classification cannot route an event around every duty. [R1 S3-E3, S3-E4]
    if "T4" in triggers:
        covered = {k for c in criteria for k in c["matches"]}
        missing = [k for k in REPORTABLE if k not in covered]
        if missing:
            E("kind_uncriteried", "/pause_criteria", f"safeguards-off run has no criterion for {missing}")

    out += retention_findings(intent)

    # Facts a filer must state. [R1 S2-E10, S2-E12, S3-E8, S3-E14, S3-E15]
    for f in ("agent_capabilities", "readable_sources", "run_scale", "forecast_basis"):
        if f not in intent:
            E("field_missing", f"/{f}", f"{f} is required")
    if intent.get("run_kind") in ("training", "training_with_evaluation") and not intent.get("reward_design"):
        E("field_missing", "/reward_design", "a training run must describe its reward and grading design")
    if any(b != "low" for b in intent["predicted_capability_band"].values()) and not intent.get("eval_plan"):
        E("eval_plan_missing", "/eval_plan", "a forecast above low needs an eval_plan that tests it")

    # Process: time for intake review, separate restart approval, explicit end, real amendments.
    win = intent["start_window"]
    if "end" not in win:
        E("end_undeclared", "/start_window/end", "state an end date or null explicitly [R1 S2-E10]")
    elif intent.get("run_kind") in ("evaluation", "internal_deployment") and win["end"] is None:
        E("end_undeclared", "/start_window/end", "an evaluation or deployment needs an end date")
    if "amends" not in intent:
        lead = datetime.fromisoformat(win["start"] + "T00:00:00+00:00") - ts(intent["filed_at"])
        if lead < timedelta(days=INTAKE_DAYS):
            E("no_intake_time", "/filed_at",
              f"file at least {INTAKE_DAYS} days before the start so intake review can happen [R1: every Intent]")
    elif not intent.get("changes"):
        E("amendment_without_changes", "/changes", "an amendment must list what changed [R1 S3-E2]")
    out += restart_findings(intent)
    return out
