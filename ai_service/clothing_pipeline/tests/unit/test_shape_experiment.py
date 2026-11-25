"""Geometry diagnostic guards: preserve source pixels and prove actual model routing."""

import json
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from gardirop_ai_clothing.benchmark_comparison import compare_delivery_runs
from gardirop_ai_clothing.onnx_experiment import sha256
from gardirop_ai_clothing.shape_experiment import (
    ITEMS,
    PROFILES,
    SHAPES,
    load_suite,
    pad_to_ratio,
    prepare_suite,
    routing_valid,
    sample_process_gpu,
    shape_of,
)


@pytest.mark.parametrize("profile,ratio", PROFILES)
def test_padding_preserves_pixels_and_produces_expected_model_shape(profile, ratio):
    original = Image.fromarray(np.arange(60 * 90 * 3, dtype=np.uint8).reshape(90, 60, 3))
    canvas, (x, y) = pad_to_ratio(original, ratio)
    assert canvas.width * ratio[1] == canvas.height * ratio[0]
    assert np.array_equal(np.asarray(canvas.crop((x, y, x + 60, y + 90))), np.asarray(original))
    assert shape_of(canvas) == SHAPES[profile]


@pytest.fixture
def suite(tmp_path):
    source = tmp_path / "outputs/step07_completion/inputs/generated"
    source.mkdir(parents=True)
    inputs = []
    for name, _, _ in ITEMS:
        row = {"name": name}
        for view in ("front", "back"):
            path = source / f"{name}_{view}.png"
            Image.new("RGB", (60, 90), (80, 120, 200)).save(path)
            row[f"{view}_sha256"] = sha256(path)
        inputs.append(row)
    baseline = tmp_path / "outputs/api_baseline/reference"
    baseline.mkdir(parents=True)
    (baseline / "report.json").write_text(
        json.dumps(
            {"status": "COMPLETED", "segmentation_backend_requested": "tensorrt", "inputs": inputs}
        )
    )
    output = tmp_path / "outputs/api_shape_compare/run"
    output.mkdir(parents=True)
    return tmp_path, prepare_suite(tmp_path, output, baseline)


def test_suite_round_trip_checks_all_twelve_cases(suite):
    root, path = suite
    cases = load_suite(path, root, 1024**2)
    assert len(cases) == 12
    assert cases[0]["profile"] == "p34"
    assert cases[0]["expected_backend"] == "pytorch"
    assert sum(row["expected_backend"] == "tensorrt" for row in cases) == 3
    assert all(isinstance(row["front"], bytes) for row in cases)


@pytest.mark.parametrize("fault", ["missing", "identity", "shape", "backend", "checksum", "escape"])
def test_invalid_suite_is_rejected(suite, fault):
    root, path = suite
    data = json.loads(path.read_text())
    row = data["cases"][0]
    if fault == "missing":
        data["cases"].pop()
    elif fault == "identity":
        row["name"] = "other"
    elif fault == "shape":
        row["expected_input_nchw"] = [1, 3, 1024, 704]
    elif fault == "backend":
        row["expected_backend"] = "tensorrt"
    elif fault == "checksum":
        row["front_sha256"] = "0" * 64
    else:
        row["front"] = str(root / "outside.png")
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_suite(path, root, 1024**2)


@pytest.mark.parametrize("backend,expected", [("tensorrt", "pytorch"), ("pytorch", "pytorch")])
def test_routing_accepts_exactly_two_successful_fallback_forwards(backend, expected):
    windows = [{"case": "tshirt_p34", "start_ns": 1, "assets_ns": 10}]
    cases = [
        {
            "name": "tshirt_p34",
            "expected_backend": "pytorch",
            "expected_input_nchw": list(SHAPES["p34"]),
        }
    ]
    events = [
        {
            "start_ns": start,
            "end_ns": start + 1,
            "backend": expected,
            "success": True,
            "input_nchw": list(SHAPES["p34"]),
        }
        for start in (2, 4)
    ]
    assert routing_valid(windows, events, cases, backend)
    assert not routing_valid(windows, events[:1], cases, backend)
    events[0]["backend"] = "tensorrt"
    assert not routing_valid(windows, events, cases, backend)


def test_memory_sample_uses_only_server_pid(monkeypatch):
    monkeypatch.setattr(
        "gardirop_ai_clothing.shape_experiment.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="12, 1000\n34, 2500\n"),
    )
    assert sample_process_gpu(34) == 2500
    assert sample_process_gpu(56) is None


@pytest.mark.parametrize("names", [(), ("../private",), ("tshirt", "tshirt"), ([],)])
def test_comparison_rejects_unsafe_or_duplicate_case_names(tmp_path, names):
    with pytest.raises(ValueError, match="case names"):
        compare_delivery_runs(tmp_path, tmp_path, case_names=names)


def test_comparison_accepts_named_shape_case(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    for root in (old, new):
        folder = root / "cases/tshirt_p34"
        folder.mkdir(parents=True)
        (root / "report.json").write_text(json.dumps({"status": "COMPLETED"}))
        (folder / "result.json").write_text(json.dumps({"tags": {}, "versions": {}}))
        (folder / "embedding.json").write_text(json.dumps({"values": [1.0] + [0.0] * 1535}))
        for view in ("front", "back"):
            Image.new("RGB", (16, 16), "white").save(folder / f"{view}.webp", lossless=True)
    assert compare_delivery_runs(old, new, case_names=("tshirt_p34",))["all_checks_passed"]
