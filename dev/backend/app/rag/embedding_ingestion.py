from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from dotenv import load_dotenv
from psycopg import Connection

from .azure_embeddings import (
    AzureEmbeddingConfig,
    AzureEmbeddingHTTPError,
    EmbeddingResponse,
    request_embedding_with_retry,
)
from .embedding_input import (
    DOCUMENT_INPUT_VERSION,
    QUERY_INPUT_VERSION,
    PreparedEmbeddingInput,
    prepare_document_embedding_input,
)


EMBEDDING_LOCK_KEY = "faceguard_evidence_chunk_embeddings"
EMBEDDING_PROVIDER = "azure_openai"
EMBEDDING_DISTANCE_METRIC = "cosine"


class EmbeddingIngestionError(RuntimeError):
    """Raised when corpus embeddings cannot be stored consistently."""


@dataclass(frozen=True, slots=True)
class ChunkEmbeddingInput:
    chunk_id: str
    source_id: str
    source_title: str
    heading_text: str
    content_sha256: str
    prepared_input: PreparedEmbeddingInput


@dataclass(frozen=True, slots=True)
class PreparedEmbeddingBatch:
    corpus_revision_id: int
    corpus_sha256: str
    chunks: tuple[ChunkEmbeddingInput, ...]


@dataclass(frozen=True, slots=True)
class PendingChunkEmbedding:
    chunk: ChunkEmbeddingInput
    response: EmbeddingResponse
    calculated_cost: Decimal | None


@dataclass(frozen=True, slots=True)
class EmbeddingGenerationResult:
    embedding_run_id: int
    embedding_model_id: int
    corpus_revision_id: int
    corpus_sha256: str
    target_chunk_count: int
    embedded_chunk_count: int
    reused_chunk_count: int
    prompt_tokens: int
    api_latency_ms: float
    calculated_cost: Decimal | None


@dataclass(frozen=True, slots=True)
class EmbeddingPricing:
    price_per_million_tokens: Decimal
    currency: str
    checked_at: date

    def cost_for_tokens(self, tokens: int) -> Decimal:
        return (
            Decimal(tokens)
            * self.price_per_million_tokens
            / Decimal(1_000_000)
        )


def load_embedding_pricing(
    repository_root: Path,
) -> EmbeddingPricing | None:
    load_dotenv(repository_root / ".env", override=False)
    raw_price = os.getenv(
        "AZURE_OPENAI_EMBEDDING_PRICE_PER_MILLION_TOKENS",
        "",
    ).strip()
    raw_currency = os.getenv("AZURE_OPENAI_PRICING_CURRENCY", "").strip()
    raw_checked_at = os.getenv("AZURE_OPENAI_PRICING_CHECKED_AT", "").strip()

    values = (raw_price, raw_currency, raw_checked_at)
    if not any(values):
        return None
    if not all(values):
        raise EmbeddingIngestionError(
            "Azure embedding pricing requires price, currency and checked date."
        )

    try:
        price = Decimal(raw_price)
    except InvalidOperation as exc:
        raise EmbeddingIngestionError(
            "Azure embedding price must be a decimal number."
        ) from exc
    if price <= 0:
        raise EmbeddingIngestionError(
            "Azure embedding price must be positive."
        )

    currency = raw_currency.upper()
    if len(currency) != 3 or not currency.isalpha():
        raise EmbeddingIngestionError(
            "Azure pricing currency must be a three-letter code."
        )
    try:
        checked_at = date.fromisoformat(raw_checked_at)
    except ValueError as exc:
        raise EmbeddingIngestionError(
            "Azure pricing checked date must use YYYY-MM-DD."
        ) from exc

    return EmbeddingPricing(
        price_per_million_tokens=price,
        currency=currency,
        checked_at=checked_at,
    )


def prepare_embedding_batch(
    connection: Connection,
    *,
    corpus_sha256: str,
    limit: int | None,
) -> PreparedEmbeddingBatch:
    normalized_sha256 = corpus_sha256.strip().upper()
    if len(normalized_sha256) != 64:
        raise EmbeddingIngestionError(
            "Corpus SHA-256 must contain 64 hexadecimal characters."
        )
    if limit is not None and limit <= 0:
        raise EmbeddingIngestionError("Embedding limit must be positive.")

    revision = connection.execute(
        """
        SELECT corpus_revision_id, corpus_sha256
        FROM rag.corpus_revisions
        WHERE corpus_sha256 = %s
        """,
        (normalized_sha256,),
    ).fetchone()
    if revision is None:
        raise EmbeddingIngestionError(
            f"Corpus revision is not ingested: {normalized_sha256}"
        )

    parameters: dict[str, Any] = {
        "corpus_revision_id": int(revision["corpus_revision_id"]),
    }
    limit_sql = ""
    if limit is not None:
        limit_sql = "LIMIT %(limit)s"
        parameters["limit"] = limit

    rows = connection.execute(
        f"""
        SELECT
            chunks.chunk_id,
            documents.source_id,
            chunks.source_title,
            chunks.heading_text,
            chunks.content,
            chunks.content_sha256
        FROM rag.evidence_chunks AS chunks
        JOIN rag.corpus_sources AS corpus_sources
          ON corpus_sources.corpus_revision_id = chunks.corpus_revision_id
         AND corpus_sources.source_document_id = chunks.source_document_id
        JOIN rag.source_documents AS documents
          ON documents.source_document_id = chunks.source_document_id
        WHERE chunks.corpus_revision_id = %(corpus_revision_id)s
        ORDER BY
            corpus_sources.source_order,
            chunks.ordinal,
            chunks.chunk_id
        {limit_sql}
        """,
        parameters,
    ).fetchall()
    if not rows:
        raise EmbeddingIngestionError(
            "The selected corpus revision contains no chunks."
        )

    chunks = tuple(
        ChunkEmbeddingInput(
            chunk_id=str(row["chunk_id"]),
            source_id=str(row["source_id"]),
            source_title=str(row["source_title"]),
            heading_text=str(row["heading_text"]),
            content_sha256=str(row["content_sha256"]),
            prepared_input=prepare_document_embedding_input(
                source_title=str(row["source_title"]),
                heading_text=str(row["heading_text"]),
                content=str(row["content"]),
            ),
        )
        for row in rows
    )
    return PreparedEmbeddingBatch(
        corpus_revision_id=int(revision["corpus_revision_id"]),
        corpus_sha256=str(revision["corpus_sha256"]),
        chunks=chunks,
    )


def _embedding_model_values(
    config: AzureEmbeddingConfig,
) -> dict[str, Any]:
    hostname = urlsplit(config.endpoint).hostname
    if hostname is None:
        raise EmbeddingIngestionError(
            "Azure endpoint does not contain a valid hostname."
        )
    return {
        "provider": EMBEDDING_PROVIDER,
        "deployment_name": config.deployment_name,
        "model_name": config.model_name,
        "model_version": config.model_version,
        "api_version": config.api_version,
        "region": config.region,
        "dimensions": config.dimensions,
        "distance_metric": EMBEDDING_DISTANCE_METRIC,
        "document_input_version": DOCUMENT_INPUT_VERSION,
        "query_input_version": QUERY_INPUT_VERSION,
        "version_upgrade_policy": config.version_upgrade_policy,
        "metadata_json": json.dumps(
            {"endpoint_hostname": hostname},
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ),
    }


def _ensure_embedding_model(
    connection: Connection,
    config: AzureEmbeddingConfig,
) -> int:
    values = _embedding_model_values(config)
    row = connection.execute(
        """
        SELECT
            embedding_model_id,
            version_upgrade_policy,
            metadata
        FROM rag.embedding_models
        WHERE provider = %(provider)s
          AND deployment_name = %(deployment_name)s
          AND model_name = %(model_name)s
          AND model_version = %(model_version)s
          AND api_version = %(api_version)s
          AND region = %(region)s
          AND dimensions = %(dimensions)s
          AND distance_metric = %(distance_metric)s
          AND document_input_version = %(document_input_version)s
          AND query_input_version = %(query_input_version)s
        """,
        values,
    ).fetchone()
    if row is None:
        row = connection.execute(
            """
            INSERT INTO rag.embedding_models (
                provider,
                deployment_name,
                model_name,
                model_version,
                api_version,
                region,
                dimensions,
                distance_metric,
                document_input_version,
                query_input_version,
                version_upgrade_policy,
                metadata
            ) VALUES (
                %(provider)s,
                %(deployment_name)s,
                %(model_name)s,
                %(model_version)s,
                %(api_version)s,
                %(region)s,
                %(dimensions)s,
                %(distance_metric)s,
                %(document_input_version)s,
                %(query_input_version)s,
                %(version_upgrade_policy)s,
                %(metadata_json)s::jsonb
            )
            RETURNING
                embedding_model_id,
                version_upgrade_policy,
                metadata
            """,
            values,
        ).fetchone()

    expected_metadata = json.loads(values["metadata_json"])
    if (
        str(row["version_upgrade_policy"])
        != values["version_upgrade_policy"]
        or row["metadata"] != expected_metadata
    ):
        raise EmbeddingIngestionError(
            "Existing embedding-model metadata conflicts with configuration."
        )
    return int(row["embedding_model_id"])


def _start_embedding_run(
    connection: Connection,
    *,
    embedding_model_id: int,
    batch: PreparedEmbeddingBatch,
    application_revision: str,
) -> int:
    with connection.transaction():
        row = connection.execute(
            """
            INSERT INTO rag.embedding_runs (
                embedding_model_id,
                corpus_revision_id,
                status,
                application_revision,
                target_chunk_count
            ) VALUES (%s, %s, 'running', %s, %s)
            RETURNING embedding_run_id
            """,
            (
                embedding_model_id,
                batch.corpus_revision_id,
                application_revision,
                len(batch.chunks),
            ),
        ).fetchone()
    return int(row["embedding_run_id"])


def _existing_embeddings(
    connection: Connection,
    *,
    embedding_model_id: int,
    batch: PreparedEmbeddingBatch,
) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            chunk_id,
            chunk_content_sha256,
            input_sha256,
            input_char_count,
            VECTOR_DIMS(embedding) AS dimensions
        FROM rag.chunk_embeddings
        WHERE corpus_revision_id = %s
          AND embedding_model_id = %s
          AND chunk_id = ANY(%s)
        """,
        (
            batch.corpus_revision_id,
            embedding_model_id,
            [chunk.chunk_id for chunk in batch.chunks],
        ),
    ).fetchall()
    return {str(row["chunk_id"]): dict(row) for row in rows}


def _verify_existing_embedding(
    *,
    chunk: ChunkEmbeddingInput,
    row: dict[str, Any],
    dimensions: int,
) -> None:
    expected = {
        "chunk_content_sha256": chunk.content_sha256,
        "input_sha256": chunk.prepared_input.sha256,
        "input_char_count": chunk.prepared_input.char_count,
        "dimensions": dimensions,
    }
    actual = {
        "chunk_content_sha256": str(row["chunk_content_sha256"]),
        "input_sha256": str(row["input_sha256"]),
        "input_char_count": int(row["input_char_count"]),
        "dimensions": int(row["dimensions"]),
    }
    if actual != expected:
        raise EmbeddingIngestionError(
            f"{chunk.chunk_id}: existing embedding conflicts with "
            "the exact chunk or input identity."
        )


def _vector_text(vector: tuple[float, ...]) -> str:
    return json.dumps(vector, ensure_ascii=True, separators=(",", ":"))


def _complete_embedding_run(
    connection: Connection,
    *,
    embedding_run_id: int,
    embedded_count: int,
    reused_count: int,
    prompt_tokens: int,
    api_latency_ms: float,
    pricing: EmbeddingPricing | None,
    calculated_cost: Decimal | None,
) -> None:
    connection.execute(
        """
        UPDATE rag.embedding_runs
        SET
            status = 'completed',
            completed_at = CLOCK_TIMESTAMP(),
            embedded_chunk_count = %s,
            reused_chunk_count = %s,
            failed_chunk_count = 0,
            prompt_tokens = %s,
            api_latency_ms = %s,
            input_price_per_million_tokens = %s,
            pricing_currency = %s,
            pricing_checked_at = %s,
            calculated_cost = %s
        WHERE embedding_run_id = %s
        """,
        (
            embedded_count,
            reused_count,
            prompt_tokens,
            api_latency_ms,
            (
                pricing.price_per_million_tokens
                if pricing is not None
                else None
            ),
            pricing.currency if pricing is not None else None,
            pricing.checked_at if pricing is not None else None,
            calculated_cost,
            embedding_run_id,
        ),
    )


def _fail_embedding_run(
    connection: Connection,
    *,
    embedding_run_id: int,
    error: Exception,
    reused_count: int,
    prompt_tokens: int,
    api_latency_ms: float,
    pricing: EmbeddingPricing | None,
    calculated_cost: Decimal | None,
) -> None:
    with connection.transaction():
        connection.execute(
            """
            UPDATE rag.embedding_runs
            SET
                status = 'failed',
                completed_at = CLOCK_TIMESTAMP(),
                embedded_chunk_count = 0,
                reused_chunk_count = %s,
                failed_chunk_count = 1,
                prompt_tokens = %s,
                api_latency_ms = %s,
                input_price_per_million_tokens = %s,
                pricing_currency = %s,
                pricing_checked_at = %s,
                calculated_cost = %s,
                error_message = %s
            WHERE embedding_run_id = %s
            """,
            (
                reused_count,
                prompt_tokens,
                api_latency_ms,
                (
                    pricing.price_per_million_tokens
                    if pricing is not None
                    else None
                ),
                pricing.currency if pricing is not None else None,
                pricing.checked_at if pricing is not None else None,
                calculated_cost,
                f"{type(error).__name__}: {error}",
                embedding_run_id,
            ),
        )


def generate_corpus_embeddings(
    connection: Connection,
    *,
    config: AzureEmbeddingConfig,
    corpus_sha256: str,
    application_revision: str,
    limit: int | None,
    pricing: EmbeddingPricing | None = None,
) -> EmbeddingGenerationResult:
    if not connection.autocommit:
        raise EmbeddingIngestionError(
            "Embedding generation requires an autocommit connection."
        )
    if not application_revision.strip():
        raise EmbeddingIngestionError(
            "Application revision must not be blank."
        )

    connection.execute(
        "SELECT PG_ADVISORY_LOCK(HASHTEXT(%s))",
        (EMBEDDING_LOCK_KEY,),
    )
    embedding_run_id: int | None = None
    pending: list[PendingChunkEmbedding] = []
    reused_count = 0
    try:
        batch = prepare_embedding_batch(
            connection,
            corpus_sha256=corpus_sha256,
            limit=limit,
        )
        with connection.transaction():
            embedding_model_id = _ensure_embedding_model(connection, config)

        embedding_run_id = _start_embedding_run(
            connection,
            embedding_model_id=embedding_model_id,
            batch=batch,
            application_revision=application_revision,
        )
        existing = _existing_embeddings(
            connection,
            embedding_model_id=embedding_model_id,
            batch=batch,
        )

        for chunk in batch.chunks:
            existing_row = existing.get(chunk.chunk_id)
            if existing_row is not None:
                _verify_existing_embedding(
                    chunk=chunk,
                    row=existing_row,
                    dimensions=config.dimensions,
                )
                reused_count += 1
                continue

            response = request_embedding_with_retry(
                config,
                chunk.prepared_input.text,
            )
            calculated_cost = (
                pricing.cost_for_tokens(response.prompt_tokens)
                if pricing is not None
                else None
            )
            pending.append(
                PendingChunkEmbedding(
                    chunk=chunk,
                    response=response,
                    calculated_cost=calculated_cost,
                )
            )

        prompt_tokens = sum(
            item.response.prompt_tokens for item in pending
        )
        api_latency_ms = sum(
            item.response.latency_ms for item in pending
        )
        calculated_cost = (
            sum(
                (
                    item.calculated_cost
                    for item in pending
                    if item.calculated_cost is not None
                ),
                Decimal("0"),
            )
            if pricing is not None
            else None
        )

        with connection.transaction():
            for item in pending:
                connection.execute(
                    """
                    INSERT INTO rag.chunk_embeddings (
                        corpus_revision_id,
                        chunk_id,
                        chunk_content_sha256,
                        embedding_model_id,
                        embedding_run_id,
                        input_sha256,
                        input_char_count,
                        prompt_tokens,
                        api_latency_ms,
                        calculated_cost,
                        response_model,
                        vector_sha256,
                        embedding
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s::vector
                    )
                    """,
                    (
                        batch.corpus_revision_id,
                        item.chunk.chunk_id,
                        item.chunk.content_sha256,
                        embedding_model_id,
                        embedding_run_id,
                        item.chunk.prepared_input.sha256,
                        item.chunk.prepared_input.char_count,
                        item.response.prompt_tokens,
                        item.response.latency_ms,
                        item.calculated_cost,
                        item.response.response_model,
                        item.response.vector_sha256,
                        _vector_text(item.response.vector),
                    ),
                )

            _complete_embedding_run(
                connection,
                embedding_run_id=embedding_run_id,
                embedded_count=len(pending),
                reused_count=reused_count,
                prompt_tokens=prompt_tokens,
                api_latency_ms=api_latency_ms,
                pricing=pricing,
                calculated_cost=calculated_cost,
            )

        return EmbeddingGenerationResult(
            embedding_run_id=embedding_run_id,
            embedding_model_id=embedding_model_id,
            corpus_revision_id=batch.corpus_revision_id,
            corpus_sha256=batch.corpus_sha256,
            target_chunk_count=len(batch.chunks),
            embedded_chunk_count=len(pending),
            reused_chunk_count=reused_count,
            prompt_tokens=prompt_tokens,
            api_latency_ms=api_latency_ms,
            calculated_cost=calculated_cost,
        )
    except Exception as exc:
        if embedding_run_id is not None:
            try:
                prompt_tokens = sum(
                    item.response.prompt_tokens for item in pending
                )
                api_latency_ms = sum(
                    item.response.latency_ms for item in pending
                )
                if isinstance(exc, AzureEmbeddingHTTPError):
                    api_latency_ms += exc.latency_ms
                calculated_cost = (
                    sum(
                        (
                            item.calculated_cost
                            for item in pending
                            if item.calculated_cost is not None
                        ),
                        Decimal("0"),
                    )
                    if pricing is not None
                    else None
                )
                _fail_embedding_run(
                    connection,
                    embedding_run_id=embedding_run_id,
                    error=exc,
                    reused_count=reused_count,
                    prompt_tokens=prompt_tokens,
                    api_latency_ms=api_latency_ms,
                    pricing=pricing,
                    calculated_cost=calculated_cost,
                )
            except Exception as failure_record_error:
                raise EmbeddingIngestionError(
                    "Embedding generation failed and its failure record could "
                    "not be persisted. Original error: "
                    f"{type(exc).__name__}: {exc}"
                ) from failure_record_error
        raise
    finally:
        connection.execute(
            "SELECT PG_ADVISORY_UNLOCK(HASHTEXT(%s))",
            (EMBEDDING_LOCK_KEY,),
        )


def apply_verified_embedding_pricing(
    connection: Connection,
    *,
    embedding_model_id: int,
    pricing: EmbeddingPricing,
) -> tuple[int, int]:
    if not connection.autocommit:
        raise EmbeddingIngestionError(
            "Embedding pricing backfill requires an autocommit connection."
        )

    with connection.transaction():
        chunk_result = connection.execute(
            """
            UPDATE rag.chunk_embeddings
            SET calculated_cost = (
                prompt_tokens
                * %(price)s::numeric
                / 1000000::numeric
            )
            WHERE embedding_model_id = %(embedding_model_id)s
              AND calculated_cost IS NULL
            """,
            {
                "embedding_model_id": embedding_model_id,
                "price": pricing.price_per_million_tokens,
            },
        )
        run_result = connection.execute(
            """
            UPDATE rag.embedding_runs
            SET
                input_price_per_million_tokens = %(price)s,
                pricing_currency = %(currency)s,
                pricing_checked_at = %(checked_at)s,
                calculated_cost = (
                    prompt_tokens
                    * %(price)s::numeric
                    / 1000000::numeric
                )
            WHERE embedding_model_id = %(embedding_model_id)s
              AND status = 'completed'
              AND input_price_per_million_tokens IS NULL
            """,
            {
                "embedding_model_id": embedding_model_id,
                "price": pricing.price_per_million_tokens,
                "currency": pricing.currency,
                "checked_at": pricing.checked_at,
            },
        )

    return chunk_result.rowcount, run_result.rowcount
