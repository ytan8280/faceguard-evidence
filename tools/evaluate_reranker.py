from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import psycopg
from psycopg.rows import dict_row


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUESTION_SET = (
    REPO_ROOT / "data" / "evaluation" / "retrieval_questions_v1.json"
)
DEFAULT_HYBRID_ARTIFACT = (
    REPO_ROOT / "data" / "evaluation" / "results"
    / "hybrid_rrf_baseline_v1.json"
)
HYBRID_ARTIFACT_SHA256 = (
    "163F90ADA3B57738E9993E2E940DFFCDC076A55ED3080368FBA481141C853876"
)

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dev.backend.app.rag.reranker import (  # noqa: E402
    RerankerError,
    load_reranker,
    load_reranker_config,
)
from dev.backend.app.rag.reranker_evaluation import (  # noqa: E402
    RerankerEvaluationError,
    evaluate_reranker,
    load_frozen_hybrid_candidates,
    reranker_evaluation_to_dict,
)
from dev.backend.app.rag.retrieval_evaluation import (  # noqa: E402
    RetrievalEvaluationError,
    load_retrieval_question_set,
)
from tools.project_runtime import (  # noqa: E402
    ProjectRuntimeError,
    application_revision,
    database_url,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a pinned local cross-encoder over frozen semantic and "
            "lexical-semantic union candidates."
        )
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=DEFAULT_QUESTION_SET,
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=DEFAULT_HYBRID_ARTIFACT,
    )
    parser.add_argument(
        "--candidate-sha256",
        default=HYBRID_ARTIFACT_SHA256,
        help="Required SHA-256 identity of the frozen candidate artifact.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON path for complete reranking results.",
    )
    parser.add_argument(
        "--application-revision",
        help="Explicit Git revision for container runs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    question_set = load_retrieval_question_set(args.questions)
    hybrid_artifact = load_frozen_hybrid_candidates(
        args.candidates,
        expected_sha256=args.candidate_sha256,
    )
    reranker = load_reranker(load_reranker_config(REPO_ROOT))

    with psycopg.connect(
        database_url(REPO_ROOT),
        autocommit=True,
        row_factory=dict_row,
    ) as connection:
        evaluation = evaluate_reranker(
            connection,
            reranker=reranker,
            question_set=question_set,
            hybrid_artifact=hybrid_artifact,
            source_artifact_sha256=args.candidate_sha256,
        )

    result = reranker_evaluation_to_dict(evaluation)
    result["application_revision"] = (
        args.application_revision
        if args.application_revision is not None
        else application_revision(REPO_ROOT)
    )
    result["measured_at"] = datetime.now(timezone.utc).isoformat()

    print(f"Model: {evaluation.model_id}")
    print(f"Revision: {evaluation.model_revision}")
    print(f"Model SHA-256: {evaluation.model_sha256}")
    for name, metrics in (
        ("Semantic top-20", evaluation.semantic_metrics),
        ("Lexical-semantic union", evaluation.union_metrics),
    ):
        print(name)
        for k, value in metrics.mean_recall_at_k.items():
            print(f"  Mean Recall@{k}: {value:.6f}")
        print(f"  MRR: {metrics.mean_reciprocal_rank:.6f}")
        print(
            "  Mean candidate recall: "
            f"{metrics.mean_candidate_recall:.6f}"
        )
    print(f"Scored pairs: {evaluation.total_scored_pairs}")
    print(f"Truncated pairs: {evaluation.truncated_pairs}")
    print(f"Model load latency: {evaluation.model_load_latency_ms:.3f} ms")
    print(
        "Mean inference latency: "
        f"{evaluation.mean_inference_latency_ms:.3f} ms"
    )

    if args.output is not None:
        output_path = args.output
        if not output_path.is_absolute():
            output_path = REPO_ROOT / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"Results written: {output_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    try:
        main()
    except (
        ProjectRuntimeError,
        RerankerError,
        RerankerEvaluationError,
        RetrievalEvaluationError,
    ) as exc:
        raise SystemExit(f"Reranker evaluation failed: {exc}") from exc
