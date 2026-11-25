"""Pixel-equivalence checks for lower-allocation crop and optional encodings."""

import io
from contextlib import contextmanager

import numpy as np
import pytest
from PIL import Image

from gardirop_ai_clothing import pipeline as pipeline_module
from gardirop_ai_clothing.analysis import create_analysis_service
from gardirop_ai_clothing.config import Settings
from gardirop_ai_clothing.errors import ImageProcessingError
from gardirop_ai_clothing.image.canonical_view import canonicalize_garment
from gardirop_ai_clothing.image.mask_postprocess import create_cropped_rgba
from gardirop_ai_clothing.image_profiling import attach_image_stage_profiling
from gardirop_ai_clothing.pipeline import ClothingImagePipeline, ImagePreparationOptions


def legacy_crop(rgb, alpha, padding_fraction, alpha_threshold):
    """Original all-coordinate algorithm, kept as an independent pixel oracle."""
    yy, xx = np.nonzero(alpha > alpha_threshold)
    if not len(xx):
        raise ImageProcessingError("Cannot crop an empty foreground mask.")
    px, py = round(rgb.width * padding_fraction), round(rgb.height * padding_fraction)
    box = (
        max(0, int(xx.min()) - px),
        max(0, int(yy.min()) - py),
        min(rgb.width, int(xx.max()) + 1 + px),
        min(rgb.height, int(yy.max()) + 1 + py),
    )
    rgba = rgb.convert("RGBA")
    rgba.putalpha(Image.fromarray(alpha, mode="L"))
    return rgba.crop(box)


@pytest.mark.parametrize(
    "kind,padding,threshold",
    [
        ("center", 0.02, 8),
        ("center", 0, 128),
        ("center", 0.25, 0),
        ("border", 0.02, 8),
        ("single", 0, 8),
        ("soft", 0.02, 8),
    ],
)
def test_crop_pixels_match_previous_algorithm(kind, padding, threshold):
    random = np.random.default_rng(10)
    rgb = Image.fromarray(random.integers(0, 256, (73, 91, 3), dtype=np.uint8))
    alpha = np.zeros((73, 91), dtype=np.uint8)
    if kind == "center":
        alpha[9:55, 12:66] = random.integers(0, 256, (46, 54), dtype=np.uint8)
    elif kind == "border":
        alpha[0:40, 0:35] = 255
    elif kind == "single":
        alpha[72, 90] = 9
    else:
        alpha[4:69, 8:80] = 8
        alpha[16:50, 20:60] = 128
        alpha[25:40, 25:55] = 255
    expected = legacy_crop(rgb, alpha, padding, threshold)
    actual = create_cropped_rgba(rgb, alpha, padding_fraction=padding, alpha_threshold=threshold)
    assert actual.mode == expected.mode == "RGBA" and actual.size == expected.size
    assert actual.tobytes() == expected.tobytes()


def test_empty_foreground_still_rejects_the_same_threshold():
    with pytest.raises(ImageProcessingError, match="empty foreground"):
        create_cropped_rgba(Image.new("RGB", (10, 20)), np.full((20, 10), 8, dtype=np.uint8))


class RecordedMask:
    def predict_alpha(self, image):
        alpha = np.zeros((image.height, image.width), dtype=np.uint8)
        alpha[5:-5, 7:-7] = 128
        alpha[10:-10, 10:-10] = 255
        return alpha


def source_photo():
    output = io.BytesIO()
    image = Image.new("RGB", (64, 96), (190, 25, 35))
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.mark.parametrize("rotation", [0, 90, -90, 180, 13.5])
def test_omitting_unused_transparent_encoding_preserves_all_image_pixels(rotation):
    options = ImagePreparationOptions(manual_rotation=rotation)
    full = ClothingImagePipeline(RecordedMask()).prepare_photo(source_photo(), options=options)
    compact = ClothingImagePipeline(RecordedMask(), include_transparent_webp=False).prepare_photo(
        source_photo(), options=options
    )
    assert full.transparent_webp and compact.transparent_webp is None
    assert compact.delivery_webp == full.delivery_webp
    assert compact.delivery_profile == full.delivery_profile
    assert compact.rotation_degrees == full.rotation_degrees
    for name in ("raw_alpha", "final_alpha", "original_cutout", "aligned_rgba", "white_rgb"):
        np.testing.assert_array_equal(getattr(compact, name), getattr(full, name))


def test_zero_rotation_output_is_independent_of_input():
    original = Image.new("RGBA", (32, 48), (10, 30, 70, 200))
    before = original.tobytes()
    result = canonicalize_garment(original, auto_align=False)
    assert original.tobytes() == before
    result.rgba.putpixel((0, 0), (255, 0, 0, 255))
    result.white_rgb.putpixel((0, 0), (0, 0, 0))
    assert original.tobytes() == before


@pytest.mark.parametrize("profile,expected", [("full", True), ("compact", False)])
def test_analysis_factory_selects_encoding_policy_without_loading_models(profile, expected):
    service = create_analysis_service(Settings(draft_storage_profile=profile))
    assert service.images.include_transparent_webp is expected
    assert service.manager.loaded_models == ()


class Events:
    def __init__(self):
        self.names = []

    @contextmanager
    def span(self, name):
        self.names.append(name)
        yield


def test_stage_profiling_records_real_steps_and_restores_functions():
    pipeline = ClothingImagePipeline(RecordedMask(), include_transparent_webp=False)
    original = pipeline_module.decode_uploaded_image
    events = Events()
    restore = attach_image_stage_profiling(pipeline, events)
    try:
        pipeline.prepare_photo(source_photo())
        assert {
            "image_decode",
            "segmentation_with_prepost",
            "foreground_crop",
            "canonicalize_and_white",
            "white_webp_encoding",
        } <= set(events.names)
        assert "transparent_webp_encoding" not in events.names
    finally:
        restore()
    assert pipeline_module.decode_uploaded_image is original
    restore()  # Repeated cleanup must leave the restored functions alone.
    assert pipeline_module.decode_uploaded_image is original


def test_stage_profiling_can_restore_after_an_image_failure():
    pipeline = ClothingImagePipeline(RecordedMask())
    original = pipeline_module.decode_uploaded_image
    restore = attach_image_stage_profiling(pipeline, Events())
    try:
        with pytest.raises(ImageProcessingError):
            pipeline.prepare_photo(b"invalid image")
    finally:
        restore()
    assert pipeline_module.decode_uploaded_image is original
