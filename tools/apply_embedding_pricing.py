from __future__ import annotations

import argparse
from pathlib import Path
import sys

import psycopg
from psycopg.rows import dict_row


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dev.backend.app.rag.azure_embeddings import (  # noqa: E402
    AzureEmbeddingError,
    load_azure_embedding_config,
)
from dev.backend.app.rag.embedding_ingestion import (  # noqa: E402
    EMBEDDING_DISTANCE_METRIC,
    EMBEDDING_PROVIDER,
    EmbeddingIngestionError,
    apply_verified_embedding_pricing,
    load_embedding_pricing,
)
from dev.backend.app.rag.embedding_input import (  # noqa: E402
    DOCUMENT_INPUT_VERSION,
    QUERY_INPUT_VERSION,
)
from tools.project_runtime import ProjectRuntimeError, database_url  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply one verified Azure input-token price to completed "
            "embedding records that do not yet have a price basis."
        )
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required confirmation that the configured price was verified.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.yes:
        raise EmbeddingIngestionError(
            "Pricing backfill requires --yes after verifying the official price."
        )

    config = load_azure_embedding_config(REPO_ROOT)
    pricing = load_embedding_pricing(REPO_ROOT)
    if pricing is None:
        raise EmbeddingIngestionError(
            "Azure embedding pricing is not configured."
        )

    with psycopg.connect(
        database_url(REPO_ROOT),
        autocommit=True,
        row_factory=dict_row,
    ) as connection:
        row = connection.execute(
            """
            SELECT embedding_model_id
            FROM rag.embedding_models
            WHERE provider = %s
              AND deployment_name = %s
              AND model_name = %s
              AND model_version = %s
              AND api_version = %s
              AND region = %s
              AND dimensions = %s
              AND distance_metric = %s
              AND document_input_version = %s
              AND query_input_version = %s
            """,
            (
                EMBEDDING_PROVIDER,
                config.deployment_name,
                config.model_name,
                config.model_version,
                config.api_version,
                config.region,
                config.dimensions,
                EMBEDDING_DISTANCE_METRIC,
                DOCUMENT_INPUT_VERSION,
                QUERY_INPUT_VERSION,
            ),
        ).fetchone()
        if row is None:
            raise EmbeddingIngestionError(
                "Configured embedding model is not registered."
            )

        chunk_count, run_count = apply_verified_embedding_pricing(
            connection,
            embedding_model_id=int(row["embedding_model_id"]),
            pricing=pricing,
        )

    print(
        "Verified price: "
        f"{pricing.price_per_million_tokens} {pricing.currency} "
        "per 1,000,000 input tokens"
    )
    print(f"Price checked: {pricing.checked_at.isoformat()}")
    print(f"Chunk rows updated: {chunk_count}")
    print(f"Run rows updated: {run_count}")


if __name__ == "__main__":
    try:
        main()
    except (
        AzureEmbeddingError,
        EmbeddingIngestionError,
        ProjectRuntimeError,
    ) as exc:
        raise SystemExit(f"Embedding pricing backfill failed: {exc}") from exc
