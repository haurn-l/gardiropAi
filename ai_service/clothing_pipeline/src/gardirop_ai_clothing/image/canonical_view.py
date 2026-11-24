"""Conservative garment orientation and white-background rendering."""

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image

from gardirop_ai_clothing.errors import ImageProcessingError
from gardirop_ai_clothing.image.io import composite_rgba_on_white


@dataclass(frozen=True)
class CanonicalView:
    rgba: Image.Image
    white_rgb: Image.Image
    rotation_degrees: float
    method: str
    axis_ratio: float | None = None
    orientation_margin: float | None = None


@dataclass(frozen=True)
class _ShapeScore:
    angle: int
    score: float
    shoulder_excess: float
    hem_flatness: float


CARDINAL_ANGLES = (0, 90, -90, 180)


def _rotate_rgba(
    image: Image.Image,
    angle: float,
) -> Image.Image:
    """
    Use lossless pixel transposition for multiples of 90 degrees.

    Other angles use interpolation.
    PIL positive angles rotate counterclockwise.
    """
    if abs(angle) < 1e-6:
        return image.copy()

    rounded = round(angle)

    if abs(angle - rounded) < 1e-6 and rounded % 90 == 0:
        quarter = rounded % 360

        operations = {
            90: Image.Transpose.ROTATE_90,
            180: Image.Transpose.ROTATE_180,
            270: Image.Transpose.ROTATE_270,
        }

        if quarter == 0:
            return image.copy()

        return image.transpose(operations[quarter])

    return image.rotate(
        angle,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=(255, 255, 255, 0),
    )


def _score_upper_orientation(
    alpha: Image.Image,
    angle: int,
) -> _ShapeScore | None:
    """
    Score how much a mask resembles an upright upper garment.

    Uses:
      - upper shoulder/sleeve width relative to lower torso
      - broad, approximately straight bottom hem
      - penalty for a broad, flat upper edge

    This is a geometric heuristic, not a learned classifier.
    """
    if alpha.mode != "L":
        raise ImageProcessingError("Expected grayscale alpha.")

    support = alpha.point(lambda value: 255 if value > 16 else 0)

    bounds = support.getbbox()

    if bounds is None:
        return None

    # Work at a fixed low resolution for cheap CPU inference.
    normalized = support.crop(bounds).resize(
        (128, 128),
        resample=Image.Resampling.NEAREST,
    )

    mask = np.asarray(normalized) > 0

    if int(mask.sum()) < 100:
        return None

    widths = np.empty(128, dtype=np.float32)

    for row in range(128):
        columns = np.flatnonzero(mask[row])

        if len(columns):
            widths[row] = float(columns[-1] - columns[0]) + 1.0
        else:
            widths[row] = 0.0

    # Upper part: shoulders and sleeves.
    upper_width = float(np.quantile(widths[20:52], 0.80)) / 128.0

    # Lower part: torso approaching the bottom hem.
    lower_width = float(np.median(widths[78:112])) / 128.0

    shoulder_excess = upper_width - lower_width

    valid_columns = mask.any(axis=0)

    first_pixels = np.where(
        valid_columns,
        np.argmax(mask, axis=0),
        128,
    )

    last_pixels = np.where(
        valid_columns,
        127 - np.argmax(mask[::-1], axis=0),
        -1,
    )

    # Fraction of columns touching the lower edge region.
    hem_flatness = float(np.mean(valid_columns & (last_pixels >= 123)))

    # Broad upper flat edges are less typical of an upright
    # shirt than a straight bottom hem.
    upper_flatness = float(np.mean(valid_columns & (first_pixels <= 4)))

    score = shoulder_excess + 2.2 * hem_flatness - 1.2 * upper_flatness

    return _ShapeScore(
        angle=angle,
        score=float(score),
        shoulder_excess=shoulder_excess,
        hem_flatness=hem_flatness,
    )


def _estimate_upper_rotation(
    rgba: Image.Image,
) -> tuple[float | None, float | None]:
    """
    Compare four cardinal orientations.

    Return (angle, score_margin).

    A rotation is accepted only when the best candidate has
    recognizable upper-garment geometry and sufficiently
    exceeds competing orientation scores.
    """
    alpha = rgba.getchannel("A")

    # Downsample before evaluating orientation candidates.
    alpha_small = alpha.copy()
    alpha_small.thumbnail(
        (256, 256),
        resample=Image.Resampling.NEAREST,
    )

    scores = []

    for angle in CARDINAL_ANGLES:
        rotated = _rotate_rgba(
            alpha_small,
            angle,
        )

        result = _score_upper_orientation(
            rotated,
            angle,
        )

        if result is not None:
            scores.append(result)

    if len(scores) < 2:
        return None, None

    scores.sort(
        key=lambda item: item.score,
        reverse=True,
    )

    best = scores[0]
    runner_up = scores[1]

    margin = best.score - runner_up.score

    # Conservative acceptance guards.
    if margin < 0.18 or best.shoulder_excess < 0.10 or best.hem_flatness < 0.27:
        return None, float(margin)

    return float(best.angle), float(margin)


def canonicalize_garment(
    rgba: Image.Image,
    *,
    auto_align: bool = True,
    manual_rotation: float = 0.0,
    padding: int = 16,
    square_margin_fraction: float = 0.10,
) -> CanonicalView:
    """
    Normalize garment orientation and create a white square.

    The transparent RGBA image is preserved separately.

    Automatic orientation is currently designed for
    upper-garment silhouettes.

    Manual rotation overrides automatic estimation.
    """
    if not isinstance(rgba, Image.Image) or rgba.mode != "RGBA":
        raise ImageProcessingError("Canonicalization requires an RGBA image.")

    if not math.isfinite(manual_rotation):
        raise ImageProcessingError("Invalid rotation angle.")

    if not isinstance(padding, int) or padding < 0:
        raise ImageProcessingError("Padding must be a non-negative integer.")

    if not math.isfinite(square_margin_fraction) or not 0 <= square_margin_fraction <= 0.5:
        raise ImageProcessingError("Invalid white canvas margin.")

    if rgba.getchannel("A").getbbox() is None:
        raise ImageProcessingError("Garment alpha is empty.")

    angle = 0.0
    method = "unchanged"
    margin = None

    # Manual override has priority.
    if abs(manual_rotation) > 1e-6:
        angle = float(manual_rotation)
        method = "manual"

    elif auto_align:
        estimated_angle, margin = _estimate_upper_rotation(rgba)

        if estimated_angle is None:
            method = "auto_skipped_low_confidence"

        else:
            angle = estimated_angle

            if abs(angle) < 1e-6:
                method = "auto_already_upright"
            else:
                method = "automatic_upper_silhouette"

    # Apply orientation exactly for cardinal angles.
    rotated = _rotate_rgba(
        rgba,
        angle,
    )

    bounds = rotated.getchannel("A").getbbox()

    if bounds is None:
        raise ImageProcessingError("Garment disappeared after rotation.")

    left, top, right, bottom = bounds

    crop_box = (
        max(0, left - padding),
        max(0, top - padding),
        min(rotated.width, right + padding),
        min(rotated.height, bottom + padding),
    )

    aligned_rgba = rotated.crop(crop_box)

    # Convert transparent edges to a real white background.
    white_garment = composite_rgba_on_white(aligned_rgba)

    # Colab-compatible: centered white square with
    # 10% margin on each side relative to garment size.
    side = math.ceil(max(white_garment.size) * (1.0 + 2.0 * square_margin_fraction))

    square = Image.new(
        "RGB",
        (side, side),
        (255, 255, 255),
    )

    offset_x = (side - white_garment.width) // 2
    offset_y = (side - white_garment.height) // 2

    square.paste(
        white_garment,
        (offset_x, offset_y),
    )

    return CanonicalView(
        rgba=aligned_rgba,
        white_rgb=square,
        rotation_degrees=float(angle),
        method=method,
        axis_ratio=None,
        orientation_margin=margin,
    )
