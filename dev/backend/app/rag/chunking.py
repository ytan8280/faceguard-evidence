from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .models import EvidenceChunk, SourceDocument


CHUNKER_VERSION = "markdown-structure-v1"
DEFAULT_MAX_CHARS = 2_000
MIN_FRAGMENT_CHARS = 100

_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_PAGE_MARKER_PATTERN = re.compile(r"^<!-- source-page: (\d+) -->$")
_FENCE_PATTERN = re.compile(r"^\s*(```+|~~~+)")
_LIST_PATTERN = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
_TABLE_SEPARATOR_PATTERN = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
)
_SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?])\s+(?=\S)")


@dataclass(frozen=True, slots=True)
class _DocumentBlock:
    content: str
    heading_path: tuple[str, ...]
    page_number: int | None
    block_type: str


def _block_type(lines: list[str]) -> str:
    if lines and _FENCE_PATTERN.match(lines[0]):
        return "code"
    if len(lines) >= 2 and "|" in lines[0] and _TABLE_SEPARATOR_PATTERN.match(lines[1]):
        return "table"
    if lines and _LIST_PATTERN.match(lines[0]):
        return "list"
    return "prose"


def _parse_blocks(document: SourceDocument) -> list[_DocumentBlock]:
    blocks: list[_DocumentBlock] = []
    heading_path: list[str] = []
    page_number: int | None = None
    current_lines: list[str] = []
    fence_marker: str | None = None

    def flush() -> None:
        nonlocal current_lines
        if not current_lines:
            return
        content = "\n".join(current_lines).strip()
        if page_number is not None and content.isdigit():
            current_lines = []
            return
        if content:
            blocks.append(
                _DocumentBlock(
                    content=content,
                    heading_path=tuple(heading_path),
                    page_number=page_number,
                    block_type=_block_type(current_lines),
                )
            )
        current_lines = []

    for line in document.content.splitlines():
        if fence_marker is not None:
            current_lines.append(line)
            if line.strip().startswith(fence_marker):
                flush()
                fence_marker = None
            continue

        fence_match = _FENCE_PATTERN.match(line)
        if fence_match:
            flush()
            fence_marker = fence_match.group(1)[:3]
            current_lines.append(line)
            continue

        heading_match = _HEADING_PATTERN.match(line)
        if heading_match:
            flush()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            heading_path = heading_path[: level - 1]
            heading_path.append(title)
            continue

        page_match = _PAGE_MARKER_PATTERN.match(line)
        if page_match:
            flush()
            page_number = int(page_match.group(1))
            continue

        if not line.strip():
            flush()
            continue

        current_lines.append(line)

    flush()
    return blocks


def _split_words(text: str, max_chars: int) -> list[str]:
    words = text.split()
    parts: list[str] = []
    current_words: list[str] = []

    for word in words:
        candidate = " ".join([*current_words, word])
        if current_words and len(candidate) > max_chars:
            parts.append(" ".join(current_words))
            current_words = [word]
        else:
            current_words.append(word)

    if current_words:
        parts.append(" ".join(current_words))
    return parts


def _split_oversized_prose(text: str, max_chars: int) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    sentences = _SENTENCE_BOUNDARY_PATTERN.split(normalized)
    parts: list[str] = []
    current_sentences: list[str] = []

    for sentence in sentences:
        if len(sentence) > max_chars:
            if current_sentences:
                parts.append(" ".join(current_sentences))
                current_sentences = []
            parts.extend(_split_words(sentence, max_chars))
            continue

        candidate = " ".join([*current_sentences, sentence])
        if current_sentences and len(candidate) > max_chars:
            parts.append(" ".join(current_sentences))
            current_sentences = [sentence]
        else:
            current_sentences.append(sentence)

    if current_sentences:
        parts.append(" ".join(current_sentences))
    return parts


def _block_parts(block: _DocumentBlock, max_chars: int) -> list[tuple[str, bool]]:
    if len(block.content) <= max_chars:
        return [(block.content, False)]
    if block.block_type == "prose":
        return [(part, False) for part in _split_oversized_prose(block.content, max_chars)]
    return [(block.content, True)]


def _content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest().upper()


def chunk_document(
    document: SourceDocument,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[EvidenceChunk]:
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero.")

    chunks: list[EvidenceChunk] = []
    current_parts: list[str] = []
    current_heading_path: tuple[str, ...] = ()
    current_page_number: int | None = None

    def emit(*, oversized: bool = False) -> None:
        nonlocal current_parts
        if not current_parts:
            return

        content = "\n\n".join(current_parts)
        content_sha256 = _content_sha256(content)
        ordinal = len(chunks) + 1
        chunks.append(
            EvidenceChunk(
                chunk_id=f"{document.source_id}:{ordinal:04d}:{content_sha256[:12]}",
                source_id=document.source_id,
                source_title=document.title,
                source_category=document.source_category,
                source_version=document.version,
                canonical_url=document.canonical_url,
                heading_path=current_heading_path,
                page_number=current_page_number,
                ordinal=ordinal,
                content=content,
                content_sha256=content_sha256,
                char_count=len(content),
                oversized=oversized or len(content) > max_chars,
                chunker_version=CHUNKER_VERSION,
            )
        )
        current_parts = []

    for block in _parse_blocks(document):
        context_changed = (
            current_parts
            and (
                block.heading_path != current_heading_path
                or block.page_number != current_page_number
            )
        )
        if context_changed:
            emit()

        current_heading_path = block.heading_path
        current_page_number = block.page_number

        for part, part_is_oversized in _block_parts(block, max_chars):
            if part_is_oversized:
                current_content = "\n\n".join(current_parts)
                if current_parts and len(current_content) >= MIN_FRAGMENT_CHARS:
                    emit()
                current_parts.append(part)
                emit(oversized=True)
                continue

            candidate = "\n\n".join([*current_parts, part])
            if current_parts and len(candidate) > max_chars:
                emit()
            current_parts.append(part)

    emit()
    return chunks


def chunk_documents(
    documents: list[SourceDocument],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[EvidenceChunk]:
    chunks: list[EvidenceChunk] = []
    for document in sorted(documents, key=lambda item: item.source_id):
        chunks.extend(chunk_document(document, max_chars=max_chars))
    return chunks
