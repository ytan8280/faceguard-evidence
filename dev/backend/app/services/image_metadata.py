from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import string

from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError


class ImageMetadataError(ValueError):
    """Raised when safe still-image metadata cannot be extracted."""


@dataclass(frozen=True, slots=True)
class ImageObservation:
    observation_id: str
    statement: str


@dataclass(frozen=True, slots=True)
class ImageMetadataResult:
    format_name: str
    width: int
    height: int
    color_mode: str
    file_size_bytes: int
    has_exif: bool
    software: str | None
    captured_at: str | None
    gps_present: bool
    content_credentials_status: str
    observations: tuple[ImageObservation, ...]


def load_clean_rgb_image(raw: bytes) -> Image.Image:
    try:
        with Image.open(BytesIO(raw)) as source:
            transposed = ImageOps.exif_transpose(source)
            return transposed.convert("RGB")
    except (OSError, UnidentifiedImageError) as exc:
        raise ImageMetadataError(
            "Unable to decode the uploaded still image."
        ) from exc


def _safe_metadata_text(value: object, *, max_length: int = 160) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    printable = "".join(
        character
        for character in normalized
        if character in string.printable and character not in "\r\n\t"
    ).strip()
    if not printable:
        return None
    return printable[:max_length]


def extract_image_metadata(
    raw: bytes,
    *,
    content_type: str,
) -> ImageMetadataResult:
    try:
        with Image.open(BytesIO(raw)) as source:
            source.load()
            frame_count = int(getattr(source, "n_frames", 1))
            if frame_count != 1:
                raise ImageMetadataError(
                    "FaceGuard Evidence currently supports one-frame still "
                    "images only."
                )
            format_name = (source.format or "unknown").upper()
            width, height = source.size
            color_mode = source.mode
            exif = source.getexif()
    except ImageMetadataError:
        raise
    except (OSError, UnidentifiedImageError) as exc:
        raise ImageMetadataError(
            "Unable to read still-image metadata."
        ) from exc

    if width <= 0 or height <= 0:
        raise ImageMetadataError("Image dimensions must be positive.")

    exif_by_name = {
        str(ExifTags.TAGS.get(tag_id, tag_id)): value
        for tag_id, value in exif.items()
    }
    software = _safe_metadata_text(exif_by_name.get("Software"))
    captured_at = _safe_metadata_text(
        exif_by_name.get("DateTimeOriginal")
        or exif_by_name.get("DateTimeDigitized")
        or exif_by_name.get("DateTime")
    )
    gps_present = bool(exif_by_name.get("GPSInfo"))

    observations = [
        ImageObservation(
            observation_id="OBS-1",
            statement=(
                f"The uploaded file is a {format_name} still image with MIME "
                f"type {content_type}."
            ),
        ),
        ImageObservation(
            observation_id="OBS-2",
            statement=(
                f"The image dimensions are {width} by {height} pixels and "
                f"the decoded color mode is {color_mode}."
            ),
        ),
        ImageObservation(
            observation_id="OBS-3",
            statement=f"The uploaded file size is {len(raw)} bytes.",
        ),
        ImageObservation(
            observation_id="OBS-4",
            statement=(
                "EXIF metadata is present."
                if exif
                else "No EXIF metadata was present in the decoded file."
            ),
        ),
        ImageObservation(
            observation_id="OBS-5",
            statement=(
                "Content Credentials were not inspected by this metadata "
                "extractor; their presence or absence is unknown."
            ),
        ),
    ]
    next_id = 6
    if software is not None:
        observations.append(
            ImageObservation(
                observation_id=f"OBS-{next_id}",
                statement=f"The EXIF software field is {software}.",
            )
        )
        next_id += 1
    if captured_at is not None:
        observations.append(
            ImageObservation(
                observation_id=f"OBS-{next_id}",
                statement=(
                    f"The EXIF capture or modification timestamp is "
                    f"{captured_at}."
                ),
            )
        )
        next_id += 1
    if gps_present:
        observations.append(
            ImageObservation(
                observation_id=f"OBS-{next_id}",
                statement=(
                    "GPS metadata is present, but precise coordinates are "
                    "not included in the generated evidence prompt."
                ),
            )
        )

    return ImageMetadataResult(
        format_name=format_name,
        width=width,
        height=height,
        color_mode=color_mode,
        file_size_bytes=len(raw),
        has_exif=bool(exif),
        software=software,
        captured_at=captured_at,
        gps_present=gps_present,
        content_credentials_status="not_inspected",
        observations=tuple(observations),
    )
