from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from typing import Any

from psycopg import Connection

from .retrieval import (
    LEXICAL_RETRIEVER_VERSION,
    RetrievedChunk,
    lexical_retrieve,
    resolve_corpus_revision_id,
)


class RetrievalEvaluationError(RuntimeError):
    """Raised when retrieval questions or judgments are invalid."""


@dataclass(frozen=True, slots=True)
class RetrievalQuestion:
    question_id: str
    question: str
    relevant_chunk_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    rationale: str
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievalQuestionSet:
    question_set_id: str
    title: str
    corpus_sha256: str
    judgment_method: str
    questions: tuple[RetrievalQuestion, ...]
    file_sha256: str


@dataclass(frozen=True, slots=True)
class RankingScore:
    first_relevant_rank: int | None
    reciprocal_rank: float
    recall_at_k: dict[int, float]


@dataclass(frozen=True, slots=True)
class QuestionEvaluation:
    question: RetrievalQuestion
    retrieved: tuple[RetrievedChunk, ...]
    ranking: RankingScore
    latency_ms: float


@dataclass(frozen=True, slots=True)
class RetrievalEvaluation:
    question_set: RetrievalQuestionSet
    corpus_revision_id: int
    retriever_version: str
    k_values: tuple[int, ...]
    questions: tuple[QuestionEvaluation, ...]
    mean_reciprocal_rank: float
    mean_recall_at_k: dict[int, float]
    zero_result_questions: int
    mean_latency_ms: float
    median_latency_ms: float


def _required_string(
    value: dict[str, Any],
    key: str,
    *,
    context: str,
) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise RetrievalEvaluationError(
            f"{context}: {key} must be a non-empty string."
        )
    return item


def _required_string_list(
    value: dict[str, Any],
    key: str,
    *,
    context: str,
) -> tuple[str, ...]:
    items = value.get(key)
    if (
        not isinstance(items, list)
        or not items
        or any(not isinstance(item, str) or not item.strip() for item in items)
    ):
        raise RetrievalEvaluationError(
            f"{context}: {key} must be a non-empty string array."
        )
    if len(set(items)) != len(items):
        raise RetrievalEvaluationError(
            f"{context}: {key} contains duplicates."
        )
    return tuple(items)


def load_retrieval_question_set(path: Path) -> RetrievalQuestionSet:
    try:
        data = path.read_bytes()
        raw = json.loads(data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, JSONDecodeError) as exc:
        raise RetrievalEvaluationError(
            f"Unable to read retrieval question set: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise RetrievalEvaluationError(
            "Retrieval question set must be a JSON object."
        )
    if raw.get("schema_version") != 1:
        raise RetrievalEvaluationError(
            "Unsupported retrieval question-set schema version."
        )

    raw_questions = raw.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise RetrievalEvaluationError(
            "Retrieval question set must contain questions."
        )

    questions: list[RetrievalQuestion] = []
    seen_question_ids: set[str] = set()
    for index, raw_question in enumerate(raw_questions, start=1):
        context = f"question {index}"
        if not isinstance(raw_question, dict):
            raise RetrievalEvaluationError(
                f"{context}: question must be a JSON object."
            )
        question_id = _required_string(
            raw_question,
            "question_id",
            context=context,
        )
        if question_id in seen_question_ids:
            raise RetrievalEvaluationError(
                f"{context}: duplicate question_id {question_id}."
            )
        questions.append(
            RetrievalQuestion(
                question_id=question_id,
                question=_required_string(
                    raw_question,
                    "question",
                    context=context,
                ),
                relevant_chunk_ids=_required_string_list(
                    raw_question,
                    "relevant_chunk_ids",
                    context=context,
                ),
                source_ids=_required_string_list(
                    raw_question,
                    "source_ids",
                    context=context,
                ),
                rationale=_required_string(
                    raw_question,
                    "rationale",
                    context=context,
                ),
                tags=_required_string_list(
                    raw_question,
                    "tags",
                    context=context,
                ),
            )
        )
        seen_question_ids.add(question_id)

    return RetrievalQuestionSet(
        question_set_id=_required_string(
            raw,
            "question_set_id",
            context="question set",
        ),
        title=_required_string(raw, "title", context="question set"),
        corpus_sha256=_required_string(
            raw,
            "corpus_sha256",
            context="question set",
        ),
        judgment_method=_required_string(
            raw,
            "judgment_method",
            context="question set",
        ),
        questions=tuple(questions),
        file_sha256=hashlib.sha256(data).hexdigest().upper(),
    )


def score_ranked_chunk_ids(
    *,
    relevant_chunk_ids: tuple[str, ...],
    ranked_chunk_ids: list[str],
    k_values: tuple[int, ...],
) -> RankingScore:
    relevant = set(relevant_chunk_ids)
    first_relevant_rank = next(
        (
            rank
            for rank, chunk_id in enumerate(ranked_chunk_ids, start=1)
            if chunk_id in relevant
        ),
        None,
    )
    recall_at_k = {
        k: len(relevant.intersection(ranked_chunk_ids[:k])) / len(relevant)
        for k in k_values
    }
    reciprocal_rank = (
        0.0 if first_relevant_rank is None else 1.0 / first_relevant_rank
    )
    return RankingScore(
        first_relevant_rank=first_relevant_rank,
        reciprocal_rank=reciprocal_rank,
        recall_at_k=recall_at_k,
    )


def _verify_judgments(
    connection: Connection,
    *,
    corpus_revision_id: int,
    question_set: RetrievalQuestionSet,
) -> None:
    relevant_chunk_ids = sorted(
        {
            chunk_id
            for question in question_set.questions
            for chunk_id in question.relevant_chunk_ids
        }
    )
    rows = connection.execute(
        """
        SELECT chunks.chunk_id, documents.source_id
        FROM rag.evidence_chunks AS chunks
        JOIN rag.source_documents AS documents
          ON documents.source_document_id = chunks.source_document_id
        WHERE chunks.corpus_revision_id = %s
          AND chunks.chunk_id = ANY(%s)
        """,
        (corpus_revision_id, relevant_chunk_ids),
    ).fetchall()
    source_by_chunk = {
        str(row["chunk_id"]): str(row["source_id"]) for row in rows
    }
    missing = [
        chunk_id
        for chunk_id in relevant_chunk_ids
        if chunk_id not in source_by_chunk
    ]
    if missing:
        raise RetrievalEvaluationError(
            "Judged chunks are missing from the pinned corpus: "
            + ", ".join(missing)
        )
    for question in question_set.questions:
        unexpected_sources = {
            source_by_chunk[chunk_id]
            for chunk_id in question.relevant_chunk_ids
            if source_by_chunk[chunk_id] not in question.source_ids
        }
        if unexpected_sources:
            raise RetrievalEvaluationError(
                f"{question.question_id}: judged chunk source is not listed."
            )


def evaluate_lexical_retrieval(
    connection: Connection,
    *,
    question_set: RetrievalQuestionSet,
    k_values: tuple[int, ...] = (1, 3, 5),
) -> RetrievalEvaluation:
    if (
        not k_values
        or any(k <= 0 for k in k_values)
        or tuple(sorted(set(k_values))) != k_values
    ):
        raise RetrievalEvaluationError(
            "k_values must be unique positive integers in ascending order."
        )

    corpus_revision_id = resolve_corpus_revision_id(
        connection,
        corpus_sha256=question_set.corpus_sha256,
    )
    _verify_judgments(
        connection,
        corpus_revision_id=corpus_revision_id,
        question_set=question_set,
    )

    question_results: list[QuestionEvaluation] = []
    max_k = max(k_values)
    for question in question_set.questions:
        started_at = perf_counter()
        retrieved = lexical_retrieve(
            connection,
            corpus_revision_id=corpus_revision_id,
            query=question.question,
            limit=max_k,
        )
        latency_ms = (perf_counter() - started_at) * 1_000
        ranking = score_ranked_chunk_ids(
            relevant_chunk_ids=question.relevant_chunk_ids,
            ranked_chunk_ids=[chunk.chunk_id for chunk in retrieved],
            k_values=k_values,
        )
        question_results.append(
            QuestionEvaluation(
                question=question,
                retrieved=tuple(retrieved),
                ranking=ranking,
                latency_ms=latency_ms,
            )
        )

    latencies = [result.latency_ms for result in question_results]
    return RetrievalEvaluation(
        question_set=question_set,
        corpus_revision_id=corpus_revision_id,
        retriever_version=LEXICAL_RETRIEVER_VERSION,
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
        mean_latency_ms=mean(latencies),
        median_latency_ms=median(latencies),
    )


def retrieval_evaluation_to_dict(
    evaluation: RetrievalEvaluation,
) -> dict[str, Any]:
    return {
        "question_set_id": evaluation.question_set.question_set_id,
        "question_set_sha256": evaluation.question_set.file_sha256,
        "corpus_sha256": evaluation.question_set.corpus_sha256,
        "corpus_revision_id": evaluation.corpus_revision_id,
        "retriever_version": evaluation.retriever_version,
        "k_values": list(evaluation.k_values),
        "metrics": {
            "mean_reciprocal_rank": evaluation.mean_reciprocal_rank,
            "mean_recall_at_k": {
                str(k): value
                for k, value in evaluation.mean_recall_at_k.items()
            },
            "zero_result_questions": evaluation.zero_result_questions,
            "mean_latency_ms": evaluation.mean_latency_ms,
            "median_latency_ms": evaluation.median_latency_ms,
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
                "latency_ms": result.latency_ms,
                "retrieved": [
                    {
                        "rank": chunk.rank,
                        "chunk_id": chunk.chunk_id,
                        "source_id": chunk.source_id,
                        "score": chunk.score,
                        "strict_match": chunk.strict_match,
                    }
                    for chunk in result.retrieved
                ],
            }
            for result in evaluation.questions
        ],
    }
