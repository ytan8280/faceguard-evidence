from __future__ import annotations

from pathlib import Path

from dev.backend.app.rag.chunking import CHUNKER_VERSION, chunk_document, chunk_documents
from dev.backend.app.rag.models import SourceDocument
from dev.backend.app.rag.source_loader import load_source_documents


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SOURCE_ROOT = REPOSITORY_ROOT / "data" / "sources"


def _document(content: str, source_id: str = "TEST-DOC-001") -> SourceDocument:
    return SourceDocument(
        source_id=source_id,
        title="Test document",
        source_category="test",
        publisher="FaceGuard Evidence",
        authors=("Tan Yan Yi",),
        version="test-v1",
        published_at="2026-10-07",
        canonical_url="repo:///test.md",
        license_name="Test",
        license_url="repo:///test-license",
        content=content,
        content_sha256="TEST",
        content_path=Path("test.md"),
        metadata_path=Path("metadata.json"),
    )


def test_chunk_document_preserves_heading_and_page_context() -> None:
    document = _document(
        """# Root

Introduction.

## Limitations

<!-- source-page: 7 -->

First limitation.

Second limitation.
"""
    )

    chunks = chunk_document(document, max_chars=25)

    assert chunks[0].heading_path == ("Root",)
    assert chunks[0].page_number is None
    assert chunks[1].heading_path == ("Root", "Limitations")
    assert chunks[1].page_number == 7
    assert all(chunk.chunker_version == CHUNKER_VERSION for chunk in chunks)


def test_chunk_document_splits_oversized_prose_at_boundaries() -> None:
    document = _document(
        "# Root\n\nFirst sentence is short. Second sentence is also short. "
        "Third sentence completes the example."
    )

    chunks = chunk_document(document, max_chars=50)

    assert len(chunks) == 3
    assert all(chunk.char_count <= 50 for chunk in chunks)
    assert all(chunk.oversized is False for chunk in chunks)


def test_chunk_document_preserves_oversized_table() -> None:
    document = _document(
        """# Root

Table 1. Long values

| Column A | Column B |
| --- | --- |
| This table cell is deliberately long | Another deliberately long cell |
"""
    )

    chunks = chunk_document(document, max_chars=40)

    assert len(chunks) == 1
    assert chunks[0].content.startswith("Table 1. Long values")
    assert "| Column A" in chunks[0].content
    assert chunks[0].char_count > 40
    assert chunks[0].oversized is True


def test_chunk_document_discards_isolated_pdf_page_number() -> None:
    document = _document(
        """# Root

<!-- source-page: 7 -->

55

Evidence from the page.
"""
    )

    chunks = chunk_document(document)

    assert len(chunks) == 1
    assert chunks[0].page_number == 7
    assert chunks[0].content == "Evidence from the page."


def test_chunk_documents_produces_deterministic_real_corpus_chunks() -> None:
    documents = load_source_documents(
        source_root=SOURCE_ROOT,
        repository_root=REPOSITORY_ROOT,
    )

    first_run = chunk_documents(documents)
    second_run = chunk_documents(documents)

    assert first_run
    assert [chunk.chunk_id for chunk in first_run] == [
        chunk.chunk_id for chunk in second_run
    ]
    assert len({chunk.chunk_id for chunk in first_run}) == len(first_run)
    assert {chunk.source_id for chunk in first_run} == {
        document.source_id for document in documents
    }
    assert all(chunk.content for chunk in first_run)
    assert all(
        chunk.char_count <= 2_000 or chunk.oversized
        for chunk in first_run
    )
    assert {
        chunk.page_number
        for chunk in first_run
        if chunk.source_id == "EXT-REPORT-001" and chunk.page_number is not None
    } == set(range(1, 82))
