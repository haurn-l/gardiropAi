"""Tests for conservative mask cleanup and RGBA cropping."""

import numpy as np
import pytest
from PIL import Image

from gardirop_ai_clothing.errors import ImageProcessingError
from gardirop_ai_clothing.image.mask_postprocess import (
    MaskCleanupConfig,
    clean_alpha_mask,
    create_cropped_rgba,
)


def sample_mask() -> np.ndarray:
    alpha = np.zeros((100, 100), dtype=np.uint8)
    alpha[10:50, 10:50] = 255
    return alpha


def test_single_component_is_preserved():
    alpha = sample_mask()
    result = clean_alpha_mask(alpha)

    assert result.removed_components == 0
    assert result.reason == "single_component"
    assert np.array_equal(result.alpha, alpha)


def test_small_distant_component_is_removed():
    alpha = sample_mask()
    alpha[80:82, 80:82] = 255

    result = clean_alpha_mask(alpha)

    assert result.removed_components == 1
    assert result.removed_pixels == 4
    assert result.reason == "cleaned"
    assert np.all(result.alpha[80:82, 80:82] == 0)
    assert np.all(result.alpha[10:50, 10:50] == 255)


def test_nearby_component_is_preserved():
    alpha = sample_mask()
    alpha[51:53, 20:22] = 255

    result = clean_alpha_mask(alpha)

    assert result.removed_components == 0
    assert np.array_equal(result.alpha, alpha)


def test_large_distant_component_is_preserved():
    alpha = sample_mask()
    alpha[75:85, 75:85] = 255

    result = clean_alpha_mask(alpha)

    assert result.removed_components == 0
    assert np.array_equal(result.alpha, alpha)


def test_safety_limit_prevents_cleanup():
    alpha = sample_mask()
    alpha[80:82, 80:82] = 255

    config = MaskCleanupConfig(
        max_removed_alpha_fraction=0.0001,
    )

    result = clean_alpha_mask(alpha, config)

    assert result.reason == "safety_limit_exceeded"
    assert result.removed_components == 0
    assert np.array_equal(result.alpha, alpha)


def test_main_component_soft_alpha_is_preserved():
    alpha = sample_mask()
    alpha[20, 20] = 140
    alpha[80:82, 80:82] = 255

    result = clean_alpha_mask(alpha)

    assert result.alpha[20, 20] == 140
    assert result.alpha[80, 80] == 0


def test_empty_mask_is_rejected():
    alpha = np.zeros((20, 20), dtype=np.uint8)

    with pytest.raises(ImageProcessingError, match="foreground"):
        clean_alpha_mask(alpha)


def test_invalid_mask_type_is_rejected():
    alpha = np.zeros((10, 10), dtype=np.float32)

    with pytest.raises(ImageProcessingError, match="uint8"):
        clean_alpha_mask(alpha)


def test_crop_preserves_visible_color_and_alpha():
    rgb = Image.new("RGB", (100, 80), (80, 40, 180))
    alpha = np.zeros((80, 100), dtype=np.uint8)
    alpha[20:60, 30:70] = 255
    alpha[30, 40] = 120

    result = create_cropped_rgba(rgb, alpha)

    assert result.mode == "RGBA"
    assert result.size == (44, 44)
    assert result.getpixel((12, 12)) == (80, 40, 180, 120)
    assert result.getpixel((0, 0))[3] == 0


def test_crop_rejects_dimension_mismatch():
    rgb = Image.new("RGB", (100, 80))
    alpha = np.zeros((100, 100), dtype=np.uint8)

    with pytest.raises(
        ImageProcessingError,
        match="do not match",
    ):
        create_cropped_rgba(rgb, alpha)


def test_invalid_cleanup_configuration():
    with pytest.raises(ValueError):
        MaskCleanupConfig(max_component_area_ratio=-1)
