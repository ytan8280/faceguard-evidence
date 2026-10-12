from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from dev.backend.app import main
from dev.backend.app.services.detector_adapter import DetectorResult


class FakeDetectorAdapter:
    model_ready = True
    model_name = "vit3"

    def ensure_ready(self) -> None:
        return

    def analyze(self, image: Image.Image) -> DetectorResult:
        assert image.mode == "RGB"
        return DetectorResult(
            label="FAKE",
            confidence=0.8765,
            fake_probability=0.8765,
            threshold=0.25,
            explanation="Detector output for endpoint regression testing.",
            model_name=self.model_name,
            heatmap_overlay=None,
            explainability_method="none",
            adapter_version="faceguard-detector-adapter-v1",
            preprocessing_version="faceguard-rgb-resize-normalize-v1",
        )


class FakeReportService:
    def build_report(self, image: Image.Image, fake_probability: float, label: str):
        assert image.mode == "RGB"
        assert fake_probability == 0.8765
        assert label == "FAKE"
        return {
            "image_type": "Uploaded Image",
            "overall_forgery_score": 87.7,
            "summary": "Baseline report for endpoint regression testing.",
            "breakdown": [],
        }


class NoWriteAuthService:
    def record_analysis_result(self, **_kwargs) -> None:
        raise AssertionError("Analysis history must not be written without an email.")


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (16, 12), color=(30, 60, 90)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_analyze_endpoint_preserves_response_contract(monkeypatch) -> None:
    monkeypatch.setattr(main, "detector_adapter", FakeDetectorAdapter())
    monkeypatch.setattr(main, "report_service", FakeReportService())
    monkeypatch.setattr(main, "auth_service", NoWriteAuthService())

    with TestClient(main.app) as client:
        response = client.post(
            "/api/analyze",
            files={"file": ("generated-test.png", _png_bytes(), "image/png")},
        )

    assert response.status_code == 200
    assert response.json() == {
        "label": "FAKE",
        "confidence": 0.8765,
        "fake_probability": 0.8765,
        "threshold": 0.25,
        "explanation": "Detector output for endpoint regression testing.",
        "model_name": "vit3",
        "heatmap_overlay": None,
        "explainability_method": "none",
        "report": {
            "image_type": "Uploaded Image",
            "overall_forgery_score": 87.7,
            "summary": "Baseline report for endpoint regression testing.",
            "breakdown": [],
        },
    }
