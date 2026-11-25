"""TensorRT delivery gates allow only declared small numerical changes."""

import json

import numpy as np
import pytest
from PIL import Image

from gardirop_ai_clothing.benchmark_comparison import compare_delivery_runs, delivery_pixel_drift


@pytest.fixture
def runs(tmp_path):
    roots = [tmp_path / name for name in ("torch", "trt")]
    vector = np.zeros(1536, dtype=np.float32)
    vector[0] = vector[768] = 1 / np.sqrt(2)
    for root in roots:
        root.mkdir()
        (root / "report.json").write_text(json.dumps({"status": "COMPLETED"}))
        for name in ("tshirt", "jeans", "jacket"):
            folder = root / "cases" / name
            folder.mkdir(parents=True)
            record = {
                "tags": {"subCategory": "demo"},
                "versions": {"encoder": "same"},
                "modelDiagnostics": {
                    "embedding": {"encoder_precision": "fp16"},
                    "classification": {
                        "alternatives": [{"class_id": i, "score": 3 - i} for i in range(3)]
                    },
                },
            }
            (folder / "result.json").write_text(json.dumps(record))
            (folder / "embedding.json").write_text(json.dumps({"values": vector.tolist()}))
            image = Image.new("RGB", (32, 32), "white")
            for x in range(8, 24):
                for y in range(8, 24):
                    image.putpixel((x, y), (50, 80, 120))
            for view in ("front", "back"):
                image.save(folder / f"{view}.webp", lossless=True)
    return roots


def test_small_rgb_change_passes_only_trt_mode_while_strict_mode_remains_strict(runs):
    old, new = runs
    path = new / "cases/tshirt/front.webp"
    with Image.open(path) as image:
        image = image.copy()
    image.putpixel((10, 10), (51, 80, 120))
    image.save(path, lossless=True)
    assert compare_delivery_runs(old, new, mode="trt")["all_checks_passed"]
    assert not compare_delivery_runs(old, new)["all_checks_passed"]
    assert not compare_delivery_runs(old, new, mode="fp16")["all_checks_passed"]


@pytest.mark.parametrize(
    "change", ["tags", "ranking", "precision", "pixels", "crop", "background", "embedding"]
)
def test_trt_mode_rejects_semantic_and_visible_regressions(runs, change):
    old, new = runs
    case = new / "cases/jacket"
    record = json.loads((case / "result.json").read_text())
    if change == "tags":
        record["tags"]["subCategory"] = "wrong"
    elif change == "ranking":
        record["modelDiagnostics"]["classification"]["alternatives"].reverse()
    elif change == "precision":
        record["modelDiagnostics"]["embedding"]["encoder_precision"] = "fp32"
    elif change == "embedding":
        vector = np.zeros(1536, dtype=np.float32)
        vector[1] = vector[769] = 1 / np.sqrt(2)
        (case / "embedding.json").write_text(json.dumps({"values": vector.tolist()}))
    else:
        path = case / "front.webp"
        with Image.open(path) as image:
            image = image.copy()
        if change == "pixels":
            image.paste((255, 0, 0), (8, 8, 24, 24))
        elif change == "crop":
            image = image.crop((0, 0, 31, 32))
        else:
            image.putpixel((0, 0), (254, 254, 254))
        image.save(path, lossless=True)
    (case / "result.json").write_text(json.dumps(record))
    assert not compare_delivery_runs(old, new, mode="trt")["all_checks_passed"]


def test_pixel_error_uses_signed_difference():
    a, b = Image.new("RGB", (8, 8), "white"), Image.new("RGB", (8, 8), "white")
    a.putpixel((3, 3), (0, 0, 0))
    assert delivery_pixel_drift(a, b)["max_error_255"] == 255
    assert not delivery_pixel_drift(a, b)["passed"]
