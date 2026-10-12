from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from dev.backend.app.rag.source_loader import SourceIntegrityError, load_source_documents


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SOURCE_ROOT = REPOSITORY_ROOT / "data" / "sources"


def test_load_source_documents_returns_verified_corpus() -> None:
    documents = load_source_documents(
        source_root=SOURCE_ROOT,
        repository_root=REPOSITORY_ROOT,
    )

    assert [document.source_id for document in documents] == [
        "EXT-GUIDE-001",
        "EXT-REPORT-001",
        "EXT-STD-001",
        "FG-DOC-001",
        "FG-DOC-002",
        "FG-DOC-003",
    ]
    assert all(document.content for document in documents)
    assert all(document.content_path.is_file() for document in documents)
    assert all(document.metadata_path.is_file() for document in documents)
    assert next(
        document for document in documents if document.source_id == "FG-DOC-001"
    ).content_path == REPOSITORY_ROOT / "docs" / "MODEL_CARD.md"


def test_load_source_documents_rejects_tampered_content(tmp_path: Path) -> None:
    source_dir = tmp_path / "sources" / "EXT-GUIDE-001"
    source_dir.mkdir(parents=True)
    original_dir = SOURCE_ROOT / "EXT-GUIDE-001"
    shutil.copyfile(original_dir / "metadata.json", source_dir / "metadata.json")
    shutil.copyfile(original_dir / "content.md", source_dir / "content.md")
    (source_dir / "content.md").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(SourceIntegrityError, match="EXT-GUIDE-001"):
        load_source_documents(
            source_root=tmp_path / "sources",
            repository_root=REPOSITORY_ROOT,
        )


def test_load_source_documents_rejects_paths_outside_repository(tmp_path: Path) -> None:
    source_dir = tmp_path / "sources" / "FG-DOC-001"
    source_dir.mkdir(parents=True)
    metadata = json.loads(
        (SOURCE_ROOT / "FG-DOC-001" / "metadata.json").read_text(encoding="utf-8")
    )
    metadata["content_path"] = "../outside.md"
    (source_dir / "metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    with pytest.raises(SourceIntegrityError, match="outside the repository"):
        load_source_documents(
            source_root=tmp_path / "sources",
            repository_root=REPOSITORY_ROOT,
        )
