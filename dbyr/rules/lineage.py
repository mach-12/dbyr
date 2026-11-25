"""Cross-run checks over a set of filings.

Per-run filings fragment oversight in the same way per-agent monitors do
(Makins et al., 2026). These checks link runs that reach the same persistent,
shared surface, so reconciliation is done over the linked group rather than run
by run. Surface identity is by surface_id, which a developer must keep stable
across runs for the same physical surface.
"""

from __future__ import annotations

from ..findings import Finding
from .common import shared_persistent, surfaces, ts


def check_lineage(intents: list[dict], closeouts: list[dict]) -> list[Finding]:
    out: list[Finding] = []
    ordered = sorted(intents, key=lambda i: ts(i["filed_at"]))

    for idx, later in enumerate(ordered):
        later_surfaces = surfaces(later)
        cited = {(l["surface_id"], l["run_id"]) for l in later["agent_surface"]["shared_surface_lineage"]}
        inherited = {(x["run_id"], x["exception_id"]) for x in later["agent_surface"].get("inherited_exceptions", [])}

        for earlier in ordered[:idx]:
            for sid, s in surfaces(earlier).items():
                if sid in later_surfaces and shared_persistent(s) and shared_persistent(later_surfaces[sid]):
                    if (sid, earlier["run_id"]) not in cited:
                        out.append(Finding(
                            "error", "lineage_not_cited", f"{later['run_id']}/agent_surface/shared_surface_lineage",
                            f"run {earlier['run_id']!r} reaches persistent shared surface {sid!r} but is not cited"))

        # Exceptions on a surface this run reaches that were on record, and still open, when it filed.
        # Only closeouts already filed count: a run cannot cite what nobody had recorded yet.
        for c in closeouts:
            if c["run_id"] == later["run_id"] or ts(c["filed_at"]) > ts(later["filed_at"]):
                continue
            for x in c["containment_exceptions"]:
                still_open = x["status"] == "open" or ts(x.get("closed_at", x["opened_at"])) > ts(later["filed_at"])
                if (x["surface_id"] in later_surfaces
                        and ts(x["opened_at"]) <= ts(later["filed_at"])
                        and still_open
                        and (c["run_id"], x["exception_id"]) not in inherited):
                    out.append(Finding(
                        "error", "inherited_exception_not_cited", f"{later['run_id']}/agent_surface/inherited_exceptions",
                        f"exception {x['exception_id']!r} on {x['surface_id']!r} (run {c['run_id']!r}) "
                        "was open when this run filed and is not cited"))
    return out + tenancy_conflicts(intents)


def tenancy_conflicts(intents: list[dict]) -> list[Finding]:
    """Two runs declaring the same surface with different tenancy cannot both be right. [T13]"""
    out: list[Finding] = []
    seen: dict[str, tuple[str, str]] = {}
    for i in intents:
        for s in i["agent_surface"]["writable_surfaces"]:
            sid = s["surface_id"]
            shared = s["tenancy"] != "run_only"
            if sid in seen and seen[sid][1] != str(shared):
                out.append(Finding("error", "tenancy_conflict", f"{i['run_id']}/agent_surface/writable_surfaces",
                                   f"surface {sid!r} is declared {s['tenancy']!r} here but shared differently by run "
                                   f"{seen[sid][0]!r}"))
            seen.setdefault(sid, (i["run_id"], str(shared)))
    return out


def linked_groups(intents: list[dict]) -> list[set[str]]:
    """Runs connected through persistent shared surfaces. Each group is one reconciliation unit."""
    parent: dict[str, str] = {i["run_id"]: i["run_id"] for i in intents}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    by_surface: dict[str, list[str]] = {}
    for i in intents:
        for sid, s in surfaces(i).items():
            if shared_persistent(s):
                by_surface.setdefault(sid, []).append(i["run_id"])
    for runs in by_surface.values():
        for r in runs[1:]:
            parent[find(r)] = find(runs[0])

    groups: dict[str, set[str]] = {}
    for run in parent:
        groups.setdefault(find(run), set()).add(run)
    return sorted(groups.values(), key=lambda g: sorted(g))
