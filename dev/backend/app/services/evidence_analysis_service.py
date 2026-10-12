from __future__ import annotations

from typing import Protocol

from PIL import Image

from ..rag.evidence_report_models import (
    EvidenceReportRequest,
    EvidenceReportResponse,
)
from ..schemas import (
    EvidenceAnalysisResponse,
    EvidenceDetectorResponse,
    EvidenceImageMetadataResponse,
)
from .image_metadata import (
    extract_image_metadata,
    load_clean_rgb_image,
)


class EvidenceDetectorResult(Protocol):
    label: str
    confidence: float
    fake_probability: float
    threshold: float
    explanation: str
    model_name: str
    heatmap_overlay: str | None
    explainability_method: str
    adapter_version: str
    preprocessing_version: str


class EvidenceDetector(Protocol):
    def analyze(self, image: Image.Image) -> EvidenceDetectorResult: ...


class EvidenceReportBuilder(Protocol):
    def build_report(
        self,
        payload: EvidenceReportRequest,
    ) -> EvidenceReportResponse: ...


def build_evidence_analysis(
    *,
    raw: bytes,
    content_type: str,
    question: str,
    detector: EvidenceDetector,
    report_builder: EvidenceReportBuilder,
) -> EvidenceAnalysisResponse:
    metadata = extract_image_metadata(raw, content_type=content_type)
    image = load_clean_rgb_image(raw)
    result = detector.analyze(image)
    evidence_report = report_builder.build_report(
        EvidenceReportRequest(
            question=question,
            observations=[
                {
                    "observation_id": item.observation_id,
                    "statement": item.statement,
                }
                for item in metadata.observations
            ],
            detector_output={
                "detector_id": "DET-1",
                "model_name": result.model_name,
                "label": result.label,
                "fake_probability": result.fake_probability,
                "threshold": result.threshold,
                "limitations": [
                    (
                        "The detector output is a probabilistic signal, not "
                        "proof of image origin or authenticity."
                    ),
                    (
                        "The active threshold is inherited and has not been "
                        "independently validated for FaceGuard Evidence."
                    ),
                    (
                        "The detector cannot establish depicted-person "
                        "identity, creator identity, generation tool, intent, "
                        "deception, or certainty."
                    ),
                ],
                "adapter_version": result.adapter_version,
                "preprocessing_version": result.preprocessing_version,
            },
        )
    )
    return EvidenceAnalysisResponse(
        metadata=EvidenceImageMetadataResponse(
            format_name=metadata.format_name,
            width=metadata.width,
            height=metadata.height,
            color_mode=metadata.color_mode,
            file_size_bytes=metadata.file_size_bytes,
            has_exif=metadata.has_exif,
            software=metadata.software,
            captured_at=metadata.captured_at,
            gps_present=metadata.gps_present,
            content_credentials_status=(
                metadata.content_credentials_status
            ),
        ),
        detector=EvidenceDetectorResponse(
            label=result.label,
            confidence=result.confidence,
            fake_probability=result.fake_probability,
            threshold=result.threshold,
            explanation=result.explanation,
            model_name=result.model_name,
            adapter_version=result.adapter_version,
            preprocessing_version=result.preprocessing_version,
            heatmap_overlay=result.heatmap_overlay,
            explainability_method=result.explainability_method,
        ),
        evidence_report=evidence_report,
    )
