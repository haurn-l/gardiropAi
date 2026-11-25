"""CPU-only checks for engine identity and safe GPU-buffer contracts."""

from copy import deepcopy

import pytest

from gardirop_ai_clothing.tensorrt_experiment import cache_key, check_static_specs


def specs():
    return [
        {
            "name": "pixels",
            "mode": "INPUT",
            "shape": [1, 3, 1024, 704],
            "dtype": "float16",
            "location": "DEVICE",
            "format": "LINEAR",
        },
        {
            "name": "logits",
            "mode": "OUTPUT",
            "shape": [1, 1, 1024, 704],
            "dtype": "float16",
            "location": "DEVICE",
            "format": "LINEAR",
        },
    ]


def test_engine_identity_ignores_json_key_order():
    left = {"onnx": "sha", "device": {"driver": "595", "sm": [8, 9]}}
    right = {"device": {"sm": [8, 9], "driver": "595"}, "onnx": "sha"}
    assert cache_key(left) == cache_key(right)


@pytest.mark.parametrize("field", ["onnx", "driver", "gpu", "sdk", "workspace", "adapter"])
def test_changed_engine_dependency_invalidates_cache(field):
    identity = {
        name: "original" for name in ("onnx", "driver", "gpu", "sdk", "workspace", "adapter")
    }
    changed = {**identity, field: "changed"}
    assert cache_key(identity) != cache_key(changed)


def test_nonfinite_engine_identity_is_rejected():
    with pytest.raises(ValueError):
        cache_key({"workspace": float("nan")})


def test_static_fp16_contract_accepts_exact_engine_and_returns_output_name():
    assert check_static_specs(specs(), {"pixels": (1, 3, 1024, 704)}) == "logits"


@pytest.mark.parametrize(
    "field,value",
    [
        ("dtype", "float32"),
        ("location", "HOST"),
        ("format", "CHW32"),
        ("shape", [1, 3, -1, 704]),
        ("shape", [1, 3, 704, 1024]),
        ("shape", [1, 3, True, 704]),
        ("name", "unexpected"),
        ("mode", "UNKNOWN"),
    ],
)
def test_engine_mismatch_is_rejected_before_buffer_binding(field, value):
    altered = specs()
    altered[0][field] = value
    with pytest.raises(ValueError):
        check_static_specs(altered, {"pixels": (1, 3, 1024, 704)})


@pytest.mark.parametrize(
    "mutation",
    ["missing_output", "extra_output", "duplicate_input", "dynamic_output", "empty_output"],
)
def test_missing_ambiguous_or_dynamic_outputs_are_rejected(mutation):
    altered = specs()
    if mutation == "missing_output":
        altered.pop()
    elif mutation == "extra_output":
        altered.append({**altered[-1], "name": "other"})
    elif mutation == "duplicate_input":
        altered.append(deepcopy(altered[0]))
    elif mutation == "dynamic_output":
        altered[-1]["shape"] = [1, 1, -1, 704]
    else:
        altered[-1]["shape"] = []
    with pytest.raises(ValueError):
        check_static_specs(altered, {"pixels": (1, 3, 1024, 704)})
