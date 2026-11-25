"""Validate the segmentation-only smoke with a synthetic runner."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from gardirop_ai_clothing.image.birefnet_local import LocalBiRefNetSegmenter

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "smoke_segmentation", ROOT / "scripts/smoke_birefnet.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def runner(chw):
    logits = np.full((1, 1, chw.shape[1], chw.shape[2]), -30, np.float32)
    logits[:, :, 200:800, 150:450] = 30
    return logits


def test_smoke_exports_source_size_masks_and_compares_same_model_reference(tmp_path):
    image = tmp_path / "input.png"
    Image.new("RGB", (899, 1599), "blue").save(image)
    segmenter = LocalBiRefNetSegmenter(runner, device="cpu")
    reference = tmp_path / "reference.png"
    Image.fromarray(segmenter.predict_alpha(Image.open(image))).save(reference)
    out = tmp_path / "out"
    report = module.run_smoke(image, out, segmenter=segmenter, reference_path=reference)
    assert report["status"] == "PASSED" and report["encoder_inference"] is False
    assert report["model"] == "birefnet_dynamic"
    assert report["model_input_wh"] == [576, 1024]
    assert report["colab_reference"]["agreement_iou"] == 1
    assert report["colab_reference"]["is_accuracy_measurement"] is False
    for name in ["alpha.png", "cutout.png", "white.png", "cutout.webp"]:
        with Image.open(out / name) as im:
            assert im.size == (899, 1599)


def test_smoke_never_claims_success_if_reference_regresses(tmp_path):
    image = tmp_path / "input.png"
    Image.new("RGB", (899, 1599), "blue").save(image)
    reference = tmp_path / "reference.png"
    Image.new("L", (899, 1599), 0).save(reference)
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="differs"):
        module.run_smoke(
            image,
            out,
            segmenter=LocalBiRefNetSegmenter(runner, device="cpu"),
            reference_path=reference,
        )
    assert json.loads((out / "report.json").read_text())["status"] == "FAILED"
