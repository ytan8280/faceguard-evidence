from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Any

from dotenv import load_dotenv
import requests


class AzureEmbeddingError(RuntimeError):
    """Raised when Azure embedding configuration or responses are invalid."""


class AzureEmbeddingHTTPError(AzureEmbeddingError):
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


@dataclass(frozen=True)
class AzureEmbeddingConfig:
    endpoint: str
    api_key: str
    api_version: str
    deployment_name: str
    model_name: str
    model_version: str
    region: str
    version_upgrade_policy: str
    dimensions: int
    timeout_seconds: float = 30.0

    @property
    def embeddings_url(self) -> str:
        return (
            f"{self.endpoint.rstrip('/')}/openai/"
            f"{self.api_version}/embeddings"
        )


@dataclass(frozen=True)
class EmbeddingResponse:
    vector: tuple[float, ...]
    response_model: str
    prompt_tokens: int
    total_tokens: int
    latency_ms: float
    vector_sha256: str
    vector_l2_norm: float
    request_id: str | None


@dataclass(frozen=True)
class EmbeddingProbeResult:
    deployment_name: str
    configured_model_name: str
    configured_model_version: str
    response_model: str | None
    dimensions: int
    input_characters: int
    input_sha256: str
    prompt_tokens: int
    total_tokens: int
    latency_ms: float
    vector_sha256: str
    vector_l2_norm: float
    request_id: str | None


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise AzureEmbeddingError(f"{name} is not configured.")
    return value


def load_azure_embedding_config(repository_root: Path) -> AzureEmbeddingConfig:
    load_dotenv(repository_root / ".env", override=False)

    endpoint = _required_environment("AZURE_OPENAI_ENDPOINT")
    if not endpoint.startswith("https://"):
        raise AzureEmbeddingError("AZURE_OPENAI_ENDPOINT must use HTTPS.")

    api_version = _required_environment("AZURE_OPENAI_API_VERSION")
    if api_version != "v1":
        raise AzureEmbeddingError(
            "The embedding probe currently supports AZURE_OPENAI_API_VERSION=v1."
        )

    dimensions_raw = _required_environment(
        "AZURE_OPENAI_EMBEDDING_DIMENSIONS"
    )
    try:
        dimensions = int(dimensions_raw)
    except ValueError as exc:
        raise AzureEmbeddingError(
            "AZURE_OPENAI_EMBEDDING_DIMENSIONS must be an integer."
        ) from exc
    if dimensions <= 0:
        raise AzureEmbeddingError(
            "AZURE_OPENAI_EMBEDDING_DIMENSIONS must be positive."
        )

    return AzureEmbeddingConfig(
        endpoint=endpoint,
        api_key=_required_environment("AZURE_OPENAI_API_KEY"),
        api_version=api_version,
        deployment_name=_required_environment(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
        ),
        model_name=_required_environment("AZURE_OPENAI_EMBEDDING_MODEL"),
        model_version=_required_environment(
            "AZURE_OPENAI_EMBEDDING_MODEL_VERSION"
        ),
        region=_required_environment("AZURE_OPENAI_REGION"),
        version_upgrade_policy=_required_environment(
            "AZURE_OPENAI_EMBEDDING_VERSION_UPGRADE_POLICY"
        ),
        dimensions=dimensions,
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


def _integer_field(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise AzureEmbeddingError(
            f"Azure response field {name} must be a non-negative integer."
        )
    return value


def _retry_after_seconds(response: requests.Response) -> float | None:
    raw_value = response.headers.get("Retry-After")
    if raw_value is None:
        return None
    try:
        value = float(raw_value)
    except ValueError:
        return None
    return value if value >= 0 else None


def request_embedding(
    config: AzureEmbeddingConfig,
    text: str,
    *,
    post: Callable[..., requests.Response] = requests.post,
    timer: Callable[[], float] = time.perf_counter,
) -> EmbeddingResponse:
    if not text.strip():
        raise AzureEmbeddingError("Embedding input must not be blank.")

    started_at = timer()
    try:
        response = post(
            config.embeddings_url,
            headers={
                "api-key": config.api_key,
                "Content-Type": "application/json",
            },
            json={
                "model": config.deployment_name,
                "input": text,
                "dimensions": config.dimensions,
                "encoding_format": "float",
            },
            timeout=config.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise AzureEmbeddingError(
            "Unable to reach the Azure embeddings endpoint."
        ) from exc
    latency_ms = (timer() - started_at) * 1000

    if response.status_code < 200 or response.status_code >= 300:
        raise AzureEmbeddingHTTPError(
            _error_message(response),
            status_code=response.status_code,
            latency_ms=latency_ms,
            retry_after_seconds=_retry_after_seconds(response),
        )

    try:
        body: Any = response.json()
    except requests.JSONDecodeError as exc:
        raise AzureEmbeddingError(
            "Azure returned a non-JSON embedding response."
        ) from exc
    if not isinstance(body, Mapping):
        raise AzureEmbeddingError("Azure embedding response must be an object.")

    data = body.get("data")
    if not isinstance(data, list) or len(data) != 1:
        raise AzureEmbeddingError(
            "Azure embedding response must contain exactly one data item."
        )
    item = data[0]
    if not isinstance(item, Mapping):
        raise AzureEmbeddingError("Azure embedding data item must be an object.")

    embedding = item.get("embedding")
    if not isinstance(embedding, list):
        raise AzureEmbeddingError("Azure response is missing the embedding vector.")
    if len(embedding) != config.dimensions:
        raise AzureEmbeddingError(
            "Azure returned "
            f"{len(embedding)} dimensions; expected {config.dimensions}."
        )
    if any(
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        for value in embedding
    ):
        raise AzureEmbeddingError(
            "Azure embedding vector contains a non-finite numeric value."
        )

    usage = body.get("usage")
    if not isinstance(usage, Mapping):
        raise AzureEmbeddingError("Azure response is missing token usage.")
    prompt_tokens = _integer_field(
        usage.get("prompt_tokens"),
        "usage.prompt_tokens",
    )
    total_tokens = _integer_field(
        usage.get("total_tokens"),
        "usage.total_tokens",
    )

    canonical_vector = json.dumps(
        embedding,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    response_model = body.get("model")
    if not isinstance(response_model, str) or not response_model.strip():
        raise AzureEmbeddingError(
            "Azure response field model must be a non-blank string."
        )

    numeric_vector = tuple(float(value) for value in embedding)
    return EmbeddingResponse(
        vector=numeric_vector,
        response_model=response_model,
        prompt_tokens=prompt_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
        vector_sha256=hashlib.sha256(canonical_vector).hexdigest().upper(),
        vector_l2_norm=math.sqrt(
            sum(value * value for value in numeric_vector)
        ),
        request_id=response.headers.get("x-request-id"),
    )


def request_embedding_with_retry(
    config: AzureEmbeddingConfig,
    text: str,
    *,
    max_attempts: int = 3,
    post: Callable[..., requests.Response] = requests.post,
    timer: Callable[[], float] = time.perf_counter,
    sleep: Callable[[float], None] = time.sleep,
) -> EmbeddingResponse:
    if max_attempts <= 0:
        raise AzureEmbeddingError("Maximum embedding attempts must be positive.")

    retryable_statuses = {429, 500, 502, 503, 504}
    failed_latency_ms = 0.0
    for attempt in range(1, max_attempts + 1):
        try:
            response = request_embedding(
                config,
                text,
                post=post,
                timer=timer,
            )
            return replace(
                response,
                latency_ms=response.latency_ms + failed_latency_ms,
            )
        except AzureEmbeddingHTTPError as exc:
            failed_latency_ms += exc.latency_ms
            if (
                exc.status_code not in retryable_statuses
                or attempt == max_attempts
            ):
                exc.latency_ms = failed_latency_ms
                raise
            delay = (
                exc.retry_after_seconds
                if exc.retry_after_seconds is not None
                else float(2 ** (attempt - 1))
            )
            sleep(delay)

    raise AzureEmbeddingError("Embedding retry loop ended unexpectedly.")


def request_embedding_probe(
    config: AzureEmbeddingConfig,
    text: str,
    *,
    post: Callable[..., requests.Response] = requests.post,
    timer: Callable[[], float] = time.perf_counter,
) -> EmbeddingProbeResult:
    response = request_embedding(
        config,
        text,
        post=post,
        timer=timer,
    )
    input_bytes = text.encode("utf-8")

    return EmbeddingProbeResult(
        deployment_name=config.deployment_name,
        configured_model_name=config.model_name,
        configured_model_version=config.model_version,
        response_model=response.response_model,
        dimensions=len(response.vector),
        input_characters=len(text),
        input_sha256=hashlib.sha256(input_bytes).hexdigest().upper(),
        prompt_tokens=response.prompt_tokens,
        total_tokens=response.total_tokens,
        latency_ms=response.latency_ms,
        vector_sha256=response.vector_sha256,
        vector_l2_norm=response.vector_l2_norm,
        request_id=response.request_id,
    )
