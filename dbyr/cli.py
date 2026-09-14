"""dbyr — command line interface.

    dbyr validate examples/intent-exploitgym-2026-05.json
    dbyr validate examples/closeout-noncompliant-2026-07.json --intent examples/intent-exploitgym-2026-05.json
    dbyr view examples/intent-exploitgym-2026-05.json --tier public
    dbyr replay --intent examples/intent-exploitgym-2026-05.json
    dbyr file examples/intent-exploitgym-2026-05.json --register register.jsonl
    dbyr interop coverage
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import envelope, interop, redact, replay as replay_mod, validate as validate_mod

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVENTS = ROOT / "data" / "events" / "openai-exploitgym-2026.jsonl"


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def cmd_validate(args) -> int:
    intent = _load(args.intent) if args.intent else None
    record = _load(args.record)
    report = validate_mod.validate(record, intent=intent)
    print(report.render())
    return 0 if report.ok else 1


def cmd_view(args) -> int:
    view = redact.project(_load(args.record), args.tier)
    print(json.dumps(view, indent=2, ensure_ascii=False))
    return 0


def cmd_commitments(args) -> int:
    print(json.dumps(redact.commitments_for(_load(args.record), args.tier), indent=2))
    return 0


def cmd_replay(args) -> int:
    intent = _load(args.intent)
    events, excluded = replay_mod.load_events(args.events, first_party_only=not args.include_circumstantial)
    result = replay_mod.replay(intent, events, excluded)
    cf = replay_mod.counterfactual(result, events)
    if args.json:
        print(json.dumps({
            "run_id": result.run_id,
            "decision_points": result.decision_points,
            "bindings": [b.as_dict() for b in result.bindings],
            "inert_criteria": result.inert_criteria,
            "counterfactual": cf,
        }, indent=2))
    else:
        print(replay_mod.to_markdown(result, cf))
        if args.verbose:
            print("\n#### Every binding, in order\n")
            for b in result.bindings:
                print(f"- {b.date}  {b.field_bound:52s} {b.action:28s} [{b.authority}]")
    return 0


def cmd_file(args) -> int:
    record = _load(args.record)
    report = validate_mod.validate(record)
    if not report.ok and not args.force:
        print(report.render(), file=sys.stderr)
        print("refusing to file an invalid record (use --force to override)", file=sys.stderr)
        return 1
    key = None
    if args.sign and envelope.HAVE_ED25519:
        key, key_id = envelope.generate_key()
        print(f"# generated ephemeral pilot key {key_id}", file=sys.stderr)
    env = envelope.sign(record, key)
    reg = envelope.Register(args.register)
    entry = reg.append(env)
    ok, msg = reg.verify_chain()
    print(json.dumps({"entry": entry, "chain_ok": ok, "chain_note": msg}, indent=2))
    return 0


def cmd_interop(args) -> int:
    if args.artifact == "coverage":
        print(interop.coverage_report())
        return 0
    closeout = _load(args.closeout) if args.closeout else None
    if args.artifact == "sb53":
        print(json.dumps(interop.emit_sb53_incident(closeout), indent=2))
    elif args.artifact == "eu_cop":
        print(json.dumps(interop.emit_eu_cop_incident(closeout), indent=2))
    elif args.artifact == "frontier":
        print(json.dumps(interop.emit_frontier_audit_index(_load(args.intent), closeout), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="dbyr", description="Declare Before You Run v0.1 reference tooling")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="schema and semantic validation")
    v.add_argument("record")
    v.add_argument("--intent", help="matching Intent, to cross-check a Closeout")
    v.set_defaults(func=cmd_validate)

    w = sub.add_parser("view", help="derive a disclosure-tier view")
    w.add_argument("record")
    w.add_argument("--tier", choices=redact.TIERS, default="public")
    w.set_defaults(func=cmd_view)

    c = sub.add_parser("commitments", help="list hash commitments withheld at a tier")
    c.add_argument("record")
    c.add_argument("--tier", choices=redact.TIERS, default="public")
    c.set_defaults(func=cmd_commitments)

    r = sub.add_parser("replay", help="backtest an Intent against an incident event stream")
    r.add_argument("--intent", required=True)
    r.add_argument("--events", default=str(DEFAULT_EVENTS))
    r.add_argument("--include-circumstantial", action="store_true",
                   help="score circumstantially attributed threads too (excluded by default)")
    r.add_argument("--json", action="store_true")
    r.add_argument("--verbose", action="store_true")
    r.set_defaults(func=cmd_replay)

    f = sub.add_parser("file", help="sign a record and append it to a register")
    f.add_argument("record")
    f.add_argument("--register", default="register.jsonl")
    f.add_argument("--sign", action="store_true", help="sign with an ephemeral Ed25519 key (pilot only)")
    f.add_argument("--force", action="store_true")
    f.set_defaults(func=cmd_file)

    i = sub.add_parser("interop", help="regime coverage and emitters")
    i.add_argument("artifact", choices=["coverage", "sb53", "eu_cop", "frontier"])
    i.add_argument("--closeout")
    i.add_argument("--intent")
    i.set_defaults(func=cmd_interop)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
