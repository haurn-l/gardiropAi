"""Tests for conservative four-way garment orientation."""

import math

import numpy as np
import pytest
from PIL import Image, ImageDraw

from gardirop_ai_clothing.errors import ImageProcessingError
from gardirop_ai_clothing.image.canonical_view import (
    canonicalize_garment,
)


def make_tshirt() -> Image.Image:
    image = Image.new(
        "RGBA",
        (320, 320),
        (255, 255, 255, 0),
    )

    draw = ImageDraw.Draw(image)

    points = [
        (140, 40),
        (120, 52),
        (95, 68),
        (48, 90),
        (75, 133),
        (104, 119),
        (108, 264),
        (213, 264),
        (215, 119),
        (242, 133),
        (272, 90),
        (225, 68),
        (200, 52),
        (180, 40),
        (168, 56),
        (151, 56),
    ]

    draw.polygon(
        points,
        fill=(30, 50, 80, 255),
    )

    return image


def make_asymmetric_polo() -> Image.Image:
    image = Image.new(
        "RGBA",
        (320, 320),
        (255, 255, 255, 0),
    )

    draw = ImageDraw.Draw(image)

    points = [
        (155, 35),
        (135, 50),
        (120, 55),
        (95, 60),
        (90, 78),
        (48, 93),
        (75, 139),
        (108, 127),
        (111, 267),
        (226, 270),
        (226, 128),
        (265, 132),
        (271, 93),
        (225, 69),
        (208, 57),
        (187, 49),
        (171, 35),
    ]

    draw.polygon(
        points,
        fill=(55, 65, 75, 255),
    )

    return image


def test_white_background_is_square():
    result = canonicalize_garment(
        make_tshirt(),
        auto_align=False,
    )

    assert result.white_rgb.mode == "RGB"
    assert result.white_rgb.width == result.white_rgb.height
    assert result.white_rgb.getpixel((0, 0)) == (255, 255, 255)


def test_transparency_is_preserved():
    result = canonicalize_garment(
        make_tshirt(),
        auto_align=False,
    )

    assert result.rgba.mode == "RGBA"
    assert result.rgba.getpixel((0, 0))[3] == 0


@pytest.mark.parametrize(
    ("input_rotation", "expected_correction"),
    [
        (0, 0),
        (90, -90),
        (-90, 90),
        (180, 180),
    ],
)
def test_tshirt_four_cardinal_orientations(
    input_rotation,
    expected_correction,
):
    rotated = make_tshirt().rotate(
        input_rotation,
        expand=True,
    )

    result = canonicalize_garment(rotated)

    assert result.rotation_degrees == expected_correction
    assert result.method in {
        "automatic_upper_silhouette",
        "auto_already_upright",
    }
    assert result.white_rgb.width == result.white_rgb.height


@pytest.mark.parametrize(
    ("input_rotation", "expected_correction"),
    [
        (0, 0),
        (90, -90),
        (-90, 90),
        (180, 180),
    ],
)
def test_asymmetric_polo_four_orientations(
    input_rotation,
    expected_correction,
):
    rotated = make_asymmetric_polo().rotate(
        input_rotation,
        expand=True,
    )

    result = canonicalize_garment(rotated)

    assert result.rotation_degrees == expected_correction
    assert result.method in {
        "automatic_upper_silhouette",
        "auto_already_upright",
    }


def test_ambiguous_rectangle_is_not_forced_to_rotate():
    image = Image.new(
        "RGBA",
        (200, 200),
        (255, 255, 255, 0),
    )

    ImageDraw.Draw(image).rectangle(
        (30, 30, 170, 170),
        fill=(40, 50, 60, 255),
    )

    result = canonicalize_garment(image)

    assert result.rotation_degrees == 0
    assert result.method == "auto_skipped_low_confidence"


def test_manual_rotation_overrides_automatic():
    image = make_tshirt()

    result = canonicalize_garment(
        image,
        auto_align=True,
        manual_rotation=-90,
    )

    assert result.method == "manual"
    assert result.rotation_degrees == -90


def test_empty_mask_is_rejected():
    image = Image.fromarray(np.zeros((32, 32, 4), dtype=np.uint8))

    with pytest.raises(
        ImageProcessingError,
        match="empty",
    ):
        canonicalize_garment(image)


def test_rgb_input_is_rejected():
    image = Image.new("RGB", (32, 32))

    with pytest.raises(
        ImageProcessingError,
        match="RGBA",
    ):
        canonicalize_garment(image)


def test_invalid_manual_rotation_is_rejected():
    with pytest.raises(ImageProcessingError):
        canonicalize_garment(
            make_tshirt(),
            manual_rotation=math.nan,
        )


def test_negative_padding_is_rejected():
    with pytest.raises(ImageProcessingError):
        canonicalize_garment(
            make_tshirt(),
            padding=-1,
        )
