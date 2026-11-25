"""Shared image preparation pipeline for GardropAI."""

import math
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from PIL import Image

from gardirop_ai_clothing.errors import ConfigurationError, ImageProcessingError
from gardirop_ai_clothing.image.canonical_view import (
    canonicalize_garment,
)
from gardirop_ai_clothing.image.io import (
    DEFAULT_MAX_PIXELS,
    DEFAULT_MAX_UPLOAD_BYTES,
    WHITE_OUTPUT_PROFILE,
    decode_uploaded_image,
    encode_transparent_webp,
    encode_white_webp,
)
from gardirop_ai_clothing.image.mask_postprocess import (
    clean_alpha_mask,
    create_cropped_rgba,
)


class AlphaSegmenter(Protocol):
    """Interface implemented by BiRefNetSegmenter."""

    def predict_alpha(self, image: Image.Image) -> np.ndarray:
        """Return an H x W uint8 alpha mask."""
        ...


@dataclass(frozen=True, slots=True)
class ImagePreparationOptions:
    """Configuration for one clothing photograph."""

    use_cleanup: bool = False
    auto_align: bool = False
    manual_rotation: float = 0.0
    padding: int = 16
    square_margin_fraction: float = 0.10

    def __post_init__(self):
        if not math.isfinite(self.manual_rotation):
            raise ConfigurationError("Rotation must be finite.")
        if isinstance(self.padding, bool) or not isinstance(self.padding, int) or self.padding < 0:
            raise ConfigurationError("Padding must be a non-negative integer.")
        if (
            not math.isfinite(self.square_margin_fraction)
            or not 0 <= self.square_margin_fraction <= 0.5
        ):
            raise ConfigurationError("White canvas margin must be between 0 and 0.5.")


@dataclass(frozen=True, slots=True)
class PreparedGarmentImage:
    """All image products generated from one photograph."""

    source_size: tuple[int, int]

    raw_alpha: np.ndarray
    final_alpha: np.ndarray

    original_cutout: Image.Image
    aligned_rgba: Image.Image
    white_rgb: Image.Image
    # Compact API jobs keep RGBA pixels for analysis but omit this unused encoding.
    transparent_webp: bytes | None

    cleanup_reason: str
    removed_components: int
    removed_pixels: int
    removed_alpha_fraction: float

    orientation_method: str
    rotation_degrees: float
    orientation_margin: float | None

    # None only when reading pre-migration immutable transparent records.
    white_webp: bytes | None = None

    @property
    def output_size(self) -> tuple[int, int]:
        return self.white_rgb.size

    @property
    def delivery_webp(self) -> bytes:
        """Primary stored/exported bytes; preserve old confirmed records verbatim."""
        if self.white_webp is not None:
            return self.white_webp
        if self.transparent_webp is None:
            raise ImageProcessingError("No delivery image was encoded.")
        return self.transparent_webp

    @property
    def delivery_profile(self) -> str:
        return (
            WHITE_OUTPUT_PROFILE["profile"]
            if self.white_webp is not None
            else "legacy-transparent-webp"
        )


@dataclass(frozen=True, slots=True)
class PreparedGarmentPair:
    """Prepared front and back photographs of one garment."""

    front: PreparedGarmentImage
    back: PreparedGarmentImage


class ClothingImagePipeline:
    """
    Shared preprocessing orchestration.

    The segmenter is injected rather than loaded internally.

    This class does not persist files or interact with a database.
    Callers are responsible for GPU concurrency control.
    """

    def __init__(
        self,
        segmenter: AlphaSegmenter,
        *,
        max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
        max_pixels: int = DEFAULT_MAX_PIXELS,
        default_options: ImagePreparationOptions | None = None,
        include_transparent_webp: bool = True,
    ) -> None:
        if any(
            isinstance(n, bool) or not isinstance(n, int) or n < 1
            for n in (max_upload_bytes, max_pixels)
        ):
            raise ConfigurationError("Image input limits must be positive integers.")
        self.include_transparent_webp = include_transparent_webp
        self._segmenter = segmenter
        self.max_upload_bytes = max_upload_bytes
        self.max_pixels = max_pixels
        self.default_options = default_options or ImagePreparationOptions()

    def prepare_photo(
        self,
        image_bytes: bytes,
        *,
        options: ImagePreparationOptions | None = None,
    ) -> PreparedGarmentImage:
        """Prepare a single clothing photograph."""

        options = options or self.default_options

        # 1. Decode, apply EXIF orientation, convert to RGB.
        rgb = decode_uploaded_image(
            image_bytes,
            max_upload_bytes=self.max_upload_bytes,
            max_pixels=self.max_pixels,
        )

        # 2. Predict a soft alpha mask with BiRefNet.
        predicted = self._segmenter.predict_alpha(rgb)

        if (
            not isinstance(predicted, np.ndarray)
            or predicted.ndim != 2
            or predicted.dtype != np.uint8
            or predicted.shape != (rgb.height, rgb.width)
        ):
            raise ImageProcessingError("Segmenter returned an invalid alpha mask.")

        raw_alpha = predicted.copy()

        if not np.any(raw_alpha > 8):
            raise ImageProcessingError("Segmenter returned an empty foreground.")

        # 3. Optional conservative A15 cleanup.
        cleanup_reason = "disabled"
        removed_components = 0
        removed_pixels = 0
        removed_fraction = 0.0

        if options.use_cleanup:
            cleanup = clean_alpha_mask(raw_alpha)

            final_alpha = cleanup.alpha
            cleanup_reason = cleanup.reason
            removed_components = cleanup.removed_components
            removed_pixels = cleanup.removed_pixels
            removed_fraction = cleanup.removed_alpha_fraction
        else:
            final_alpha = raw_alpha.copy()

        # 4. Apply mask to the original RGB image and crop.
        original_cutout = create_cropped_rgba(
            rgb,
            final_alpha,
        )

        # 5. Orientation correction and white background.
        canonical = canonicalize_garment(
            original_cutout,
            auto_align=options.auto_align,
            manual_rotation=options.manual_rotation,
            padding=options.padding,
            square_margin_fraction=options.square_margin_fraction,
        )

        # 6. Main output is actual white RGB WebP; RGBA stays internal for mask/color diagnostics.
        transparent_webp = (
            encode_transparent_webp(canonical.rgba) if self.include_transparent_webp else None
        )

        return PreparedGarmentImage(
            source_size=rgb.size,
            raw_alpha=raw_alpha,
            final_alpha=final_alpha,
            original_cutout=original_cutout,
            aligned_rgba=canonical.rgba,
            white_rgb=canonical.white_rgb,
            transparent_webp=transparent_webp,
            white_webp=encode_white_webp(canonical.white_rgb),
            cleanup_reason=cleanup_reason,
            removed_components=removed_components,
            removed_pixels=removed_pixels,
            removed_alpha_fraction=removed_fraction,
            orientation_method=canonical.method,
            rotation_degrees=canonical.rotation_degrees,
            orientation_margin=canonical.orientation_margin,
        )

    def prepare_pair(
        self,
        front_bytes: bytes,
        back_bytes: bytes,
        *,
        front_options: ImagePreparationOptions | None = None,
        back_options: ImagePreparationOptions | None = None,
    ) -> PreparedGarmentPair:
        """
        Prepare two independent views of the same garment.

        Each view can have a different orientation and cleanup
        configuration.
        """
        front = self.prepare_photo(
            front_bytes,
            options=front_options,
        )

        back = self.prepare_photo(
            back_bytes,
            options=back_options,
        )

        return PreparedGarmentPair(
            front=front,
            back=back,
        )
