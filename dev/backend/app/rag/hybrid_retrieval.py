from __future__ import annotations

from dataclasses import dataclass

from .retrieval import RetrievedChunk
from .semantic_retrieval import SemanticRetrievedChunk


HYBRID_RETRIEVER_VERSION = "rrf-lexical-semantic-v1"
HYBRID_CANDIDATE_LIMIT = 20
RRF_CONSTANT = 60


class HybridRetrievalError(ValueError):
    """Raised when hybrid candidate rankings cannot be fused."""


@dataclass(frozen=True, slots=True)
class HybridRetrievedChunk:
    rank: int
    chunk_id: str
    source_id: str
    source_title: str
    heading_path: tuple[str, ...]
    page_number: int | None
    content: str
    score: float
    lexical_rank: int | None
    semantic_rank: int | None
    lexical_score: float | None
    semantic_score: float | None
    cosine_distance: float | None


def reciprocal_rank_fuse(
    *,
    lexical: list[RetrievedChunk],
    semantic: list[SemanticRetrievedChunk],
    limit: int,
    rrf_constant: int = RRF_CONSTANT,
) -> list[HybridRetrievedChunk]:
    if limit <= 0:
        raise HybridRetrievalError("Hybrid retrieval limit must be positive.")
    if rrf_constant <= 0:
        raise HybridRetrievalError("RRF constant must be positive.")

    candidates: dict[str, dict[str, object]] = {}
    for chunk in lexical:
        candidates[chunk.chunk_id] = {
            "chunk": chunk,
            "lexical_rank": chunk.rank,
            "semantic_rank": None,
            "lexical_score": chunk.score,
            "semantic_score": None,
            "cosine_distance": None,
            "score": 1.0 / (rrf_constant + chunk.rank),
        }

    for chunk in semantic:
        candidate = candidates.setdefault(
            chunk.chunk_id,
            {
                "chunk": chunk,
                "lexical_rank": None,
                "semantic_rank": None,
                "lexical_score": None,
                "semantic_score": None,
                "cosine_distance": None,
                "score": 0.0,
            },
        )
        candidate["semantic_rank"] = chunk.rank
        candidate["semantic_score"] = chunk.score
        candidate["cosine_distance"] = chunk.cosine_distance
        candidate["score"] = float(candidate["score"]) + (
            1.0 / (rrf_constant + chunk.rank)
        )

    def best_rank(candidate: dict[str, object]) -> int:
        ranks = [
            rank
            for rank in (
                candidate["lexical_rank"],
                candidate["semantic_rank"],
            )
            if isinstance(rank, int)
        ]
        return min(ranks)

    ordered = sorted(
        candidates.values(),
        key=lambda candidate: (
            -float(candidate["score"]),
            best_rank(candidate),
            str(candidate["chunk"].chunk_id),
        ),
    )

    results: list[HybridRetrievedChunk] = []
    for rank, candidate in enumerate(ordered[:limit], start=1):
        chunk = candidate["chunk"]
        results.append(
            HybridRetrievedChunk(
                rank=rank,
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                source_title=chunk.source_title,
                heading_path=chunk.heading_path,
                page_number=chunk.page_number,
                content=chunk.content,
                score=float(candidate["score"]),
                lexical_rank=(
                    int(candidate["lexical_rank"])
                    if candidate["lexical_rank"] is not None
                    else None
                ),
                semantic_rank=(
                    int(candidate["semantic_rank"])
                    if candidate["semantic_rank"] is not None
                    else None
                ),
                lexical_score=(
                    float(candidate["lexical_score"])
                    if candidate["lexical_score"] is not None
                    else None
                ),
                semantic_score=(
                    float(candidate["semantic_score"])
                    if candidate["semantic_score"] is not None
                    else None
                ),
                cosine_distance=(
                    float(candidate["cosine_distance"])
                    if candidate["cosine_distance"] is not None
                    else None
                ),
            )
        )
    return results
