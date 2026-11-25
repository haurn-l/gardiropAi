"""White background is embedded in primary file bytes, not a UI style."""

import io

import numpy as np
import pytest
from PIL import Image

from gardirop_ai_clothing.errors import ImageProcessingError
from gardirop_ai_clothing.image.io import composite_rgba_on_white, encode_white_webp
from gardirop_ai_clothing.pipeline import ClothingImagePipeline


def test_white_webp_roundtrip_preserves_all_rgb_pixels_and_has_no_alpha():
    rgba = Image.new("RGBA", (3, 2), (10, 40, 90, 0))
    rgba.putpixel((1, 0), (20, 80, 190, 255))
    rgba.putpixel((2, 0), (20, 80, 190, 128))
    rgb = composite_rgba_on_white(rgba)
    encoded = encode_white_webp(rgb)
    with Image.open(io.BytesIO(encoded)) as image:
        assert image.format == "WEBP" and image.mode == "RGB"
        assert image.getpixel((0, 0)) == (255, 255, 255)
        np.testing.assert_array_equal(image, rgb)


def test_white_encoder_rejects_rgba_instead_of_discarding_alpha():
    with pytest.raises(ImageProcessingError, match="already-composited RGB"):
        encode_white_webp(Image.new("RGBA", (10, 10), (255, 0, 0, 0)))


def test_primary_pipeline_bytes_are_exactly_the_white_encoder_input():
    class Segmenter:
        def predict_alpha(self, image):
            alpha = np.zeros((image.height, image.width), np.uint8)
            alpha[10:50, 10:35] = 255
            alpha[20:30, 20:25] = 128
            return alpha

    image = Image.new("RGB", (60, 80), (10, 90, 140))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    prepared = ClothingImagePipeline(Segmenter()).prepare_photo(buffer.getvalue())
    assert prepared.delivery_profile == "white-square-lossless-webp-v1"
    assert prepared.delivery_webp == prepared.white_webp
    with Image.open(io.BytesIO(prepared.delivery_webp)) as actual:
        assert actual.mode == "RGB" and actual.width == actual.height
        np.testing.assert_array_equal(actual, prepared.white_rgb)
        for corner in [
            (0, 0),
            (actual.width - 1, 0),
            (0, actual.height - 1),
            (actual.width - 1, actual.height - 1),
        ]:
            assert actual.getpixel(corner) == (255, 255, 255)
    # Soft mask and internal transparency remain available for foreground color analysis.
    assert 128 in prepared.raw_alpha
    assert prepared.original_cutout.getchannel("A").getextrema() == (0, 255)
