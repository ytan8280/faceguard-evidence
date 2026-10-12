from __future__ import annotations

from dev.backend.app.rag.evidence_report import (
    _candidate_union,
)
from dev.backend.app.rag.retrieval import RetrievedChunk
from dev.backend.app.rag.semantic_retrieval import SemanticRetrievedChunk


def _lexical(chunk_id: str, rank: int) -> RetrievedChunk:
    return RetrievedChunk(
        rank=rank,
        chunk_id=chunk_id,
        source_id="SOURCE",
        source_title="Source",
        heading_path=("Heading",),
        page_number=None,
        content=chunk_id,
        score=1.0,
        strict_match=False,
    )


def _semantic(chunk_id: str, rank: int) -> SemanticRetrievedChunk:
    return SemanticRetrievedChunk(
        rank=rank,
        chunk_id=chunk_id,
        source_id="SOURCE",
        source_title="Source",
        heading_path=("Heading",),
        page_number=None,
        content=chunk_id,
        score=0.9,
        cosine_distance=0.1,
    )


def test_candidate_union_preserves_both_rank_signals() -> None:
    candidates = _candidate_union(
        [_lexical("chunk-a", 1), _lexical("chunk-b", 2)],
        [_semantic("chunk-b", 1), _semantic("chunk-c", 2)],
    )

    assert [candidate.chunk_id for candidate in candidates] == [
        "chunk-a",
        "chunk-b",
        "chunk-c",
    ]
    assert candidates[0].lexical_rank == 1
    assert candidates[0].semantic_rank is None
    assert candidates[1].lexical_rank == 2
    assert candidates[1].semantic_rank == 1
    assert candidates[2].lexical_rank is None
    assert candidates[2].semantic_rank == 2
