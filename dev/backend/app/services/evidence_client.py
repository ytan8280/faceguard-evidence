from __future__ import annotations

import requests
from urllib.parse import urlsplit

from ..rag.evidence_report_models import (
    EvidenceReportRequest,
    EvidenceReportResponse,
)


class EvidenceClientError(RuntimeError):
    """Raised when the local RAG sidecar cannot build a report."""


class EvidenceReportClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 90.0,
    ) -> None:
        normalized = base_url.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost", "rag-api"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise EvidenceClientError(
                "RAG_API_URL must use loopback or the private rag-api host."
            )
        self._base_url = normalized
        self._timeout_seconds = timeout_seconds

    def build_report(
        self,
        payload: EvidenceReportRequest,
    ) -> EvidenceReportResponse:
        try:
            response = requests.post(
                f"{self._base_url}/build-report",
                json=payload.model_dump(mode="json"),
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            raise EvidenceClientError(
                "The local FaceGuard Evidence RAG service is unavailable."
            ) from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise EvidenceClientError(
                "The local FaceGuard Evidence RAG service failed with "
                f"HTTP {response.status_code}."
            )
        try:
            return EvidenceReportResponse.model_validate(response.json())
        except (requests.JSONDecodeError, ValueError) as exc:
            raise EvidenceClientError(
                "The local FaceGuard Evidence RAG service returned an "
                "invalid response."
            ) from exc
