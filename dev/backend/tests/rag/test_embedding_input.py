from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from dev.backend.app.rag.embedding_ingestion import EmbeddingPricing
from dev.backend.app.rag.embedding_input import (
    DOCUMENT_INPUT_VERSION,
    QUERY_INPUT_VERSION,
    EmbeddingInputError,
    prepare_document_embedding_input,
    prepare_query_embedding_input,
)


def test_document_input_includes_source_heading_and_content() -> None:
    prepared = prepare_document_embedding_input(
        source_title="FaceGuard Model Card",
        heading_text="Input > Decision Threshold",
        content="The inherited threshold is 0.25.",
    )

    assert prepared.text == (
        "Source: FaceGuard Model Card\n"
        "Section: Input > Decision Threshold\n\n"
        "The inherited threshold is 0.25."
    )
    assert prepared.version == DOCUMENT_INPUT_VERSION
    assert prepared.char_count == len(prepared.text)
    assert len(prepared.sha256) == 64


def test_document_input_omits_blank_heading() -> None:
    prepared = prepare_document_embedding_input(
        source_title="FaceGuard Model Card",
        heading_text="",
        content="Document-level content.",
    )

    assert prepared.text == (
        "Source: FaceGuard Model Card\n\nDocument-level content."
    )


def test_query_input_is_trimmed_without_added_instruction() -> None:
    prepared = prepare_query_embedding_input(
        "  What threshold does FaceGuard use?  "
    )

    assert prepared.text == "What threshold does FaceGuard use?"
    assert prepared.version == QUERY_INPUT_VERSION


def test_embedding_input_rejects_blank_content() -> None:
    with pytest.raises(EmbeddingInputError, match="Chunk content"):
        prepare_document_embedding_input(
            source_title="FaceGuard Model Card",
            heading_text="Input",
            content=" ",
        )


def test_embedding_pricing_calculates_exact_decimal_cost() -> None:
    pricing = EmbeddingPricing(
        price_per_million_tokens=Decimal("0.025"),
        currency="USD",
        checked_at=date(2026, 10, 11),
    )

    assert pricing.cost_for_tokens(698) == Decimal("0.00001745")
