from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from dev.backend.app.rag.azure_generation import (
    AzureGenerationConfig,
    GenerationPricing,
    request_structured_generation,
)


class _SmokeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    deployment_verified: bool


class _Response:
    status_code = 200
    headers: dict[str, str] = {}

    def json(self) -> object:
        return {
            "id": "resp-test",
            "model": "gpt-4.1-mini-2025-04-14",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": (
                                '{"status":"ok",'
                                '"deployment_verified":true}'
                            ),
                        }
                    ],
                }
            ],
            "usage": {
                "input_tokens": 100,
                "input_tokens_details": {"cached_tokens": 20},
                "output_tokens": 10,
                "total_tokens": 110,
            },
        }


def _config() -> AzureGenerationConfig:
    return AzureGenerationConfig(
        endpoint="https://faceguard.example.com",
        api_key="test-key",
        api_version="v1",
        deployment_name="gpt-4.1-mini",
        model_name="gpt-4.1-mini",
        model_version="2025-04-14",
        region="Japan East",
        version_upgrade_policy="OnceCurrentVersionExpired",
        max_output_tokens=128,
    )


def _pricing() -> GenerationPricing:
    return GenerationPricing(
        input_price_per_million_tokens=Decimal("0.40"),
        cached_input_price_per_million_tokens=Decimal("0.10"),
        output_price_per_million_tokens=Decimal("1.60"),
        currency="USD",
        checked_at=date(2026, 10, 11),
    )


def test_structured_generation_validates_schema_and_cost() -> None:
    captured: dict[str, object] = {}

    def post(url: str, **kwargs: object) -> _Response:
        captured["url"] = url
        captured.update(kwargs)
        return _Response()

    times = iter((1.0, 1.25))
    result = request_structured_generation(
        _config(),
        _pricing(),
        system_prompt="Return structured output.",
        user_prompt="Confirm deployment.",
        response_model=_SmokeResponse,
        schema_name="smoke",
        post=post,
        timer=lambda: next(times),
    )

    assert captured["url"] == (
        "https://faceguard.example.com/openai/v1/responses"
    )
    assert captured["headers"] == {
        "api-key": "test-key",
        "Content-Type": "application/json",
    }
    payload = captured["json"]
    assert payload["model"] == "gpt-4.1-mini"
    assert payload["store"] is False
    assert payload["text"]["format"]["strict"] is True
    assert result.parsed.deployment_verified is True
    assert result.input_tokens == 100
    assert result.cached_input_tokens == 20
    assert result.output_tokens == 10
    assert result.latency_ms == 250.0
    assert result.calculated_cost == Decimal("0.00005")
