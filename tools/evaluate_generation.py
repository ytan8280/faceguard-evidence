from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import psycopg
from psycopg.rows import dict_row


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = REPO_ROOT / "data" / "evaluation" / "generation_cases_v1.json"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dev.backend.app.rag.azure_generation import (  # noqa: E402
    AzureGenerationError,
    load_azure_generation_config,
    load_generation_pricing,
)
from dev.backend.app.rag.generation_evaluation import (  # noqa: E402
    GenerationEvaluationError,
    evaluate_generation,
    generation_evaluation_to_dict,
    load_generation_case_set,
)
from dev.backend.app.rag.evidence_generation import (  # noqa: E402
    prepare_generation_prompt,
)
from tools.project_runtime import (  # noqa: E402
    ProjectRuntimeError,
    application_revision,
    database_url,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate evidence-bounded structured generation."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES,
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON path for complete generation results.",
    )
    parser.add_argument(
        "--application-revision",
        help="Explicit Git revision for container runs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate cases and prompts without calling Azure.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_azure_generation_config(REPO_ROOT)
    pricing = load_generation_pricing(REPO_ROOT)
    with psycopg.connect(
        database_url(REPO_ROOT),
        autocommit=True,
        row_factory=dict_row,
    ) as connection:
        case_set = load_generation_case_set(
            connection,
            path=args.cases,
        )

    if args.dry_run:
        print(f"Evaluation set: {case_set.evaluation_set_id}")
        print(f"Cases: {len(case_set.cases)}")
        print(f"File SHA-256: {case_set.file_sha256}")
        for case in case_set.cases:
            prompt = prepare_generation_prompt(
                case.request,
                prompt_version=case_set.prompt_version,
            )
            print(
                f"{case.case_id}\t"
                f"{len(prompt.system_prompt)}\t"
                f"{len(prompt.user_prompt)}\t"
                f"{prompt.prompt_sha256}"
            )
        return

    revision = (
        args.application_revision
        if args.application_revision is not None
        else application_revision(REPO_ROOT)
    )
    evaluation = evaluate_generation(
        config=config,
        pricing=pricing,
        case_set=case_set,
    )
    result = generation_evaluation_to_dict(evaluation)
    result["deployment"] = {
        "deployment_name": config.deployment_name,
        "model_name": config.model_name,
        "model_version": config.model_version,
        "region": config.region,
        "version_upgrade_policy": config.version_upgrade_policy,
        "max_output_tokens": config.max_output_tokens,
    }
    result["pricing"] = {
        "input_price_per_million_tokens": str(
            pricing.input_price_per_million_tokens
        ),
        "cached_input_price_per_million_tokens": str(
            pricing.cached_input_price_per_million_tokens
        ),
        "output_price_per_million_tokens": str(
            pricing.output_price_per_million_tokens
        ),
        "currency": pricing.currency,
        "checked_at": pricing.checked_at.isoformat(),
    }
    result["application_revision"] = revision
    result["measured_at"] = datetime.now(timezone.utc).isoformat()

    print(f"Evaluation set: {case_set.evaluation_set_id}")
    print(f"Cases passed: {evaluation.passed_cases}/{len(evaluation.cases)}")
    print(f"Input tokens: {evaluation.total_input_tokens}")
    print(f"Cached input tokens: {evaluation.total_cached_input_tokens}")
    print(f"Output tokens: {evaluation.total_output_tokens}")
    print(f"Cost: {evaluation.total_cost} {pricing.currency}")
    print(f"Mean latency: {evaluation.mean_latency_ms:.3f} ms")
    print(f"Median latency: {evaluation.median_latency_ms:.3f} ms")
    for case in evaluation.cases:
        print(
            f"{case.case.case_id}: "
            f"{'PASS' if case.score.passed else 'FAIL'}"
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
        AzureGenerationError,
        GenerationEvaluationError,
        ProjectRuntimeError,
    ) as exc:
        raise SystemExit(f"Generation evaluation failed: {exc}") from exc
