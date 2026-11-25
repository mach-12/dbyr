"""Command line: dbyr <command> ...   (also python -m dbyr <command> ...)

  run PATH... [--out DIR] [--ledger FILE --key KEYFILE] [--json]
                                   the whole protocol over one filing set: a folder,
                                   its manifest.json, or a list of record files
  validate FILE...                 each filing on its own: schema and every check for its type
  project --view TIER FILE         print the public | restricted | sealed view of a filing
  keygen KEYFILE                   write a new Ed25519 signing key (PEM), for run --ledger
  verify LEDGER                    recheck every hash link and signature in a ledger
  freeze                           print the schema hash
  docs [DIR] [--check]             rewrite the field tables in the record docs (default docs/records)
                                   from the schemas; --check only reports stale docs (exit code 1)
  backtest init DIR [--name NAME]  write the example case to a new folder, to start from
  backtest check CASE...           check cases before scoring: shape, frozen schema hash, record keys, schema fields,
                                   placeholders. Scores nothing.
  backtest score CASE... [--out DIR] [--design NAME]... [--json]
                                   score cases; every input is hashed before and after scoring.
                                   Prints the verdicts and tables; --out writes the report and
                                   the per-case results
  backtest score CASE --mode dp_coverage [--filer_type F]
                                   how many decision points the filings make attributable:
                                   {total_dp, found_dp, coverage}
  backtest score CASE --mode visibility_gap --dp_num DP --filer_type F [--closeout-lag DAYS]
                                   how much earlier an outsider would have held one decision
                                   point's material fact: {actual_date, dbyr_date, found_early_by}.
                                   found_early_by is null where no filing was due before the fact
                                   reached the outside

  A CASE is a folder holding decision_points.json, or the decision_points.json file itself. Its
  filings are either listed in "records" or found through "filings": the path to any filing set
  (a folder or manifest.json), the same thing `dbyr run` takes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, load_pem_private_key)

from .backtest import (Backtest, Case, CaseError, DESIGNS, InputsChanged, SchemaChanged, VisibilityError,
                       check_case, dp_coverage, init_case, visibility_gap)
from .disclosure import project
from .docgen import sync
from .filingset import FilingSetError, load_filing_set
from .integrity import schema_hash
from .ledger import Ledger
from .protocol import run_protocol, safe_name
from .rules import validate_record


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _report(label: str, findings) -> int:
    n = lambda s: sum(f.severity == s for f in findings)
    errs = n("error")
    print(f"{'FAIL' if errs else 'ok':4}  {label}  ({errs} errors, {n('conduct')} conduct, {n('warning')} warnings)")
    for f in findings:
        print(f"      {f}")
    return 1 if errs else 0


def run(args) -> int:
    if args.ledger and not args.key:
        print("dbyr run: --ledger needs --key", file=sys.stderr)
        return 2
    try:
        filings = load_filing_set(*args.paths)
    except FilingSetError as exc:
        print(f"dbyr run: {exc}", file=sys.stderr)
        return 2
    key = load_pem_private_key(args.key.read_bytes(), password=None) if args.key else None
    report = run_protocol(filings, ledger=args.ledger, signing_key=key)
    print(json.dumps(report.to_json(), indent=2) if args.json else report.to_markdown(), end="")
    if args.out:
        _write(args.out / "report.json", report.to_json())
        (args.out / "report.md").write_text(report.to_markdown(), encoding="utf-8")
        for k, views in report.views.items():
            for tier in ("public", "restricted", "sealed", "openings"):
                _write(args.out / "views" / safe_name(k) / f"{tier}.json", views[tier])
    return 0 if report.ok else 1


def backtest(args) -> int:
    if args.bt_cmd == "init":
        try:
            path = init_case(args.dir, args.name)
        except CaseError as exc:
            print(f"dbyr backtest init: {exc}", file=sys.stderr)
            return 2
        print(f"wrote the example case to {path}; check it with: dbyr backtest check {path}")
        return 0

    if args.bt_cmd == "check":
        worst = 0
        for case in args.cases:
            problems = check_case(case)
            errs = sum(s == "error" for s, _ in problems)
            print(f"{'FAIL' if errs else 'ok':4}  {case}  ({errs} errors, {len(problems) - errs} warnings)")
            for severity, message in problems:
                print(f"      [{severity}] {message}")
            worst = max(worst, 1 if errs else 0)
        return worst

    if args.out:                      # make the output folder, and any parent, before scoring
        try:
            Path(args.out).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"dbyr backtest score: --out {args.out}: {exc}", file=sys.stderr)
            return 2

    if args.mode:
        if args.mode == "visibility_gap" and not (args.dp_num and args.filer_type):
            print("dbyr backtest score --mode visibility_gap: needs --dp_num and --filer_type", file=sys.stderr)
            return 2
        results = {}
        for case_path in args.cases:
            try:
                case = Case.load(case_path)
                results[case.name] = (
                    dp_coverage(case, args.filer_type) if args.mode == "dp_coverage"
                    else visibility_gap(case, args.dp_num, args.filer_type, args.closeout_lag))
            except (CaseError, VisibilityError) as exc:
                print(f"dbyr backtest score: {exc}", file=sys.stderr)
                return 2
        out = results if len(results) > 1 else next(iter(results.values()))
        print(json.dumps(out, indent=2, ensure_ascii=False))
        if args.out:
            path = Path(args.out) / f"{args.mode}.json"
            _write(path, out)
            print(f"wrote {path}", file=sys.stderr)
        return 0

    try:
        report = Backtest(*args.cases, designs=args.design or None).run()
    except (CaseError, ValueError, KeyError) as exc:
        print(f"dbyr backtest score: {exc}", file=sys.stderr)
        return 2
    except (InputsChanged, SchemaChanged) as exc:
        print(f"dbyr backtest score: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report.to_json(), indent=2, ensure_ascii=False) if args.json else report.markdown(), end="")
    if args.out:
        for path in report.write(args.out).values():
            print(f"wrote {path}", file=sys.stderr)
        for path in report.write_results():
            print(f"wrote {path}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="dbyr", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="the whole protocol over one filing set")
    r.add_argument("paths", nargs="+", help="a filing-set folder, its manifest.json, or record files")
    r.add_argument("--out", type=Path, help="write report.json, report.md and views/ here")
    r.add_argument("--ledger", type=Path, help="sign and append lodged filings to this ledger")
    r.add_argument("--key", type=Path, help="Ed25519 signing key for --ledger (see dbyr keygen)")
    r.add_argument("--json", action="store_true", help="print the report as JSON instead of Markdown")
    sub.add_parser("validate", help="check each filing on its own").add_argument("files", nargs="+")
    pr = sub.add_parser("project", help="print one disclosure view of a filing")
    pr.add_argument("--view", required=True, choices=["public", "restricted", "sealed"])
    pr.add_argument("file")
    sub.add_parser("keygen", help="write a new Ed25519 signing key").add_argument("keyfile")
    sub.add_parser("verify", help="recheck a ledger").add_argument("ledger")
    sub.add_parser("freeze", help="print the schema hash")
    d = sub.add_parser("docs", help="rewrite the field tables in the record docs from the schemas")
    d.add_argument("dir", nargs="?", type=Path, default=Path("docs/records"))
    d.add_argument("--check", action="store_true", help="only report stale docs; exit code 1 if any")
    b = sub.add_parser("backtest", help="score DBYR against incident cases: init, check, score")
    bsub = b.add_subparsers(dest="bt_cmd", required=True)
    bi = bsub.add_parser("init", help="write the example case to a new folder")
    bi.add_argument("dir", type=Path)
    bi.add_argument("--name", help="case name (default: the folder name)")
    bc = bsub.add_parser("check", help="check cases before scoring; scores nothing")
    bc.add_argument("cases", nargs="+", type=Path, help="case folders or decision_points.json files")
    bs = bsub.add_parser("score", help="score cases and build the results tables")
    bs.add_argument("cases", nargs="+", type=Path, help="case folders or decision_points.json files")
    bs.add_argument("--out", type=Path, help="write the results here")
    bs.add_argument("--mode", choices=["dp_coverage", "visibility_gap"],
                    help="dp_coverage: how many decision points the filings make attributable. "
                         "visibility_gap: how much earlier an outsider would have held one decision "
                         "point's material fact. Omit for the full report.")
    bs.add_argument("--dp_num", help="visibility_gap: the decision point, e.g. DP2 or 2")
    bs.add_argument("--filer_type", choices=["as_believed", "diligent"],
                    help="which filer to score; required for visibility_gap")
    bs.add_argument("--closeout-lag", type=int, metavar="DAYS",
                    help="filing lag after a closeout period ends; required for a closeout-carried point")
    bs.add_argument("--design", action="append", choices=sorted(DESIGNS), help="table design(s) to build (default: all)")
    bs.add_argument("--json", action="store_true", help="print the report as JSON instead of Markdown")
    args = p.parse_args(argv)

    if args.cmd == "run":
        return run(args)
    if args.cmd == "backtest":
        return backtest(args)
    if args.cmd == "validate":
        return max(_report(f, validate_record(_load(f))) for f in args.files)
    if args.cmd == "project":
        view, _ = project(_load(args.file), args.view)
        print(json.dumps(view, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "keygen":
        key = Ed25519PrivateKey.generate()
        Path(args.keyfile).write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
        Path(args.keyfile).chmod(0o600)
        print(f"wrote {args.keyfile}")
        return 0
    if args.cmd == "verify":
        return _report(args.ledger, Ledger(Path(args.ledger)).verify())
    if args.cmd == "freeze":
        print(schema_hash())
        return 0
    if args.cmd == "docs":
        try:
            stale = sync(args.dir, check=args.check)
        except (OSError, ValueError) as exc:
            print(f"dbyr docs: {exc}", file=sys.stderr)
            return 2
        for path in stale:
            print(f"{'out of date' if args.check else 'wrote'} {path}")
        return 1 if args.check and stale else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
