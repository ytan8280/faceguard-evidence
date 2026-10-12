from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from psycopg import Connection

from .chunking import CHUNKER_VERSION, DEFAULT_MAX_CHARS
from .models import EvidenceChunk, SourceDocument


CORPUS_MANIFEST_SCHEMA_VERSION = 1
DEFAULT_CORPUS_NAME = "faceguard-evidence"
DEFAULT_OVERLAP_CHARS = 0
INGESTION_LOCK_KEY = "faceguard_evidence_corpus_ingestion"


class CorpusIngestionError(RuntimeError):
    """Raised when a corpus cannot be prepared or stored consistently."""


@dataclass(frozen=True, slots=True)
class PreparedSource:
    document: SourceDocument
    content_path: str
    content_bytes: int
    content_lines: int
    metadata_json: str


@dataclass(frozen=True, slots=True)
class PreparedCorpus:
    name: str
    sources: tuple[PreparedSource, ...]
    chunks: tuple[EvidenceChunk, ...]
    chunker_version: str
    max_chunk_chars: int
    overlap_chars: int
    manifest_json: str
    corpus_sha256: str


@dataclass(frozen=True, slots=True)
class IngestionResult:
    ingestion_run_id: int
    corpus_revision_id: int
    corpus_sha256: str
    source_count: int
    chunk_count: int
    reused: bool


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest().upper()


def _prepare_source(
    document: SourceDocument,
    *,
    repository_root: Path,
) -> PreparedSource:
    content_path = document.content_path.resolve()
    try:
        relative_content_path = content_path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise CorpusIngestionError(
            f"{document.source_id}: content path is outside the repository."
        ) from exc

    if _content_sha256(document.content) != document.content_sha256:
        raise CorpusIngestionError(
            f"{document.source_id}: loaded content no longer matches its SHA-256."
        )

    try:
        metadata = json.loads(document.metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, JSONDecodeError) as exc:
        raise CorpusIngestionError(
            f"{document.source_id}: unable to read its metadata snapshot."
        ) from exc

    if not isinstance(metadata, dict):
        raise CorpusIngestionError(
            f"{document.source_id}: metadata snapshot must be a JSON object."
        )
    if metadata.get("source_id") != document.source_id:
        raise CorpusIngestionError(
            f"{document.source_id}: metadata source identity changed after loading."
        )
    normalized = metadata.get("normalized")
    if (
        not isinstance(normalized, dict)
        or normalized.get("sha256") != document.content_sha256
    ):
        raise CorpusIngestionError(
            f"{document.source_id}: metadata content identity changed after loading."
        )

    content_bytes = len(document.content.encode("utf-8"))
    content_lines = len(document.content.splitlines())
    if normalized.get("bytes") != content_bytes:
        raise CorpusIngestionError(
            f"{document.source_id}: metadata byte count changed after loading."
        )
    if normalized.get("lines") != content_lines:
        raise CorpusIngestionError(
            f"{document.source_id}: metadata line count changed after loading."
        )

    return PreparedSource(
        document=document,
        content_path=relative_content_path.as_posix(),
        content_bytes=content_bytes,
        content_lines=content_lines,
        metadata_json=_canonical_json(metadata),
    )


def _validate_chunks(
    *,
    documents_by_id: dict[str, SourceDocument],
    chunks: tuple[EvidenceChunk, ...],
    chunker_version: str,
    max_chunk_chars: int,
) -> None:
    seen_chunk_ids: set[str] = set()
    chunks_by_source: dict[str, list[EvidenceChunk]] = {
        source_id: [] for source_id in documents_by_id
    }

    for chunk in chunks:
        document = documents_by_id.get(chunk.source_id)
        if document is None:
            raise CorpusIngestionError(
                f"{chunk.chunk_id}: chunk references an unknown source."
            )
        if chunk.chunk_id in seen_chunk_ids:
            raise CorpusIngestionError(
                f"{chunk.chunk_id}: duplicate chunk identity."
            )
        if chunk.source_title != document.title:
            raise CorpusIngestionError(
                f"{chunk.chunk_id}: source title does not match its document."
            )
        if chunk.source_category != document.source_category:
            raise CorpusIngestionError(
                f"{chunk.chunk_id}: source category does not match its document."
            )
        if chunk.source_version != document.version:
            raise CorpusIngestionError(
                f"{chunk.chunk_id}: source version does not match its document."
            )
        if chunk.canonical_url != document.canonical_url:
            raise CorpusIngestionError(
                f"{chunk.chunk_id}: canonical URL does not match its document."
            )
        if chunk.chunker_version != chunker_version:
            raise CorpusIngestionError(
                f"{chunk.chunk_id}: unexpected chunker version."
            )
        expected_chunk_id = (
            f"{chunk.source_id}:{chunk.ordinal:04d}:"
            f"{chunk.content_sha256[:12]}"
        )
        if chunk.chunk_id != expected_chunk_id:
            raise CorpusIngestionError(
                f"{chunk.chunk_id}: chunk identity does not match its content."
            )
        if chunk.char_count != len(chunk.content):
            raise CorpusIngestionError(
                f"{chunk.chunk_id}: character count does not match its content."
            )
        if _content_sha256(chunk.content) != chunk.content_sha256:
            raise CorpusIngestionError(
                f"{chunk.chunk_id}: content does not match its SHA-256."
            )
        if chunk.char_count > max_chunk_chars and not chunk.oversized:
            raise CorpusIngestionError(
                f"{chunk.chunk_id}: oversized content is not marked oversized."
            )

        seen_chunk_ids.add(chunk.chunk_id)
        chunks_by_source[chunk.source_id].append(chunk)

    for source_id, source_chunks in chunks_by_source.items():
        if not source_chunks:
            raise CorpusIngestionError(
                f"{source_id}: source produced no chunks."
            )
        ordinals = [chunk.ordinal for chunk in source_chunks]
        if ordinals != list(range(1, len(source_chunks) + 1)):
            raise CorpusIngestionError(
                f"{source_id}: chunk ordinals are not contiguous from one."
            )


def prepare_corpus(
    *,
    documents: list[SourceDocument],
    chunks: list[EvidenceChunk],
    repository_root: Path,
    name: str = DEFAULT_CORPUS_NAME,
    chunker_version: str = CHUNKER_VERSION,
    max_chunk_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> PreparedCorpus:
    if not name.strip():
        raise CorpusIngestionError("Corpus name must not be blank.")
    if not documents:
        raise CorpusIngestionError("At least one source document is required.")
    if not chunks:
        raise CorpusIngestionError("At least one evidence chunk is required.")
    if max_chunk_chars <= 0:
        raise CorpusIngestionError("Maximum chunk characters must be positive.")
    if overlap_chars < 0:
        raise CorpusIngestionError("Overlap characters must not be negative.")

    ordered_documents = tuple(
        sorted(documents, key=lambda document: document.source_id)
    )
    documents_by_id = {
        document.source_id: document for document in ordered_documents
    }
    if len(documents_by_id) != len(ordered_documents):
        raise CorpusIngestionError("Source document identities must be unique.")

    ordered_chunks = tuple(
        sorted(chunks, key=lambda chunk: (chunk.source_id, chunk.ordinal))
    )
    _validate_chunks(
        documents_by_id=documents_by_id,
        chunks=ordered_chunks,
        chunker_version=chunker_version,
        max_chunk_chars=max_chunk_chars,
    )

    prepared_sources = tuple(
        _prepare_source(document, repository_root=repository_root)
        for document in ordered_documents
    )
    manifest = {
        "schema_version": CORPUS_MANIFEST_SCHEMA_VERSION,
        "name": name,
        "chunking": {
            "chunker_version": chunker_version,
            "max_chunk_chars": max_chunk_chars,
            "overlap_chars": overlap_chars,
        },
        "sources": [
            {
                "source_id": source.document.source_id,
                "source_version": source.document.version,
                "content_sha256": source.document.content_sha256,
            }
            for source in prepared_sources
        ],
        "chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "source_id": chunk.source_id,
                "ordinal": chunk.ordinal,
                "content_sha256": chunk.content_sha256,
                "heading_path": list(chunk.heading_path),
                "page_number": chunk.page_number,
                "char_count": chunk.char_count,
                "oversized": chunk.oversized,
            }
            for chunk in ordered_chunks
        ],
    }
    manifest_json = _canonical_json(manifest)
    corpus_sha256 = hashlib.sha256(
        manifest_json.encode("utf-8")
    ).hexdigest().upper()

    return PreparedCorpus(
        name=name,
        sources=prepared_sources,
        chunks=ordered_chunks,
        chunker_version=chunker_version,
        max_chunk_chars=max_chunk_chars,
        overlap_chars=overlap_chars,
        manifest_json=manifest_json,
        corpus_sha256=corpus_sha256,
    )


def _start_ingestion_run(
    connection: Connection,
    *,
    application_revision: str,
) -> int:
    with connection.transaction():
        row = connection.execute(
            """
            INSERT INTO rag.ingestion_runs (
                status,
                application_revision
            ) VALUES ('running', %s)
            RETURNING ingestion_run_id
            """,
            (application_revision,),
        ).fetchone()
    return int(row["ingestion_run_id"])


def _source_database_values(source: PreparedSource) -> dict[str, Any]:
    document = source.document
    return {
        "source_id": document.source_id,
        "content_sha256": document.content_sha256,
        "title": document.title,
        "source_category": document.source_category,
        "publisher": document.publisher,
        "authors": list(document.authors),
        "source_version": document.version,
        "published_at": document.published_at,
        "canonical_url": document.canonical_url,
        "license_name": document.license_name,
        "license_url": document.license_url,
        "content_path": source.content_path,
        "content": document.content,
        "content_bytes": source.content_bytes,
        "content_lines": source.content_lines,
        "metadata_json": source.metadata_json,
    }


def _verify_existing_source(
    source: PreparedSource,
    row: dict[str, Any],
) -> int:
    expected = _source_database_values(source)
    actual = {
        "source_id": row["source_id"],
        "content_sha256": row["content_sha256"],
        "title": row["title"],
        "source_category": row["source_category"],
        "publisher": row["publisher"],
        "authors": list(row["authors"]),
        "source_version": row["source_version"],
        "published_at": row["published_at"].isoformat(),
        "canonical_url": row["canonical_url"],
        "license_name": row["license_name"],
        "license_url": row["license_url"],
        "content_path": row["content_path"],
        "content": row["content"],
        "content_bytes": row["content_bytes"],
        "content_lines": row["content_lines"],
        "metadata_json": _canonical_json(row["metadata"]),
    }
    if actual != expected:
        raise CorpusIngestionError(
            f"{source.document.source_id}: existing source version differs "
            "from the verified source snapshot."
        )
    return int(row["source_document_id"])


def _upsert_source(
    connection: Connection,
    source: PreparedSource,
) -> int:
    values = _source_database_values(source)
    row = connection.execute(
        """
        INSERT INTO rag.source_documents (
            source_id,
            content_sha256,
            title,
            source_category,
            publisher,
            authors,
            source_version,
            published_at,
            canonical_url,
            license_name,
            license_url,
            content_path,
            content,
            content_bytes,
            content_lines,
            metadata
        ) VALUES (
            %(source_id)s,
            %(content_sha256)s,
            %(title)s,
            %(source_category)s,
            %(publisher)s,
            %(authors)s,
            %(source_version)s,
            %(published_at)s,
            %(canonical_url)s,
            %(license_name)s,
            %(license_url)s,
            %(content_path)s,
            %(content)s,
            %(content_bytes)s,
            %(content_lines)s,
            %(metadata_json)s::jsonb
        )
        ON CONFLICT (source_id, content_sha256) DO NOTHING
        RETURNING source_document_id
        """,
        values,
    ).fetchone()
    if row is not None:
        return int(row["source_document_id"])

    existing = connection.execute(
        """
        SELECT
            source_document_id,
            source_id,
            content_sha256,
            title,
            source_category,
            publisher,
            authors,
            source_version,
            published_at,
            canonical_url,
            license_name,
            license_url,
            content_path,
            content,
            content_bytes,
            content_lines,
            metadata
        FROM rag.source_documents
        WHERE source_id = %s
          AND content_sha256 = %s
        """,
        (source.document.source_id, source.document.content_sha256),
    ).fetchone()
    if existing is None:
        raise CorpusIngestionError(
            f"{source.document.source_id}: source insert conflicted but no "
            "existing source was found."
        )
    return _verify_existing_source(source, existing)


def _find_corpus_revision(
    connection: Connection,
    prepared: PreparedCorpus,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT
            corpus_revision_id,
            corpus_sha256,
            name,
            chunker_version,
            max_chunk_chars,
            overlap_chars,
            source_count,
            chunk_count,
            manifest
        FROM rag.corpus_revisions
        WHERE corpus_sha256 = %s
        """,
        (prepared.corpus_sha256,),
    ).fetchone()
    if row is None:
        return None

    expected = {
        "corpus_sha256": prepared.corpus_sha256,
        "name": prepared.name,
        "chunker_version": prepared.chunker_version,
        "max_chunk_chars": prepared.max_chunk_chars,
        "overlap_chars": prepared.overlap_chars,
        "source_count": len(prepared.sources),
        "chunk_count": len(prepared.chunks),
        "manifest_json": prepared.manifest_json,
    }
    actual = {
        "corpus_sha256": row["corpus_sha256"],
        "name": row["name"],
        "chunker_version": row["chunker_version"],
        "max_chunk_chars": row["max_chunk_chars"],
        "overlap_chars": row["overlap_chars"],
        "source_count": row["source_count"],
        "chunk_count": row["chunk_count"],
        "manifest_json": _canonical_json(row["manifest"]),
    }
    if actual != expected:
        raise CorpusIngestionError(
            "Existing corpus revision does not match its recorded identity."
        )
    return row


def _create_corpus_revision(
    connection: Connection,
    prepared: PreparedCorpus,
) -> int:
    row = connection.execute(
        """
        INSERT INTO rag.corpus_revisions (
            corpus_sha256,
            name,
            chunker_version,
            max_chunk_chars,
            overlap_chars,
            source_count,
            chunk_count,
            manifest
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        RETURNING corpus_revision_id
        """,
        (
            prepared.corpus_sha256,
            prepared.name,
            prepared.chunker_version,
            prepared.max_chunk_chars,
            prepared.overlap_chars,
            len(prepared.sources),
            len(prepared.chunks),
            prepared.manifest_json,
        ),
    ).fetchone()
    return int(row["corpus_revision_id"])


def _insert_corpus_sources(
    connection: Connection,
    *,
    corpus_revision_id: int,
    prepared: PreparedCorpus,
    source_document_ids: dict[str, int],
) -> None:
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO rag.corpus_sources (
                corpus_revision_id,
                source_document_id,
                source_order
            ) VALUES (%s, %s, %s)
            """,
            [
                (
                    corpus_revision_id,
                    source_document_ids[source.document.source_id],
                    source_order,
                )
                for source_order, source in enumerate(
                    prepared.sources,
                    start=1,
                )
            ],
        )


def _insert_chunks(
    connection: Connection,
    *,
    corpus_revision_id: int,
    prepared: PreparedCorpus,
    source_document_ids: dict[str, int],
) -> None:
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO rag.evidence_chunks (
                corpus_revision_id,
                chunk_id,
                source_document_id,
                source_title,
                ordinal,
                heading_path,
                heading_text,
                page_number,
                content,
                content_sha256,
                char_count,
                oversized,
                chunker_version
            ) VALUES (
                %(corpus_revision_id)s,
                %(chunk_id)s,
                %(source_document_id)s,
                %(source_title)s,
                %(ordinal)s,
                %(heading_path)s,
                %(heading_text)s,
                %(page_number)s,
                %(content)s,
                %(content_sha256)s,
                %(char_count)s,
                %(oversized)s,
                %(chunker_version)s
            )
            """,
            [
                {
                    "corpus_revision_id": corpus_revision_id,
                    "chunk_id": chunk.chunk_id,
                    "source_document_id": source_document_ids[chunk.source_id],
                    "source_title": chunk.source_title,
                    "ordinal": chunk.ordinal,
                    "heading_path": list(chunk.heading_path),
                    "heading_text": " > ".join(chunk.heading_path),
                    "page_number": chunk.page_number,
                    "content": chunk.content,
                    "content_sha256": chunk.content_sha256,
                    "char_count": chunk.char_count,
                    "oversized": chunk.oversized,
                    "chunker_version": chunk.chunker_version,
                }
                for chunk in prepared.chunks
            ],
        )


def _expected_chunk_record(chunk: EvidenceChunk) -> tuple[Any, ...]:
    return (
        chunk.chunk_id,
        chunk.source_id,
        chunk.source_title,
        chunk.ordinal,
        chunk.heading_path,
        chunk.page_number,
        chunk.content,
        chunk.content_sha256,
        chunk.char_count,
        chunk.oversized,
        chunk.chunker_version,
    )


def _verify_existing_corpus_content(
    connection: Connection,
    *,
    corpus_revision_id: int,
    prepared: PreparedCorpus,
) -> None:
    source_rows = connection.execute(
        """
        SELECT
            documents.source_id,
            documents.content_sha256,
            membership.source_order
        FROM rag.corpus_sources AS membership
        JOIN rag.source_documents AS documents
          ON documents.source_document_id = membership.source_document_id
        WHERE membership.corpus_revision_id = %s
        ORDER BY membership.source_order
        """,
        (corpus_revision_id,),
    ).fetchall()
    actual_sources = [
        (
            row["source_id"],
            row["content_sha256"],
            row["source_order"],
        )
        for row in source_rows
    ]
    expected_sources = [
        (
            source.document.source_id,
            source.document.content_sha256,
            source_order,
        )
        for source_order, source in enumerate(prepared.sources, start=1)
    ]
    if actual_sources != expected_sources:
        raise CorpusIngestionError(
            "Existing corpus source membership is incomplete or inconsistent."
        )

    chunk_rows = connection.execute(
        """
        SELECT
            chunks.chunk_id,
            documents.source_id,
            chunks.source_title,
            chunks.ordinal,
            chunks.heading_path,
            chunks.page_number,
            chunks.content,
            chunks.content_sha256,
            chunks.char_count,
            chunks.oversized,
            chunks.chunker_version
        FROM rag.evidence_chunks AS chunks
        JOIN rag.source_documents AS documents
          ON documents.source_document_id = chunks.source_document_id
        WHERE chunks.corpus_revision_id = %s
        ORDER BY documents.source_id, chunks.ordinal
        """,
        (corpus_revision_id,),
    ).fetchall()
    actual_chunks = [
        (
            row["chunk_id"],
            row["source_id"],
            row["source_title"],
            row["ordinal"],
            tuple(row["heading_path"]),
            row["page_number"],
            row["content"],
            row["content_sha256"],
            row["char_count"],
            row["oversized"],
            row["chunker_version"],
        )
        for row in chunk_rows
    ]
    expected_chunks = [
        _expected_chunk_record(chunk) for chunk in prepared.chunks
    ]
    if actual_chunks != expected_chunks:
        raise CorpusIngestionError(
            "Existing corpus chunks are incomplete or inconsistent."
        )


def _complete_ingestion_run(
    connection: Connection,
    *,
    ingestion_run_id: int,
    corpus_revision_id: int,
    prepared: PreparedCorpus,
) -> None:
    connection.execute(
        """
        UPDATE rag.ingestion_runs
        SET
            corpus_revision_id = %s,
            status = 'completed',
            completed_at = CLOCK_TIMESTAMP(),
            source_count = %s,
            chunk_count = %s
        WHERE ingestion_run_id = %s
        """,
        (
            corpus_revision_id,
            len(prepared.sources),
            len(prepared.chunks),
            ingestion_run_id,
        ),
    )


def _fail_ingestion_run(
    connection: Connection,
    *,
    ingestion_run_id: int,
    error: Exception,
) -> None:
    with connection.transaction():
        connection.execute(
            """
            UPDATE rag.ingestion_runs
            SET
                status = 'failed',
                completed_at = CLOCK_TIMESTAMP(),
                error_message = %s
            WHERE ingestion_run_id = %s
            """,
            (
                f"{type(error).__name__}: {error}",
                ingestion_run_id,
            ),
        )


def ingest_prepared_corpus(
    connection: Connection,
    *,
    prepared: PreparedCorpus,
    application_revision: str,
) -> IngestionResult:
    if not connection.autocommit:
        raise CorpusIngestionError(
            "Corpus ingestion requires an autocommit connection."
        )
    if not application_revision.strip():
        raise CorpusIngestionError("Application revision must not be blank.")

    connection.execute(
        "SELECT PG_ADVISORY_LOCK(HASHTEXT(%s))",
        (INGESTION_LOCK_KEY,),
    )
    ingestion_run_id: int | None = None
    try:
        ingestion_run_id = _start_ingestion_run(
            connection,
            application_revision=application_revision,
        )
        reused = False
        with connection.transaction():
            source_document_ids = {
                source.document.source_id: _upsert_source(connection, source)
                for source in prepared.sources
            }
            existing_revision = _find_corpus_revision(connection, prepared)
            if existing_revision is None:
                corpus_revision_id = _create_corpus_revision(
                    connection,
                    prepared,
                )
                _insert_corpus_sources(
                    connection,
                    corpus_revision_id=corpus_revision_id,
                    prepared=prepared,
                    source_document_ids=source_document_ids,
                )
                _insert_chunks(
                    connection,
                    corpus_revision_id=corpus_revision_id,
                    prepared=prepared,
                    source_document_ids=source_document_ids,
                )
            else:
                reused = True
                corpus_revision_id = int(
                    existing_revision["corpus_revision_id"]
                )
                _verify_existing_corpus_content(
                    connection,
                    corpus_revision_id=corpus_revision_id,
                    prepared=prepared,
                )

            _complete_ingestion_run(
                connection,
                ingestion_run_id=ingestion_run_id,
                corpus_revision_id=corpus_revision_id,
                prepared=prepared,
            )

        return IngestionResult(
            ingestion_run_id=ingestion_run_id,
            corpus_revision_id=corpus_revision_id,
            corpus_sha256=prepared.corpus_sha256,
            source_count=len(prepared.sources),
            chunk_count=len(prepared.chunks),
            reused=reused,
        )
    except Exception as exc:
        if ingestion_run_id is not None:
            try:
                _fail_ingestion_run(
                    connection,
                    ingestion_run_id=ingestion_run_id,
                    error=exc,
                )
            except Exception as failure_record_error:
                raise CorpusIngestionError(
                    "Corpus ingestion failed and its failure record could not "
                    f"be persisted. Original error: {type(exc).__name__}: {exc}"
                ) from failure_record_error
        raise
    finally:
        connection.execute(
            "SELECT PG_ADVISORY_UNLOCK(HASHTEXT(%s))",
            (INGESTION_LOCK_KEY,),
        )
