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

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dev.backend.app.rag.azure_embeddings import (  # noqa: E402
    AzureEmbeddingError,
    load_azure_embedding_config,
)
from dev.backend.app.rag.embedding_ingestion import (  # noqa: E402
    EmbeddingIngestionError,
    load_embedding_pricing,
)
from dev.backend.app.rag.hybrid_retrieval import (  # noqa: E402
    HYBRID_CANDIDATE_LIMIT,
    HybridRetrievalError,
    RRF_CONSTANT,
)
from dev.backend.app.rag.hybrid_retrieval_evaluation import (  # noqa: E402
    evaluate_hybrid_retrieval,
    hybrid_evaluation_to_dict,
)
from dev.backend.app.rag.retrieval_evaluation import (  # noqa: E402
    RetrievalEvaluationError,
    load_retrieval_question_set,
)
from dev.backend.app.rag.semantic_retrieval import (  # noqa: E402
    SemanticRetrievalError,
)
from tools.project_runtime import (  # noqa: E402
    ProjectRuntimeError,
    application_revision,
    database_url,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate equal-weight reciprocal-rank fusion over lexical and "
            "exact semantic candidates."
        )
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=DEFAULT_QUESTION_SET,
        help="Versioned retrieval question-set JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON path for complete fusion results.",
    )
    parser.add_argument(
        "--application-revision",
        help="Explicit Git revision for container runs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    question_set = load_retrieval_question_set(args.questions)
    config = load_azure_embedding_config(REPO_ROOT)
    pricing = load_embedding_pricing(REPO_ROOT)
    if pricing is None:
        raise EmbeddingIngestionError(
            "Verified Azure embedding pricing is not configured."
        )

    with psycopg.connect(
        database_url(REPO_ROOT),
        autocommit=True,
        row_factory=dict_row,
    ) as connection:
        evaluation = evaluate_hybrid_retrieval(
            connection,
            config=config,
            pricing=pricing,
            question_set=question_set,
        )

    result = hybrid_evaluation_to_dict(evaluation)
    result["embedding_configuration"] = {
        "deployment_name": config.deployment_name,
        "model_name": config.model_name,
        "model_version": config.model_version,
        "dimensions": config.dimensions,
        "region": config.region,
        "document_input_version": "source-heading-content-v1",
        "query_input_version": "raw-question-v1",
        "semantic_ranking": "exact cosine; index and bitmap scans disabled",
    }
    result["pricing"] = {
        "price_per_million_input_tokens": str(
            pricing.price_per_million_tokens
        ),
        "currency": pricing.currency,
        "checked_at": pricing.checked_at.isoformat(),
    }
    result["application_revision"] = (
        args.application_revision
        if args.application_revision is not None
        else application_revision(REPO_ROOT)
    )
    result["measured_at"] = datetime.now(timezone.utc).isoformat()

    print(f"Question set: {question_set.question_set_id}")
    print(f"Questions: {len(question_set.questions)}")
    print(f"Candidate limit: {HYBRID_CANDIDATE_LIMIT}")
    print(f"RRF constant: {RRF_CONSTANT}")
    for k in evaluation.k_values:
        print(
            f"Mean Recall@{k}: "
            f"{evaluation.mean_recall_at_k[k]:.6f}"
        )
    print(f"MRR: {evaluation.mean_reciprocal_rank:.6f}")
    print(f"Zero-result questions: {evaluation.zero_result_questions}")
    print(f"Query tokens: {evaluation.total_query_tokens}")
    print(f"Query cost: {evaluation.total_query_cost} {pricing.currency}")
    print(
        "Mean query embedding latency: "
        f"{evaluation.mean_query_embedding_latency_ms:.3f} ms"
    )
    print(
        "Mean lexical latency: "
        f"{evaluation.mean_lexical_latency_ms:.3f} ms"
    )
    print(
        "Mean semantic latency: "
        f"{evaluation.mean_semantic_latency_ms:.3f} ms"
    )
    print(
        "Mean fusion latency: "
        f"{evaluation.mean_fusion_latency_ms:.3f} ms"
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
        AzureEmbeddingError,
        EmbeddingIngestionError,
        HybridRetrievalError,
        ProjectRuntimeError,
        RetrievalEvaluationError,
        SemanticRetrievalError,
    ) as exc:
        raise SystemExit(f"Hybrid retrieval evaluation failed: {exc}") from exc
