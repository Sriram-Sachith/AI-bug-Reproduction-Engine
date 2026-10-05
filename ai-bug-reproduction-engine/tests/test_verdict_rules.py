from bugrepro.models import AttemptClass, ExecutionResult
from bugrepro.verifier import classify_execution, verify


def _ex(*, code: int, stdout: str = "", stderr: str = "", timed_out: bool = False) -> ExecutionResult:
    return ExecutionResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=code,
        duration_ms=10,
        timed_out=timed_out,
        backend="local",
    )


def test_assertion_failure_is_reproduced() -> None:
    blob = "E       assert 2 == 1\nE       AssertionError"
    result = verify([_ex(code=1, stdout=blob), _ex(code=1, stdout=blob), _ex(code=1, stdout=blob)])
    assert result.verdict.value == "REPRODUCED"
    assert result.intermittent is False
    assert result.attempts[0].classification == AttemptClass.ASSERT_FAIL


def test_all_pass_is_not_reproduced() -> None:
    result = verify([_ex(code=0, stdout="1 passed"), _ex(code=0, stdout="1 passed")])
    assert result.verdict.value == "NOT_REPRODUCED"


def test_import_error_is_inconclusive() -> None:
    err = "ImportError: cannot import name OrderService"
    result = verify([_ex(code=2, stdout="ERROR collecting", stderr=err)])
    assert result.verdict.value == "INCONCLUSIVE"
    assert result.attempts[0].classification == AttemptClass.ERROR


def test_timeout_is_inconclusive() -> None:
    result = verify([_ex(code=-1, stderr="TIMEOUT", timed_out=True)])
    assert result.verdict.value == "INCONCLUSIVE"
    assert result.attempts[0].classification == AttemptClass.TIMEOUT


def test_mixed_pass_and_assert_is_intermittent_reproduced() -> None:
    fail = "AssertionError: expected 1 order, got 2"
    result = verify([_ex(code=0, stdout="passed"), _ex(code=1, stdout=fail)])
    assert result.verdict.value == "REPRODUCED"
    assert result.intermittent is True


def test_error_plus_assert_is_inconclusive() -> None:
    fail = "AssertionError: expected 1 order, got 2"
    err = "ModuleNotFoundError: shop"
    result = verify([_ex(code=1, stdout=fail), _ex(code=2, stderr=err)])
    assert result.verdict.value == "INCONCLUSIVE"


def test_classify_wrong_api_typeerror() -> None:
    cls = classify_execution(_ex(code=1, stdout="TypeError: place_order() got an unexpected keyword"))
    assert cls == AttemptClass.ERROR
