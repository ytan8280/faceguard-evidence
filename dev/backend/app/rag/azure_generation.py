from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError
import requests


StructuredResponse = TypeVar("StructuredResponse", bound=BaseModel)


class AzureGenerationError(RuntimeError):
    """Raised when Azure structured generation cannot be completed safely."""


class AzureGenerationHTTPError(AzureGenerationError):
    """Raised when Azure returns a non-successful HTTP response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        latency_ms: float,
        retry_after_seconds: float | None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.latency_ms = latency_ms
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class AzureGenerationConfig:
    endpoint: str
    api_key: str
    api_version: str
    deployment_name: str
    model_name: str
    model_version: str
    region: str
    version_upgrade_policy: str
    max_output_tokens: int
    timeout_seconds: float = 60.0

    @property
    def responses_url(self) -> str:
        return (
            f"{self.endpoint.rstrip('/')}/openai/"
            f"{self.api_version}/responses"
        )


@dataclass(frozen=True, slots=True)
class GenerationPricing:
    input_price_per_million_tokens: Decimal
    cached_input_price_per_million_tokens: Decimal
    output_price_per_million_tokens: Decimal
    currency: str
    checked_at: date

    def calculate_cost(
        self,
        *,
        input_tokens: int,
        cached_input_tokens: int,
        output_tokens: int,
    ) -> Decimal:
        uncached_tokens = input_tokens - cached_input_tokens
        if uncached_tokens < 0:
            raise AzureGenerationError(
                "Cached input tokens exceed total input tokens."
            )
        return (
            Decimal(uncached_tokens)
            * self.input_price_per_million_tokens
            / Decimal(1_000_000)
            + Decimal(cached_input_tokens)
            * self.cached_input_price_per_million_tokens
            / Decimal(1_000_000)
            + Decimal(output_tokens)
            * self.output_price_per_million_tokens
            / Decimal(1_000_000)
        )


@dataclass(frozen=True, slots=True)
class StructuredGenerationResult:
    parsed: BaseModel
    response_model: str
    response_id: str
    input_sha256: str
    output_sha256: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    calculated_cost: Decimal


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise AzureGenerationError(f"{name} is not configured.")
    return value


def _positive_integer_environment(name: str) -> int:
    raw_value = _required_environment(name)
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise AzureGenerationError(f"{name} must be an integer.") from exc
    if value <= 0:
        raise AzureGenerationError(f"{name} must be positive.")
    return value


def load_azure_generation_config(
    repository_root: Path,
) -> AzureGenerationConfig:
    load_dotenv(repository_root / ".env", override=False)
    endpoint = _required_environment("AZURE_OPENAI_ENDPOINT")
    if not endpoint.startswith("https://"):
        raise AzureGenerationError("AZURE_OPENAI_ENDPOINT must use HTTPS.")
    api_version = _required_environment("AZURE_OPENAI_API_VERSION")
    if api_version != "v1":
        raise AzureGenerationError(
            "Structured generation currently supports API version v1."
        )
    return AzureGenerationConfig(
        endpoint=endpoint,
        api_key=_required_environment("AZURE_OPENAI_API_KEY"),
        api_version=api_version,
        deployment_name=_required_environment(
            "AZURE_OPENAI_CHAT_DEPLOYMENT"
        ),
        model_name=_required_environment("AZURE_OPENAI_CHAT_MODEL"),
        model_version=_required_environment(
            "AZURE_OPENAI_CHAT_MODEL_VERSION"
        ),
        region=_required_environment("AZURE_OPENAI_REGION"),
        version_upgrade_policy=_required_environment(
            "AZURE_OPENAI_CHAT_VERSION_UPGRADE_POLICY"
        ),
        max_output_tokens=_positive_integer_environment(
            "AZURE_OPENAI_CHAT_MAX_OUTPUT_TOKENS"
        ),
    )


def _decimal_environment(name: str) -> Decimal:
    raw_value = _required_environment(name)
    try:
        value = Decimal(raw_value)
    except InvalidOperation as exc:
        raise AzureGenerationError(f"{name} must be a decimal.") from exc
    if value < 0:
        raise AzureGenerationError(f"{name} must not be negative.")
    return value


def load_generation_pricing(repository_root: Path) -> GenerationPricing:
    load_dotenv(repository_root / ".env", override=False)
    currency = _required_environment(
        "AZURE_OPENAI_CHAT_PRICING_CURRENCY"
    ).upper()
    if len(currency) != 3 or not currency.isalpha():
        raise AzureGenerationError(
            "Chat pricing currency must be a three-letter code."
        )
    try:
        checked_at = date.fromisoformat(
            _required_environment("AZURE_OPENAI_CHAT_PRICING_CHECKED_AT")
        )
    except ValueError as exc:
        raise AzureGenerationError(
            "Chat pricing checked date must use YYYY-MM-DD."
        ) from exc
    return GenerationPricing(
        input_price_per_million_tokens=_decimal_environment(
            "AZURE_OPENAI_CHAT_INPUT_PRICE_PER_MILLION_TOKENS"
        ),
        cached_input_price_per_million_tokens=_decimal_environment(
            "AZURE_OPENAI_CHAT_CACHED_INPUT_PRICE_PER_MILLION_TOKENS"
        ),
        output_price_per_million_tokens=_decimal_environment(
            "AZURE_OPENAI_CHAT_OUTPUT_PRICE_PER_MILLION_TOKENS"
        ),
        currency=currency,
        checked_at=checked_at,
    )


def _error_message(response: requests.Response) -> str:
    try:
        body = response.json()
    except requests.JSONDecodeError:
        return f"Azure returned HTTP {response.status_code}."
    if isinstance(body, Mapping):
        error = body.get("error")
        if isinstance(error, Mapping):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return (
                    f"Azure returned HTTP {response.status_code}: "
                    f"{message.strip()}"
                )
    return f"Azure returned HTTP {response.status_code}."


def _retry_after_seconds(response: requests.Response) -> float | None:
    raw_value = response.headers.get("Retry-After")
    if raw_value is None:
        return None
    try:
        value = float(raw_value)
    except ValueError:
        return None
    return value if value >= 0 else None


def _nonnegative_integer(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise AzureGenerationError(
            f"Azure response field {name} must be a non-negative integer."
        )
    return value


def _extract_output_text(body: Mapping[str, Any]) -> str:
    output = body.get("output")
    if not isinstance(output, list):
        raise AzureGenerationError("Azure response is missing output items.")
    for item in output:
        if not isinstance(item, Mapping) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, Mapping):
                continue
            if part.get("type") == "refusal":
                refusal = part.get("refusal")
                raise AzureGenerationError(
                    "Azure model refused the structured generation request"
                    + (f": {refusal}" if isinstance(refusal, str) else ".")
                )
            if part.get("type") == "output_text":
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    return text
    raise AzureGenerationError(
        "Azure response contains no structured output text."
    )


def request_structured_generation(
    config: AzureGenerationConfig,
    pricing: GenerationPricing,
    *,
    system_prompt: str,
    user_prompt: str,
    response_model: type[StructuredResponse],
    schema_name: str,
    max_output_tokens: int | None = None,
    max_attempts: int = 3,
    post: Callable[..., requests.Response] = requests.post,
    timer: Callable[[], float] = time.perf_counter,
    sleep: Callable[[float], None] = time.sleep,
) -> StructuredGenerationResult:
    if not system_prompt.strip() or not user_prompt.strip():
        raise AzureGenerationError("Generation prompts must not be blank.")
    if not schema_name.strip():
        raise AzureGenerationError("Structured-output schema name is blank.")
    if max_attempts <= 0:
        raise AzureGenerationError("Maximum generation attempts must be positive.")
    output_limit = (
        config.max_output_tokens
        if max_output_tokens is None
        else max_output_tokens
    )
    if output_limit <= 0:
        raise AzureGenerationError("Generation output limit must be positive.")

    messages = [
        {
            "role": "system",
            "content": [{"type": "input_text", "text": system_prompt}],
        },
        {
            "role": "user",
            "content": [{"type": "input_text", "text": user_prompt}],
        },
    ]
    payload = {
        "model": config.deployment_name,
        "input": messages,
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": response_model.model_json_schema(),
            }
        },
        "max_output_tokens": output_limit,
        "temperature": 0,
        "store": False,
    }
    canonical_input = json.dumps(
        messages,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    retryable_statuses = {429, 500, 502, 503, 504}
    failed_latency_ms = 0.0
    response: requests.Response | None = None
    for attempt in range(1, max_attempts + 1):
        started_at = timer()
        try:
            response = post(
                config.responses_url,
                headers={
                    "api-key": config.api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=config.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise AzureGenerationError(
                "Unable to reach the Azure generation endpoint."
            ) from exc
        latency_ms = (timer() - started_at) * 1_000
        if 200 <= response.status_code < 300:
            total_latency_ms = failed_latency_ms + latency_ms
            break
        error = AzureGenerationHTTPError(
            _error_message(response),
            status_code=response.status_code,
            latency_ms=failed_latency_ms + latency_ms,
            retry_after_seconds=_retry_after_seconds(response),
        )
        failed_latency_ms += latency_ms
        if (
            response.status_code not in retryable_statuses
            or attempt == max_attempts
        ):
            raise error
        delay = (
            error.retry_after_seconds
            if error.retry_after_seconds is not None
            else float(2 ** (attempt - 1))
        )
        sleep(delay)
    else:
        raise AzureGenerationError("Generation retry loop ended unexpectedly.")

    try:
        body: Any = response.json()
    except requests.JSONDecodeError as exc:
        raise AzureGenerationError(
            "Azure returned a non-JSON generation response."
        ) from exc
    if not isinstance(body, Mapping):
        raise AzureGenerationError("Azure generation response must be an object.")
    if body.get("status") != "completed":
        incomplete_details = body.get("incomplete_details")
        detail = (
            json.dumps(incomplete_details, ensure_ascii=True)
            if incomplete_details is not None
            else "none"
        )
        raise AzureGenerationError(
            "Azure generation status is not completed: "
            f"{body.get('status')}; incomplete_details={detail}"
        )

    output_text = _extract_output_text(body)
    try:
        parsed_json = json.loads(output_text)
        parsed = response_model.model_validate(parsed_json)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AzureGenerationError(
            "Azure output failed strict local schema validation."
        ) from exc

    usage = body.get("usage")
    if not isinstance(usage, Mapping):
        raise AzureGenerationError("Azure response is missing token usage.")
    input_tokens = _nonnegative_integer(
        usage.get("input_tokens"),
        "usage.input_tokens",
    )
    output_tokens = _nonnegative_integer(
        usage.get("output_tokens"),
        "usage.output_tokens",
    )
    total_tokens = _nonnegative_integer(
        usage.get("total_tokens"),
        "usage.total_tokens",
    )
    input_details = usage.get("input_tokens_details")
    cached_input_tokens = 0
    if isinstance(input_details, Mapping):
        cached_input_tokens = _nonnegative_integer(
            input_details.get("cached_tokens", 0),
            "usage.input_tokens_details.cached_tokens",
        )

    response_id = body.get("id")
    actual_model = body.get("model")
    if not isinstance(response_id, str) or not response_id.strip():
        raise AzureGenerationError("Azure response ID is missing.")
    if not isinstance(actual_model, str) or not actual_model.strip():
        raise AzureGenerationError("Azure response model is missing.")

    return StructuredGenerationResult(
        parsed=parsed,
        response_model=actual_model,
        response_id=response_id,
        input_sha256=hashlib.sha256(canonical_input).hexdigest().upper(),
        output_sha256=hashlib.sha256(
            output_text.encode("utf-8")
        ).hexdigest().upper(),
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        latency_ms=total_latency_ms,
        calculated_cost=pricing.calculate_cost(
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
        ),
    )
