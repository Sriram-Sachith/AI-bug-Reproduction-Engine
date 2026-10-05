"""Command-line interface: run, retest, list, show."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bugrepro.config import get_settings
from bugrepro.pipeline import Pipeline, load_report
from bugrepro.store import FileStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bugrepro", description="AI Bug Reproduction Engine")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Collect a report and try to reproduce it")
    run_p.add_argument("--report", required=True, type=Path)
    run_p.add_argument("--repo", required=True)
    run_p.add_argument("--local", action="store_true", help="Development-only host execution")
    run_p.add_argument("--repeats", type=int, default=None)

    retest_p = sub.add_parser("retest", help="Rerun a saved test against a (fixed) repo")
    retest_p.add_argument("run_id")
    retest_p.add_argument("--repo", required=True)
    retest_p.add_argument("--local", action="store_true")
    retest_p.add_argument("--repeats", type=int, default=None)

    sub.add_parser("list", help="List stored runs")

    show_p = sub.add_parser("show", help="Print the Markdown report for a run")
    show_p.add_argument("run_id")
    show_p.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    settings = get_settings()
    store = FileStore(settings.resolved_data_dir())

    if args.cmd == "list":
        for summary in store.list_runs():
            verdict = summary.verdict.value if summary.verdict else "PENDING"
            print(f"{summary.run_id}\t{verdict}\t{summary.title}\t{summary.repo}")
        return 0

    if args.cmd == "show":
        if not store.exists(args.run_id):
            print(f"unknown run: {args.run_id}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(store.read_json(args.run_id, "report.json"), indent=2))
        else:
            print(store.read_text(args.run_id, "report.md"), end="")
        return 0

    pipeline = Pipeline(settings=settings, store=store, force_local=args.local)

    if args.cmd == "run":
        report = load_report(args.report)
        result = pipeline.run(report, args.repo, repeats=args.repeats)
        print(f"{result.run_id} {result.status.value}")
        if result.intermittent:
            print("intermittent: true")
        for warning in result.warnings:
            print(f"warning: {warning}", file=sys.stderr)
        print(store._folder(result.run_id) / "report.md")
        return 0 if result.status.value else 1

    if args.cmd == "retest":
        payload = pipeline.retest(args.run_id, args.repo, repeats=args.repeats)
        print(json.dumps(payload, indent=2))
        return 0 if payload["status"] == "FIX_VERIFIED" else 2

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
