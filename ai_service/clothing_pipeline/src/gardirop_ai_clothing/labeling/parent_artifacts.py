"""Verify the 1536D parent LR package, without running classification."""

import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from gardirop_ai_clothing.contracts import (
    EMBEDDING_DIMENSION,
    FUSION_METHOD,
    MAIN_CATEGORIES,
    NUM_CLASSES,
    TAXONOMY,
    TAXONOMY_VERSION,
    VIEW_ORDER,
    class_ids_for_category,
)
from gardirop_ai_clothing.model_specs import ENCODERS, MARQO_REVISION


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ParentLRParameters:
    weights: np.ndarray
    bias: np.ndarray


def load_parent_parameters(
    weights_path: Path,
    metadata_path: Path,
    *,
    weights_sha256: str,
    metadata_sha256: str,
) -> ParentLRParameters:
    for path, expected in ((weights_path, weights_sha256), (metadata_path, metadata_sha256)):
        if not hmac.compare_digest(file_sha256(path), expected):
            raise ValueError(f"SHA256 mismatch: {path.name}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    expected_fields = {
        "schema_version": 1,
        "model_kind": "parent_logistic_regression",
        "embedding_dim": EMBEDDING_DIMENSION,
        "num_classes": NUM_CLASSES,
        "taxonomy_version": TAXONOMY_VERSION,
        "taxonomy": [list(row) for row in TAXONOMY],
        "marqo_repo_id": ENCODERS["marqo_fashionsiglip"]["repo_id"],
        "marqo_revision": MARQO_REVISION,
        "fusion_method": FUSION_METHOD,
        "view_order": list(VIEW_ORDER),
        "parent_class_ids": {
            parent: list(class_ids_for_category(parent)) for parent in sorted(MAIN_CATEGORIES)
        },
        "artifact_sha256": weights_sha256,
    }
    if not isinstance(metadata, dict):
        raise ValueError("Parent LR metadata must be a mapping.")
    for key, expected in expected_fields.items():
        if metadata.get(key) != expected:
            raise ValueError(f"Parent LR metadata mismatch: {key}")
    with np.load(weights_path, allow_pickle=False) as data:
        if set(data.files) != {"weights", "bias", "class_ids"}:
            raise ValueError("Unexpected parent LR arrays.")
        ids = data["class_ids"]
        if ids.dtype.kind not in "iu" or not np.array_equal(ids, np.arange(NUM_CLASSES)):
            raise ValueError("Parent LR class ordering mismatch.")
        weights, bias = data["weights"], data["bias"]
        if weights.shape != (NUM_CLASSES, EMBEDDING_DIMENSION) or bias.shape != (NUM_CLASSES,):
            raise ValueError("Parent LR requires weights (20,1536) and bias (20,).")
        if weights.dtype.kind != "f" or bias.dtype.kind != "f":
            raise ValueError("Parent LR parameters must be floating point.")
        if not (np.isfinite(weights).all() and np.isfinite(bias).all()):
            raise ValueError("Parent LR parameters must be finite.")
        weights = weights.astype(np.float64, copy=True)
        bias = bias.astype(np.float64, copy=True)
    weights.setflags(write=False)
    bias.setflags(write=False)
    return ParentLRParameters(weights=weights, bias=bias)
