"""File-backed run store.

Layout (PostgreSQL-replaceable):
  data/runs/RUN-0001/
    original_report.json
    analysis.json
    location.json
    test_repro.py
    executions/attempt-N.json
    verify.json
    report.md
    report.json
    timeline.json
    meta.json
    retest/  (optional)

A SQL backend would map each JSON file to a table with the same keys.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bugrepro.models import BugReport, JsonReport, RunSummary, TimelineEvent, utcnow


class FileStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.runs_dir = root / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def next_run_id(self) -> str:
        existing = [p.name for p in self.runs_dir.iterdir() if p.name.startswith("RUN-")]
        numbers = []
        for name in existing:
            try:
                numbers.append(int(name.split("-", 1)[1]))
            except (IndexError, ValueError):
                continue
        nxt = max(numbers, default=0) + 1
        return f"RUN-{nxt:04d}"

    def create_run(self, report: BugReport, repo: str) -> str:
        run_id = self.next_run_id()
        folder = self._folder(run_id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "executions").mkdir(exist_ok=True)
        self.write_json(run_id, "original_report.json", report.model_dump())
        self.write_json(
            run_id,
            "meta.json",
            {
                "run_id": run_id,
                "created_at": utcnow().isoformat(),
                "repo": repo,
                "title": report.title,
            },
        )
        self.write_json(run_id, "timeline.json", [])
        return run_id

    def _folder(self, run_id: str) -> Path:
        if not run_id.startswith("RUN-") or "/" in run_id or ".." in run_id:
            raise ValueError(f"invalid run id: {run_id}")
        return self.runs_dir / run_id

    def write_json(self, run_id: str, name: str, payload: Any) -> None:
        path = self._folder(run_id) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def write_text(self, run_id: str, name: str, text: str) -> None:
        path = self._folder(run_id) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def read_json(self, run_id: str, name: str) -> Any:
        path = self._folder(run_id) / name
        return json.loads(path.read_text(encoding="utf-8"))

    def read_text(self, run_id: str, name: str) -> str:
        return (self._folder(run_id) / name).read_text(encoding="utf-8")

    def exists(self, run_id: str) -> bool:
        return self._folder(run_id).is_dir()

    def append_timeline(self, run_id: str, event: TimelineEvent) -> None:
        events = self.read_json(run_id, "timeline.json")
        events.append(json.loads(event.model_dump_json()))
        self.write_json(run_id, "timeline.json", events)

    def list_runs(self) -> list[RunSummary]:
        summaries: list[RunSummary] = []
        for folder in sorted(self.runs_dir.iterdir()):
            if not folder.is_dir():
                continue
            try:
                summaries.append(self.summary(folder.name))
            except (OSError, KeyError, ValueError):
                continue
        return summaries

    def summary(self, run_id: str) -> RunSummary:
        meta = self.read_json(run_id, "meta.json")
        verdict = None
        intermittent = False
        used_docker = False
        used_llm = False
        report_path = self._folder(run_id) / "report.json"
        if report_path.exists():
            report = JsonReport.model_validate(self.read_json(run_id, "report.json"))
            verdict = report.status
            intermittent = report.intermittent
            used_docker = report.used_docker
            used_llm = report.used_llm
        return RunSummary(
            run_id=run_id,
            created_at=meta["created_at"],
            repo=meta["repo"],
            title=meta.get("title", ""),
            verdict=verdict,
            intermittent=intermittent,
            used_docker=used_docker,
            used_llm=used_llm,
        )
