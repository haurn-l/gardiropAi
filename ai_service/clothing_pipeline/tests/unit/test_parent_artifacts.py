"""Reject incompatible arrays even when their file hashes are internally valid."""

import json

import numpy as np
import pytest

from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256, load_parent_parameters


def load(bundle):
    weights, info = bundle
    return load_parent_parameters(
        weights, info, weights_sha256=file_sha256(weights), metadata_sha256=file_sha256(info)
    )


def test_parent_parameters_load_readonly(parent_bundle):
    result = load(parent_bundle)
    assert result.weights.shape == (20, 1536)
    assert result.bias.shape == (20,)
    with pytest.raises(ValueError):
        result.weights[0, 0] = 1


def test_checksum_tampering_is_rejected(parent_bundle):
    weights, info = parent_bundle
    expected = file_sha256(weights)
    weights.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="SHA256"):
        load_parent_parameters(
            weights, info, weights_sha256=expected, metadata_sha256=file_sha256(info)
        )


@pytest.mark.parametrize(
    ("key", "bad"),
    [
        ("embedding_dim", 768),
        ("marqo_revision", "0" * 40),
        ("fusion_method", "mean768"),
        ("view_order", ["BACK", "FRONT"]),
        ("model_kind", "global_lr"),
        ("parent_class_ids", {"üst": [10]}),
    ],
)
def test_wrong_metadata_rejected_even_with_rehashed_file(parent_bundle, key, bad):
    _, info = parent_bundle
    data = json.loads(info.read_text())
    data[key] = bad
    info.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=key):
        load(parent_bundle)


@pytest.mark.parametrize("kind", ["legacy768", "nan", "swapped_ids", "float_ids"])
def test_wrong_parameter_arrays_rejected(parent_bundle, kind):
    weights, info = parent_bundle
    matrix = np.zeros((20, 768 if kind == "legacy768" else 1536))
    ids = np.arange(20)
    if kind == "nan":
        matrix[0, 0] = np.nan
    if kind == "swapped_ids":
        ids[[0, 1]] = ids[[1, 0]]
    if kind == "float_ids":
        ids = ids.astype(float)
    np.savez_compressed(weights, weights=matrix, bias=np.zeros(20), class_ids=ids)
    data = json.loads(info.read_text())
    data["artifact_sha256"] = file_sha256(weights)
    info.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load(parent_bundle)
