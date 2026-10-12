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
from dev.backend.app.rag.embedding_input import (  # noqa: E402
    prepare_query_embedding_input,
)
from dev.backend.app.rag.retrieval import resolve_corpus_revision_id  # noqa: E402
from dev.backend.app.rag.retrieval_evaluation import (  # noqa: E402
    RetrievalEvaluationError,
    load_retrieval_question_set,
)
from dev.backend.app.rag.semantic_retrieval import (  # noqa: E402
    SemanticRetrievalError,
    resolve_embedding_model_id,
    verify_embedding_coverage,
)
from dev.backend.app.rag.semantic_retrieval_evaluation import (  # noqa: E402
    evaluate_semantic_retrieval,
    semantic_evaluation_to_dict,
)
from tools.project_runtime import (  # noqa: E402
    ProjectRuntimeError,
    application_revision,
    database_url,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate exact pgvector cosine retrieval separately from "
            "answer generation."
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
        help="Optional JSON path for complete per-question results.",
    )
    parser.add_argument(
        "--application-revision",
        help="Explicit Git revision for container runs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Verify questions and vector coverage without calling Azure or "
            "ranking results."
        ),
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
        if args.dry_run:
            corpus_revision_id = resolve_corpus_revision_id(
                connection,
                corpus_sha256=question_set.corpus_sha256,
            )
            embedding_model_id = resolve_embedding_model_id(
                connection,
                config=config,
            )
            coverage = verify_embedding_coverage(
                connection,
                corpus_revision_id=corpus_revision_id,
                embedding_model_id=embedding_model_id,
            )
            print(f"Corpus revision: {corpus_revision_id}")
            print(f"Embedding model: {embedding_model_id}")
            print(f"Embedding coverage: {coverage}")
            print(f"Questions: {len(question_set.questions)}")
            for question in question_set.questions:
                prepared = prepare_query_embedding_input(question.question)
                print(
                    f"{question.question_id}\t"
                    f"{prepared.char_count}\t"
                    f"{prepared.sha256}"
                )
            return

        evaluation = evaluate_semantic_retrieval(
            connection,
            config=config,
            pricing=pricing,
            question_set=question_set,
        )

    result = semantic_evaluation_to_dict(evaluation)
    result["embedding_configuration"] = {
        "deployment_name": config.deployment_name,
        "model_name": config.model_name,
        "model_version": config.model_version,
        "dimensions": config.dimensions,
        "region": config.region,
        "document_input_version": "source-heading-content-v1",
        "query_input_version": "raw-question-v1",
        "ranking": "exact cosine; index and bitmap scans disabled",
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
        "Mean database latency: "
        f"{evaluation.mean_database_latency_ms:.3f} ms"
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
        ProjectRuntimeError,
        RetrievalEvaluationError,
        SemanticRetrievalError,
    ) as exc:
        raise SystemExit(f"Semantic retrieval evaluation failed: {exc}") from exc
