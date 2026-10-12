from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import mean, median
from time import perf_counter
from typing import Any

from psycopg import Connection

from .azure_embeddings import (
    AzureEmbeddingConfig,
    request_embedding_with_retry,
)
from .embedding_ingestion import EmbeddingPricing
from .embedding_input import prepare_query_embedding_input
from .hybrid_retrieval import (
    HYBRID_CANDIDATE_LIMIT,
    HYBRID_RETRIEVER_VERSION,
    RRF_CONSTANT,
    HybridRetrievedChunk,
    reciprocal_rank_fuse,
)
from .retrieval import RetrievedChunk, lexical_retrieve, resolve_corpus_revision_id
from .retrieval_evaluation import (
    RankingScore,
    RetrievalEvaluationError,
    RetrievalQuestion,
    RetrievalQuestionSet,
    score_ranked_chunk_ids,
    verify_retrieval_judgments,
)
from .semantic_retrieval import (
    SemanticRetrievedChunk,
    resolve_embedding_model_id,
    semantic_retrieve_exact,
    verify_embedding_coverage,
)


@dataclass(frozen=True, slots=True)
class HybridQuestionEvaluation:
    question: RetrievalQuestion
    lexical_candidates: tuple[RetrievedChunk, ...]
    semantic_candidates: tuple[SemanticRetrievedChunk, ...]
    retrieved: tuple[HybridRetrievedChunk, ...]
    ranking: RankingScore
    query_input_sha256: str
    query_vector_sha256: str
    query_prompt_tokens: int
    query_embedding_latency_ms: float
    query_cost: Decimal
    lexical_latency_ms: float
    semantic_latency_ms: float
    fusion_latency_ms: float


@dataclass(frozen=True, slots=True)
class HybridRetrievalEvaluation:
    question_set: RetrievalQuestionSet
    corpus_revision_id: int
    embedding_model_id: int
    retriever_version: str
    candidate_limit: int
    rrf_constant: int
    k_values: tuple[int, ...]
    questions: tuple[HybridQuestionEvaluation, ...]
    mean_reciprocal_rank: float
    mean_recall_at_k: dict[int, float]
    zero_result_questions: int
    total_query_tokens: int
    total_query_cost: Decimal
    mean_query_embedding_latency_ms: float
    median_query_embedding_latency_ms: float
    mean_lexical_latency_ms: float
    mean_semantic_latency_ms: float
    mean_fusion_latency_ms: float


def evaluate_hybrid_retrieval(
    connection: Connection,
    *,
    config: AzureEmbeddingConfig,
    pricing: EmbeddingPricing,
    question_set: RetrievalQuestionSet,
    candidate_limit: int = HYBRID_CANDIDATE_LIMIT,
    rrf_constant: int = RRF_CONSTANT,
    k_values: tuple[int, ...] = (1, 3, 5),
) -> HybridRetrievalEvaluation:
    if (
        not k_values
        or any(k <= 0 for k in k_values)
        or tuple(sorted(set(k_values))) != k_values
    ):
        raise RetrievalEvaluationError(
            "k_values must be unique positive integers in ascending order."
        )
    if candidate_limit < max(k_values):
        raise RetrievalEvaluationError(
            "Hybrid candidate limit must cover the largest K."
        )

    corpus_revision_id = resolve_corpus_revision_id(
        connection,
        corpus_sha256=question_set.corpus_sha256,
    )
    verify_retrieval_judgments(
        connection,
        corpus_revision_id=corpus_revision_id,
        question_set=question_set,
    )
    embedding_model_id = resolve_embedding_model_id(
        connection,
        config=config,
    )
    verify_embedding_coverage(
        connection,
        corpus_revision_id=corpus_revision_id,
        embedding_model_id=embedding_model_id,
    )

    question_results: list[HybridQuestionEvaluation] = []
    max_k = max(k_values)
    for question in question_set.questions:
        query_input = prepare_query_embedding_input(question.question)
        response = request_embedding_with_retry(config, query_input.text)
        query_cost = pricing.cost_for_tokens(response.prompt_tokens)

        started_at = perf_counter()
        lexical = lexical_retrieve(
            connection,
            corpus_revision_id=corpus_revision_id,
            query=question.question,
            limit=candidate_limit,
        )
        lexical_latency_ms = (perf_counter() - started_at) * 1_000

        started_at = perf_counter()
        semantic = semantic_retrieve_exact(
            connection,
            corpus_revision_id=corpus_revision_id,
            embedding_model_id=embedding_model_id,
            query_vector=response.vector,
            expected_dimensions=config.dimensions,
            limit=candidate_limit,
        )
        semantic_latency_ms = (perf_counter() - started_at) * 1_000

        started_at = perf_counter()
        retrieved = reciprocal_rank_fuse(
            lexical=lexical,
            semantic=semantic,
            limit=max_k,
            rrf_constant=rrf_constant,
        )
        fusion_latency_ms = (perf_counter() - started_at) * 1_000

        ranking = score_ranked_chunk_ids(
            relevant_chunk_ids=question.relevant_chunk_ids,
            ranked_chunk_ids=[chunk.chunk_id for chunk in retrieved],
            k_values=k_values,
        )
        question_results.append(
            HybridQuestionEvaluation(
                question=question,
                lexical_candidates=tuple(lexical),
                semantic_candidates=tuple(semantic),
                retrieved=tuple(retrieved),
                ranking=ranking,
                query_input_sha256=query_input.sha256,
                query_vector_sha256=response.vector_sha256,
                query_prompt_tokens=response.prompt_tokens,
                query_embedding_latency_ms=response.latency_ms,
                query_cost=query_cost,
                lexical_latency_ms=lexical_latency_ms,
                semantic_latency_ms=semantic_latency_ms,
                fusion_latency_ms=fusion_latency_ms,
            )
        )

    embedding_latencies = [
        result.query_embedding_latency_ms for result in question_results
    ]
    return HybridRetrievalEvaluation(
        question_set=question_set,
        corpus_revision_id=corpus_revision_id,
        embedding_model_id=embedding_model_id,
        retriever_version=HYBRID_RETRIEVER_VERSION,
        candidate_limit=candidate_limit,
        rrf_constant=rrf_constant,
        k_values=k_values,
        questions=tuple(question_results),
        mean_reciprocal_rank=mean(
            result.ranking.reciprocal_rank
            for result in question_results
        ),
        mean_recall_at_k={
            k: mean(
                result.ranking.recall_at_k[k]
                for result in question_results
            )
            for k in k_values
        },
        zero_result_questions=sum(
            not result.retrieved for result in question_results
        ),
        total_query_tokens=sum(
            result.query_prompt_tokens for result in question_results
        ),
        total_query_cost=sum(
            (result.query_cost for result in question_results),
            Decimal("0"),
        ),
        mean_query_embedding_latency_ms=mean(embedding_latencies),
        median_query_embedding_latency_ms=median(embedding_latencies),
        mean_lexical_latency_ms=mean(
            result.lexical_latency_ms for result in question_results
        ),
        mean_semantic_latency_ms=mean(
            result.semantic_latency_ms for result in question_results
        ),
        mean_fusion_latency_ms=mean(
            result.fusion_latency_ms for result in question_results
        ),
    )


def _lexical_candidate_to_dict(chunk: RetrievedChunk) -> dict[str, Any]:
    return {
        "rank": chunk.rank,
        "chunk_id": chunk.chunk_id,
        "source_id": chunk.source_id,
        "score": chunk.score,
        "strict_match": chunk.strict_match,
    }


def _semantic_candidate_to_dict(
    chunk: SemanticRetrievedChunk,
) -> dict[str, Any]:
    return {
        "rank": chunk.rank,
        "chunk_id": chunk.chunk_id,
        "source_id": chunk.source_id,
        "score": chunk.score,
        "cosine_distance": chunk.cosine_distance,
    }


def hybrid_evaluation_to_dict(
    evaluation: HybridRetrievalEvaluation,
) -> dict[str, Any]:
    return {
        "question_set_id": evaluation.question_set.question_set_id,
        "question_set_sha256": evaluation.question_set.file_sha256,
        "corpus_sha256": evaluation.question_set.corpus_sha256,
        "corpus_revision_id": evaluation.corpus_revision_id,
        "embedding_model_id": evaluation.embedding_model_id,
        "retriever_version": evaluation.retriever_version,
        "fusion": {
            "method": "reciprocal_rank_fusion",
            "candidate_limit_per_retriever": evaluation.candidate_limit,
            "rrf_constant": evaluation.rrf_constant,
            "lexical_weight": 1.0,
            "semantic_weight": 1.0,
        },
        "k_values": list(evaluation.k_values),
        "metrics": {
            "mean_reciprocal_rank": evaluation.mean_reciprocal_rank,
            "mean_recall_at_k": {
                str(k): value
                for k, value in evaluation.mean_recall_at_k.items()
            },
            "zero_result_questions": evaluation.zero_result_questions,
            "total_query_tokens": evaluation.total_query_tokens,
            "total_query_cost": str(evaluation.total_query_cost),
            "mean_query_embedding_latency_ms": (
                evaluation.mean_query_embedding_latency_ms
            ),
            "median_query_embedding_latency_ms": (
                evaluation.median_query_embedding_latency_ms
            ),
            "mean_lexical_latency_ms": evaluation.mean_lexical_latency_ms,
            "mean_semantic_latency_ms": evaluation.mean_semantic_latency_ms,
            "mean_fusion_latency_ms": evaluation.mean_fusion_latency_ms,
        },
        "questions": [
            {
                "question_id": result.question.question_id,
                "question": result.question.question,
                "relevant_chunk_ids": list(
                    result.question.relevant_chunk_ids
                ),
                "first_relevant_rank": (
                    result.ranking.first_relevant_rank
                ),
                "reciprocal_rank": result.ranking.reciprocal_rank,
                "recall_at_k": {
                    str(k): value
                    for k, value in result.ranking.recall_at_k.items()
                },
                "query_input_sha256": result.query_input_sha256,
                "query_vector_sha256": result.query_vector_sha256,
                "query_prompt_tokens": result.query_prompt_tokens,
                "query_embedding_latency_ms": (
                    result.query_embedding_latency_ms
                ),
                "query_cost": str(result.query_cost),
                "lexical_latency_ms": result.lexical_latency_ms,
                "semantic_latency_ms": result.semantic_latency_ms,
                "fusion_latency_ms": result.fusion_latency_ms,
                "lexical_candidates": [
                    _lexical_candidate_to_dict(chunk)
                    for chunk in result.lexical_candidates
                ],
                "semantic_candidates": [
                    _semantic_candidate_to_dict(chunk)
                    for chunk in result.semantic_candidates
                ],
                "retrieved": [
                    {
                        "rank": chunk.rank,
                        "chunk_id": chunk.chunk_id,
                        "source_id": chunk.source_id,
                        "score": chunk.score,
                        "lexical_rank": chunk.lexical_rank,
                        "semantic_rank": chunk.semantic_rank,
                        "lexical_score": chunk.lexical_score,
                        "semantic_score": chunk.semantic_score,
                        "cosine_distance": chunk.cosine_distance,
                    }
                    for chunk in result.retrieved
                ],
            }
            for result in evaluation.questions
        ],
    }
