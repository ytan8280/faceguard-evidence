from __future__ import annotations

from dev.backend.app.rag.reranker_evaluation import (
    ScoredCandidate,
    _rank_path,
)


def _candidate(chunk_id: str, score: float) -> ScoredCandidate:
    return ScoredCandidate(
        chunk_id=chunk_id,
        source_id="SOURCE",
        reranker_score=score,
        lexical_rank=None,
        semantic_rank=1,
        original_token_count=100,
        truncated=False,
    )


def test_rank_path_orders_by_cross_encoder_score() -> None:
    result = _rank_path(
        path_name="test",
        candidates=[
            _candidate("chunk-b", 1.0),
            _candidate("chunk-a", 2.0),
        ],
        relevant_chunk_ids=("chunk-a",),
        k_values=(1, 3, 5),
    )

    assert result.ranking.first_relevant_rank == 1
    assert result.ranking.recall_at_k[1] == 1.0
    assert result.retrieved[0].chunk_id == "chunk-a"


def test_rank_path_uses_chunk_id_for_score_tie() -> None:
    result = _rank_path(
        path_name="test",
        candidates=[
            _candidate("chunk-b", 1.0),
            _candidate("chunk-a", 1.0),
        ],
        relevant_chunk_ids=("chunk-a",),
        k_values=(1, 3, 5),
    )

    assert result.retrieved[0].chunk_id == "chunk-a"
