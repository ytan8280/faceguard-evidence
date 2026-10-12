from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dev.backend.app.rag.evidence_report_models import (  # noqa: E402
    EvidenceReportRequest,
    EvidenceReportResponse,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one synthetic end-to-end report through the localhost RAG "
            "sidecar."
        )
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8002",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = EvidenceReportRequest(
        question=(
            "Does this high detector score prove the image is fake, identify "
            "who created it, or identify which AI tool was used?"
        ),
        observations=[
            {
                "observation_id": "OBS-1",
                "statement": (
                    "The supplied test record describes a JPEG still image."
                ),
            },
            {
                "observation_id": "OBS-2",
                "statement": (
                    "No verified creator-identity field is present in the "
                    "supplied test record."
                ),
            },
        ],
        detector_output={
            "detector_id": "DET-1",
            "model_name": "vit3",
            "label": "FAKE",
            "fake_probability": 0.94,
            "threshold": 0.25,
            "limitations": [
                (
                    "The detector output is a probabilistic signal, not proof "
                    "of image origin or authenticity."
                ),
                (
                    "The active threshold is inherited and has not been "
                    "independently validated for FaceGuard Evidence."
                ),
                (
                    "The detector cannot establish depicted-person identity, "
                    "creator identity, generation tool, intent, deception, or "
                    "certainty."
                ),
            ],
            "adapter_version": "faceguard-detector-adapter-v1",
            "preprocessing_version": (
                "faceguard-rgb-resize-normalize-v1"
            ),
        },
    )
    response = requests.post(
        f"{args.url.rstrip('/')}/build-report",
        json=payload.model_dump(mode="json"),
        timeout=120,
    )
    response.raise_for_status()
    result = EvidenceReportResponse.model_validate(response.json())

    print(f"Assessment: {result.report.overall_assessment}")
    print(f"Evidence chunks: {len(result.evidence)}")
    print(
        "Supported conclusions: "
        f"{len(result.report.supported_conclusions)}"
    )
    print(
        "Unsupported conclusions: "
        f"{len(result.report.unsupported_conclusions)}"
    )
    print(
        "Measured cost: "
        f"{result.metrics.total_measured_cost} USD"
    )
    print(
        "Query embedding latency: "
        f"{result.metrics.query_embedding_latency_ms:.3f} ms"
    )
    print(
        "Reranker latency: "
        f"{result.metrics.reranker_latency_ms:.3f} ms"
    )
    print(
        "Generation latency: "
        f"{result.metrics.generation_latency_ms:.3f} ms"
    )

    if args.output is not None:
        output_path = args.output
        if not output_path.is_absolute():
            output_path = REPO_ROOT / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                result.model_dump(mode="json"),
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"Results written: {output_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
