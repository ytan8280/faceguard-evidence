from __future__ import annotations

import hashlib
import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from .models import SourceDocument


class SourceIntegrityError(ValueError):
    """Raised when corpus metadata and source content do not agree."""


def _load_metadata(metadata_path: Path) -> dict[str, Any]:
    source_id = metadata_path.parent.name
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, JSONDecodeError) as exc:
        raise SourceIntegrityError(
            f"{source_id}: unable to read valid UTF-8 JSON metadata."
        ) from exc

    if not isinstance(metadata, dict):
        raise SourceIntegrityError(f"{source_id}: metadata must be a JSON object.")
    return metadata


def _resolve_content_path(
    *,
    metadata: dict[str, Any],
    metadata_path: Path,
    repository_root: Path,
) -> Path:
    content_path_value = metadata.get("content_path")
    if content_path_value is None:
        return metadata_path.with_name("content.md").resolve()
    if not isinstance(content_path_value, str) or not content_path_value.strip():
        raise SourceIntegrityError(
            f"{metadata_path.parent.name}: content_path must be a non-empty string."
        )

    content_path = (repository_root / content_path_value).resolve()
    try:
        content_path.relative_to(repository_root)
    except ValueError as exc:
        raise SourceIntegrityError(
            f"{metadata_path.parent.name}: content_path resolves outside the repository."
        ) from exc
    return content_path


def _verified_content(
    *,
    source_id: str,
    content_path: Path,
    metadata: dict[str, Any],
) -> tuple[str, str]:
    try:
        normalized = metadata["normalized"]
        expected_bytes = normalized["bytes"]
        expected_lines = normalized["lines"]
        expected_sha256 = normalized["sha256"]
    except (KeyError, TypeError) as exc:
        raise SourceIntegrityError(
            f"{source_id}: normalized content metadata is incomplete."
        ) from exc

    try:
        content_bytes = content_path.read_bytes()
    except OSError as exc:
        raise SourceIntegrityError(
            f"{source_id}: unable to read content from {content_path}."
        ) from exc

    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SourceIntegrityError(f"{source_id}: content is not valid UTF-8.") from exc

    actual_sha256 = hashlib.sha256(content_bytes).hexdigest().upper()
    actual_lines = len(content.splitlines())
    mismatches: list[str] = []

    if len(content_bytes) != expected_bytes:
        mismatches.append(f"bytes expected {expected_bytes}, received {len(content_bytes)}")
    if actual_lines != expected_lines:
        mismatches.append(f"lines expected {expected_lines}, received {actual_lines}")
    if actual_sha256 != expected_sha256:
        mismatches.append(f"SHA-256 expected {expected_sha256}, received {actual_sha256}")

    if mismatches:
        raise SourceIntegrityError(f"{source_id}: " + "; ".join(mismatches))

    return content, actual_sha256


def _build_source_document(
    *,
    metadata: dict[str, Any],
    metadata_path: Path,
    content_path: Path,
    content: str,
    content_sha256: str,
) -> SourceDocument:
    source_id = metadata_path.parent.name
    try:
        license_metadata = metadata["license"]
        return SourceDocument(
            source_id=metadata["source_id"],
            title=metadata["title"],
            source_category=metadata["source_category"],
            publisher=metadata["publisher"],
            authors=tuple(metadata["authors"]),
            version=metadata["version"],
            published_at=metadata["published_at"],
            canonical_url=metadata["canonical_url"],
            license_name=license_metadata["name"],
            license_url=license_metadata["url"],
            content=content,
            content_sha256=content_sha256,
            content_path=content_path,
            metadata_path=metadata_path,
        )
    except (KeyError, TypeError) as exc:
        raise SourceIntegrityError(
            f"{source_id}: required source metadata is incomplete."
        ) from exc


def load_source_documents(
    *,
    source_root: Path,
    repository_root: Path,
) -> list[SourceDocument]:
    """Load and verify every registered corpus source."""

    resolved_source_root = source_root.resolve()
    resolved_repository_root = repository_root.resolve()
    documents: list[SourceDocument] = []
    seen_source_ids: set[str] = set()

    for metadata_path in sorted(resolved_source_root.glob("*/metadata.json")):
        metadata = _load_metadata(metadata_path)
        source_id = metadata.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise SourceIntegrityError(
                f"{metadata_path.parent.name}: source_id must be a non-empty string."
            )
        if source_id != metadata_path.parent.name:
            raise SourceIntegrityError(
                f"{source_id}: source_id does not match its source directory."
            )
        if source_id in seen_source_ids:
            raise SourceIntegrityError(f"{source_id}: duplicate source_id.")

        content_path = _resolve_content_path(
            metadata=metadata,
            metadata_path=metadata_path,
            repository_root=resolved_repository_root,
        )
        content, content_sha256 = _verified_content(
            source_id=source_id,
            content_path=content_path,
            metadata=metadata,
        )
        documents.append(
            _build_source_document(
                metadata=metadata,
                metadata_path=metadata_path,
                content_path=content_path,
                content=content,
                content_sha256=content_sha256,
            )
        )
        seen_source_ids.add(source_id)

    return sorted(documents, key=lambda document: document.source_id)
