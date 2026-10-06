from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SourceDocument:
    source_id: str
    title: str
    source_category: str
    publisher: str
    authors: tuple[str, ...]
    version: str
    published_at: str
    canonical_url: str
    license_name: str
    license_url: str
    content: str
    content_sha256: str
    content_path: Path
    metadata_path: Path


@dataclass(frozen=True, slots=True)
class EvidenceChunk:
    chunk_id: str
    source_id: str
    source_title: str
    source_category: str
    source_version: str
    canonical_url: str
    heading_path: tuple[str, ...]
    page_number: int | None
    ordinal: int
    content: str
    content_sha256: str
    char_count: int
    oversized: bool
    chunker_version: str
