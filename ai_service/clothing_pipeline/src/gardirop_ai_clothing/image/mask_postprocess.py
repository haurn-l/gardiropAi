"""Conservative alpha-mask cleanup and garment cropping."""

import math
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from gardirop_ai_clothing.errors import ImageProcessingError


@dataclass(frozen=True, slots=True)
class MaskCleanupConfig:
    """Thresholds for conservative disconnected-component cleanup."""

    alpha_threshold: int = 8
    max_component_area_ratio: float = 0.01
    min_distance_fraction: float = 0.03
    max_removed_alpha_fraction: float = 0.01

    def __post_init__(self) -> None:
        if not 0 <= self.alpha_threshold < 255:
            raise ValueError("Invalid alpha threshold.")

        for name in (
            "max_component_area_ratio",
            "min_distance_fraction",
            "max_removed_alpha_fraction",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"Invalid mask configuration: {name}")


@dataclass(frozen=True, slots=True)
class MaskCleanupResult:
    alpha: np.ndarray
    removed_components: int
    removed_pixels: int
    removed_alpha_fraction: float
    reason: str


def _validate_alpha(alpha: np.ndarray) -> None:
    if (
        not isinstance(alpha, np.ndarray)
        or alpha.ndim != 2
        or alpha.dtype != np.uint8
        or not all(alpha.shape)
    ):
        raise ImageProcessingError("Alpha mask must be a non-empty 2D uint8 array.")


def clean_alpha_mask(
    alpha: np.ndarray,
    config: MaskCleanupConfig | None = None,
) -> MaskCleanupResult:
    """
    Remove only sufficiently small and distant alpha components.

    The largest connected foreground component is always preserved.
    Soft alpha values are retained outside removed regions.

    Cleanup is skipped entirely if its alpha-removal safety limit
    would be exceeded.
    """
    _validate_alpha(alpha)

    config = config or MaskCleanupConfig()
    support = np.ascontiguousarray((alpha > config.alpha_threshold).astype(np.uint8))

    if not np.any(support):
        raise ImageProcessingError("Alpha mask has no foreground pixels.")

    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        support,
        connectivity=8,
    )

    def unchanged(reason: str) -> MaskCleanupResult:
        return MaskCleanupResult(
            alpha=alpha.copy(),
            removed_components=0,
            removed_pixels=0,
            removed_alpha_fraction=0.0,
            reason=reason,
        )

    # Background + one foreground component.
    if count <= 2:
        return unchanged("single_component")

    main = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, width, height, main_area = map(int, stats[main])

    diagonal = math.hypot(*alpha.shape)
    candidates: list[int] = []

    for label in range(1, count):
        if label == main:
            continue

        x2, y2, width2, height2, area2 = map(int, stats[label])

        dx = max(
            x - (x2 + width2),
            x2 - (x + width),
            0,
        )
        dy = max(
            y - (y2 + height2),
            y2 - (y + height),
            0,
        )

        distance = math.hypot(dx, dy) / diagonal
        small_enough = area2 <= config.max_component_area_ratio * main_area
        far_enough = distance >= config.min_distance_fraction

        if small_enough and far_enough:
            candidates.append(label)

    if not candidates:
        return unchanged("no_eligible_components")

    removed = np.isin(labels, candidates)

    # Remove very low-alpha halos around rejected components.
    halo = cv2.dilate(
        removed.astype(np.uint8),
        np.ones((5, 5), dtype=np.uint8),
    ).astype(bool)

    erase = removed | (halo & (alpha <= config.alpha_threshold))

    total_mass = float(alpha.sum(dtype=np.float64))
    removed_mass = float(alpha[erase].sum(dtype=np.float64))
    removed_fraction = removed_mass / total_mass

    if removed_fraction > config.max_removed_alpha_fraction:
        return unchanged("safety_limit_exceeded")

    cleaned = alpha.copy()
    cleaned[erase] = 0

    return MaskCleanupResult(
        alpha=cleaned,
        removed_components=len(candidates),
        removed_pixels=int(np.count_nonzero(alpha[erase])),
        removed_alpha_fraction=removed_fraction,
        reason="cleaned",
    )


def create_cropped_rgba(
    rgb: Image.Image,
    alpha: np.ndarray,
    *,
    padding_fraction: float = 0.02,
    alpha_threshold: int = 8,
) -> Image.Image:
    """
    Apply an alpha mask to an RGB image and crop to its foreground.

    The original colors and surviving soft alpha values are kept.
    No illumination correction or resizing is performed.
    """
    if rgb.mode != "RGB":
        raise ImageProcessingError("Expected an RGB source image.")

    _validate_alpha(alpha)

    if alpha.shape != (rgb.height, rgb.width):
        raise ImageProcessingError("Alpha dimensions do not match the source image.")

    if not math.isfinite(padding_fraction) or not 0 <= padding_fraction <= 0.5:
        raise ImageProcessingError("Invalid crop padding.")

    if not 0 <= alpha_threshold < 255:
        raise ImageProcessingError("Invalid crop alpha threshold.")

    support = alpha > alpha_threshold
    rows = np.flatnonzero(support.any(axis=1))
    columns = np.flatnonzero(support.any(axis=0))

    if not len(columns):
        raise ImageProcessingError("Cannot crop an empty foreground mask.")

    padding_x = round(rgb.width * padding_fraction)
    padding_y = round(rgb.height * padding_fraction)

    box = (
        max(0, int(columns[0]) - padding_x),
        max(0, int(rows[0]) - padding_y),
        min(rgb.width, int(columns[-1]) + 1 + padding_x),
        min(rgb.height, int(rows[-1]) + 1 + padding_y),
    )

    # Crop before allocating four-channel pixels; this keeps the exact source
    # RGB and soft alpha while avoiding a full-frame RGBA intermediate.
    rgba = rgb.crop(box).convert("RGBA")
    rgba.putalpha(Image.fromarray(alpha, mode="L").crop(box))
    return rgba
