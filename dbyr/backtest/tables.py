"""The results-table designs, built from metrics (metrics.compute) for any set of cases.

  table1          section 6: attributable decision points, one row per framework
  table2          section 7: lead time of the outside record, one row per decision point
  scorecard       one row per case, one column per question
  question_matrix one row per question asked after an incident, one column per case
  today_vs_dbyr   one row per question: today's record, the DBYR record, and the evidence
  lifecycle       one row per stage of an incident, in the order they happen

A Table is plain data (strings), so every renderer draws the same numbers. Cells whose input a
case does not have say so instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .metrics import ESCAPE_LABELS, KIND_LABELS

NOT_ANNOTATED = "not annotated"


@dataclass
class Table:
    id: str
    title: str
    columns: list[str]
    rows: list[list[str]]
    new_columns: set[int] = field(default_factory=set)   # column indexes holding new metrics
    new_rows: set[int] = field(default_factory=set)      # row indexes holding new metrics
    notes: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ formatting

def duration(hours: float | None) -> str:
    if hours is None:
        return "n/a"
    if hours < 48:
        return f"{hours:g} hours"
    days = hours / 24
    if days < 21:
        return f"{days:.0f} days"
    if days < 90:
        return f"{days / 7:.0f} weeks"
    return f"{days / 30.4:.0f} months"


def span(s: dict | None) -> str:
    if not s:
        return "n/a"
    lo, hi = duration(s["min"]), duration(s["max"])
    return lo if lo == hi else f"{lo} to {hi}"


def verdict(m: dict) -> str:
    r = m["registered"][m["primary_variant"]]
    if m["void"]:
        return "void: scored against a schema other than the frozen one"
    if m["is_derivation_case"]:
        return "reference (design case)"
    margin = r["attributable"] - r["needed"]
    if not r["passes"]:
        return f"fails by {-margin}"
    return "passes at the line" if margin == 0 else f"passes by {margin}"


def attributable_cell(m: dict) -> str:
    r = m["registered"][m["primary_variant"]]
    return f"{r['attributable']} of {r['n']}; {verdict(m)}"


def known_cell(m: dict) -> str:
    a = m["awareness"]
    parts = [f"{a['yes']['n']} known", f"{a['no']['n']} not known"]
    if a["unclear"]["n"]:
        parts.append(f"{a['unclear']['n']} unclear")
    return ", ".join(parts)


def escapes_cell(m: dict) -> str:
    if not m["escapes"]:
        return "none"
    order = list(ESCAPE_LABELS)
    return "; ".join(f"{ESCAPE_LABELS[k]} ({n})" for k, n in sorted(m["escapes"].items(), key=lambda kv: order.index(kv[0])))


def stop_cell(m: dict) -> str:
    if m["changed"]:
        return f"Yes: {m['changed']} decisions would have been changed"
    if m["unseen"]:
        return f"No: {m['unseen']} events went unseen, so no rule could act"
    return "No: no decision would have been changed"


def outside_cell(m: dict) -> str:
    t = m["timeliness"]
    today = duration(t["outside_today_hours"]) if t["outside_today_hours"] is not None else "not annotated"
    return f"{today} → {duration(t['outside_dbyr_hours'])}"


def parties_cell(m: dict) -> str:
    p = m["affected_parties"]
    if not p["parties"]:
        return "no affected parties recorded"
    text = f"{p['with_record']} of {p['parties']} have a record"
    if p["without_record"]:
        text += f" (missing: {', '.join(p['without_record'])})"
    return text


def investigation_cell(m: dict) -> str:
    inv = m["investigation"]
    if not inv:
        return NOT_ANNOTATED
    return f"review covered {inv['review_days_inside']} of {inv['incident_days']} incident days ({inv['share']:.0%})"


def intake_cell(m: dict) -> str:
    errs = {k: v for k, v in m["registered"][m["primary_variant"]]["intake_errors"].items() if v}
    if not errs:
        return "the plan would have been accepted at intake"
    codes = sorted({c for v in errs.values() for c in v})
    return f"the plan would have been rejected at intake ({', '.join(codes)})"


def provenance_cell(m: dict) -> str:
    if not m["provenance"]:
        return "not assessed (no sources.json)"
    order = ["first-party", "required", "forced-choice", "hindsight", "placeholder", "unknown"]
    return "; ".join(f"{k} {n}" for k, n in sorted(m["provenance"].items(), key=lambda kv: order.index(kv[0])))


def deployment_cell(m: dict) -> str:
    d = m["deployment"]
    if not d:
        return "no deployment in this case"
    parts = [f"{d['systems']} system{'s' * (d['systems'] != 1)} on {d['base_runs']} run{'s' * (d['base_runs'] != 1)}",
             f"uncleared: {d['uncleared']}", f"over open incidents: {d['open_incidents']}"]
    if d["unknown_runs"]:
        parts.append(f"runs not on record: {d['unknown_runs']}")
    return "; ".join(parts)


def kind_cell(m: dict, kind: str) -> str:
    if not m["by_kind"]:
        return NOT_ANNOTATED
    k = m["by_kind"][kind]
    return f"{k['attributable']} of {k['n']}" if k["n"] else "none"


def common_notes(ms: list[dict]) -> list[str]:
    notes = ["Decision point: a moment where someone decided, or failed to decide, something that shaped the outcome.",
             "Attributable: the fact was written down before the run and the evidence to check it was kept.",
             "Pre-registered test: a case passes if at least half its decision points are attributable."]
    variants = sorted({m["primary_variant"] for m in ms})
    notes.append(f"Counts are for the {', '.join(variants)} filer variant.")
    if any(m["is_derivation_case"] for m in ms):
        notes.append("A design case is the one the protocol was written from; its score holds by construction.")
    notes.append("Metrics marked new were added after the pre-registered scoring and do not change any verdict.")
    return notes


# ------------------------------------------------------------------ the four designs

def scorecard(ms: list[dict]) -> Table:
    cols = ["Case", "Decision points", "Known at the time", "Attributable", "Why the rest escaped",
            "Unseen, so no rule could act", "Outsider learned: today → DBYR", "Affected parties with a record",
            "Decisions changed"]
    rows = [[m["label"], str(len(m["decision_points"])), known_cell(m), attributable_cell(m), escapes_cell(m),
             str(m["unseen"]), outside_cell(m), parties_cell(m), str(m["changed"])] for m in ms]
    return Table("scorecard", "Incident scorecard", cols, rows, new_columns={2, 4, 5, 6, 7}, notes=common_notes(ms))


QUESTIONS = [
    ("Which decisions shaped it?", False, lambda m: f"{len(m['decision_points'])} decision points"),
    ("Who knew at the time?", True, known_cell),
    ("Can each decision be traced to a prior record and checked?", False, attributable_cell),
    ("Why could the rest not be?", True, escapes_cell),
    ("Could a rule have stopped it?", True, stop_cell),
    ("Was it deployed on a cleared run, with known problems resolved?", True, deployment_cell),
    ("When did someone outside learn? (today → DBYR)", True, outside_cell),
    ("Was everyone affected told, or a reason recorded?", True, parties_cell),
    ("How far could investigators look?", True, investigation_cell),
    ("Would DBYR have changed a decision?", False,
     lambda m: f"{m['changed']} of {len(m['decision_points'])}; {intake_cell(m)}"),
    ("How much of the score rests on what the filer actually stated?", True, provenance_cell),
]


def question_matrix(ms: list[dict]) -> Table:
    cols = ["Question after the incident"] + [m["label"] for m in ms]
    rows = [[q] + [fn(m) for m in ms] for q, _, fn in QUESTIONS]
    return Table("question_matrix", "Question matrix", cols, rows,
                 new_rows={i for i, (_, new, _) in enumerate(QUESTIONS) if new}, notes=common_notes(ms))


DBYR_ANSWERS = [
    ("commitments", "What did they commit to before the run?",
     "A signed plan before the run: pause rules, who may pause, who approves a restart",
     lambda m: f"traceable and checkable: {m['registered'][m['primary_variant']]['attributable']} of {len(m['decision_points'])}"),
    ("who_knew", "Who knew, and when?", "Detection times fixed by notices filed within 72 hours",
     lambda m: f"not known at the time: {m['awareness']['no']['n']} of {len(m['decision_points'])}"),
    ("outside", "When did an outsider learn?", "The evaluator holds a notice within 72 hours of detection",
     outside_cell),
    ("affected", "Was everyone affected told?", "Every affected party has an entry with a date or a stated reason",
     parties_cell),
    ("investigation", "How far could investigators look?",
     "A standing right to extend scope; any refusal is logged with its grounds", investigation_cell),
    ("checkable", "Can the account be checked?", "Against evidence the filing promised to keep",
     lambda m: f"on record but uncheckable: {m['outcomes']['uncheckable']}"),
]


def today_vs_dbyr(ms: list[dict]) -> Table:
    cols = ["Question after the incident", "Today: from the organisations' own accounts", "Under DBYR: from the filings",
            "Backtest evidence"]
    rows = []
    for key, question, dbyr_text, evidence in DBYR_ANSWERS:
        today = "; ".join(f"{m['label']}: {m['today'][key]}" for m in ms if key in m["today"]) or NOT_ANNOTATED
        rows.append([question, today, dbyr_text, "; ".join(f"{m['label']}: {evidence(m)}" for m in ms)])
    notes = common_notes(ms) + ["The 'today' column comes from each case's annotations.json and is not scored."]
    return Table("today_vs_dbyr", "Today vs DBYR", cols, rows, new_columns={1, 3}, notes=notes)


def lifecycle(ms: list[dict]) -> Table:
    cols = ["Stage"] + [m["label"] for m in ms]
    rows = [
        [KIND_LABELS["setup"]] + [kind_cell(m, "setup") for m in ms],
        [KIND_LABELS["deploy"]] + [f"{kind_cell(m, 'deploy')}; {deployment_cell(m)}" for m in ms],
        ["Noticing the problem (event to detection)"] + [span(m["timeliness"]["detect_hours"]) for m in ms],
        [KIND_LABELS["respond"]] + [f"{kind_cell(m, 'respond')}; unseen: {m['unseen']}" for m in ms],
        [KIND_LABELS["tell"]] + [f"{kind_cell(m, 'tell')}; {parties_cell(m)}; outsider learned {outside_cell(m)}"
                                  for m in ms],
        [KIND_LABELS["investigate"]] + [f"{kind_cell(m, 'investigate')}; {investigation_cell(m)}" for m in ms],
        ["Overall"] + [f"{attributable_cell(m)}; decisions changed: {m['changed']}" for m in ms],
    ]
    notes = common_notes(ms) + ["Stages come from annotations.json (decision_kinds); the grouping was made after scoring."]
    return Table("lifecycle", "Incident lifecycle", cols, rows, new_rows={0, 1, 2, 3, 4, 5}, notes=notes)



# ------------------------------------------------------------------ the two design tables

FILER_LABELS = {"as_believed": "DBYR, as-believed filer", "diligent": "DBYR, diligent filer"}


def _share(f: dict) -> str:
    """The attributable share as a decimal, with the count beside it."""
    return f"{f['attributable'] / f['n']:.2f} ({f['attributable']})" if f["n"] else "-"


def table1(ms: list[dict]) -> Table:
    """Section 6: attributable decision points. One column per case, one row per filer."""
    cols = ["Framework"] + [f"{m['label']}{', in-sample' if m['is_derivation_case'] else ''} "
                            f"(N = {m['table1']['n']})" for m in ms]
    rows = []
    for key in ("as_believed", "diligent"):
        if any(key in m["table1"]["filers"] for m in ms):
            rows.append([FILER_LABELS.get(key, key)] +
                        [_share(m["table1"]["filers"][key]) if key in m["table1"]["filers"] else "-"
                         for m in ms])
    changed = "; ".join(f"{m['label']} {m['table1']['filers'][m['primary_variant']]['changed']} of "
                        f"{m['table1']['n']}" for m in ms)
    bar = "; ".join(
        f"{m['label']}: {m['registered'][m['primary_variant']]['attributable']} of {m['table1']['n']}, needs "
        f"{m['registered'][m['primary_variant']]['needed']} - "
        f"{'reference (in-sample)' if m['is_derivation_case'] else ('passes' if m['registered'][m['primary_variant']]['passes'] else 'fails')}"
        for m in ms)
    notes = [f"Each cell is the share of decision points that are attributable, with the count beside it.",
             f"Pass bar, fixed before scoring - at least half the decision points attributable. {bar}.",
             f"Reported separately, not folded into the above - decisions a rule would have changed (c): {changed}.",
             "An in-sample case is the one the protocol was written from; it shows traceability, not validation."]
    return Table("table1", "Table 1: attributable decision points", cols, rows, notes=notes)


def _lead(e: dict) -> str:
    if e["lead"] is None and e["dbyr"] is None and e["actual"] is None:
        return "-"
    if e.get("lead_range"):
        low, high = e["lead_range"]
        return f"{low}-{high}"
    if e["lead"] is None:
        return "none"
    prefix = {"lower": "\u2265", "upper": "\u2264"}.get(e.get("bound"), "")
    return f"{prefix}{e['lead']}"


def table2(ms: list[dict]) -> Table:
    """Section 7: lead time of the outside record, one row per decision point of each case."""
    cols = ["Decision point", "Decision", "Carrying filing", "Actual", "DBYR", "Lead time (days)"]
    rows, medians = [], []
    for m in ms:
        for e in m["table2"]:
            rows.append([e["id"], e["decision"][:80], e["carried_by"] or "-",
                         e["actual"] or "-", e["dbyr"] or "-", _lead(e)])
        got = sorted(e["lead"] for e in m["table2"] if e["lead"] is not None)
        if got:
            mid = got[len(got) // 2] if len(got) % 2 else (got[len(got)//2 - 1] + got[len(got)//2]) // 2
            by_carrier = {}
            for e in m["table2"]:
                if e["lead"] is not None:
                    by_carrier.setdefault(e["carried_by"], []).append(e["lead"])
            split = ", ".join(f"{k} n={len(v)} median {sorted(v)[len(v)//2]}d" for k, v in sorted(by_carrier.items()))
            medians.append(f"{m['label']}: median {mid} days, range {got[0]}-{got[-1]}, "
                           f"{len(got)} of {len(m['table2'])} scored. By carrying filing: {split}.")
    notes = medians + [
        "Measures visibility, not the length of an incident. Not 'days saved'.",
        "The three carrying filings mean different things, so do not average across them.",
        "Scored on the as-believed filer. A lead is zero where no filing was due.",
        "A range is a contested detection date, scored both ways. A sign is a bound, not an estimate."]
    missing = [f"{e['id']}: {e['note']}" for m in ms for e in m["table2"]
               if e["lead"] is None and e.get("note") and e["dbyr"] is None and e["actual"] is None]
    return Table("table2", "Table 2: lead time of the outside record", cols, rows, notes=notes + missing)


DESIGNS = {"table1": table1, "table2": table2, "scorecard": scorecard, "question_matrix": question_matrix,
           "today_vs_dbyr": today_vs_dbyr, "lifecycle": lifecycle}


def build(design: str, ms: list[dict]) -> Table:
    if design not in DESIGNS:
        raise KeyError(f"unknown table design {design!r}; choose from {sorted(DESIGNS)}")
    return DESIGNS[design](ms)
