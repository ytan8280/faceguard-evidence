from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from dev.backend.app.rag.chunking import CHUNKER_VERSION, chunk_document
from dev.backend.app.rag.ingestion import (
    CorpusIngestionError,
    prepare_corpus,
)
from dev.backend.app.rag.models import SourceDocument


def _document(
    *,
    tmp_path: Path,
    source_id: str = "TEST-001",
    content: str = "# Evidence\n\nMeasured evidence.",
) -> SourceDocument:
    content_path = tmp_path / f"{source_id}.md"
    content_path.write_text(content, encoding="utf-8", newline="\n")
    content_bytes = content.encode("utf-8")

    content_sha256 = hashlib.sha256(content_bytes).hexdigest().upper()
    metadata_path = tmp_path / f"{source_id}.json"
    metadata_path.write_text(
        json.dumps(
            {
                "source_id": source_id,
                "normalized": {
                    "bytes": len(content_bytes),
                    "lines": len(content.splitlines()),
                    "sha256": content_sha256,
                },
            }
        ),
        encoding="utf-8",
        newline="\n",
    )
    return SourceDocument(
        source_id=source_id,
        title=f"Title {source_id}",
        source_category="test_evidence",
        publisher="FaceGuard Evidence",
        authors=("Tan Yan Yi",),
        version=f"sha256:{content_sha256}",
        published_at="2026-10-11",
        canonical_url=f"repo:///{content_path.name}",
        license_name="Test",
        license_url="repo:///ATTRIBUTION.md",
        content=content,
        content_sha256=content_sha256,
        content_path=content_path,
        metadata_path=metadata_path,
    )


def test_prepare_corpus_is_deterministic_across_input_order(
    tmp_path: Path,
) -> None:
    first_document = _document(tmp_path=tmp_path, source_id="TEST-001")
    second_document = _document(
        tmp_path=tmp_path,
        source_id="TEST-002",
        content="# Evidence\n\nSecond measured source.",
    )
    first_chunks = chunk_document(first_document)
    second_chunks = chunk_document(second_document)

    first = prepare_corpus(
        documents=[second_document, first_document],
        chunks=[*second_chunks, *first_chunks],
        repository_root=tmp_path,
    )
    second = prepare_corpus(
        documents=[first_document, second_document],
        chunks=[*first_chunks, *second_chunks],
        repository_root=tmp_path,
    )

    assert first.corpus_sha256 == second.corpus_sha256
    assert first.manifest_json == second.manifest_json
    assert [source.document.source_id for source in first.sources] == [
        "TEST-001",
        "TEST-002",
    ]


def test_prepare_corpus_hash_changes_with_chunk_content(
    tmp_path: Path,
) -> None:
    document = _document(tmp_path=tmp_path)
    chunks = chunk_document(document)
    original = prepare_corpus(
        documents=[document],
        chunks=chunks,
        repository_root=tmp_path,
    )
    changed_content = "Different measured evidence."
    changed_sha256 = hashlib.sha256(
        changed_content.encode("utf-8")
    ).hexdigest().upper()
    changed_chunk = replace(
        chunks[0],
        chunk_id=f"{document.source_id}:0001:{changed_sha256[:12]}",
        content=changed_content,
        content_sha256=changed_sha256,
        char_count=len(changed_content),
    )
    changed = prepare_corpus(
        documents=[document],
        chunks=[changed_chunk],
        repository_root=tmp_path,
    )

    assert changed.corpus_sha256 != original.corpus_sha256


def test_prepare_corpus_rejects_unknown_chunk_source(
    tmp_path: Path,
) -> None:
    document = _document(tmp_path=tmp_path)
    chunk = replace(
        chunk_document(document)[0],
        source_id="UNKNOWN",
    )

    with pytest.raises(CorpusIngestionError, match="unknown source"):
        prepare_corpus(
            documents=[document],
            chunks=[chunk],
            repository_root=tmp_path,
        )


def test_prepare_corpus_rejects_wrong_chunker_version(
    tmp_path: Path,
) -> None:
    document = _document(tmp_path=tmp_path)
    chunk = replace(
        chunk_document(document)[0],
        chunker_version="different-version",
    )

    with pytest.raises(CorpusIngestionError, match="chunker version"):
        prepare_corpus(
            documents=[document],
            chunks=[chunk],
            repository_root=tmp_path,
            chunker_version=CHUNKER_VERSION,
        )
