"""Markdown + JSON reports for a completed run."""

from __future__ import annotations

from bugrepro.models import (
    Analysis,
    JsonReport,
    LocationResult,
    TimelineEvent,
    Verdict,
    VerifyResult,
)
from bugrepro.store import FileStore
from bugrepro.verifier import assertion_excerpt


def build_json_report(
    run_id: str,
    *,
    repo: str,
    title: str,
    analysis: Analysis,
    location: LocationResult,
    test_source: str,
    verify_result: VerifyResult,
    timeline: list[TimelineEvent],
    warnings: list[str],
    used_docker: bool,
) -> JsonReport:
    return JsonReport(
        run_id=run_id,
        status=verify_result.verdict,
        intermittent=verify_result.intermittent,
        analysis=analysis,
        location=location,
        generated_test=test_source,
        attempts=verify_result.attempts,
        assertion_output=assertion_excerpt(verify_result),
        follow_up_questions=analysis.follow_up_questions,
        timeline=timeline,
        warnings=warnings,
        repaired=verify_result.repaired,
        used_llm=analysis.used_llm,
        used_docker=used_docker,
        repo=repo,
        title=title,
        created_at=timeline[0].ts if timeline else None,
    )


def render_markdown(report: JsonReport) -> str:
    lines = [
        f"# {report.run_id}: {report.status}",
        "",
        f"- **Title:** {report.title}",
        f"- **Repository:** `{report.repo}`",
        f"- **Intermittent:** {report.intermittent}",
        f"- **Repaired test:** {report.repaired}",
        f"- **LLM used:** {report.used_llm}",
        f"- **Docker sandbox:** {report.used_docker}",
        "",
        "## Analysis",
        f"- **Observed:** {report.analysis.observed}",
        f"- **Expected:** {report.analysis.expected}",
        f"- **Hypothesis (testable, not confirmed):** {report.analysis.hypothesis}",
        f"- **Bug class:** {report.analysis.bug_class.value}",
        f"- **Keywords:** {', '.join(report.analysis.keywords)}",
        "",
        "## Located files",
    ]
    for hit in report.location.files:
        lines.append(f"- `{hit.path}` (score {hit.score:.1f}) — {hit.reason}")
    if not report.location.files:
        lines.append("- (none)")
    lines.extend(["", "## Generated test", "```python", report.generated_test.rstrip(), "```", ""])
    lines.extend(["## Attempts", ""])
    for attempt in report.attempts:
        ex = attempt.execution
        lines.append(
            f"- Attempt {attempt.index}: **{attempt.classification.value}** "
            f"(exit {ex.exit_code}, {ex.duration_ms:.0f} ms, {ex.backend})"
        )
    lines.extend(["", "## Failed-assertion output", ""])
    if report.assertion_output:
        lines.extend(["```", report.assertion_output.rstrip(), "```"])
    else:
        lines.append("_No failed assertion captured._")
    if report.follow_up_questions:
        lines.extend(["", "## Follow-up questions", ""])
        for q in report.follow_up_questions:
            lines.append(f"- {q}")
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        for w in report.warnings:
            lines.append(f"- {w}")
    lines.extend(["", "## Timeline", ""])
    for event in report.timeline:
        lines.append(f"- `{event.ts.isoformat()}` **{event.step}** — {event.detail}")
    if report.status == Verdict.REPRODUCED and report.assertion_output:
        pass
    elif report.status != Verdict.REPRODUCED:
        lines.extend(
            [
                "",
                "_This engine never claims a reproduction without a matching failed assertion._",
            ]
        )
    return "\n".join(lines) + "\n"


def persist_reports(store: FileStore, report: JsonReport) -> None:
    store.write_json(report.run_id, "report.json", json_ready(report))
    store.write_text(report.run_id, "report.md", render_markdown(report))
    store.write_json(
        report.run_id,
        "verify.json",
        {
            "verdict": report.status.value,
            "intermittent": report.intermittent,
            "repaired": report.repaired,
        },
    )


def json_ready(report: JsonReport) -> dict:
    return report.model_dump(mode="json")
