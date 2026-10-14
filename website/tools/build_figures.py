#!/usr/bin/env python3
"""Regenerate the generated blocks of website/index.html.

Three blocks on the landing page are derived rather than hand-written, so that
they cannot drift from the schemas or the paper:

  fig1      the DBYR lifecycle, laid out from the four record names
  fig2      the record schema, built from the \\fig*List macros that
            code/reproduce.sh writes into generated/schema_fields.tex
  fig3      the incident timeline by thread, from the event dates below
            (kept in step with the paper's tikz figure by hand)

Each is spliced into index.html between
``<!-- BEGIN generated: NAME -->`` and ``<!-- END generated: NAME -->``.

    python website/tools/build_figures.py
"""

from __future__ import annotations

import argparse
import html
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
INDEX = ROOT / "website" / "index.html"
SCHEMA_FIELDS = ROOT / "generated" / "schema_fields.tex"

IND = " " * 14  # indentation of elements inside <svg> in index.html


# --------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------
def field_list(tex: str, macro: str) -> list[tuple[str, str]]:
    """Parse one \\newcommand{\\figXList}{P/a, R/b, ...} into [(tier, field)]."""
    m = re.search(r"\\newcommand\{\\" + macro + r"\}\{(.*?)\}\n", tex, re.S)
    if not m:
        raise SystemExit(f"{macro} not found in {SCHEMA_FIELDS}")
    out = []
    for item in m.group(1).split(","):
        tier, field = item.strip().replace("\\_", "_").split("/", 1)
        out.append((tier, field))
    return out


# --------------------------------------------------------------------------
# figure 2: record schema at a glance
# --------------------------------------------------------------------------
ROW, HEAD, PAD = 20.0, 46.0, 10.0
COLW, GAP, X0 = 300.0, 35.0, 10.0


def schema_column(x: float, y: float, title: str, fields: list[tuple[str, str]]):
    h = HEAD + ROW * len(fields) + PAD
    s = [
        f'{IND}<rect class="fig-box" x="{x:g}" y="{y:g}" width="{COLW:g}" height="{h:g}" rx="6" />',
        # tinted header band: rounded on top, square where it meets the rule
        f'{IND}<rect class="fig-head" x="{x + 1:g}" y="{y + 1:g}" width="{COLW - 2:g}" '
        f'height="{HEAD - 9:g}" rx="5" />',
        f'{IND}<rect class="fig-head" x="{x + 1:g}" y="{y + HEAD - 20:g}" width="{COLW - 2:g}" '
        f'height="12" />',
        f'{IND}<line class="tl-grid" x1="{x:g}" y1="{y + HEAD - 8:g}" '
        f'x2="{x + COLW:g}" y2="{y + HEAD - 8:g}" />',
        f'{IND}<text class="fig-label" x="{x + 14:g}" y="{y + 20:g}">{title}</text>',
        f'{IND}<text class="fig-sublabel" x="{x + 14:g}" y="{y + 33:g}">'
        f"{len(fields)} required fields</text>",
    ]
    for i, (tier, field) in enumerate(fields):
        cy = y + HEAD + ROW * i + ROW / 2
        if i:
            s.append(
                f'{IND}<line class="tl-grid" x1="{x + 14:g}" y1="{cy - ROW / 2:g}" '
                f'x2="{x + COLW - 14:g}" y2="{cy - ROW / 2:g}" />'
            )
        cls = "fig-dot-public" if tier == "P" else "fig-dot-restricted"
        s.append(f'{IND}<circle class="{cls}" cx="{x + 24:g}" cy="{cy:g}" r="3.5" />')
        s.append(
            f'{IND}<text class="fig-field" x="{x + 38:g}" y="{cy + 4:g}">'
            f"{html.escape(field)}</text>"
        )
    return s, h


def build_fig2(tex: str) -> str:
    intent = field_list(tex, "figIntentList")
    closeout = field_list(tex, "figCloseoutList")
    notice = field_list(tex, "figNoticeList")
    runtime = field_list(tex, "figRuntimeList")

    parts: list[str] = []
    s, h_intent = schema_column(X0, 10, "TrainingRunIntent", intent)
    parts += s
    s, _ = schema_column(X0 + COLW + GAP, 10, "TrainingRunCloseout", closeout)
    parts += s
    x3 = X0 + 2 * (COLW + GAP)
    s, h_notice = schema_column(x3, 10, "ExceptionNotice", notice)
    parts += s
    y_rt = 10 + h_notice + 18
    s, h_runtime = schema_column(x3, y_rt, "SystemRuntimeRecord", runtime)
    parts += s

    # legend sits in the right-hand column under SystemRuntimeRecord, as in the paper
    legy = y_rt + h_runtime + 30
    lx = x3 + 14
    parts += [
        f'{IND}<text class="fig-label" x="{lx:g}" y="{legy:g}">Disclosure tier at filing</text>',
        f'{IND}<circle class="fig-dot-public" cx="{lx + 6:g}" cy="{legy + 20:g}" r="3.5" />',
        f'{IND}<text class="fig-sublabel" x="{lx + 18:g}" y="{legy + 24:g}">Public</text>',
        f'{IND}<circle class="fig-dot-restricted" cx="{lx + 96:g}" cy="{legy + 20:g}" r="3.5" />',
        f'{IND}<text class="fig-sublabel" x="{lx + 108:g}" y="{legy + 24:g}">Restricted</text>',
    ]
    height = max(10 + h_intent, legy + 24) + 10

    return (
        f'            <svg viewBox="0 0 1000 {height:g}" role="img" '
        'aria-labelledby="fig2-title fig2-desc">\n'
        f'{IND}<title id="fig2-title">Record schema at a glance</title>\n'
        f'{IND}<desc id="fig2-desc">The fields each of the four DBYR records must carry, '
        f"marked by disclosure tier at filing: TrainingRunIntent "
        f"({len(intent)} fields), TrainingRunCloseout ({len(closeout)}), ExceptionNotice "
        f"({len(notice)}) and SystemRuntimeRecord ({len(runtime)}).</desc>\n"
        + "\n".join(parts)
        + "\n            </svg>"
    )


# --------------------------------------------------------------------------
# figure 1: the lifecycle
# --------------------------------------------------------------------------
BOXES = [
    ("BEFORE THE RUN, \u2265 3 DAYS", "TrainingRunIntent",
     "topology, safeguards,", "criteria, monitors"),
    ("WITHIN 72 H OF DETECTION", "ExceptionNotice",
     "events, kinds, criteria,", "parties, action"),
    ("EVERY 30 DAYS / AT END", "TrainingRunCloseout",
     "events, pauses, notices,", "preservation, scope"),
    ("BEFORE DEPLOYMENT", "SystemRuntimeRecord",
     "scaffolding, scaling,", "inter-agent comms"),
]
TIERS = [
    ("tint", "Public", "existence, compute band,", "commitment hashes", ""),
    ("mid", "Restricted", "full record, vetted evaluator", "and auditor access", ""),
    ("dark", "Sealed", "withheld pending challenge,", "salted hash commitments", " on-dark"),
]
BW, BH, BY = 236.0, 112.0, 10.0
LY, LH = 196.0, 58.0
TY, TH, TW = 300.0, 86.0, 300.0


def build_fig1() -> str:
    q: list[str] = []
    for i, (kick, label, s1, s2) in enumerate(BOXES):
        x = 10 + i * (BW + 12)
        q += [
            f'{IND}<rect class="fig-box" x="{x:g}" y="{BY:g}" width="{BW:g}" height="{BH:g}" rx="6" />',
            f'{IND}<text class="fig-title" x="{x + 16:g}" y="{BY + 26:g}">{html.escape(kick)}</text>',
            f'{IND}<text class="fig-label" x="{x + 16:g}" y="{BY + 52:g}">{label}</text>',
            f'{IND}<text class="fig-sublabel" x="{x + 16:g}" y="{BY + 74:g}">{s1}</text>',
            f'{IND}<text class="fig-sublabel" x="{x + 16:g}" y="{BY + 90:g}">{s2}</text>',
            f'{IND}<line class="fig-arrow" x1="{x + BW / 2:g}" y1="{BY + BH:g}" '
            f'x2="{x + BW / 2:g}" y2="{LY - 4:g}" marker-end="url(#fig1-arrow)" />',
        ]
    q += [
        f'{IND}<rect class="fig-box dark" x="10" y="{LY:g}" width="980" height="{LH:g}" rx="6" />',
        f'{IND}<text class="fig-label on-dark" x="500" y="{LY + 25:g}" text-anchor="middle">'
        "Append-only record: evaluator archive (Layer A) or register (Layer B)</text>",
        f'{IND}<text class="fig-sublabel on-dark" x="500" y="{LY + 44:g}" text-anchor="middle">'
        "hash-chained \u00b7 Ed25519-signed \u00b7 salted commitments for hidden fields</text>",
    ]
    for i, (kind, label, s1, s2, dark) in enumerate(TIERS):
        x = 10 + i * (TW + 40)
        q += [
            f'{IND}<line class="fig-arrow" x1="{x + TW / 2:g}" y1="{LY + LH:g}" '
            f'x2="{x + TW / 2:g}" y2="{TY - 4:g}" marker-end="url(#fig1-arrow)" />',
            f'{IND}<rect class="fig-box {kind}" x="{x:g}" y="{TY:g}" width="{TW:g}" '
            f'height="{TH:g}" rx="6" />',
            f'{IND}<text class="fig-label{dark}" x="{x + 16:g}" y="{TY + 28:g}">{label}</text>',
            f'{IND}<text class="fig-sublabel{dark}" x="{x + 16:g}" y="{TY + 50:g}">{s1}</text>',
            f'{IND}<text class="fig-sublabel{dark}" x="{x + 16:g}" y="{TY + 66:g}">{s2}</text>',
        ]
    # arrow annotations, beside the first record arrow and the first tier arrow
    q += [
        f'{IND}<text class="fig-note" x="{10 + BW / 2 + 8:g}" y="{(BY + BH + LY) / 2 + 4:g}">'
        "filed &amp; signed</text>",
        f'{IND}<text class="fig-note" x="{10 + TW / 2 + 8:g}" y="{(LY + LH + TY) / 2 + 4:g}">'
        "per-field redaction map</text>",
    ]

    return (
        f'            <svg viewBox="0 0 1000 {TY + TH + 10:g}" role="img" '
        'aria-labelledby="fig1-title fig1-desc">\n'
        f'{IND}<title id="fig1-title">The DBYR lifecycle</title>\n'
        f'{IND}<desc id="fig1-desc">Four signed records \u2014 TrainingRunIntent, '
        "ExceptionNotice, TrainingRunCloseout and SystemRuntimeRecord \u2014 are filed at "
        "different points in a covered run\u2019s life and flow into an append-only, "
        "hash-chained record, which projects into Public, Restricted and Sealed disclosure "
        "tiers.</desc>\n"
        f"{IND}<defs>\n"
        f'{IND}  <marker id="fig1-arrow" viewBox="0 0 10 10" refX="8" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">\n'
        f'{IND}    <path class="fig-arrow-head" d="M0,0 L10,5 L0,10 z" />\n'
        f"{IND}  </marker>\n{IND}</defs>\n" + "\n".join(q) + "\n            </svg>"
    )


# --------------------------------------------------------------------------
# figure 3: incident timeline by thread (mirrors the paper's tikz figure)
# --------------------------------------------------------------------------
MONTH_OFFSET = {5: 0, 6: 31, 7: 61, 8: 92, 9: 123}  # days before the 1st, from 30 Apr
TL_X0, TL_PX, TL_END = 110.0, 6.3, 139  # x of 1 May, px per day, last day drawn (16 Sep)
LANE_A, LANE_B, LANE_C = 170.0, 320.0, 380.0
LANES = [(LANE_A, "Artifactory/HF"), (LANE_B, "German wiki"), (LANE_C, "RubyGems")]
# multi-day events: (lane, start, end, muted)
TL_SPANS = [(LANE_A, (7, 4), (7, 8), False), (LANE_A, (7, 8), (7, 19), False),
            (LANE_B, (6, 16), (6, 19), True), (LANE_C, (5, 11), (5, 12), True)]
TL_PRIMARY = [(5, 7), (5, 12), (7, 4), (7, 5), (7, 8), (7, 10), (7, 11), (7, 12), (7, 13),
              (7, 20), (7, 21), (7, 27), (8, 5), (8, 18), (8, 26), (9, 4), (9, 9)]
TL_WIKI = [(5, 11), (5, 24), (5, 26), (6, 2), (6, 16), (6, 21), (6, 22), (6, 26), (7, 2), (7, 7)]
TL_RUBY = [(5, 5), (5, 11), (5, 12), (5, 16), (6, 18), (9, 11)]
# decision points, labelled above the line: (date, label, date text, high tier)
TL_DECISIONS = [((5, 8), "Write access found", "8 May", False),
                ((6, 11), "2nd model started", "11 Jun", False),
                ((7, 8), "Restart", "after 8 Jul", False),
                ((5, 26), "First SSRF", "26 May", True),
                ((6, 26), "Admin access", "26 Jun", True),
                ((7, 29), "Review scoped", "29 Jul", True)]
# disclosure / detection, labelled below the line: (date, label, date text, depth, anchor)
TL_CONTEXT = [((7, 16), "HF discloses", "16 Jul", 86, "end"),
              ((7, 19), "OpenAI’s alert", "19 Jul", 34, "start")]


def tx(md: tuple[int, int]) -> float:
    m, d = md
    return round(TL_X0 + (MONTH_OFFSET[m] + d - 1) * TL_PX, 1)


def diamond(x: float, y: float, r: float = 4.0) -> str:
    return (f'{IND}<path class="tl-dot-secondary" '
            f'd="M{x:g},{y - r:g} L{x + r:g},{y:g} L{x:g},{y + r:g} L{x - r:g},{y:g} z" />')


def build_fig3() -> str:
    q: list[str] = []
    for m, name in [(5, "May"), (6, "Jun"), (7, "Jul"), (8, "Aug"), (9, "Sep")]:
        x = tx((m, 1))
        q += [f'{IND}<line class="tl-grid dashed" x1="{x:g}" y1="32" x2="{x:g}" y2="{LANE_C + 22:g}" />',
              f'{IND}<text class="tl-month" x="{x + 4:g}" y="24">{name}</text>']
    xend = tx((5, 1)) + (TL_END - 1) * TL_PX
    for y, name in LANES:
        q += [f'{IND}<line class="tl-lane" x1="{TL_X0:g}" y1="{y:g}" x2="{xend:g}" y2="{y:g}" />',
              f'{IND}<text class="tl-lane-label" x="{TL_X0 - 8:g}" y="{y + 4:g}" '
              f'text-anchor="end">{name}</text>']
    for y, a, b, muted in TL_SPANS:
        cls = "tl-span muted" if muted else "tl-span"
        q.append(f'{IND}<line class="{cls}" x1="{tx(a):g}" y1="{y:g}" x2="{tx(b):g}" y2="{y:g}" />')
    q += [f'{IND}<circle class="tl-dot-primary" cx="{tx(d):g}" cy="{LANE_A:g}" r="2.5" />'
          for d in TL_PRIMARY]
    q += [f'{IND}<circle class="tl-dot-secondary" cx="{tx(d):g}" cy="{LANE_B:g}" r="3" />'
          for d in TL_WIKI]
    q += [diamond(tx(d), LANE_C) for d in TL_RUBY]
    for d, label, date, high in TL_DECISIONS:
        x, top = tx(d), LANE_A - (74 if high else 36)
        q += [f'{IND}<line class="tl-leader" x1="{x:g}" y1="{top:g}" x2="{x:g}" y2="{LANE_A:g}" />',
              f'{IND}<text class="tl-key-label" x="{x:g}" y="{top - 18:g}" text-anchor="middle">{label}</text>',
              f'{IND}<text class="tl-key-date" x="{x:g}" y="{top - 6:g}" text-anchor="middle">{date}</text>',
              f'{IND}<circle class="tl-dot-decision" cx="{x:g}" cy="{LANE_A:g}" r="5" />']
    for d, label, date, depth, anchor in TL_CONTEXT:
        x, bot = tx(d), LANE_A + depth
        tx_ = x + 3 if anchor == "start" else x - 3
        q += [f'{IND}<line class="tl-leader" x1="{x:g}" y1="{LANE_A:g}" x2="{x:g}" y2="{bot:g}" />',
              f'{IND}<text class="tl-key-label" x="{tx_:g}" y="{bot + 12:g}" text-anchor="{anchor}">{label}</text>',
              f'{IND}<text class="tl-key-date" x="{tx_:g}" y="{bot + 24:g}" text-anchor="{anchor}">{date}</text>',
              f'{IND}<circle class="tl-dot-context" cx="{x:g}" cy="{LANE_A:g}" r="4.5" />']
    ly = LANE_C + 58
    q += [f'{IND}<circle class="tl-dot-decision" cx="{TL_X0:g}" cy="{ly:g}" r="5" />',
          f'{IND}<text class="tl-legend" x="{TL_X0 + 12:g}" y="{ly + 4:g}">Decision point</text>',
          f'{IND}<circle class="tl-dot-context" cx="{TL_X0 + 140:g}" cy="{ly:g}" r="4.5" />',
          f'{IND}<text class="tl-legend" x="{TL_X0 + 152:g}" y="{ly + 4:g}">Disclosure / detection</text>',
          f'{IND}<circle class="tl-dot-primary" cx="{TL_X0 + 320:g}" cy="{ly:g}" r="2.5" />',
          f'{IND}<circle class="tl-dot-secondary" cx="{TL_X0 + 331:g}" cy="{ly:g}" r="3" />',
          diamond(TL_X0 + 343, ly),
          f'{IND}<text class="tl-legend" x="{TL_X0 + 355:g}" y="{ly + 4:g}">Other event (by thread)</text>',
          f'{IND}<line class="tl-span" x1="{TL_X0 + 530:g}" y1="{ly:g}" x2="{TL_X0 + 552:g}" y2="{ly:g}" />',
          f'{IND}<text class="tl-legend" x="{TL_X0 + 564:g}" y="{ly + 4:g}">Multi-day event</text>']

    return (
        f'            <svg viewBox="0 0 1000 {ly + 20:g}" role="img" '
        'aria-labelledby="fig3-title fig3-desc">\n'
        f'{IND}<title id="fig3-title">Incident timeline by thread</title>\n'
        f'{IND}<desc id="fig3-desc">Three concurrent threads from 5 May to 11 September 2026: '
        "Artifactory/Hugging Face (first-party), German wiki (circumstantial) and RubyGems "
        "(circumstantial). Six decision points and two disclosure or detection events on the "
        "first-party thread are labelled.</desc>\n"
        + "\n".join(q) + "\n            </svg>"
    )


# --------------------------------------------------------------------------
def splice(page: str, name: str, block: str) -> str:
    begin, end = f"<!-- BEGIN generated: {name} -->", f"<!-- END generated: {name} -->"
    i, j = page.index(begin) + len(begin), page.index(end)
    return page[:i] + "\n" + block + "\n" + " " * 10 + page[j:]


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()

    page = INDEX.read_text(encoding="utf-8")
    tex = SCHEMA_FIELDS.read_text(encoding="utf-8")

    page = splice(page, "fig1", build_fig1())
    page = splice(page, "fig2", build_fig2(tex))
    page = splice(page, "fig3", build_fig3())

    INDEX.write_text(page, encoding="utf-8")
    print(f"wrote {INDEX.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
