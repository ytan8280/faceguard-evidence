from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "data" / "sources"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dev.backend.app.rag.chunking import (  # noqa: E402
    DEFAULT_MAX_CHARS,
    chunk_documents,
)
from dev.backend.app.rag.ingestion import (  # noqa: E402
    CorpusIngestionError,
    ingest_prepared_corpus,
    prepare_corpus,
)
from dev.backend.app.rag.source_loader import (  # noqa: E402
    load_source_documents,
)


def _database_url() -> str:
    load_dotenv(REPO_ROOT / ".env", override=False)
    database_url = os.getenv("RAG_DATABASE_URL", "").strip()
    if not database_url:
        raise CorpusIngestionError("RAG_DATABASE_URL is not configured.")
    return database_url


def _application_revision() -> str:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CorpusIngestionError(
            "Unable to determine the application Git revision."
        ) from exc
    if not revision:
        raise CorpusIngestionError("Application Git revision is blank.")
    return f"{revision}-dirty" if status.strip() else revision


def main() -> None:
    documents = load_source_documents(
        source_root=SOURCE_ROOT,
        repository_root=REPO_ROOT,
    )
    chunks = chunk_documents(
        documents,
        max_chars=DEFAULT_MAX_CHARS,
    )
    prepared = prepare_corpus(
        documents=documents,
        chunks=chunks,
        repository_root=REPO_ROOT,
        max_chunk_chars=DEFAULT_MAX_CHARS,
    )

    with psycopg.connect(
        _database_url(),
        autocommit=True,
        row_factory=dict_row,
    ) as connection:
        result = ingest_prepared_corpus(
            connection,
            prepared=prepared,
            application_revision=_application_revision(),
        )

    action = "reused" if result.reused else "created"
    print(f"Corpus revision {action}: {result.corpus_sha256}")
    print(f"Corpus revision ID: {result.corpus_revision_id}")
    print(f"Ingestion run ID: {result.ingestion_run_id}")
    print(f"Verified sources: {result.source_count}")
    print(f"Evidence chunks: {result.chunk_count}")


if __name__ == "__main__":
    try:
        main()
    except CorpusIngestionError as exc:
        raise SystemExit(f"Corpus ingestion failed: {exc}") from exc
