from __future__ import annotations

from dev.backend.app.rag.hybrid_retrieval import reciprocal_rank_fuse
from dev.backend.app.rag.retrieval import RetrievedChunk
from dev.backend.app.rag.semantic_retrieval import SemanticRetrievedChunk


def _lexical(
    *,
    rank: int,
    chunk_id: str,
    score: float,
) -> RetrievedChunk:
    return RetrievedChunk(
        rank=rank,
        chunk_id=chunk_id,
        source_id="SOURCE",
        source_title="Source",
        heading_path=("Heading",),
        page_number=None,
        content=chunk_id,
        score=score,
        strict_match=False,
    )


def _semantic(
    *,
    rank: int,
    chunk_id: str,
    score: float,
) -> SemanticRetrievedChunk:
    return SemanticRetrievedChunk(
        rank=rank,
        chunk_id=chunk_id,
        source_id="SOURCE",
        source_title="Source",
        heading_path=("Heading",),
        page_number=None,
        content=chunk_id,
        score=score,
        cosine_distance=1.0 - score,
    )


def test_reciprocal_rank_fusion_rewards_shared_candidates() -> None:
    results = reciprocal_rank_fuse(
        lexical=[
            _lexical(rank=1, chunk_id="chunk-a", score=10.0),
            _lexical(rank=2, chunk_id="chunk-b", score=9.0),
        ],
        semantic=[
            _semantic(rank=1, chunk_id="chunk-b", score=0.9),
            _semantic(rank=2, chunk_id="chunk-c", score=0.8),
        ],
        limit=3,
        rrf_constant=60,
    )

    assert [result.chunk_id for result in results] == [
        "chunk-b",
        "chunk-a",
        "chunk-c",
    ]
    assert results[0].lexical_rank == 2
    assert results[0].semantic_rank == 1
    assert results[1].semantic_rank is None


def test_reciprocal_rank_fusion_uses_chunk_id_for_complete_tie() -> None:
    results = reciprocal_rank_fuse(
        lexical=[_lexical(rank=1, chunk_id="chunk-b", score=1.0)],
        semantic=[_semantic(rank=1, chunk_id="chunk-a", score=1.0)],
        limit=2,
        rrf_constant=60,
    )

    assert [result.chunk_id for result in results] == [
        "chunk-a",
        "chunk-b",
    ]
