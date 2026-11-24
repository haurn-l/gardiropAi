"""Full smoke export contract, using synthetic runners instead of real weights."""

import importlib.util
import io
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from gardirop_ai_clothing.errors import ImageProcessingError
from gardirop_ai_clothing.schemas import ClothingAnalysisResult

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("smoke_pipeline", ROOT / "scripts/smoke_pipeline.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_two_raw_photos_export_valid_contract_images_and_front_back_features(
    tmp_path, analysis_factory
):
    service, calls = analysis_factory()
    source = ROOT / "tests/fixtures/pipeline"
    output = tmp_path / "run"
    report = module.run_smoke(
        source / "G001_front_raw.jpg", source / "G001_back_raw.jpg", "üst", output, service=service
    )
    assert report["status"] == "PASSED" and report["dimension"] == 1536
    assert calls["segmentation"] == calls["marqo"] == 2
    assert report["backend_connected"] is False and report["training_run"] is False
    assert report["cuda_memory"] is None
    result = ClothingAnalysisResult.model_validate_json((output / "result.json").read_text())
    assert result.category == "üst" and result.tags.color is None
    for name in ("front", "back"):
        with Image.open(io.BytesIO((output / f"{name}.webp").read_bytes())) as image:
            assert image.format == "WEBP" and image.mode == "RGB"
        with Image.open(output / f"{name}_white.png") as image:
            assert image.mode == "RGB" and image.width == image.height
    with np.load(output / "embedding.npz", allow_pickle=False) as data:
        assert data["view_order"].tolist() == ["FRONT", "BACK"]
        np.testing.assert_allclose(
            data["embedding"][:768], data["front"] / np.sqrt(2), atol=1e-7, rtol=0
        )
        np.testing.assert_allclose(
            data["embedding"][768:], data["back"] / np.sqrt(2), atol=1e-7, rtol=0
        )
        np.testing.assert_allclose(data["embedding"], result.embedding, atol=1e-7, rtol=0)


def test_bad_back_photo_never_exports_a_success_result(tmp_path, analysis_factory):
    service, calls = analysis_factory()
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not an image")
    output = tmp_path / "run"
    with pytest.raises(ImageProcessingError):
        module.run_smoke(
            ROOT / "tests/fixtures/pipeline/G001_front_raw.jpg", bad, "üst", output, service=service
        )
    report = json.loads((output / "report.json").read_text())
    assert report["status"] == "FAILED" and calls["head_load"] == 0
    assert not (output / "result.json").exists() and not (output / "embedding.npz").exists()
