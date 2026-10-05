"""REST API and HTML dashboard. Repository paths must stay under allowed_root."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from bugrepro.config import get_settings
from bugrepro.models import BugReport
from bugrepro.paths import PathNotAllowed
from bugrepro.pipeline import Pipeline
from bugrepro.store import FileStore

app = FastAPI(title="AI Bug Reproduction Engine", version="0.1.0")
DASHBOARD = Path(__file__).resolve().parent / "static" / "index.html"


class RunRequest(BaseModel):
    report: BugReport
    repo: str
    local: bool = False
    repeats: int | None = Field(default=None, ge=1, le=10)


class RetestRequest(BaseModel):
    repo: str
    local: bool = False
    repeats: int | None = Field(default=None, ge=1, le=10)


def _pipeline(local: bool) -> Pipeline:
    settings = get_settings()
    return Pipeline(
        settings=settings,
        store=FileStore(settings.resolved_data_dir()),
        force_local=local,
        allow_any_repo=False,
    )


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD.read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/runs")
def list_runs() -> list[dict]:
    settings = get_settings()
    store = FileStore(settings.resolved_data_dir())
    return [s.model_dump(mode="json") for s in store.list_runs()]


@app.get("/api/runs/{run_id}")
def show_run(run_id: str) -> dict:
    settings = get_settings()
    store = FileStore(settings.resolved_data_dir())
    if not store.exists(run_id):
        raise HTTPException(404, "unknown run")
    payload = store.read_json(run_id, "report.json")
    payload["markdown"] = store.read_text(run_id, "report.md")
    return payload


@app.post("/api/runs")
def create_run(body: RunRequest) -> dict:
    try:
        report = _pipeline(body.local).run(body.report, body.repo, repeats=body.repeats)
    except PathNotAllowed as exc:
        raise HTTPException(403, str(exc)) from exc
    except Exception as exc:  # surface unexpected failures as 400
        raise HTTPException(400, str(exc)) from exc
    return report.model_dump(mode="json")


@app.post("/api/runs/{run_id}/retest")
def retest_run(run_id: str, body: RetestRequest) -> dict:
    settings = get_settings()
    store = FileStore(settings.resolved_data_dir())
    if not store.exists(run_id):
        raise HTTPException(404, "unknown run")
    try:
        return _pipeline(body.local).retest(run_id, body.repo, repeats=body.repeats)
    except PathNotAllowed as exc:
        raise HTTPException(403, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
