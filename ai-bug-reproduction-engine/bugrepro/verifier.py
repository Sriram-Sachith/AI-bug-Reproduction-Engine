"""Classify pytest attempts and produce an evidence-backed verdict.

Only a failed assertion is a reproduction. Import errors, API misuse and
timeouts are INCONCLUSIVE. Mixed PASS/ASSERT_FAIL is intermittent.
"""

from __future__ import annotations

from bugrepro.models import (
    AttemptClass,
    AttemptResult,
    ExecutionResult,
    Verdict,
    VerifyResult,
)

ASSERT_MARKERS = (
    "AssertionError",
    "assert ",
    "Failed:",
    "E       assert",
)

ERROR_MARKERS = (
    "ImportError",
    "ModuleNotFoundError",
    "SyntaxError",
    "TypeError",
    "AttributeError",
    "NameError",
    "pytest.PytestCollectionWarning",
    "ERROR collecting",
)


def classify_execution(execution: ExecutionResult) -> AttemptClass:
    if execution.timed_out:
        return AttemptClass.TIMEOUT
    blob = f"{execution.stdout}\n{execution.stderr}"
    if execution.exit_code == 0:
        return AttemptClass.PASS
    if any(marker in blob for marker in ERROR_MARKERS) and "AssertionError" not in blob:
        return AttemptClass.ERROR
    if execution.exit_code != 0 and any(marker in blob for marker in ASSERT_MARKERS):
        return AttemptClass.ASSERT_FAIL
    if execution.exit_code != 0:
        return AttemptClass.ERROR
    return AttemptClass.PASS


def verify(executions: list[ExecutionResult], *, repaired: bool = False) -> VerifyResult:
    attempts = [
        AttemptResult(index=i + 1, classification=classify_execution(ex), execution=ex)
        for i, ex in enumerate(executions)
    ]
    classes = {a.classification for a in attempts}
    notes: list[str] = []

    if AttemptClass.TIMEOUT in classes or AttemptClass.ERROR in classes:
        if AttemptClass.ASSERT_FAIL not in classes:
            notes.append("Failures were errors or timeouts, not failed assertions.")
            return VerifyResult(
                verdict=Verdict.INCONCLUSIVE,
                attempts=attempts,
                intermittent=len(classes) > 1,
                repaired=repaired,
                notes=" ".join(notes),
            )
        notes.append("At least one attempt errored or timed out; cannot treat as a clean reproduction.")
        return VerifyResult(
            verdict=Verdict.INCONCLUSIVE,
            attempts=attempts,
            intermittent=True,
            repaired=repaired,
            notes=" ".join(notes),
        )

    if classes == {AttemptClass.PASS}:
        return VerifyResult(
            verdict=Verdict.NOT_REPRODUCED,
            attempts=attempts,
            intermittent=False,
            repaired=repaired,
            notes="Generated test passed on every attempt.",
        )

    if AttemptClass.ASSERT_FAIL in classes:
        intermittent = AttemptClass.PASS in classes
        if intermittent:
            notes.append("Mixed PASS and ASSERT_FAIL — flagged as intermittent.")
        return VerifyResult(
            verdict=Verdict.REPRODUCED,
            attempts=attempts,
            intermittent=intermittent,
            repaired=repaired,
            notes=" ".join(notes) or "Failed assertion matched expected behaviour.",
        )

    return VerifyResult(
        verdict=Verdict.INCONCLUSIVE,
        attempts=attempts,
        intermittent=False,
        repaired=repaired,
        notes="Unable to classify attempts.",
    )


def assertion_excerpt(result: VerifyResult) -> str | None:
    for attempt in result.attempts:
        if attempt.classification == AttemptClass.ASSERT_FAIL:
            text = attempt.execution.stdout or attempt.execution.stderr
            return text[-4000:]
    return None


def error_excerpt(result: VerifyResult) -> str | None:
    for attempt in result.attempts:
        if attempt.classification in {AttemptClass.ERROR, AttemptClass.TIMEOUT}:
            return (attempt.execution.stdout + "\n" + attempt.execution.stderr)[-4000:]
    return None
