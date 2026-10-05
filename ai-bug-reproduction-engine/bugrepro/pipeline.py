"""Orchestrate collect → analyse → locate → generate → execute → verify → report."""

from __future__ import annotations

from pathlib import Path

from bugrepro.analyzer import analyse
from bugrepro.config import Settings, get_settings
from bugrepro.generator import generate_test, repair_test
from bugrepro.llm import LLMClient
from bugrepro.locator import locate
from bugrepro.models import (
    BugReport,
    JsonReport,
    RetestStatus,
    TimelineEvent,
    Verdict,
)
from bugrepro.paths import resolve_repo
from bugrepro.report import build_json_report, persist_reports
from bugrepro.runner import run_pytest
from bugrepro.store import FileStore
from bugrepro.verifier import error_excerpt, verify


class Pipeline:
    def __init__(
        self,
        settings: Settings | None = None,
        store: FileStore | None = None,
        *,
        force_local: bool = False,
        allow_any_repo: bool = False,
    ) -> None:
        self.settings = settings or get_settings()
        self.store = store or FileStore(self.settings.resolved_data_dir())
        self.llm = LLMClient(self.settings)
        self.force_local = force_local
        self.allow_any_repo = allow_any_repo

    def _repo(self, repo: str | Path) -> Path:
        if self.allow_any_repo:
            path = Path(repo).expanduser().resolve()
            if not path.is_dir():
                raise ValueError(f"not a directory: {path}")
            return path
        return resolve_repo(repo, self.settings.resolved_allowed_root())

    def run(self, report: BugReport, repo: str | Path, *, repeats: int | None = None) -> JsonReport:
        repeats = repeats or self.settings.repeat
        repo_path = self._repo(repo)
        run_id = self.store.create_run(report, str(repo_path))
        self._event(run_id, "collect", "Stored original report unchanged.")

        analysis = analyse(report, self.llm)
        self.store.write_json(run_id, "analysis.json", analysis.model_dump(mode="json"))
        self._event(run_id, "analyse", f"Hypothesis: {analysis.hypothesis}")

        location = locate(repo_path, analysis)
        self.store.write_json(run_id, "location.json", location.model_dump(mode="json"))
        self._event(run_id, "locate", f"{len(location.files)} candidate file(s).")

        generated = generate_test(report, analysis, location, repo_path, self.llm)
        test_source = generated.source
        self.store.write_text(run_id, "test_repro.py", test_source)
        self._event(
            run_id,
            "generate",
            f"Wrote one pytest file (llm={generated.used_llm}, template={generated.template_id}).",
        )

        warnings: list[str] = []
        executions, run_warnings = self._repeat(repo_path, test_source, repeats)
        warnings.extend(run_warnings)
        for i, ex in enumerate(executions, start=1):
            self.store.write_json(run_id, f"executions/attempt-{i}.json", ex.model_dump(mode="json"))
        self._event(run_id, "execute", f"Ran generated test {len(executions)} time(s).")

        result = verify(executions, repaired=False)
        if result.verdict == Verdict.INCONCLUSIVE and error_excerpt(result):
            self._event(run_id, "repair", "Test errored; requesting a single repair pass.")
            test_source = repair_test(test_source, error_excerpt(result) or "", self.llm)
            self.store.write_text(run_id, "test_repro.py", test_source)
            executions, extra = self._repeat(repo_path, test_source, repeats)
            warnings.extend(extra)
            for i, ex in enumerate(executions, start=1):
                self.store.write_json(
                    run_id, f"executions/attempt-{i}-repaired.json", ex.model_dump(mode="json")
                )
            result = verify(executions, repaired=True)

        self._event(run_id, "verify", f"Verdict {result.verdict.value}: {result.notes}")
        timeline = [TimelineEvent.model_validate(e) for e in self.store.read_json(run_id, "timeline.json")]
        used_docker = any(a.execution.backend == "docker" for a in result.attempts)
        json_report = build_json_report(
            run_id,
            repo=str(repo_path),
            title=report.title,
            analysis=analysis,
            location=location,
            test_source=test_source,
            verify_result=result,
            timeline=timeline,
            warnings=warnings,
            used_docker=used_docker,
        )
        persist_reports(self.store, json_report)
        self._event(run_id, "report", "Wrote Markdown and JSON reports.")
        return json_report

    def retest(self, run_id: str, repo: str | Path, *, repeats: int | None = None) -> dict:
        repeats = repeats or self.settings.repeat
        if not self.store.exists(run_id):
            raise FileNotFoundError(run_id)
        repo_path = self._repo(repo)
        test_source = self.store.read_text(run_id, "test_repro.py")
        executions, warnings = self._repeat(repo_path, test_source, repeats)
        result = verify(executions, repaired=False)
        if result.verdict == Verdict.NOT_REPRODUCED:
            status = RetestStatus.FIX_VERIFIED
        elif result.verdict == Verdict.REPRODUCED:
            status = RetestStatus.FIX_NOT_VERIFIED
        else:
            status = RetestStatus.INCONCLUSIVE
        payload = {
            "run_id": run_id,
            "repo": str(repo_path),
            "status": status.value,
            "attempts": [a.model_dump(mode="json") for a in result.attempts],
            "warnings": warnings,
            "notes": (
                "Exact saved test rerun against the provided tree. "
                "FIX_VERIFIED means every attempt passed."
            ),
        }
        self.store.write_json(run_id, "retest/result.json", payload)
        self._event(run_id, "retest", f"{status.value} on {repo_path}")
        return payload

    def _repeat(self, repo: Path, test_source: str, repeats: int):
        executions = []
        warnings: list[str] = []
        for _ in range(repeats):
            execution, extra = run_pytest(
                repo, test_source, self.settings, force_local=self.force_local
            )
            executions.append(execution)
            for item in extra:
                if item not in warnings:
                    warnings.append(item)
        return executions, warnings

    def _event(self, run_id: str, step: str, detail: str) -> None:
        self.store.append_timeline(run_id, TimelineEvent(step=step, detail=detail))


def load_report(path: Path) -> BugReport:
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    return BugReport.model_validate(data)
