"""Benchmark harness: reproduction rate, false-positive rate, mean time to reproduce."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from bugrepro.config import Settings, PROJECT_ROOT
from bugrepro.pipeline import Pipeline, load_report
from bugrepro.store import FileStore


def run_benchmark(manifest_path: Path, *, local: bool = True) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    settings = Settings(use_docker=not local, repeat=3, timeout_seconds=30)
    pipeline = Pipeline(
        settings=settings,
        store=FileStore(settings.resolved_data_dir()),
        force_local=local,
        allow_any_repo=True,
    )
    rows = []
    for case in manifest["cases"]:
        report = load_report(PROJECT_ROOT / case["report"])
        buggy = PROJECT_ROOT / case["buggy_repo"]
        fixed = PROJECT_ROOT / case["fixed_repo"]
        started = time.perf_counter()
        result = pipeline.run(report, buggy, repeats=3)
        elapsed = time.perf_counter() - started
        retest = pipeline.retest(result.run_id, fixed, repeats=3)
        false_positive = retest["status"] != "FIX_VERIFIED" and result.status.value == "REPRODUCED"
        rows.append(
            {
                "id": case["id"],
                "verdict": result.status.value,
                "reproduced": result.status.value == "REPRODUCED",
                "false_positive": false_positive,
                "seconds": elapsed,
                "retest": retest["status"],
            }
        )
    n = len(rows) or 1
    summary = {
        "cases": rows,
        "reproduction_rate": sum(1 for r in rows if r["reproduced"]) / n,
        "false_positive_rate": sum(1 for r in rows if r["false_positive"]) / n,
        "mean_time_to_reproduce_s": statistics.mean(r["seconds"] for r in rows),
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the reproduction benchmark")
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--local", action="store_true", default=True)
    args = parser.parse_args()
    summary = run_benchmark(args.manifest, local=args.local)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
