"""Execute a generated pytest file in Docker (preferred) or a local subprocess."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from bugrepro.config import Settings
from bugrepro.models import ExecutionResult

LOCAL_WARNING = (
    "LOCAL MODE: tests run on the host, not in the Docker sandbox. "
    "Use this only for development. Treat repository code as untrusted."
)


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        proc = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=8,
            check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def run_pytest(
    repo: Path,
    test_source: str,
    settings: Settings,
    *,
    force_local: bool = False,
) -> tuple[ExecutionResult, list[str]]:
    warnings: list[str] = []
    use_docker = settings.use_docker and not force_local
    if use_docker and docker_available():
        return _run_docker(repo, test_source, settings), warnings
    if use_docker and not docker_available():
        warnings.append("Docker is unavailable; falling back to local mode.")
    warnings.append(LOCAL_WARNING)
    return _run_local(repo, test_source, settings), warnings


def _run_local(repo: Path, test_source: str, settings: Settings) -> ExecutionResult:
    with tempfile.TemporaryDirectory(prefix="bugrepro-") as tmp:
        test_path = Path(tmp) / "test_repro.py"
        test_path.write_text(test_source, encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo.resolve()) + os.pathsep + env.get("PYTHONPATH", "")
        # Never leak an API key into the test process.
        env.pop("ANTHROPIC_API_KEY", None)
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "--tb=short", str(test_path)],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                timeout=settings.timeout_seconds,
                check=False,
            )
            duration = (time.perf_counter() - started) * 1000
            return ExecutionResult(
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
                duration_ms=duration,
                timed_out=False,
                backend="local",
            )
        except subprocess.TimeoutExpired as exc:
            duration = (time.perf_counter() - started) * 1000
            return ExecutionResult(
                stdout=exc.stdout or "" if isinstance(exc.stdout, str) else "",
                stderr=(exc.stderr or "" if isinstance(exc.stderr, str) else "") + "\nTIMEOUT",
                exit_code=-1,
                duration_ms=duration,
                timed_out=True,
                backend="local",
            )


def _run_docker(repo: Path, test_source: str, settings: Settings) -> ExecutionResult:
    with tempfile.TemporaryDirectory(prefix="bugrepro-docker-") as tmp:
        tests_dir = Path(tmp) / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_repro.py").write_text(test_source, encoding="utf-8")
        cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=64m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            settings.memory,
            "--cpus",
            settings.cpus,
            "--pids-limit",
            str(settings.pids),
            "--user",
            "1000:1000",
            "-e",
            "PYTHONPATH=/repo",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-v",
            f"{repo.resolve()}:/repo:ro",
            "-v",
            f"{tests_dir.resolve()}:/tests:ro",
            settings.docker_image,
            "pytest",
            "-q",
            "--tb=short",
            "--cache-dir=/tmp/pytest-cache",
            "/tests/test_repro.py",
        ]
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=settings.timeout_seconds + 5,
                check=False,
            )
            duration = (time.perf_counter() - started) * 1000
            return ExecutionResult(
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
                duration_ms=duration,
                timed_out=False,
                backend="docker",
            )
        except subprocess.TimeoutExpired as exc:
            duration = (time.perf_counter() - started) * 1000
            return ExecutionResult(
                stdout=exc.stdout or "" if isinstance(exc.stdout, str) else "",
                stderr=(exc.stderr or "" if isinstance(exc.stderr, str) else "") + "\nTIMEOUT",
                exit_code=-1,
                duration_ms=duration,
                timed_out=True,
                backend="docker",
            )
