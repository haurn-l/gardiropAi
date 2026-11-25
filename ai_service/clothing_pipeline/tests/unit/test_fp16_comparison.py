"""The predeclared FP16 demo gate never relaxes image or tag checks."""

import json

import numpy as np
import pytest
from PIL import Image

from gardirop_ai_clothing.benchmark_comparison import compare_delivery_runs, embedding_drift


def paired_runs(tmp_path):
    left, right = tmp_path / "fp32", tmp_path / "fp16"
    vector = np.zeros(1536, dtype=np.float32)
    vector[0] = vector[768] = 1 / np.sqrt(2)
    for root, precision in ((left, "fp32"), (right, "fp16")):
        root.mkdir()
        (root / "report.json").write_text(json.dumps({"status": "COMPLETED"}))
        for name in ("tshirt", "jeans", "jacket"):
            folder = root / "cases" / name
            folder.mkdir(parents=True)
            record = {
                "tags": {"subCategory": "demo", "color": "Mavi", "season": None, "hasPrint": False},
                "versions": {"encoder": "same-frozen-checkpoint"},
                "modelDiagnostics": {
                    "embedding": {"encoder_precision": precision},
                    "classification": {
                        "alternatives": [{"class_id": n, "score": 3 - n} for n in range(3)]
                    },
                },
            }
            (folder / "result.json").write_text(json.dumps(record))
            (folder / "embedding.json").write_text(json.dumps({"values": vector.tolist()}))
            for view in ("front", "back"):
                Image.new("RGB", (16, 16), "white").save(folder / f"{view}.webp", lossless=True)
    return left, right, vector


def test_small_normalized_embedding_change_can_pass_without_claiming_exactness(tmp_path):
    old, new, vector = paired_runs(tmp_path)
    candidate = vector.copy()
    candidate[1] = 1e-5
    candidate[:768] *= (1 / np.sqrt(2)) / np.linalg.norm(candidate[:768])
    (new / "cases" / "tshirt" / "embedding.json").write_text(
        json.dumps({"values": candidate.tolist()})
    )
    result = compare_delivery_runs(old, new, mode="fp16")
    assert result["all_checks_passed"] is True
    assert result["embedding_drift"]["tshirt"]["float32_identical"] is False


@pytest.mark.parametrize("change", ["tag", "pixels", "precision", "ranking", "large_embedding"])
def test_fp16_gate_rejects_each_relevant_regression(tmp_path, change):
    old, new, vector = paired_runs(tmp_path)
    folder = new / "cases" / "jacket"
    record = json.loads((folder / "result.json").read_text())
    if change == "tag":
        record["tags"]["hasPrint"] = True
    elif change == "pixels":
        Image.new("RGB", (16, 16), "red").save(folder / "front.webp", lossless=True)
    elif change == "precision":
        record["modelDiagnostics"]["embedding"]["encoder_precision"] = "fp32"
    elif change == "ranking":
        record["modelDiagnostics"]["classification"]["alternatives"].reverse()
    else:
        candidate = vector.copy()
        candidate[0], candidate[1] = 0, candidate[0]
        (folder / "embedding.json").write_text(json.dumps({"values": candidate.tolist()}))
    (folder / "result.json").write_text(json.dumps(record))
    assert compare_delivery_runs(old, new, mode="fp16")["all_checks_passed"] is False


@pytest.mark.parametrize("values", [[0.0] * 1536, [float("nan")] * 1536, [1.0] * 768])
def test_invalid_embedding_contract_never_passes(values):
    assert embedding_drift(values, values)["within_tolerance"] is False
