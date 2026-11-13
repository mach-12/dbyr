"""Draw tables and reports: Markdown and a self-contained HTML page.

Also holds the per-case results.md writer of the pre-registered scorer, unchanged.
"""

from __future__ import annotations

import html
import math

from .metrics import ESCAPE_LABELS, KIND_LABELS
from .tables import Table

NEW = "new"


# ------------------------------------------------------------------ escaping

def _md(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


# ------------------------------------------------------------------ tables

def table_markdown(t: Table) -> str:
    head = [c + (f" *({NEW})*" if i in t.new_columns else "") for i, c in enumerate(t.columns)]
    lines = [f"### {t.title}", "", "| " + " | ".join(_md(h) for h in head) + " |",
             "|" + "---|" * len(head)]
    for i, row in enumerate(t.rows):
        cells = [_md(c) for c in row]
        if i in t.new_rows:
            cells[0] += f" *({NEW})*"
        lines.append("| " + " | ".join(cells) + " |")
    lines += [""] + [f"- {n}" for n in t.notes]
    return "\n".join(lines) + "\n"


def table_html(t: Table) -> str:
    th = "".join(f"<th>{html.escape(c)}{' <span class=new>new</span>' if i in t.new_columns else ''}</th>"
                 for i, c in enumerate(t.columns))
    trs = []
    for i, row in enumerate(t.rows):
        first = html.escape(row[0]) + (" <span class=new>new</span>" if i in t.new_rows else "")
        tds = "".join(f"<td>{html.escape(c)}</td>" for c in row[1:])
        trs.append(f"<tr><th>{first}</th>{tds}</tr>")
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in t.notes)
    return (f'<section id="{t.id}"><h2>{html.escape(t.title)}</h2>'
            f'<div class="scroll"><table><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table></div>'
            f'<ul class="notes">{notes}</ul></section>')


# ------------------------------------------------------------------ per-decision detail

def decisions_markdown(m: dict) -> str:
    lines = [f"### {m['label']}: every decision point ({m['primary_variant']} filer)", "",
             "| Decision point | Kind | Known at the time | Recorded before | Checkable after | Changes decision | Outcome | Why not attributable | Rests on |",
             "|---|---|---|---|---|---|---|---|---|"]
    for x in m["decision_points"]:
        lines.append("| " + " | ".join(_md(s) for s in [
            f"{x['id']}: {x['decision']}", KIND_LABELS.get(x["kind"], "") if x["kind"] else "", x["aware"],
            x["recorded_before"], x["checkable_after"], x["changes_decision"], x["outcome"],
            ESCAPE_LABELS.get(x["escape"], x["escape"] or ""), x["provenance"] or ""]) + " |")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ full report

CSS = """
:root{--bg:#f5f7fa;--surface:#fff;--ink:#16202b;--muted:#5a6676;--rule:#dce2ea;--accent:#2c5c8c;--soft:#e6eef7;--ok:#2c7a57;--bad:#b0434a}
@media (prefers-color-scheme:dark){:root{--bg:#11161d;--surface:#18202a;--ink:#e5eaf1;--muted:#9aa6b6;--rule:#2a3441;--accent:#86aedb;--soft:#1f2c3b;--ok:#62c194;--bad:#e7868b;color-scheme:dark}}
body{background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,sans-serif;margin:0;padding:32px max(16px,env(safe-area-inset-left,0px))}
main{max-width:1100px;margin:0 auto;display:grid;gap:32px}h1,h2{margin:0;line-height:1.2}p{max-width:72ch;margin:0}
.scroll{overflow-x:auto;background:var(--surface);border:1px solid var(--rule);border-radius:8px}
table{border-collapse:collapse;width:100%;min-width:720px;font-size:.88rem}th,td{text-align:left;vertical-align:top;padding:8px 12px;border-bottom:1px solid var(--rule)}
thead th{font-size:.74rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);background:var(--bg)}
.new{font-size:.66rem;text-transform:uppercase;color:var(--accent);border:1px solid var(--accent);border-radius:4px;padding:0 4px}
.notes{color:var(--muted);font-size:.85rem}.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}
code{font-family:ui-monospace,Consolas,monospace;font-size:.85em}
"""


def report_markdown(report) -> str:
    out = ["# DBYR backtest report", "", f"Schema hash: `{report.schema_hash}`", "",
           "## Input integrity", ""]
    for name, check in report.integrity.items():
        state = "unchanged" if check["unchanged"] else "CHANGED: " + "; ".join(check["diff"])
        out.append(f"- `{name}`: {len(check['files'])} input files hashed before and after scoring, {state}")
    out += [""] + [table_markdown(t) for t in report.tables]
    return "\n".join(out)


def report_html(report) -> str:
    integrity = "".join(
        f"<li><code>{html.escape(n)}</code>: {len(c['files'])} input files hashed before and after scoring, "
        f"{'unchanged' if c['unchanged'] else 'CHANGED'}</li>" for n, c in report.integrity.items())
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'><title>DBYR backtest report</title>"
            f"<style>{CSS}</style></head><body><main><header><h1>DBYR backtest report</h1>"
            f"<p>Schema hash <code>{html.escape(report.schema_hash)}</code></p></header>"
            f"<section><h2>Input integrity</h2><ul>{integrity}</ul></section>"
            + "".join(table_html(t) for t in report.tables) + "</main></body></html>\n")


def _decisions_html(m: dict) -> str:
    head = ["Decision point", "Kind", "Known at the time", "Recorded before", "Checkable after",
            "Changes decision", "Outcome", "Why not attributable", "Rests on"]
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in [
            f"{x['id']}: {x['decision']}", KIND_LABELS.get(x["kind"], "") if x["kind"] else "", x["aware"],
            x["recorded_before"], x["checkable_after"], x["changes_decision"], x["outcome"],
            ESCAPE_LABELS.get(x["escape"], x["escape"] or ""), x["provenance"] or ""]) + "</tr>"
        for x in m["decision_points"])
    return "<table><thead><tr>" + "".join(f"<th>{h}</th>" for h in head) + f"</tr></thead><tbody>{body}</tbody></table>"


# ------------------------------------------------------------------ pre-registered per-case outputs

def results_markdown(result: dict) -> str:
    out = [f"# Backtest: {result['case']}", ""]
    if result["is_derivation_case"]:
        out += ["**Derivation case.** (a) and (b) are traceability, not validation.", ""]
    out += [f"Schema hash: `{result['schema_hash']}`",
            f"Reconstructed filings well formed: {result['filings_well_formed']}", ""]
    for name, v in result["variants"].items():
        out += [f"## Filer variant: {name}", "",
                "| DP | (a) recorded before | (b) checkable after | (c) changes decision | why |",
                "|---|---|---|---|---|"]
        out += [f"| {r['id']} | {r['recorded_before']} | {r['checkable_after']} | {r['changes_decision']} | {r['reason']} |"
                for r in v["rows"]]
        out += ["", "Intake review of the reconstructed Intents: " +
                "; ".join(f"{k}: {', '.join(c) or 'accepted'}" for k, c in v["intake_errors"].items())]
        verdict = "passes" if v["passes_heldout_criterion"] else "FAILS"
        out += ["", f"Attributable on {v['attributable']} of {v['n']}; {verdict} the held-out criterion "
                    f"(needs {math.ceil(v['n'] / 2)}).", ""]
    return "\n".join(out)
