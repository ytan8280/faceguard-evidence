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

from dev.backend.app.rag.retrieval_evaluation import (  # noqa: E402
    RetrievalEvaluationError,
    evaluate_lexical_retrieval,
    load_retrieval_question_set,
    retrieval_evaluation_to_dict,
)
from dev.backend.app.rag.retrieval import RetrievalError  # noqa: E402
from tools.project_runtime import (  # noqa: E402
    ProjectRuntimeError,
    application_revision,
    database_url,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate PostgreSQL lexical retrieval separately from generation."
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    question_set = load_retrieval_question_set(args.questions)
    with psycopg.connect(
        database_url(REPO_ROOT),
        autocommit=True,
        row_factory=dict_row,
    ) as connection:
        evaluation = evaluate_lexical_retrieval(
            connection,
            question_set=question_set,
        )

    result = retrieval_evaluation_to_dict(evaluation)
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
    print(f"Mean latency: {evaluation.mean_latency_ms:.3f} ms")
    print(f"Median latency: {evaluation.median_latency_ms:.3f} ms")

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
        RetrievalError,
        RetrievalEvaluationError,
    ) as exc:
        raise SystemExit(f"Lexical retrieval evaluation failed: {exc}") from exc
