from __future__ import annotations

from typing import Literal
from pathlib import Path
import sys

from pydantic import BaseModel, ConfigDict


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dev.backend.app.rag.azure_generation import (  # noqa: E402
    AzureGenerationError,
    load_azure_generation_config,
    load_generation_pricing,
    request_structured_generation,
)


class GenerationSmokeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    deployment_verified: bool
    message: str


def main() -> None:
    config = load_azure_generation_config(REPO_ROOT)
    pricing = load_generation_pricing(REPO_ROOT)
    result = request_structured_generation(
        config,
        pricing,
        system_prompt=(
            "Return only the requested structured deployment verification. "
            "Do not add facts or commentary."
        ),
        user_prompt=(
            "Confirm that this structured-output smoke test completed. "
            "Set status to ok, deployment_verified to true, and provide a "
            "short message."
        ),
        response_model=GenerationSmokeResponse,
        schema_name="faceguard_generation_smoke",
    )

    print("Azure structured generation smoke test succeeded.")
    print(f"Deployment: {config.deployment_name}")
    print(f"Configured model: {config.model_name}")
    print(f"Configured version: {config.model_version}")
    print(f"Response model: {result.response_model}")
    print(f"Status: {result.parsed.status}")
    print(
        "Deployment verified: "
        f"{result.parsed.deployment_verified}"
    )
    print(f"Input SHA-256: {result.input_sha256}")
    print(f"Output SHA-256: {result.output_sha256}")
    print(f"Input tokens: {result.input_tokens}")
    print(f"Cached input tokens: {result.cached_input_tokens}")
    print(f"Output tokens: {result.output_tokens}")
    print(f"Total tokens: {result.total_tokens}")
    print(f"Latency: {result.latency_ms:.3f} ms")
    print(f"Calculated cost: {result.calculated_cost} {pricing.currency}")


if __name__ == "__main__":
    try:
        main()
    except AzureGenerationError as exc:
        raise SystemExit(
            f"Azure generation verification failed: {exc}"
        ) from exc
