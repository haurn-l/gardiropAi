"""Regression checks for aspect geometry, padding removal and selected pins."""

import numpy as np
import pytest
from PIL import Image

from gardirop_ai_clothing.errors import ConfigurationError, ImageProcessingError
from gardirop_ai_clothing.image.segmentation import (
    BiRefNetSegmenter,
    load_huggingface_birefnet_runner,
    prepare_birefnet_canvas,
    preprocess_birefnet,
    validate_birefnet_input,
)


@pytest.mark.parametrize(
    ("size", "canvas_size", "content_size"),
    [
        ((899, 1599), (576, 1024), (576, 1024)),
        ((1599, 899), (1024, 576), (1024, 576)),
        ((32, 48), (704, 1024), (683, 1024)),
        ((1024, 1024), (1024, 1024), (1024, 1024)),
        ((11, 803), (256, 1024), (14, 1024)),
    ],
)
def test_geometry_preserves_ratio_with_bounded_sides(size, canvas_size, content_size):
    canvas, box = prepare_birefnet_canvas(Image.new("RGB", size, "black"))
    assert canvas.size == canvas_size
    assert (box[2] - box[0], box[3] - box[1]) == content_size
    assert canvas.getpixel((box[0], box[1])) == (0, 0, 0)
    if box[0] or box[1]:
        assert canvas.getpixel((0, 0)) == (255, 255, 255)
    normalized = preprocess_birefnet(Image.new("RGB", size, "black"))
    assert normalized.shape == (3, canvas_size[1], canvas_size[0])
    validate_birefnet_input(normalized)


def test_padding_predictions_do_not_leak_into_original_photo():
    image = Image.new("RGB", (11, 803), "black")
    canvas, box = prepare_birefnet_canvas(image)

    # All positive logits are padding. Source pixels are completely background.
    def runner(chw):
        assert chw.shape == (3, canvas.height, canvas.width)
        logits = np.full((1, 1, canvas.height, canvas.width), 30, np.float32)
        x1, y1, x2, y2 = box
        logits[:, :, y1:y2, x1:x2] = -30
        return logits

    alpha = BiRefNetSegmenter(runner).predict_alpha(image)
    assert alpha.shape == (803, 11) and alpha.max() == 0


def test_content_coordinates_return_to_source_without_shifting_or_rotation():
    image = Image.new("RGB", (11, 803), "black")
    canvas, box = prepare_birefnet_canvas(image)

    def runner(chw):
        logits = np.full((1, 1, canvas.height, canvas.width), -30, np.float32)
        x1, y1, x2, y2 = box
        logits[:, :, y1 : (y1 + y2) // 2, x1:x2] = 30
        return logits

    alpha = BiRefNetSegmenter(runner).predict_alpha(image)
    assert np.all(alpha[:390] == 255) and np.all(alpha[410:] == 0)


@pytest.mark.parametrize("shape", [(3, 1024, 577), (3, 128, 1024), (3, 1088, 1024), (4, 576, 1024)])
def test_adapter_rejects_unsupported_shapes_before_model(shape):
    with pytest.raises(ImageProcessingError):
        validate_birefnet_input(np.zeros(shape, np.float32))


def test_adapter_rejects_nonfinite_input():
    array = np.zeros((3, 256, 1024), np.float32)
    array[0, 0, 0] = np.nan
    with pytest.raises(ImageProcessingError):
        validate_birefnet_input(array)


def test_old_lite_revision_cannot_be_used_with_dynamic_repo():
    with pytest.raises(ConfigurationError, match="Dynamic revision"):
        load_huggingface_birefnet_runner(revision="aa62cd87eafb9cc43056d08ef3615a14628b831d")
