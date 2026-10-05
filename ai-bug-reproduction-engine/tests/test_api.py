from pathlib import Path

from fastapi.testclient import TestClient

from bugrepro.api import app
from bugrepro.config import Settings
import bugrepro.api as api_module
from bugrepro.pipeline import load_report

ROOT = Path(__file__).resolve().parents[1]


def test_api_run_and_retest(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        allowed_root=ROOT / "examples",
        use_docker=False,
        timeout_seconds=20,
        repeat=2,
    )
    monkeypatch.setattr(api_module, "get_settings", lambda: settings)

    client = TestClient(app)
    report = load_report(ROOT / "examples" / "bug_report.json")
    repo = str((ROOT / "examples" / "sample-shop").resolve())
    created = client.post(
        "/api/runs",
        json={"report": report.model_dump(), "repo": repo, "local": True, "repeats": 2},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "REPRODUCED"
    run_id = body["run_id"]

    listed = client.get("/api/runs")
    assert listed.status_code == 200
    assert any(item["run_id"] == run_id for item in listed.json())

    shown = client.get(f"/api/runs/{run_id}")
    assert shown.status_code == 200
    assert "markdown" in shown.json()

    fixed = str((ROOT / "examples" / "sample-shop-fixed").resolve())
    retested = client.post(
        f"/api/runs/{run_id}/retest",
        json={"repo": fixed, "local": True, "repeats": 2},
    )
    assert retested.status_code == 200
    assert retested.json()["status"] == "FIX_VERIFIED"


def test_api_rejects_repo_outside_allowed_root(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        allowed_root=ROOT / "examples",
        use_docker=False,
    )
    monkeypatch.setattr(api_module, "get_settings", lambda: settings)
    client = TestClient(app)
    report = load_report(ROOT / "examples" / "bug_report.json")
    denied = client.post(
        "/api/runs",
        json={"report": report.model_dump(), "repo": "/tmp", "local": True, "repeats": 1},
    )
    assert denied.status_code == 403
