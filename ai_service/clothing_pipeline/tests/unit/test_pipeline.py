"""Integration-style unit tests for image preparation."""

import io

import numpy as np
import pytest
from PIL import Image

from gardirop_ai_clothing.errors import ImageProcessingError
from gardirop_ai_clothing.pipeline import (
    ClothingImagePipeline,
    ImagePreparationOptions,
)


def make_image_bytes(
    color: tuple[int, int, int] = (40, 80, 120),
    size: tuple[int, int] = (100, 100),
) -> bytes:
    image = Image.new("RGB", size, color)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    return buffer.getvalue()


class FakeSegmenter:
    def __init__(self, *, add_noise: bool = False):
        self.calls = []
        self.add_noise = add_noise

    def predict_alpha(self, image: Image.Image) -> np.ndarray:
        self.calls.append((image.mode, image.size))

        alpha = np.zeros(
            (image.height, image.width),
            dtype=np.uint8,
        )

        alpha[10:50, 10:50] = 255

        if self.add_noise:
            alpha[80:82, 80:82] = 255

        return alpha


def test_pipeline_prepares_all_image_outputs():
    segmenter = FakeSegmenter()
    pipeline = ClothingImagePipeline(segmenter)

    result = pipeline.prepare_photo(make_image_bytes())

    assert segmenter.calls == [("RGB", (100, 100))]
    assert result.source_size == (100, 100)

    assert result.raw_alpha.shape == (100, 100)
    assert result.final_alpha.shape == (100, 100)

    assert result.original_cutout.mode == "RGBA"
    assert result.aligned_rgba.mode == "RGBA"
    assert result.white_rgb.mode == "RGB"

    assert result.white_rgb.width == result.white_rgb.height
    assert result.white_rgb.getpixel((0, 0)) == (255, 255, 255)

    assert result.transparent_webp


def test_transparent_webp_is_readable():
    pipeline = ClothingImagePipeline(FakeSegmenter())
    result = pipeline.prepare_photo(make_image_bytes())

    with Image.open(io.BytesIO(result.transparent_webp)) as image:
        assert image.format == "WEBP"

        restored = image.convert("RGBA")

    assert restored.size == result.aligned_rgba.size
    assert restored.getchannel("A").getextrema() == (0, 255)


def test_white_image_contains_garment_color():
    pipeline = ClothingImagePipeline(FakeSegmenter())

    result = pipeline.prepare_photo(make_image_bytes(color=(20, 60, 100)))

    pixels = np.asarray(result.white_rgb)

    garment_pixels = np.all(
        pixels == [20, 60, 100],
        axis=2,
    )

    assert garment_pixels.any()


def test_cleanup_is_disabled_by_default():
    pipeline = ClothingImagePipeline(FakeSegmenter(add_noise=True))

    result = pipeline.prepare_photo(make_image_bytes())

    assert result.cleanup_reason == "disabled"
    assert result.removed_components == 0
    assert result.final_alpha[80, 80] == 255


def test_a15_cleanup_removes_distant_noise():
    pipeline = ClothingImagePipeline(FakeSegmenter(add_noise=True))

    options = ImagePreparationOptions(
        use_cleanup=True,
    )

    result = pipeline.prepare_photo(
        make_image_bytes(),
        options=options,
    )

    assert result.cleanup_reason == "cleaned"
    assert result.removed_components == 1
    assert result.final_alpha[80, 80] == 0

    # The original prediction must remain unchanged.
    assert result.raw_alpha[80, 80] == 255


def test_manual_orientation_is_forwarded():
    pipeline = ClothingImagePipeline(FakeSegmenter())

    options = ImagePreparationOptions(
        auto_align=True,
        manual_rotation=-90,
    )

    result = pipeline.prepare_photo(
        make_image_bytes(),
        options=options,
    )

    assert result.orientation_method == "manual"
    assert result.rotation_degrees == -90


def test_default_does_not_force_automatic_rotation():
    pipeline = ClothingImagePipeline(FakeSegmenter())

    result = pipeline.prepare_photo(make_image_bytes())

    assert result.rotation_degrees == 0
    assert result.orientation_method == "unchanged"


def test_front_back_are_processed_independently():
    segmenter = FakeSegmenter()
    pipeline = ClothingImagePipeline(segmenter)

    pair = pipeline.prepare_pair(
        make_image_bytes(color=(255, 0, 0)),
        make_image_bytes(color=(0, 0, 255)),
    )

    assert len(segmenter.calls) == 2

    front = np.asarray(pair.front.white_rgb)
    back = np.asarray(pair.back.white_rgb)

    assert np.any(np.all(front == [255, 0, 0], axis=2))
    assert np.any(np.all(back == [0, 0, 255], axis=2))


def test_pair_supports_different_rotations():
    pipeline = ClothingImagePipeline(FakeSegmenter())

    pair = pipeline.prepare_pair(
        make_image_bytes(),
        make_image_bytes(),
        front_options=ImagePreparationOptions(
            manual_rotation=-90,
        ),
        back_options=ImagePreparationOptions(
            manual_rotation=180,
        ),
    )

    assert pair.front.rotation_degrees == -90
    assert pair.back.rotation_degrees == 180


def test_invalid_alpha_shape_is_rejected():
    class InvalidSegmenter:
        def predict_alpha(self, image):
            return np.zeros((4, 4), dtype=np.uint8)

    pipeline = ClothingImagePipeline(InvalidSegmenter())

    with pytest.raises(
        ImageProcessingError,
        match="invalid alpha",
    ):
        pipeline.prepare_photo(make_image_bytes())


def test_empty_foreground_is_rejected():
    class EmptySegmenter:
        def predict_alpha(self, image):
            return np.zeros(
                (image.height, image.width),
                dtype=np.uint8,
            )

    pipeline = ClothingImagePipeline(EmptySegmenter())

    with pytest.raises(
        ImageProcessingError,
        match="empty foreground",
    ):
        pipeline.prepare_photo(make_image_bytes())


def test_corrupted_image_is_rejected():
    pipeline = ClothingImagePipeline(FakeSegmenter())

    with pytest.raises(ImageProcessingError):
        pipeline.prepare_photo(b"this is not a valid image")
