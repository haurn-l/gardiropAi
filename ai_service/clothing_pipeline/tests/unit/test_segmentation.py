"""Unit tests for BiRefNet preprocessing and alpha generation."""

import numpy as np
import pytest
from PIL import Image

from gardirop_ai_clothing.errors import (
    ConfigurationError,
    ImageProcessingError,
)
from gardirop_ai_clothing.image.segmentation import (
    BiRefNetSegmenter,
    load_huggingface_birefnet_runner,
    logits_to_alpha,
    preprocess_birefnet,
)


def test_preprocessing_shape_and_dtype():
    image = Image.new("RGB", (100, 160), (255, 0, 0))

    tensor = preprocess_birefnet(image)

    assert tensor.shape == (3, 1024, 640)
    assert tensor.dtype == np.float32
    assert np.isfinite(tensor).all()


def test_imagenet_normalization():
    image = Image.new("RGB", (4, 4), (255, 0, 0))

    tensor = preprocess_birefnet(image)

    assert tensor[0, 0, 0] == pytest.approx((1.0 - 0.485) / 0.229)
    assert tensor[1, 0, 0] == pytest.approx((0.0 - 0.456) / 0.224)
    assert tensor[2, 0, 0] == pytest.approx((0.0 - 0.406) / 0.225)


def test_preprocessing_rejects_rgba():
    image = Image.new("RGBA", (16, 16))

    with pytest.raises(ImageProcessingError, match="RGB"):
        preprocess_birefnet(image)


def test_zero_logits_produce_half_alpha():
    logits = np.zeros((16, 16), dtype=np.float32)

    alpha = logits_to_alpha(logits, (32, 24))

    assert alpha.shape == (24, 32)
    assert alpha.dtype == np.uint8
    assert np.all(alpha == 128)


def test_extreme_logits_produce_expected_alpha():
    logits = np.array(
        [[20.0, -20.0]],
        dtype=np.float32,
    )

    alpha = logits_to_alpha(logits, (2, 1))

    assert alpha[0, 0] == 255
    assert alpha[0, 1] == 0


def test_batched_logits_shape():
    logits = np.zeros(
        (1, 1, 8, 8),
        dtype=np.float32,
    )

    alpha = logits_to_alpha(logits, (16, 16))

    assert alpha.shape == (16, 16)


def test_nan_logits_rejected():
    logits = np.zeros((8, 8), dtype=np.float32)
    logits[0, 0] = np.nan

    with pytest.raises(ImageProcessingError, match="NaN"):
        logits_to_alpha(logits, (8, 8))


def test_invalid_logit_dimensions_rejected():
    logits = np.zeros((2, 3, 8, 8), dtype=np.float32)

    with pytest.raises(
        ImageProcessingError,
        match="single-channel",
    ):
        logits_to_alpha(logits, (8, 8))


def test_segmenter_uses_runner_and_restores_dimensions():
    calls = []

    def fake_model(normalized):
        calls.append(normalized.shape)
        return np.zeros(
            (1, 1, 1024, 1024),
            dtype=np.float32,
        )

    segmenter = BiRefNetSegmenter(fake_model)

    image = Image.new("RGB", (32, 48), "blue")
    alpha = segmenter.predict_alpha(image)

    assert calls == [(3, 1024, 704)]
    assert alpha.shape == (48, 32)
    assert np.all(alpha == 128)


def test_invalid_runner_rejected():
    with pytest.raises(ConfigurationError, match="callable"):
        BiRefNetSegmenter(None)


def test_unpinned_model_revision_rejected():
    with pytest.raises(ConfigurationError, match="revision"):
        load_huggingface_birefnet_runner(
            revision="main",
            device="cpu",
        )
