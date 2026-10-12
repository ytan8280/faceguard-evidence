from __future__ import annotations

from dataclasses import dataclass

from psycopg import Connection


LEXICAL_RETRIEVER_VERSION = "postgresql-fts-v1"


class RetrievalError(RuntimeError):
    """Raised when retrieval configuration or database state is invalid."""


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    rank: int
    chunk_id: str
    source_id: str
    source_title: str
    heading_path: tuple[str, ...]
    page_number: int | None
    content: str
    score: float
    strict_match: bool


def resolve_corpus_revision_id(
    connection: Connection,
    *,
    corpus_sha256: str,
) -> int:
    row = connection.execute(
        """
        SELECT corpus_revision_id
        FROM rag.corpus_revisions
        WHERE corpus_sha256 = %s
        """,
        (corpus_sha256,),
    ).fetchone()
    if row is None:
        raise RetrievalError(
            f"Corpus revision is not ingested: {corpus_sha256}"
        )
    return int(row["corpus_revision_id"])


def lexical_retrieve(
    connection: Connection,
    *,
    corpus_revision_id: int,
    query: str,
    limit: int = 5,
) -> list[RetrievedChunk]:
    normalized_query = query.strip()
    if not normalized_query:
        raise RetrievalError("Retrieval query must not be blank.")
    if limit <= 0:
        raise RetrievalError("Retrieval limit must be positive.")

    rows = connection.execute(
        """
        WITH query_text AS (
            SELECT
                WEBSEARCH_TO_TSQUERY('english', %(query)s) AS strict_query,
                ARRAY_TO_STRING(
                    TSVECTOR_TO_ARRAY(
                        TO_TSVECTOR('english', %(query)s)
                    ),
                    ' | '
                ) AS broad_query_text
        ),
        queries AS (
            SELECT
                strict_query,
                CASE
                    WHEN broad_query_text = '' THEN NULL
                    ELSE TO_TSQUERY('english', broad_query_text)
                END AS broad_query
            FROM query_text
        )
        SELECT
            chunks.chunk_id,
            documents.source_id,
            chunks.source_title,
            chunks.heading_path,
            chunks.page_number,
            chunks.content,
            (
                TS_RANK_CD(chunks.search_vector, queries.broad_query)
                +
                CASE
                    WHEN chunks.search_vector @@ queries.strict_query
                    THEN 2 * TS_RANK_CD(
                        chunks.search_vector,
                        queries.strict_query
                    )
                    ELSE 0
                END
            ) AS score,
            chunks.search_vector @@ queries.strict_query AS strict_match
        FROM rag.evidence_chunks AS chunks
        JOIN rag.source_documents AS documents
          ON documents.source_document_id = chunks.source_document_id
        CROSS JOIN queries
        WHERE chunks.corpus_revision_id = %(corpus_revision_id)s
          AND queries.broad_query IS NOT NULL
          AND chunks.search_vector @@ queries.broad_query
        ORDER BY
            score DESC,
            chunks.chunk_id
        LIMIT %(limit)s
        """,
        {
            "query": normalized_query,
            "corpus_revision_id": corpus_revision_id,
            "limit": limit,
        },
    ).fetchall()

    return [
        RetrievedChunk(
            rank=rank,
            chunk_id=str(row["chunk_id"]),
            source_id=str(row["source_id"]),
            source_title=str(row["source_title"]),
            heading_path=tuple(row["heading_path"]),
            page_number=row["page_number"],
            content=str(row["content"]),
            score=float(row["score"]),
            strict_match=bool(row["strict_match"]),
        )
        for rank, row in enumerate(rows, start=1)
    ]
