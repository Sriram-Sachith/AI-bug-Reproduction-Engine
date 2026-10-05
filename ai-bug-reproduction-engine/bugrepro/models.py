"""Pydantic models shared across the pipeline.

The store persists these as JSON so a later PostgreSQL backend can map
each model to a table (runs, analyses, executions, reports).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BugClass(str, Enum):
    RACE_CONDITION = "race_condition"
    DUPLICATE_SUBMISSION = "duplicate_submission"
    LOGIC_ERROR = "logic_error"
    UNKNOWN = "unknown"


class Verdict(str, Enum):
    REPRODUCED = "REPRODUCED"
    NOT_REPRODUCED = "NOT_REPRODUCED"
    INCONCLUSIVE = "INCONCLUSIVE"


class AttemptClass(str, Enum):
    PASS = "PASS"
    ASSERT_FAIL = "ASSERT_FAIL"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


class RetestStatus(str, Enum):
    FIX_VERIFIED = "FIX_VERIFIED"
    FIX_NOT_VERIFIED = "FIX_NOT_VERIFIED"
    INCONCLUSIVE = "INCONCLUSIVE"


class BugReport(BaseModel):
    """Original developer report. Stored unchanged."""

    title: str
    description: str
    steps: list[str] = Field(default_factory=list)
    observed: str | None = None
    expected: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Analysis(BaseModel):
    observed: str
    expected: str
    hypothesis: str
    bug_class: BugClass
    keywords: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    used_llm: bool = False


class FileHit(BaseModel):
    path: str
    score: float
    reason: str


class LocationResult(BaseModel):
    files: list[FileHit] = Field(default_factory=list)


class GeneratedTest(BaseModel):
    source: str
    used_llm: bool = False
    template_id: str | None = None


class ExecutionResult(BaseModel):
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    duration_ms: float = 0.0
    timed_out: bool = False
    backend: str = "local"


class AttemptResult(BaseModel):
    index: int
    classification: AttemptClass
    execution: ExecutionResult


class VerifyResult(BaseModel):
    verdict: Verdict
    attempts: list[AttemptResult] = Field(default_factory=list)
    intermittent: bool = False
    repaired: bool = False
    notes: str = ""


class TimelineEvent(BaseModel):
    ts: datetime = Field(default_factory=utcnow)
    step: str
    detail: str


class RunSummary(BaseModel):
    run_id: str
    created_at: datetime
    repo: str
    title: str
    verdict: Verdict | None = None
    intermittent: bool = False
    used_docker: bool = False
    used_llm: bool = False


class JsonReport(BaseModel):
    run_id: str
    status: Verdict
    intermittent: bool
    analysis: Analysis
    location: LocationResult
    generated_test: str
    attempts: list[AttemptResult]
    assertion_output: str | None = None
    follow_up_questions: list[str] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    repaired: bool = False
    used_llm: bool = False
    used_docker: bool = False
    repo: str = ""
    title: str = ""
    created_at: datetime | None = None
