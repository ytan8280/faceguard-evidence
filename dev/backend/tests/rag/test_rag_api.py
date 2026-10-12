from __future__ import annotations

from fastapi.testclient import TestClient

from dev.backend.app import rag_api
from dev.backend.app.rag.evidence_generation import (
    DetectorAssessment,
    FaceGuardEvidenceReportAnswer,
)
from dev.backend.app.rag.evidence_report_models import (
    EvidencePipelineConfiguration,
    EvidencePipelineMetrics,
    EvidenceReportResponse,
)


def _fake_response(question: str) -> EvidenceReportResponse:
    return EvidenceReportResponse(
        question=question,
        report=FaceGuardEvidenceReportAnswer(
            schema_version="faceguard-evidence-report-answer-v2",
            overall_assessment="requires_verification",
            observed_facts=[],
            detector_output=DetectorAssessment(
                statement="Detector output requires verification.",
                detector_ids=["DET-1"],
                caveats=[],
            ),
            retrieved_evidence=[],
            supported_conclusions=[],
            unsupported_conclusions=[],
            recommended_verification_steps=[],
        ),
        evidence=[],
        metrics=EvidencePipelineMetrics(
            query_embedding_tokens=1,
            query_embedding_cost="0.0",
            query_embedding_latency_ms=1.0,
            lexical_latency_ms=1.0,
            semantic_latency_ms=1.0,
            reranker_latency_ms=1.0,
            generation_input_tokens=1,
            generation_cached_input_tokens=0,
            generation_output_tokens=1,
            generation_cost="0.0",
            generation_latency_ms=1.0,
            total_measured_cost="0.0",
        ),
        configuration=EvidencePipelineConfiguration(
            pipeline_version="faceguard-evidence-report-v1",
            corpus_sha256="A" * 64,
            lexical_retriever_version="lexical",
            semantic_retriever_version="semantic",
            candidate_limit_per_retriever=20,
            reranker_version="reranker",
            prompt_version="prompt",
            answer_schema_version="schema",
            embedding_model="embedding",
            generation_model="generation",
        ),
    )


def test_build_report_endpoint_uses_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(
        rag_api.psycopg,
        "connect",
        lambda *args, **kwargs: _ConnectionContext(),
    )
    monkeypatch.setattr(
        rag_api,
        "build_evidence_report",
        lambda connection, request, **kwargs: _fake_response(
            request.question
        ),
    )
    rag_api.app.state.database_url = "postgresql://test"
    rag_api.app.state.embedding_config = object()
    rag_api.app.state.embedding_pricing = object()
    rag_api.app.state.reranker = object()
    rag_api.app.state.generation_config = object()
    rag_api.app.state.generation_pricing = object()

    client = TestClient(rag_api.app)
    response = client.post(
        "/build-report",
        json={
            "question": "What can be concluded?",
            "observations": [
                {
                    "observation_id": "OBS-1",
                    "statement": "The file is a JPEG.",
                }
            ],
            "detector_output": {
                "detector_id": "DET-1",
                "model_name": "vit3",
                "label": "FAKE",
                "fake_probability": 0.9,
                "threshold": 0.25,
                "limitations": [],
                "adapter_version": "adapter-v1",
                "preprocessing_version": "preprocessing-v1",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["question"] == "What can be concluded?"


class _ConnectionContext:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None
