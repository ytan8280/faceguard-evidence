from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PIL import Image
import torch

from .model_service import PredictionResult
from .preprocessing import crop_largest_face, image_to_tensor


DETECTOR_ADAPTER_VERSION = "faceguard-detector-adapter-v1"
PREPROCESSING_VERSION = "faceguard-rgb-resize-normalize-v1"


@dataclass(frozen=True)
class DetectorResult:
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


class InferenceBackend(Protocol):
    model_ready: bool
    model_name: str
    image_size: int
    device: torch.device
    mean: tuple[float, ...]
    std: tuple[float, ...]

    def ensure_loaded(self) -> None: ...

    def predict(
        self,
        image_tensor: torch.Tensor,
        source_image: Image.Image | None = None,
    ) -> PredictionResult: ...


class FaceGuardDetectorAdapterV1:
    """Stable boundary around the imported FaceGuard inference service."""

    def __init__(
        self,
        inference_service: InferenceBackend,
        *,
        enable_face_crop: bool,
        face_crop_margin: float,
    ) -> None:
        self._inference_service = inference_service
        self._enable_face_crop = enable_face_crop
        self._face_crop_margin = face_crop_margin

    @property
    def model_ready(self) -> bool:
        return self._inference_service.model_ready

    @property
    def model_name(self) -> str:
        return self._inference_service.model_name

    def ensure_ready(self) -> None:
        self._inference_service.ensure_loaded()

    def analyze(self, image: Image.Image) -> DetectorResult:
        self.ensure_ready()
        inference_image = crop_largest_face(
            image=image,
            enabled=self._enable_face_crop,
            margin=self._face_crop_margin,
        )
        tensor = image_to_tensor(
            image=inference_image,
            image_size=self._inference_service.image_size,
            device=self._inference_service.device,
            mean=self._inference_service.mean,
            std=self._inference_service.std,
        )
        prediction = self._inference_service.predict(
            image_tensor=tensor,
            source_image=inference_image,
        )
        return self._to_detector_result(prediction)

    @staticmethod
    def _to_detector_result(prediction: PredictionResult) -> DetectorResult:
        return DetectorResult(
            label=prediction.label,
            confidence=prediction.confidence,
            fake_probability=prediction.fake_probability,
            threshold=prediction.threshold,
            explanation=prediction.explanation,
            model_name=prediction.model_name,
            heatmap_overlay=prediction.heatmap_overlay,
            explainability_method=prediction.explainability_method,
            adapter_version=DETECTOR_ADAPTER_VERSION,
            preprocessing_version=PREPROCESSING_VERSION,
        )
