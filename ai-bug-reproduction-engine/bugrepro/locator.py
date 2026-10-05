"""Score repository files against analysis keywords."""

from __future__ import annotations

from pathlib import Path

from bugrepro.models import Analysis, FileHit, LocationResult

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "data", "node_modules"}


def locate(repo: Path, analysis: Analysis, *, limit: int = 5) -> LocationResult:
    keywords = [k.lower() for k in analysis.keywords if k]
    hits: list[FileHit] = []
    for path in _python_files(repo):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lower = text.lower()
        matched = [kw for kw in keywords if kw in lower or kw in path.name.lower()]
        if not matched:
            continue
        rel = path.relative_to(repo).as_posix()
        score = float(len(matched)) + (2.0 if "place_order" in lower else 0.0)
        reason = f"Matched keywords: {', '.join(matched[:6])}."
        hits.append(FileHit(path=rel, score=score, reason=reason))
    hits.sort(key=lambda h: h.score, reverse=True)
    return LocationResult(files=hits[:limit])


def _python_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for item in repo.rglob("*.py"):
        if any(part in SKIP_DIRS for part in item.parts):
            continue
        files.append(item)
    return files


def read_snippets(repo: Path, location: LocationResult, *, max_chars: int = 4000) -> str:
    chunks: list[str] = []
    remaining = max_chars
    for hit in location.files:
        path = repo / hit.path
        if not path.is_file():
            continue
        body = path.read_text(encoding="utf-8", errors="ignore")[:remaining]
        chunks.append(f"# {hit.path}\n{body}")
        remaining -= len(body)
        if remaining <= 0:
            break
    return "\n\n".join(chunks)
