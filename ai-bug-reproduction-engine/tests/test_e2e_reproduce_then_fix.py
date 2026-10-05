from pathlib import Path

from bugrepro.config import Settings
from bugrepro.models import BugReport
from bugrepro.pipeline import Pipeline, load_report
from bugrepro.store import FileStore

ROOT = Path(__file__).resolve().parents[1]
BUGGY = ROOT / "examples" / "sample-shop"
FIXED = ROOT / "examples" / "sample-shop-fixed"
REPORT = ROOT / "examples" / "bug_report.json"


def _pipeline(tmp_path: Path) -> Pipeline:
    settings = Settings(
        data_dir=tmp_path / "data",
        allowed_root=ROOT / "examples",
        use_docker=False,
        timeout_seconds=20,
        repeat=3,
    )
    return Pipeline(
        settings=settings,
        store=FileStore(settings.resolved_data_dir()),
        force_local=True,
        allow_any_repo=True,
    )


def test_reproduce_then_verify_fix(tmp_path: Path) -> None:
    report = load_report(REPORT)
    pipeline = _pipeline(tmp_path)
    result = pipeline.run(report, BUGGY, repeats=3)
    assert result.status.value == "REPRODUCED"
    assert result.assertion_output
    assert "def test_" in result.generated_test

    retest = pipeline.retest(result.run_id, FIXED, repeats=3)
    assert retest["status"] == "FIX_VERIFIED"


def test_single_click_hides_bug() -> None:
    import sys

    sys.path.insert(0, str(BUGGY))
    from shop.orders import OrderService  # noqa: E402

    service = OrderService()
    first = service.place_order("widget", 10.0, "idem-1")
    second = service.place_order("widget", 10.0, "idem-1")
    assert first.id == second.id
    assert len(service.orders) == 1
    assert len(service.payments) == 1
