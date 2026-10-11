from __future__ import annotations

import json
from pathlib import Path

import pytest

from dev.backend.app.rag.retrieval_evaluation import (
    RetrievalEvaluationError,
    load_retrieval_question_set,
    score_ranked_chunk_ids,
)


def _question_set() -> dict[str, object]:
    return {
        "schema_version": 1,
        "question_set_id": "test-v1",
        "title": "Test retrieval questions",
        "created_at": "2026-10-11",
        "corpus_sha256": "A" * 64,
        "judgment_method": "Manual test judgment.",
        "questions": [
            {
                "question_id": "Q-001",
                "question": "Which chunk is relevant?",
                "relevant_chunk_ids": ["chunk-2"],
                "source_ids": ["SOURCE-1"],
                "rationale": "The second chunk contains the answer.",
                "tags": ["test"],
            }
        ],
    }


def test_load_retrieval_question_set_records_file_identity(
    tmp_path: Path,
) -> None:
    path = tmp_path / "questions.json"
    path.write_text(
        json.dumps(_question_set()),
        encoding="utf-8",
        newline="\n",
    )

    question_set = load_retrieval_question_set(path)

    assert question_set.question_set_id == "test-v1"
    assert len(question_set.file_sha256) == 64
    assert question_set.questions[0].relevant_chunk_ids == ("chunk-2",)


def test_load_retrieval_question_set_rejects_duplicate_ids(
    tmp_path: Path,
) -> None:
    raw = _question_set()
    raw["questions"] = [
        raw["questions"][0],
        raw["questions"][0],
    ]
    path = tmp_path / "questions.json"
    path.write_text(
        json.dumps(raw),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(RetrievalEvaluationError, match="duplicate question_id"):
        load_retrieval_question_set(path)


def test_score_ranked_chunk_ids_calculates_recall_and_rr() -> None:
    score = score_ranked_chunk_ids(
        relevant_chunk_ids=("chunk-2", "chunk-4"),
        ranked_chunk_ids=["chunk-1", "chunk-2", "chunk-3", "chunk-4"],
        k_values=(1, 3, 5),
    )

    assert score.first_relevant_rank == 2
    assert score.reciprocal_rank == 0.5
    assert score.recall_at_k == {
        1: 0.0,
        3: 0.5,
        5: 1.0,
    }


def test_score_ranked_chunk_ids_handles_no_relevant_result() -> None:
    score = score_ranked_chunk_ids(
        relevant_chunk_ids=("chunk-9",),
        ranked_chunk_ids=["chunk-1", "chunk-2"],
        k_values=(1, 3, 5),
    )

    assert score.first_relevant_rank is None
    assert score.reciprocal_rank == 0.0
    assert score.recall_at_k == {
        1: 0.0,
        3: 0.0,
        5: 0.0,
    }
