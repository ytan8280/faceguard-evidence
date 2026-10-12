from __future__ import annotations

from PIL import Image
import torch

from dev.backend.app.services.detector_adapter import (
    DETECTOR_ADAPTER_VERSION,
    PREPROCESSING_VERSION,
    FaceGuardDetectorAdapterV1,
)
from dev.backend.app.services.model_service import PredictionResult


class FakeInferenceService:
    model_ready = False
    model_name = "vit3"
    image_size = 8
    device = torch.device("cpu")
    mean = (0.485, 0.456, 0.406)
    std = (0.229, 0.224, 0.225)

    def __init__(self) -> None:
        self.received_tensor: torch.Tensor | None = None
        self.received_image: Image.Image | None = None

    def ensure_loaded(self) -> None:
        self.model_ready = True

    def predict(
        self,
        image_tensor: torch.Tensor,
        source_image: Image.Image | None = None,
    ) -> PredictionResult:
        self.received_tensor = image_tensor
        self.received_image = source_image
        return PredictionResult(
            label="FAKE",
            confidence=0.8,
            fake_probability=0.8,
            threshold=0.25,
            explanation="Detector output for regression testing.",
            model_name=self.model_name,
            heatmap_overlay=None,
            explainability_method="none",
        )


def test_adapter_preserves_preprocessing_and_maps_detector_result() -> None:
    inference_service = FakeInferenceService()
    adapter = FaceGuardDetectorAdapterV1(
        inference_service,
        enable_face_crop=False,
        face_crop_margin=0.35,
    )

    result = adapter.analyze(Image.new("RGB", (12, 10), color=(120, 80, 40)))

    assert inference_service.model_ready is True
    assert inference_service.received_tensor is not None
    assert inference_service.received_tensor.shape == (1, 3, 8, 8)
    assert inference_service.received_image is not None
    assert inference_service.received_image.size == (12, 10)
    assert result.label == "FAKE"
    assert result.fake_probability == 0.8
    assert result.model_name == "vit3"
    assert result.adapter_version == DETECTOR_ADAPTER_VERSION
    assert result.preprocessing_version == PREPROCESSING_VERSION
