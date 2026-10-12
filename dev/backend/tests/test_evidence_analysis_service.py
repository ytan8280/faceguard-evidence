from __future__ import annotations

from io import BytesIO

from PIL import Image

from dev.backend.app.rag.evidence_generation import (
    DetectorAssessment,
    FaceGuardEvidenceReportAnswer,
)
from dev.backend.app.rag.evidence_report_models import (
    EvidencePipelineConfiguration,
    EvidencePipelineMetrics,
    EvidenceReportResponse,
)
from dev.backend.app.services.evidence_analysis_service import (
    build_evidence_analysis,
)


class FakeDetectorResult:
    label = "FAKE"
    confidence = 0.91
    fake_probability = 0.91
    threshold = 0.25
    explanation = "Fake detector result."
    model_name = "vit3"
    heatmap_overlay = None
    explainability_method = "none"
    adapter_version = "adapter-v1"
    preprocessing_version = "preprocessing-v1"


class FakeDetector:
    def analyze(self, image: Image.Image) -> FakeDetectorResult:
        assert image.mode == "RGB"
        return FakeDetectorResult()


class FakeReportBuilder:
    def build_report(self, payload):
        assert payload.question == "Could this identify the creator?"
        assert payload.observations[0].observation_id == "OBS-1"
        assert payload.detector_output.detector_id == "DET-1"
        return EvidenceReportResponse(
            question=payload.question,
            report=FaceGuardEvidenceReportAnswer(
                schema_version="faceguard-evidence-report-answer-v2",
                overall_assessment="insufficient_evidence",
                observed_facts=[],
                detector_output=DetectorAssessment(
                    statement="The detector returned FAKE.",
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
                pipeline_version="report-v1",
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


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (16, 12), color=(30, 60, 90)).save(
        buffer,
        format="PNG",
    )
    return buffer.getvalue()


def test_build_evidence_analysis_is_typed_and_versioned() -> None:
    result = build_evidence_analysis(
        raw=_png_bytes(),
        content_type="image/png",
        question="Could this identify the creator?",
        detector=FakeDetector(),
        report_builder=FakeReportBuilder(),
    )

    assert result.metadata.format_name == "PNG"
    assert result.metadata.width == 16
    assert result.detector.adapter_version == "adapter-v1"
    assert (
        result.evidence_report.report.overall_assessment
        == "insufficient_evidence"
    )
