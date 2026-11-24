"""FRONT/BACK feature fusion under the fixed 1536D storage contract."""

import math

import numpy as np

from gardirop_ai_clothing.contracts import (
    EMBEDDING_DIMENSION,
    NORM_ABS_TOLERANCE,
    VIEW_EMBEDDING_DIMENSION,
)


def _unit_view(vector: np.ndarray, view: str) -> np.ndarray:
    values = np.asarray(vector)
    if values.shape != (VIEW_EMBEDDING_DIMENSION,) or values.dtype.kind != "f":
        raise ValueError(f"{view} requires one floating-point 768D vector.")
    values = values.astype(np.float64)
    if not np.isfinite(values).all():
        raise ValueError(f"{view} contains NaN or Infinity.")
    norm = float(np.linalg.norm(values))
    if not np.isfinite(norm) or norm <= 0:
        raise ValueError(f"{view} has an invalid norm.")
    return values / norm


def validate_fused_embedding(embedding: np.ndarray) -> np.ndarray:
    """Validate both halves; total norm alone cannot detect a missing view."""
    values = np.asarray(embedding)
    if values.shape != (EMBEDDING_DIMENSION,) or values.dtype.kind != "f":
        raise ValueError("Expected a floating-point 1536D fused embedding.")
    values = values.astype(np.float64)
    if not np.isfinite(values).all():
        raise ValueError("Fused embedding contains NaN or Infinity.")
    target = 1.0 / math.sqrt(2.0)
    for half in (values[:VIEW_EMBEDDING_DIMENSION], values[VIEW_EMBEDDING_DIMENSION:]):
        if not np.isclose(np.linalg.norm(half), target, atol=NORM_ABS_TOLERANCE, rtol=0):
            raise ValueError("Each FRONT/BACK half must have norm 1/sqrt(2).")
    return values


def fuse_views(*, front: np.ndarray, back: np.ndarray) -> np.ndarray:
    """Normalize independently; concatenate FRONT then BACK and divide by sqrt(2)."""
    front_unit = _unit_view(front, "FRONT")
    back_unit = _unit_view(back, "BACK")
    fused = (np.concatenate((front_unit, back_unit)) / math.sqrt(2.0)).astype(np.float32)
    validate_fused_embedding(fused)
    fused.setflags(write=False)
    return fused
