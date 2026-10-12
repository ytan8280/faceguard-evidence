from __future__ import annotations

import argparse
from pathlib import Path
import sys

import psycopg
from psycopg.rows import dict_row


REPO_ROOT = Path(__file__).resolve().parents[1]
LEXICAL_BASELINE_CORPUS_SHA256 = (
    "842CBBEFA28D2B8389FF2694420F771A12DFAEBF9F9DDFA5A214BF258F596CEB"
)

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dev.backend.app.rag.azure_embeddings import (  # noqa: E402
    AzureEmbeddingError,
    load_azure_embedding_config,
)
from dev.backend.app.rag.embedding_ingestion import (  # noqa: E402
    EmbeddingIngestionError,
    generate_corpus_embeddings,
    load_embedding_pricing,
    prepare_embedding_batch,
)
from tools.project_runtime import (  # noqa: E402
    ProjectRuntimeError,
    application_revision,
    database_url,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate verified Azure embeddings for one exact corpus revision."
        )
    )
    parser.add_argument(
        "--corpus-sha256",
        default=LEXICAL_BASELINE_CORPUS_SHA256,
        help="Exact ingested corpus SHA-256.",
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--limit",
        type=int,
        help="Embed only the first N deterministic chunks for a pilot.",
    )
    selection.add_argument(
        "--all",
        action="store_true",
        help="Explicitly embed every chunk in the selected corpus.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prepare and summarize inputs without calling Azure or writing rows.",
    )
    parser.add_argument(
        "--application-revision",
        help=(
            "Explicit Git revision for container runs whose worktree metadata "
            "is not mounted."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    limit = None if args.all else args.limit

    with psycopg.connect(
        database_url(REPO_ROOT),
        autocommit=True,
        row_factory=dict_row,
    ) as connection:
        if args.dry_run:
            batch = prepare_embedding_batch(
                connection,
                corpus_sha256=args.corpus_sha256,
                limit=limit,
            )
            print(f"Corpus revision: {batch.corpus_revision_id}")
            print(f"Corpus SHA-256: {batch.corpus_sha256}")
            print(f"Prepared chunks: {len(batch.chunks)}")
            print(
                "Maximum input characters: "
                f"{max(chunk.prepared_input.char_count for chunk in batch.chunks)}"
            )
            for chunk in batch.chunks:
                print(
                    f"{chunk.chunk_id}\t"
                    f"{chunk.prepared_input.char_count}\t"
                    f"{chunk.prepared_input.sha256}"
                )
            return

        config = load_azure_embedding_config(REPO_ROOT)
        result = generate_corpus_embeddings(
            connection,
            config=config,
            corpus_sha256=args.corpus_sha256,
            application_revision=(
                args.application_revision
                if args.application_revision is not None
                else application_revision(REPO_ROOT)
            ),
            limit=limit,
            pricing=load_embedding_pricing(REPO_ROOT),
        )

    print(f"Embedding run: {result.embedding_run_id}")
    print(f"Embedding model: {result.embedding_model_id}")
    print(f"Corpus revision: {result.corpus_revision_id}")
    print(f"Target chunks: {result.target_chunk_count}")
    print(f"Embedded chunks: {result.embedded_chunk_count}")
    print(f"Reused chunks: {result.reused_chunk_count}")
    print(f"Prompt tokens: {result.prompt_tokens}")
    print(f"API latency: {result.api_latency_ms:.3f} ms")
    if result.calculated_cost is None:
        print("Calculated cost: unavailable (official price not configured)")
    else:
        print(f"Calculated cost: {result.calculated_cost}")


if __name__ == "__main__":
    try:
        main()
    except (
        AzureEmbeddingError,
        EmbeddingIngestionError,
        ProjectRuntimeError,
    ) as exc:
        raise SystemExit(f"Corpus embedding failed: {exc}") from exc
