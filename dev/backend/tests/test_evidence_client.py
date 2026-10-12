from __future__ import annotations

import pytest

from dev.backend.app.services.evidence_client import (
    EvidenceClientError,
    EvidenceReportClient,
)


def test_evidence_client_requires_local_or_private_url() -> None:
    with pytest.raises(EvidenceClientError, match="private"):
        EvidenceReportClient(base_url="https://example.com")


def test_evidence_client_accepts_localhost() -> None:
    client = EvidenceReportClient(base_url="http://localhost:8002/")

    assert client is not None


def test_evidence_client_accepts_private_compose_host() -> None:
    client = EvidenceReportClient(base_url="http://rag-api:8002")

    assert client is not None
