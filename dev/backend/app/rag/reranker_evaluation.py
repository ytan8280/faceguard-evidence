from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from statistics import mean, median
from typing import Any

from psycopg import Connection

from .embedding_input import prepare_document_embedding_input
from .reranker import (
    RERANKER_VERSION,
    LoadedReranker,
    RerankerScore,
    score_passages,
)
from .retrieval_evaluation import (
    RankingScore,
    RetrievalQuestionSet,
    score_ranked_chunk_ids,
)


SEMANTIC_PATH = "semantic_top20"
UNION_PATH = "lexical_semantic_union_top20"


class RerankerEvaluationError(RuntimeError):
    """Raised when frozen candidates cannot be reranked consistently."""


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    chunk_id: str
    source_id: str
    reranker_score: float
    lexical_rank: int | None
    semantic_rank: int | None
    original_token_count: int
    truncated: bool


@dataclass(frozen=True, slots=True)
class RerankedPathResult:
    path_name: str
    candidate_count: int
    candidate_recall: float
    ranking: RankingScore
    retrieved: tuple[ScoredCandidate, ...]


@dataclass(frozen=True, slots=True)
class RerankerQuestionEvaluation:
    question_id: str
    question: str
    relevant_chunk_ids: tuple[str, ...]
    scored_candidates: tuple[ScoredCandidate, ...]
    semantic_path: RerankedPathResult
    union_path: RerankedPathResult
    inference_latency_ms: float


@dataclass(frozen=True, slots=True)
class RerankerPathMetrics:
    mean_reciprocal_rank: float
    mean_recall_at_k: dict[int, float]
    mean_candidate_recall: float
    zero_result_questions: int


@dataclass(frozen=True, slots=True)
class RerankerEvaluation:
    reranker_version: str
    source_artifact_sha256: str
    corpus_sha256: str
    corpus_revision_id: int
    question_set_id: str
    question_set_sha256: str
    model_id: str
    model_revision: str
    model_sha256: str
    max_length: int
    batch_size: int
    model_load_latency_ms: float
    questions: tuple[RerankerQuestionEvaluation, ...]
    semantic_metrics: RerankerPathMetrics
    union_metrics: RerankerPathMetrics
    total_scored_pairs: int
    truncated_pairs: int
    mean_inference_latency_ms: float
    median_inference_latency_ms: float


def _artifact_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def load_frozen_hybrid_candidates(
    path: Path,
    *,
    expected_sha256: str,
) -> dict[str, Any]:
    actual_sha256 = _artifact_sha256(path)
    if actual_sha256 != expected_sha256:
        raise RerankerEvaluationError(
            "Hybrid candidate artifact SHA-256 does not match the frozen "
            "identity."
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RerankerEvaluationError(
            f"Unable to read hybrid candidate artifact: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise RerankerEvaluationError(
            "Hybrid candidate artifact must be a JSON object."
        )
    fusion = raw.get("fusion")
    if not isinstance(fusion, dict) or fusion.get(
        "candidate_limit_per_retriever"
    ) != 20:
        raise RerankerEvaluationError(
            "Hybrid artifact does not contain the frozen top-20 candidates."
        )
    return raw


def _load_candidate_documents(
    connection: Connection,
    *,
    corpus_revision_id: int,
    chunk_ids: set[str],
) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            chunks.chunk_id,
            documents.source_id,
            chunks.source_title,
            chunks.heading_text,
            chunks.content
        FROM rag.evidence_chunks AS chunks
        JOIN rag.source_documents AS documents
          ON documents.source_document_id = chunks.source_document_id
        WHERE chunks.corpus_revision_id = %s
          AND chunks.chunk_id = ANY(%s)
        """,
        (corpus_revision_id, sorted(chunk_ids)),
    ).fetchall()
    documents = {str(row["chunk_id"]): dict(row) for row in rows}
    missing = sorted(chunk_ids.difference(documents))
    if missing:
        raise RerankerEvaluationError(
            "Candidate chunks are missing from the pinned corpus: "
            + ", ".join(missing)
        )
    return documents


def _rank_path(
    *,
    path_name: str,
    candidates: list[ScoredCandidate],
    relevant_chunk_ids: tuple[str, ...],
    k_values: tuple[int, ...],
) -> RerankedPathResult:
    ordered = sorted(
        candidates,
        key=lambda candidate: (
            -candidate.reranker_score,
            candidate.chunk_id,
        ),
    )
    top_k = ordered[: max(k_values)]
    relevant = set(relevant_chunk_ids)
    candidate_recall = (
        len(relevant.intersection(candidate.chunk_id for candidate in ordered))
        / len(relevant)
    )
    return RerankedPathResult(
        path_name=path_name,
        candidate_count=len(ordered),
        candidate_recall=candidate_recall,
        ranking=score_ranked_chunk_ids(
            relevant_chunk_ids=relevant_chunk_ids,
            ranked_chunk_ids=[candidate.chunk_id for candidate in top_k],
            k_values=k_values,
        ),
        retrieved=tuple(top_k),
    )


def _path_metrics(
    results: tuple[RerankerQuestionEvaluation, ...],
    *,
    path_name: str,
    k_values: tuple[int, ...],
) -> RerankerPathMetrics:
    paths = [
        (
            result.semantic_path
            if path_name == SEMANTIC_PATH
            else result.union_path
        )
        for result in results
    ]
    return RerankerPathMetrics(
        mean_reciprocal_rank=mean(
            path.ranking.reciprocal_rank for path in paths
        ),
        mean_recall_at_k={
            k: mean(path.ranking.recall_at_k[k] for path in paths)
            for k in k_values
        },
        mean_candidate_recall=mean(path.candidate_recall for path in paths),
        zero_result_questions=sum(not path.retrieved for path in paths),
    )


def evaluate_reranker(
    connection: Connection,
    *,
    reranker: LoadedReranker,
    question_set: RetrievalQuestionSet,
    hybrid_artifact: dict[str, Any],
    source_artifact_sha256: str,
    k_values: tuple[int, ...] = (1, 3, 5),
) -> RerankerEvaluation:
    if hybrid_artifact.get("question_set_sha256") != question_set.file_sha256:
        raise RerankerEvaluationError(
            "Hybrid artifact question set does not match."
        )
    if hybrid_artifact.get("corpus_sha256") != question_set.corpus_sha256:
        raise RerankerEvaluationError(
            "Hybrid artifact corpus does not match."
        )

    raw_questions = hybrid_artifact.get("questions")
    if not isinstance(raw_questions, list):
        raise RerankerEvaluationError(
            "Hybrid artifact questions must be an array."
        )
    artifact_by_id = {
        str(question["question_id"]): question for question in raw_questions
    }
    if set(artifact_by_id) != {
        question.question_id for question in question_set.questions
    }:
        raise RerankerEvaluationError(
            "Hybrid artifact question identities do not match."
        )

    all_chunk_ids: set[str] = set()
    for raw_question in raw_questions:
        for key in ("lexical_candidates", "semantic_candidates"):
            candidates = raw_question.get(key)
            if not isinstance(candidates, list) or len(candidates) != 20:
                raise RerankerEvaluationError(
                    f"{raw_question.get('question_id')}: {key} must contain "
                    "20 candidates."
                )
            all_chunk_ids.update(
                str(candidate["chunk_id"]) for candidate in candidates
            )

    corpus_revision_id = int(hybrid_artifact["corpus_revision_id"])
    documents = _load_candidate_documents(
        connection,
        corpus_revision_id=corpus_revision_id,
        chunk_ids=all_chunk_ids,
    )

    question_results: list[RerankerQuestionEvaluation] = []
    for question in question_set.questions:
        raw_question = artifact_by_id[question.question_id]
        lexical_candidates = raw_question["lexical_candidates"]
        semantic_candidates = raw_question["semantic_candidates"]
        lexical_by_id = {
            str(candidate["chunk_id"]): int(candidate["rank"])
            for candidate in lexical_candidates
        }
        semantic_by_id = {
            str(candidate["chunk_id"]): int(candidate["rank"])
            for candidate in semantic_candidates
        }
        union_ids = list(lexical_by_id)
        union_ids.extend(
            chunk_id for chunk_id in semantic_by_id if chunk_id not in lexical_by_id
        )

        passages = [
            prepare_document_embedding_input(
                source_title=str(documents[chunk_id]["source_title"]),
                heading_text=str(documents[chunk_id]["heading_text"]),
                content=str(documents[chunk_id]["content"]),
            ).text
            for chunk_id in union_ids
        ]
        scores, inference_latency_ms = score_passages(
            reranker,
            query=question.question,
            passages=passages,
        )
        score_by_id: dict[str, RerankerScore] = dict(
            zip(union_ids, scores, strict=True)
        )
        scored_candidates = [
            ScoredCandidate(
                chunk_id=chunk_id,
                source_id=str(documents[chunk_id]["source_id"]),
                reranker_score=score_by_id[chunk_id].score,
                lexical_rank=lexical_by_id.get(chunk_id),
                semantic_rank=semantic_by_id.get(chunk_id),
                original_token_count=(
                    score_by_id[chunk_id].original_token_count
                ),
                truncated=score_by_id[chunk_id].truncated,
            )
            for chunk_id in union_ids
        ]
        semantic_scored = [
            candidate
            for candidate in scored_candidates
            if candidate.semantic_rank is not None
        ]
        question_results.append(
            RerankerQuestionEvaluation(
                question_id=question.question_id,
                question=question.question,
                relevant_chunk_ids=question.relevant_chunk_ids,
                scored_candidates=tuple(scored_candidates),
                semantic_path=_rank_path(
                    path_name=SEMANTIC_PATH,
                    candidates=semantic_scored,
                    relevant_chunk_ids=question.relevant_chunk_ids,
                    k_values=k_values,
                ),
                union_path=_rank_path(
                    path_name=UNION_PATH,
                    candidates=scored_candidates,
                    relevant_chunk_ids=question.relevant_chunk_ids,
                    k_values=k_values,
                ),
                inference_latency_ms=inference_latency_ms,
            )
        )

    results = tuple(question_results)
    latencies = [result.inference_latency_ms for result in results]
    return RerankerEvaluation(
        reranker_version=RERANKER_VERSION,
        source_artifact_sha256=source_artifact_sha256,
        corpus_sha256=question_set.corpus_sha256,
        corpus_revision_id=corpus_revision_id,
        question_set_id=question_set.question_set_id,
        question_set_sha256=question_set.file_sha256,
        model_id=reranker.config.model_id,
        model_revision=reranker.config.model_revision,
        model_sha256=reranker.model_sha256,
        max_length=reranker.config.max_length,
        batch_size=reranker.config.batch_size,
        model_load_latency_ms=reranker.load_latency_ms,
        questions=results,
        semantic_metrics=_path_metrics(
            results,
            path_name=SEMANTIC_PATH,
            k_values=k_values,
        ),
        union_metrics=_path_metrics(
            results,
            path_name=UNION_PATH,
            k_values=k_values,
        ),
        total_scored_pairs=sum(
            len(result.scored_candidates) for result in results
        ),
        truncated_pairs=sum(
            candidate.truncated
            for result in results
            for candidate in result.scored_candidates
        ),
        mean_inference_latency_ms=mean(latencies),
        median_inference_latency_ms=median(latencies),
    )


def _path_to_dict(path: RerankedPathResult) -> dict[str, Any]:
    return {
        "candidate_count": path.candidate_count,
        "candidate_recall": path.candidate_recall,
        "first_relevant_rank": path.ranking.first_relevant_rank,
        "reciprocal_rank": path.ranking.reciprocal_rank,
        "recall_at_k": {
            str(k): value for k, value in path.ranking.recall_at_k.items()
        },
        "retrieved": [
            {
                "rank": rank,
                "chunk_id": candidate.chunk_id,
                "source_id": candidate.source_id,
                "reranker_score": candidate.reranker_score,
                "lexical_rank": candidate.lexical_rank,
                "semantic_rank": candidate.semantic_rank,
                "original_token_count": candidate.original_token_count,
                "truncated": candidate.truncated,
            }
            for rank, candidate in enumerate(path.retrieved, start=1)
        ],
    }


def _metrics_to_dict(metrics: RerankerPathMetrics) -> dict[str, Any]:
    return {
        "mean_reciprocal_rank": metrics.mean_reciprocal_rank,
        "mean_recall_at_k": {
            str(k): value for k, value in metrics.mean_recall_at_k.items()
        },
        "mean_candidate_recall": metrics.mean_candidate_recall,
        "zero_result_questions": metrics.zero_result_questions,
    }


def reranker_evaluation_to_dict(
    evaluation: RerankerEvaluation,
) -> dict[str, Any]:
    return {
        "reranker_version": evaluation.reranker_version,
        "source_artifact_sha256": evaluation.source_artifact_sha256,
        "corpus_sha256": evaluation.corpus_sha256,
        "corpus_revision_id": evaluation.corpus_revision_id,
        "question_set_id": evaluation.question_set_id,
        "question_set_sha256": evaluation.question_set_sha256,
        "model": {
            "model_id": evaluation.model_id,
            "model_revision": evaluation.model_revision,
            "model_sha256": evaluation.model_sha256,
            "max_length": evaluation.max_length,
            "batch_size": evaluation.batch_size,
        },
        "metrics": {
            SEMANTIC_PATH: _metrics_to_dict(evaluation.semantic_metrics),
            UNION_PATH: _metrics_to_dict(evaluation.union_metrics),
            "model_load_latency_ms": evaluation.model_load_latency_ms,
            "total_scored_pairs": evaluation.total_scored_pairs,
            "truncated_pairs": evaluation.truncated_pairs,
            "mean_inference_latency_ms": (
                evaluation.mean_inference_latency_ms
            ),
            "median_inference_latency_ms": (
                evaluation.median_inference_latency_ms
            ),
        },
        "questions": [
            {
                "question_id": result.question_id,
                "question": result.question,
                "relevant_chunk_ids": list(result.relevant_chunk_ids),
                "inference_latency_ms": result.inference_latency_ms,
                "scored_candidates": [
                    {
                        "chunk_id": candidate.chunk_id,
                        "source_id": candidate.source_id,
                        "reranker_score": candidate.reranker_score,
                        "lexical_rank": candidate.lexical_rank,
                        "semantic_rank": candidate.semantic_rank,
                        "original_token_count": (
                            candidate.original_token_count
                        ),
                        "truncated": candidate.truncated,
                    }
                    for candidate in result.scored_candidates
                ],
                SEMANTIC_PATH: _path_to_dict(result.semantic_path),
                UNION_PATH: _path_to_dict(result.union_path),
            }
            for result in evaluation.questions
        ],
    }
