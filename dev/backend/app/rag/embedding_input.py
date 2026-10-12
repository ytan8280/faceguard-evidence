from __future__ import annotations

from dataclasses import dataclass
import hashlib


DOCUMENT_INPUT_VERSION = "source-heading-content-v1"
QUERY_INPUT_VERSION = "raw-question-v1"


class EmbeddingInputError(ValueError):
    """Raised when deterministic embedding input cannot be constructed."""


@dataclass(frozen=True, slots=True)
class PreparedEmbeddingInput:
    text: str
    sha256: str
    char_count: int
    version: str


def _normalize_text(value: str, name: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise EmbeddingInputError(f"{name} must not be blank.")
    return normalized


def _prepared(text: str, version: str) -> PreparedEmbeddingInput:
    return PreparedEmbeddingInput(
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest().upper(),
        char_count=len(text),
        version=version,
    )


def prepare_document_embedding_input(
    *,
    source_title: str,
    heading_text: str,
    content: str,
) -> PreparedEmbeddingInput:
    title = _normalize_text(source_title, "Source title")
    normalized_content = _normalize_text(content, "Chunk content")
    normalized_heading = (
        heading_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    )

    context_lines = [f"Source: {title}"]
    if normalized_heading:
        context_lines.append(f"Section: {normalized_heading}")
    text = "\n".join(context_lines) + "\n\n" + normalized_content
    return _prepared(text, DOCUMENT_INPUT_VERSION)


def prepare_query_embedding_input(query: str) -> PreparedEmbeddingInput:
    normalized_query = _normalize_text(query, "Query")
    return _prepared(normalized_query, QUERY_INPUT_VERSION)
