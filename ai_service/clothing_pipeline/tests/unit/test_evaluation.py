"""Tests for GardropAI evaluation and benchmarking."""

import io
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from gardirop_ai_clothing.evaluation import (
    benchmark_photo,
    image_diagnostics,
    summarize_timings_ms,
)
from gardirop_ai_clothing.pipeline import ClothingImagePipeline


def fake_prepared():
    raw = np.zeros((10, 10), dtype=np.uint8)
    raw[2:8, 2:8] = 255

    final = raw.copy()
    white = Image.new("RGB", (20, 20), "white")
    white.putpixel((10, 10), (40, 60, 80))

    return SimpleNamespace(
        raw_alpha=raw,
        final_alpha=final,
        white_rgb=white,
        source_size=(10, 10),
        orientation_method="auto_already_upright",
        rotation_degrees=0.0,
    )


def test_latency_summary():
    result = summarize_timings_ms([10, 20, 30, 40, 50])

    assert result["min"] == 10
    assert result["mean"] == 30
    assert result["p50"] == 30
    assert result["p95"] == 50
    assert result["max"] == 50


def test_single_latency_sample():
    result = summarize_timings_ms([12.5])

    assert result["p50"] == 12.5
    assert result["p95"] == 12.5


def test_empty_samples_rejected():
    with pytest.raises(ValueError):
        summarize_timings_ms([])


def test_negative_latency_rejected():
    with pytest.raises(ValueError):
        summarize_timings_ms([10, -1])


def test_nonfinite_latency_rejected():
    with pytest.raises(ValueError):
        summarize_timings_ms([10, float("nan")])


def test_image_diagnostics():
    result = image_diagnostics(fake_prepared())

    assert result["foreground_fraction"] == 0.36
    assert result["white_canvas_square"] is True
    assert result["white_canvas_corners_white"] is True
    assert result["removed_alpha_fraction"] == 0


def test_alpha_removal_is_reported():
    prepared = fake_prepared()
    prepared.final_alpha[2, 2] = 0

    result = image_diagnostics(prepared)

    assert result["removed_alpha_fraction"] > 0


def test_invalid_mask_dimensions_rejected():
    prepared = fake_prepared()
    prepared.final_alpha = np.zeros((5, 5), dtype=np.uint8)

    with pytest.raises(ValueError):
        image_diagnostics(prepared)


def test_non_square_canvas_is_detected():
    prepared = fake_prepared()
    prepared.white_rgb = Image.new(
        "RGB",
        (20, 30),
        "white",
    )

    result = image_diagnostics(prepared)

    assert result["white_canvas_square"] is False


class FakeSegmenter:
    def __init__(self):
        self.calls = 0

    def predict_alpha(self, image):
        self.calls += 1

        alpha = np.zeros(
            (image.height, image.width),
            dtype=np.uint8,
        )

        alpha[8:45, 8:45] = 255
        return alpha


def sample_image_bytes():
    image = Image.new("RGB", (64, 64), (30, 60, 90))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_cpu_benchmark_reuses_pipeline():
    segmenter = FakeSegmenter()
    pipeline = ClothingImagePipeline(segmenter)

    result = benchmark_photo(
        pipeline,
        sample_image_bytes(),
        repeats=3,
        warmup=1,
        device="cpu",
    )

    assert segmenter.calls == 4
    assert len(result.samples_ms) == 3
    assert result.timings_ms["min"] >= 0
    assert result.timings_ms["max"] >= result.timings_ms["min"]

    assert result.gpu_peak_allocated_mib is None
    assert result.gpu_peak_reserved_mib is None

    assert result.prepared.white_rgb.mode == "RGB"
    assert result.diagnostics["white_canvas_square"] is True


def test_benchmark_invalid_repeats():
    pipeline = ClothingImagePipeline(FakeSegmenter())

    with pytest.raises(ValueError, match="repeats"):
        benchmark_photo(
            pipeline,
            sample_image_bytes(),
            repeats=0,
            device="cpu",
        )


def test_benchmark_invalid_warmup():
    pipeline = ClothingImagePipeline(FakeSegmenter())

    with pytest.raises(ValueError, match="warmup"):
        benchmark_photo(
            pipeline,
            sample_image_bytes(),
            warmup=-1,
            device="cpu",
        )


def test_benchmark_invalid_device():
    pipeline = ClothingImagePipeline(FakeSegmenter())

    with pytest.raises(ValueError, match="device"):
        benchmark_photo(
            pipeline,
            sample_image_bytes(),
            device="invalid",
        )
