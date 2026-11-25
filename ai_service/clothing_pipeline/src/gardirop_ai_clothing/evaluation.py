"""Shared image diagnostics and repeatable latency benchmarks."""

import math
import time
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean, median

import numpy as np
import torch

from gardirop_ai_clothing.pipeline import (
    ClothingImagePipeline,
    ImagePreparationOptions,
    PreparedGarmentImage,
)


def summarize_timings_ms(samples: Sequence[float]) -> dict[str, float]:
    """Return descriptive latency statistics in milliseconds."""
    if not samples:
        raise ValueError("At least one timing sample is required.")

    values = sorted(float(value) for value in samples)

    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("Timing samples must be finite and non-negative.")

    p95_index = math.ceil(0.95 * len(values)) - 1

    return {
        "min": round(values[0], 2),
        "mean": round(fmean(values), 2),
        "p50": round(median(values), 2),
        "p95": round(values[p95_index], 2),
        "max": round(values[-1], 2),
    }


def image_diagnostics(prepared: PreparedGarmentImage) -> dict:
    """
    Check basic image invariants.

    These diagnostics cannot determine whether segmentation or
    predicted orientation is semantically correct.
    """
    raw = prepared.raw_alpha
    final = prepared.final_alpha

    if raw.shape != final.shape or raw.ndim != 2:
        raise ValueError("Raw and final masks must have equal 2D shapes.")

    raw_mass = float(raw.sum(dtype=np.float64))
    final_mass = float(final.sum(dtype=np.float64))

    removed_fraction = max(0.0, (raw_mass - final_mass) / raw_mass) if raw_mass > 0 else 0.0

    white = prepared.white_rgb
    width, height = white.size

    corners = (
        (0, 0),
        (width - 1, 0),
        (0, height - 1),
        (width - 1, height - 1),
    )

    return {
        "foreground_fraction": round(float(np.mean(final > 8)), 5),
        "removed_alpha_fraction": round(removed_fraction, 6),
        "white_canvas_square": width == height,
        "white_canvas_corners_white": all(
            white.getpixel(point) == (255, 255, 255) for point in corners
        ),
        "orientation_method": prepared.orientation_method,
        "rotation_degrees": prepared.rotation_degrees,
        "white_canvas_size": [width, height],
        "source_size": list(prepared.source_size),
    }


@dataclass(frozen=True)
class BenchmarkResult:
    """Results for one original photograph."""

    prepared: PreparedGarmentImage
    timings_ms: dict[str, float]
    samples_ms: list[float]
    gpu_peak_allocated_mib: float | None
    gpu_peak_reserved_mib: float | None
    diagnostics: dict


def benchmark_photo(
    pipeline: ClothingImagePipeline,
    image_bytes: bytes,
    *,
    options: ImagePreparationOptions | None = None,
    repeats: int = 7,
    warmup: int = 2,
    device: str = "cuda",
) -> BenchmarkResult:
    """
    Benchmark a complete in-memory image preparation.

    Includes decoding, BiRefNet, A15, alignment, white rendering
    and lossless WebP encoding.

    Excludes model loading, source-file reads and output-file writes.
    """
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError("repeats must be a positive integer.")

    if isinstance(warmup, bool) or not isinstance(warmup, int) or warmup < 0:
        raise ValueError("warmup must be a non-negative integer.")

    if device not in {"cpu", "cuda"}:
        raise ValueError("device must be cpu or cuda.")

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available.")

    options = options or ImagePreparationOptions()

    def synchronize() -> None:
        if device == "cuda":
            torch.cuda.synchronize()

    for _ in range(warmup):
        pipeline.prepare_photo(image_bytes, options=options)
        synchronize()

    samples = []
    allocated = []
    reserved = []
    prepared = None

    for _ in range(repeats):
        synchronize()

        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()

        start = time.perf_counter()
        prepared = pipeline.prepare_photo(image_bytes, options=options)
        synchronize()

        samples.append((time.perf_counter() - start) * 1000.0)

        if device == "cuda":
            allocated.append(torch.cuda.max_memory_allocated() / (1024**2))
            reserved.append(torch.cuda.max_memory_reserved() / (1024**2))

    assert prepared is not None

    return BenchmarkResult(
        prepared=prepared,
        timings_ms=summarize_timings_ms(samples),
        samples_ms=[round(value, 2) for value in samples],
        gpu_peak_allocated_mib=(round(max(allocated), 2) if allocated else None),
        gpu_peak_reserved_mib=(round(max(reserved), 2) if reserved else None),
        diagnostics=image_diagnostics(prepared),
    )
