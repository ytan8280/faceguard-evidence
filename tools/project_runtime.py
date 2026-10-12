from __future__ import annotations

import os
from pathlib import Path
import subprocess

from dotenv import load_dotenv


class ProjectRuntimeError(RuntimeError):
    """Raised when local project runtime information is unavailable."""


def database_url(repository_root: Path) -> str:
    load_dotenv(repository_root / ".env", override=False)
    value = os.getenv("RAG_DATABASE_URL", "").strip()
    if not value:
        raise ProjectRuntimeError("RAG_DATABASE_URL is not configured.")
    return value


def application_revision(repository_root: Path) -> str:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ProjectRuntimeError(
            "Unable to determine the application Git revision."
        ) from exc
    if not revision:
        raise ProjectRuntimeError("Application Git revision is blank.")
    return f"{revision}-dirty" if status.strip() else revision
