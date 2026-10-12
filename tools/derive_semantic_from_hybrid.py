from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from statistics import mean, median
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dev.backend.app.rag.retrieval_evaluation import (  # noqa: E402
    RetrievalEvaluationError,
    load_retrieval_question_set,
    score_ranked_chunk_ids,
)
from dev.backend.app.rag.semantic_retrieval import (  # noqa: E402
    SEMANTIC_RETRIEVER_VERSION,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Derive an exact-semantic result artifact from a frozen hybrid "
            "artifact without repeating Azure query embeddings."
        )
    )
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--hybrid", type=Path, required=True)
    parser.add_argument("--hybrid-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    question_set = load_retrieval_question_set(args.questions)
    hybrid_bytes = args.hybrid.read_bytes()
    actual_sha256 = hashlib.sha256(hybrid_bytes).hexdigest().upper()
    expected_sha256 = args.hybrid_sha256.strip().upper()
    if actual_sha256 != expected_sha256:
        raise RetrievalEvaluationError(
            "Hybrid artifact SHA-256 does not match the frozen identity."
        )
    hybrid = json.loads(hybrid_bytes.decode("utf-8"))
    if hybrid.get("question_set_sha256") != question_set.file_sha256:
        raise RetrievalEvaluationError(
            "Hybrid artifact question set does not match."
        )

    hybrid_by_id = {
        question["question_id"]: question
        for question in hybrid["questions"]
    }
    results: list[dict[str, object]] = []
    reciprocal_ranks: list[float] = []
    recalls: dict[int, list[float]] = {1: [], 3: [], 5: []}
    query_latencies: list[float] = []
    database_latencies: list[float] = []
    total_tokens = 0
    total_cost = Decimal("0")

    for question in question_set.questions:
        source = hybrid_by_id[question.question_id]
        retrieved = source["semantic_candidates"][:5]
        ranking = score_ranked_chunk_ids(
            relevant_chunk_ids=question.relevant_chunk_ids,
            ranked_chunk_ids=[
                str(candidate["chunk_id"]) for candidate in retrieved
            ],
            k_values=(1, 3, 5),
        )
        reciprocal_ranks.append(ranking.reciprocal_rank)
        for k in recalls:
            recalls[k].append(ranking.recall_at_k[k])

        query_latency = float(source["query_embedding_latency_ms"])
        database_latency = float(source["semantic_latency_ms"])
        query_tokens = int(source["query_prompt_tokens"])
        query_cost = Decimal(str(source["query_cost"]))
        query_latencies.append(query_latency)
        database_latencies.append(database_latency)
        total_tokens += query_tokens
        total_cost += query_cost

        results.append(
            {
                "question_id": question.question_id,
                "question": question.question,
                "relevant_chunk_ids": list(question.relevant_chunk_ids),
                "first_relevant_rank": ranking.first_relevant_rank,
                "reciprocal_rank": ranking.reciprocal_rank,
                "recall_at_k": {
                    str(k): ranking.recall_at_k[k] for k in (1, 3, 5)
                },
                "query_input_sha256": source["query_input_sha256"],
                "query_vector_sha256": source["query_vector_sha256"],
                "query_prompt_tokens": query_tokens,
                "query_embedding_latency_ms": query_latency,
                "query_cost": str(query_cost),
                "database_latency_ms": database_latency,
                "retrieved": [
                    {
                        "rank": candidate["rank"],
                        "chunk_id": candidate["chunk_id"],
                        "source_id": candidate["source_id"],
                        "score": candidate["score"],
                        "cosine_distance": candidate["cosine_distance"],
                    }
                    for candidate in retrieved
                ],
            }
        )

    result = {
        "question_set_id": question_set.question_set_id,
        "question_set_sha256": question_set.file_sha256,
        "corpus_sha256": question_set.corpus_sha256,
        "corpus_revision_id": hybrid["corpus_revision_id"],
        "embedding_model_id": hybrid["embedding_model_id"],
        "retriever_version": SEMANTIC_RETRIEVER_VERSION,
        "source_artifact_sha256": actual_sha256,
        "k_values": [1, 3, 5],
        "metrics": {
            "mean_reciprocal_rank": mean(reciprocal_ranks),
            "mean_recall_at_k": {
                str(k): mean(values) for k, values in recalls.items()
            },
            "zero_result_questions": sum(
                not question["retrieved"] for question in results
            ),
            "total_query_tokens": total_tokens,
            "total_query_cost": str(total_cost),
            "mean_query_embedding_latency_ms": mean(query_latencies),
            "median_query_embedding_latency_ms": median(query_latencies),
            "mean_database_latency_ms": mean(database_latencies),
            "median_database_latency_ms": median(database_latencies),
        },
        "questions": results,
        "embedding_configuration": hybrid["embedding_configuration"],
        "pricing": hybrid["pricing"],
        "application_revision": hybrid["application_revision"],
        "measured_at": hybrid["measured_at"],
        "derived_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path = args.output
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Mean Recall@1: {mean(recalls[1]):.6f}")
    print(f"Mean Recall@3: {mean(recalls[3]):.6f}")
    print(f"Mean Recall@5: {mean(recalls[5]):.6f}")
    print(f"MRR: {mean(reciprocal_ranks):.6f}")
    print(f"Query tokens: {total_tokens}")
    print(f"Query cost: {total_cost}")
    print(f"Results written: {output_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        RetrievalEvaluationError,
    ) as exc:
        raise SystemExit(
            f"Semantic artifact derivation failed: {exc}"
        ) from exc
