"""Generate one Pytest test that asserts EXPECTED behaviour."""

from __future__ import annotations

from pathlib import Path

from bugrepro.llm import LLMClient, LLMError
from bugrepro.locator import read_snippets
from bugrepro.models import Analysis, BugClass, BugReport, GeneratedTest, LocationResult

RACE_TEMPLATE = '''"""Auto-generated reproduction test. Asserts expected behaviour."""

from __future__ import annotations

import threading

from shop.orders import OrderService


def test_duplicate_submission_is_idempotent() -> None:
    """Two concurrent place_order calls with one key must create one order/payment."""
    service = OrderService()
    key = "idem-demo-1"
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def worker() -> None:
        try:
            barrier.wait(timeout=5)
            service.place_order(item="widget", amount=10.0, idempotency_key=key)
        except BaseException as exc:  # collect so the assertion is the verdict
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not errors, f"workers raised: {errors!r}"
    assert len(service.orders) == 1, f"expected 1 order, got {len(service.orders)}"
    assert len(service.payments) == 1, f"expected 1 payment, got {len(service.payments)}"
'''


def generate_test(
    report: BugReport,
    analysis: Analysis,
    location: LocationResult,
    repo: Path,
    llm: LLMClient,
) -> GeneratedTest:
    if analysis.bug_class in {BugClass.RACE_CONDITION, BugClass.DUPLICATE_SUBMISSION}:
        template = GeneratedTest(source=RACE_TEMPLATE, used_llm=False, template_id="race_barrier")
    else:
        template = GeneratedTest(source=RACE_TEMPLATE, used_llm=False, template_id="race_barrier_fallback")

    snippets = read_snippets(repo, location)
    try:
        source = llm.complete(
            system=(
                "Write ONE Python pytest test file (no markdown). "
                "It must assert EXPECTED behaviour so it FAILS while the bug exists. "
                "Use threading.Barrier for races. No network, no sleep longer than 0.05s, "
                "deterministic. Do not modify application code. Import from the given repo."
            ),
            user=(
                f"Report: {report.model_dump_json()}\n"
                f"Analysis: {analysis.model_dump_json()}\n"
                f"Files:\n{snippets}"
            ),
        )
        if "def test_" not in source:
            return template
        return GeneratedTest(source=source, used_llm=True, template_id=None)
    except LLMError:
        return template


def repair_test(source: str, error_output: str, llm: LLMClient) -> str:
    try:
        repaired = llm.complete(
            system=(
                "Repair this pytest file so it imports and runs. Keep a single test that "
                "asserts expected behaviour. Return only Python source."
            ),
            user=f"Current test:\n{source}\n\nError output:\n{error_output[-4000:]}",
        )
        if "def test_" in repaired:
            return repaired
    except LLMError:
        pass
    return source
