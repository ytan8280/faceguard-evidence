from __future__ import annotations

import math

import pytest

from dev.backend.app.rag.azure_embeddings import (
    AzureEmbeddingConfig,
    AzureEmbeddingError,
    request_embedding,
    request_embedding_probe,
    request_embedding_with_retry,
)


class _Response:
    def __init__(
        self,
        body: object,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._body = body
        self.status_code = status_code
        self.headers = headers or {}

    def json(self) -> object:
        return self._body


def _config(*, dimensions: int = 3) -> AzureEmbeddingConfig:
    return AzureEmbeddingConfig(
        endpoint="https://faceguard.example.com",
        api_key="test-key",
        api_version="v1",
        deployment_name="faceguard-embedding-3-small",
        model_name="text-embedding-3-small",
        model_version="1",
        region="Japan East",
        version_upgrade_policy="OnceNewDefaultVersionAvailable",
        dimensions=dimensions,
    )


def test_request_embedding_probe_validates_and_summarizes_response() -> None:
    captured: dict[str, object] = {}

    def post(url: str, **kwargs: object) -> _Response:
        captured["url"] = url
        captured.update(kwargs)
        return _Response(
            {
                "data": [{"embedding": [0.25, -0.5, 0.75]}],
                "model": "text-embedding-3-small",
                "usage": {
                    "prompt_tokens": 4,
                    "total_tokens": 4,
                },
            },
            headers={"x-request-id": "request-123"},
        )

    times = iter((10.0, 10.125))
    result = request_embedding_probe(
        _config(),
        "Evidence test",
        post=post,
        timer=lambda: next(times),
    )

    assert captured["url"] == (
        "https://faceguard.example.com/openai/v1/embeddings"
    )
    assert captured["json"] == {
        "model": "faceguard-embedding-3-small",
        "input": "Evidence test",
        "dimensions": 3,
        "encoding_format": "float",
    }
    assert captured["headers"] == {
        "api-key": "test-key",
        "Content-Type": "application/json",
    }
    assert result.dimensions == 3
    assert result.prompt_tokens == 4
    assert result.latency_ms == 125.0
    assert result.request_id == "request-123"
    assert result.vector_l2_norm == pytest.approx(math.sqrt(0.875))
    assert len(result.input_sha256) == 64
    assert len(result.vector_sha256) == 64


def test_request_embedding_returns_vector_for_storage() -> None:
    def post(url: str, **kwargs: object) -> _Response:
        return _Response(
            {
                "data": [{"embedding": [0.25, -0.5, 0.75]}],
                "model": "text-embedding-3-small",
                "usage": {
                    "prompt_tokens": 4,
                    "total_tokens": 4,
                },
            }
        )

    response = request_embedding(_config(), "Evidence test", post=post)

    assert response.vector == (0.25, -0.5, 0.75)
    assert response.response_model == "text-embedding-3-small"


def test_request_embedding_probe_rejects_dimension_mismatch() -> None:
    def post(url: str, **kwargs: object) -> _Response:
        return _Response(
            {
                "data": [{"embedding": [0.25, -0.5]}],
                "usage": {
                    "prompt_tokens": 4,
                    "total_tokens": 4,
                },
            }
        )

    with pytest.raises(AzureEmbeddingError, match="2 dimensions; expected 3"):
        request_embedding_probe(_config(), "Evidence test", post=post)


def test_request_embedding_probe_surfaces_safe_azure_error() -> None:
    def post(url: str, **kwargs: object) -> _Response:
        return _Response(
            {"error": {"message": "Deployment was not found."}},
            status_code=404,
        )

    with pytest.raises(
        AzureEmbeddingError,
        match="Azure returned HTTP 404: Deployment was not found",
    ):
        request_embedding_probe(_config(), "Evidence test", post=post)


def test_request_embedding_retries_transient_http_error() -> None:
    responses = iter(
        (
            _Response(
                {"error": {"message": "Temporary gateway failure."}},
                status_code=502,
            ),
            _Response(
                {
                    "data": [{"embedding": [0.25, -0.5, 0.75]}],
                    "model": "text-embedding-3-small",
                    "usage": {
                        "prompt_tokens": 4,
                        "total_tokens": 4,
                    },
                }
            ),
        )
    )
    times = iter((1.0, 1.1, 2.0, 2.2))
    delays: list[float] = []

    response = request_embedding_with_retry(
        _config(),
        "Evidence test",
        post=lambda url, **kwargs: next(responses),
        timer=lambda: next(times),
        sleep=delays.append,
    )

    assert response.vector == (0.25, -0.5, 0.75)
    assert response.latency_ms == pytest.approx(300.0)
    assert delays == [1.0]
