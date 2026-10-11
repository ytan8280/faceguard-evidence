from __future__ import annotations

from pathlib import Path
import sys

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
from tools.project_runtime import (  # noqa: E402
    ProjectRuntimeError,
    application_revision,
    database_url,
)


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
        database_url(REPO_ROOT),
        autocommit=True,
        row_factory=dict_row,
    ) as connection:
        result = ingest_prepared_corpus(
            connection,
            prepared=prepared,
            application_revision=application_revision(REPO_ROOT),
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
    except (CorpusIngestionError, ProjectRuntimeError) as exc:
        raise SystemExit(f"Corpus ingestion failed: {exc}") from exc
