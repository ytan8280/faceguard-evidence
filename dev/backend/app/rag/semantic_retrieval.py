from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from psycopg import Connection

from .azure_embeddings import AzureEmbeddingConfig
from .embedding_ingestion import (
    EMBEDDING_DISTANCE_METRIC,
    EMBEDDING_PROVIDER,
)
from .embedding_input import DOCUMENT_INPUT_VERSION, QUERY_INPUT_VERSION


SEMANTIC_RETRIEVER_VERSION = "pgvector-exact-cosine-v1"


class SemanticRetrievalError(RuntimeError):
    """Raised when exact semantic retrieval cannot be performed."""


@dataclass(frozen=True, slots=True)
class SemanticRetrievedChunk:
    rank: int
    chunk_id: str
    source_id: str
    source_title: str
    heading_path: tuple[str, ...]
    page_number: int | None
    content: str
    score: float
    cosine_distance: float


def resolve_embedding_model_id(
    connection: Connection,
    *,
    config: AzureEmbeddingConfig,
) -> int:
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
        raise SemanticRetrievalError(
            "Configured embedding model is not registered."
        )
    return int(row["embedding_model_id"])


def verify_embedding_coverage(
    connection: Connection,
    *,
    corpus_revision_id: int,
    embedding_model_id: int,
) -> int:
    row = connection.execute(
        """
        SELECT
            revisions.chunk_count AS expected_count,
            COUNT(embeddings.chunk_id) AS embedding_count
        FROM rag.corpus_revisions AS revisions
        LEFT JOIN rag.chunk_embeddings AS embeddings
          ON embeddings.corpus_revision_id = revisions.corpus_revision_id
         AND embeddings.embedding_model_id = %s
        WHERE revisions.corpus_revision_id = %s
        GROUP BY revisions.chunk_count
        """,
        (embedding_model_id, corpus_revision_id),
    ).fetchone()
    if row is None:
        raise SemanticRetrievalError(
            f"Corpus revision is not ingested: {corpus_revision_id}"
        )
    expected_count = int(row["expected_count"])
    embedding_count = int(row["embedding_count"])
    if embedding_count != expected_count:
        raise SemanticRetrievalError(
            "Embedding coverage is incomplete: "
            f"{embedding_count} of {expected_count} chunks."
        )
    return embedding_count


def semantic_retrieve_exact(
    connection: Connection,
    *,
    corpus_revision_id: int,
    embedding_model_id: int,
    query_vector: tuple[float, ...],
    expected_dimensions: int,
    limit: int = 5,
) -> list[SemanticRetrievedChunk]:
    if len(query_vector) != expected_dimensions:
        raise SemanticRetrievalError(
            "Query-vector dimensions do not match the registered model."
        )
    if limit <= 0:
        raise SemanticRetrievalError("Retrieval limit must be positive.")

    vector_text = json.dumps(
        query_vector,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    parameters: dict[str, Any] = {
        "corpus_revision_id": corpus_revision_id,
        "embedding_model_id": embedding_model_id,
        "query_vector": vector_text,
        "limit": limit,
    }

    with connection.transaction():
        connection.execute("SET LOCAL enable_indexscan = off")
        connection.execute("SET LOCAL enable_indexonlyscan = off")
        connection.execute("SET LOCAL enable_bitmapscan = off")
        rows = connection.execute(
            """
            SELECT
                chunks.chunk_id,
                documents.source_id,
                chunks.source_title,
                chunks.heading_path,
                chunks.page_number,
                chunks.content,
                (
                    embeddings.embedding
                    <=> %(query_vector)s::vector
                ) AS cosine_distance
            FROM rag.chunk_embeddings AS embeddings
            JOIN rag.evidence_chunks AS chunks
              ON chunks.corpus_revision_id = embeddings.corpus_revision_id
             AND chunks.chunk_id = embeddings.chunk_id
            JOIN rag.source_documents AS documents
              ON documents.source_document_id = chunks.source_document_id
            WHERE embeddings.corpus_revision_id = %(corpus_revision_id)s
              AND embeddings.embedding_model_id = %(embedding_model_id)s
            ORDER BY
                embeddings.embedding <=> %(query_vector)s::vector,
                chunks.chunk_id
            LIMIT %(limit)s
            """,
            parameters,
        ).fetchall()

    return [
        SemanticRetrievedChunk(
            rank=rank,
            chunk_id=str(row["chunk_id"]),
            source_id=str(row["source_id"]),
            source_title=str(row["source_title"]),
            heading_path=tuple(row["heading_path"]),
            page_number=row["page_number"],
            content=str(row["content"]),
            score=1.0 - float(row["cosine_distance"]),
            cosine_distance=float(row["cosine_distance"]),
        )
        for rank, row in enumerate(rows, start=1)
    ]
