"""Path safety helpers. Repository code is treated as untrusted."""

from __future__ import annotations

from pathlib import Path


class PathNotAllowed(ValueError):
    pass


def resolve_repo(path: str | Path, allowed_root: Path) -> Path:
    repo = Path(path).expanduser().resolve()
    root = allowed_root.resolve()
    if not repo.is_dir():
        raise PathNotAllowed(f"repository is not a directory: {repo}")
    if not repo.is_relative_to(root):
        raise PathNotAllowed(f"repository {repo} is outside allowed root {root}")
    return repo
