"""Analyse a bug report into a TESTABLE hypothesis (not a root cause)."""

from __future__ import annotations

import json
import re

from bugrepro.llm import LLMClient, LLMError
from bugrepro.models import Analysis, BugClass, BugReport

RACE_HINTS = (
    "race",
    "concurrent",
    "double click",
    "double-click",
    "twice",
    "two requests",
    "duplicate",
    "idempoten",
    "parallel",
    "simultaneous",
    "two orders",
    "charged twice",
)


def _blob(report: BugReport) -> str:
    parts = [report.title, report.description, report.observed or "", report.expected or ""]
    parts.extend(report.steps)
    return "\n".join(parts).lower()


def _guess_class(text: str) -> BugClass:
    if any(h in text for h in ("race", "concurrent", "parallel", "simultaneous", "thread")):
        return BugClass.RACE_CONDITION
    if any(h in text for h in ("double click", "double-click", "twice", "duplicate", "idempoten", "two orders")):
        return BugClass.DUPLICATE_SUBMISSION
    return BugClass.UNKNOWN


def heuristic_analyse(report: BugReport) -> Analysis:
    text = _blob(report)
    observed = report.observed or _extract(report.description, "observed", "actual") or report.description.strip()
    expected = report.expected or _extract(report.description, "expected") or (
        "The operation is applied once for a given idempotency key."
        if _guess_class(text) in {BugClass.RACE_CONDITION, BugClass.DUPLICATE_SUBMISSION}
        else "Behaviour matches the documented contract of the API under test."
    )
    bug_class = _guess_class(text)
    keywords = _keywords(text, bug_class)
    questions: list[str] = []
    if not report.steps:
        questions.append("What exact UI or API steps trigger the failure?")
    if not report.observed:
        questions.append("What did you observe (counts, error messages, HTTP status)?")
    if not report.expected:
        questions.append("What should happen instead?")
    hypothesis = (
        "If two callers invoke the same mutating API at the same time with one "
        "idempotency key, more than one side effect is committed."
        if bug_class in {BugClass.RACE_CONDITION, BugClass.DUPLICATE_SUBMISSION}
        else "Exercising the reported steps will violate the stated expected behaviour."
    )
    return Analysis(
        observed=observed,
        expected=expected,
        hypothesis=hypothesis,
        bug_class=bug_class,
        keywords=keywords,
        follow_up_questions=questions,
        used_llm=False,
    )


def _extract(description: str, *labels: str) -> str | None:
    for label in labels:
        match = re.search(rf"{label}\s*[:\-]\s*(.+)", description, flags=re.I)
        if match:
            return match.group(1).strip()
    return None


def _keywords(text: str, bug_class: BugClass) -> list[str]:
    words = {
        "order",
        "orders",
        "payment",
        "payments",
        "place_order",
        "idempotency",
        "idempotency_key",
        "shop",
    }
    found = [w for w in words if w in text]
    if bug_class in {BugClass.RACE_CONDITION, BugClass.DUPLICATE_SUBMISSION}:
        found.extend(["place_order", "idempotency_key", "orders", "payments"])
    # preserve order, drop empties
    seen: list[str] = []
    for item in found:
        if item not in seen:
            seen.append(item)
    return seen or ["bug", "error"]


def analyse(report: BugReport, llm: LLMClient) -> Analysis:
    fallback = heuristic_analyse(report)
    try:
        raw = llm.complete(
            system=(
                "You analyse software bug reports. Return JSON only with keys: "
                "observed, expected, hypothesis, bug_class, keywords, follow_up_questions. "
                "hypothesis must be TESTABLE behaviour, never a confirmed root cause. "
                "bug_class must be one of: race_condition, duplicate_submission, logic_error, unknown."
            ),
            user=report.model_dump_json(),
            json_mode=True,
        )
        data = json.loads(raw)
        return Analysis(
            observed=data.get("observed") or fallback.observed,
            expected=data.get("expected") or fallback.expected,
            hypothesis=data.get("hypothesis") or fallback.hypothesis,
            bug_class=BugClass(data.get("bug_class", fallback.bug_class.value)),
            keywords=list(data.get("keywords") or fallback.keywords),
            follow_up_questions=list(data.get("follow_up_questions") or fallback.follow_up_questions),
            used_llm=True,
        )
    except (LLMError, json.JSONDecodeError, ValueError, KeyError):
        return fallback
