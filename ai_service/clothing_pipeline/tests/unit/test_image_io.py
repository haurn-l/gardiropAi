"""Unit tests for image decoding and lossless WebP encoding."""

import io

import numpy as np
import pytest
from PIL import Image, ImageCms

from gardirop_ai_clothing.errors import ImageProcessingError
from gardirop_ai_clothing.image.io import (
    composite_rgba_on_white,
    decode_uploaded_image,
    encode_transparent_webp,
)


def to_bytes(image, format_name="PNG", **kwargs):
    output = io.BytesIO()
    image.save(output, format=format_name, **kwargs)
    return output.getvalue()


def test_decode_rgb_png():
    image = Image.new("RGB", (16, 12), (120, 40, 220))
    result = decode_uploaded_image(to_bytes(image))

    assert result.mode == "RGB"
    assert result.size == (16, 12)
    assert result.getpixel((0, 0)) == (120, 40, 220)


def test_transparent_upload_composites_on_white():
    image = Image.new("RGBA", (4, 4), (255, 0, 0, 0))
    image.putpixel((1, 1), (10, 20, 30, 255))

    result = decode_uploaded_image(to_bytes(image))

    assert result.mode == "RGB"
    assert result.getpixel((0, 0)) == (255, 255, 255)
    assert result.getpixel((1, 1)) == (10, 20, 30)


def test_exif_orientation_is_applied():
    image = Image.new("RGB", (12, 20), "red")
    exif = Image.Exif()
    exif[274] = 6

    encoded = to_bytes(
        image,
        "JPEG",
        exif=exif,
    )

    result = decode_uploaded_image(encoded)

    assert result.size == (20, 12)


def test_srgb_icc_profile_is_accepted():
    image = Image.new("RGB", (8, 8), (80, 100, 120))
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()

    encoded = to_bytes(
        image,
        "PNG",
        icc_profile=profile,
    )

    result = decode_uploaded_image(encoded)

    assert result.mode == "RGB"
    assert result.size == image.size


def test_corrupted_image_is_rejected():
    with pytest.raises(ImageProcessingError):
        decode_uploaded_image(b"this is not an image")


def test_upload_byte_limit():
    image = Image.new("RGB", (8, 8), "blue")
    encoded = to_bytes(image)

    with pytest.raises(ImageProcessingError, match="byte limit"):
        decode_uploaded_image(
            encoded,
            max_upload_bytes=10,
        )


def test_pixel_limit():
    image = Image.new("RGB", (10, 10), "green")
    encoded = to_bytes(image)

    with pytest.raises(ImageProcessingError, match="dimensions"):
        decode_uploaded_image(
            encoded,
            max_pixels=50,
        )


def test_unsupported_format():
    image = Image.new("RGB", (8, 8), "red")
    encoded = to_bytes(image, "GIF")

    with pytest.raises(ImageProcessingError, match="Unsupported"):
        decode_uploaded_image(encoded)


def test_rgba_composite():
    image = Image.new("RGBA", (2, 2), (0, 0, 255, 0))
    image.putpixel((0, 0), (40, 50, 60, 255))

    result = composite_rgba_on_white(image)

    assert result.getpixel((0, 0)) == (40, 50, 60)
    assert result.getpixel((1, 1)) == (255, 255, 255)


def test_lossless_webp_roundtrip():
    image = Image.new("RGBA", (3, 2), (255, 0, 0, 0))
    image.putpixel((1, 1), (24, 80, 180, 255))
    image.putpixel((2, 1), (100, 150, 200, 128))

    encoded = encode_transparent_webp(image)

    with Image.open(io.BytesIO(encoded)) as decoded:
        assert decoded.format == "WEBP"

        restored = decoded.convert("RGBA")

    assert restored.size == image.size

    original = np.asarray(image)
    actual = np.asarray(restored)

    # Alpha must be preserved exactly.
    assert np.array_equal(original[:, :, 3], actual[:, :, 3])

    # Visible RGB must be preserved exactly.
    visible = original[:, :, 3] > 0
    assert np.array_equal(
        original[visible, :3],
        actual[visible, :3],
    )


def test_webp_encoder_rejects_rgb_input():
    image = Image.new("RGB", (4, 4))

    with pytest.raises(ImageProcessingError, match="RGBA"):
        encode_transparent_webp(image)
