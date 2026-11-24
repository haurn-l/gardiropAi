"""Check smoke report/reference behavior with a fake runner only."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from gardirop_ai_clothing.embeddings.marqo import (
    MARQO_MODEL_NAME,
    MarqoEmbeddingService,
    MarqoEncoder,
)
from gardirop_ai_clothing.model_manager import ModelManager

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/marqo"
spec = importlib.util.spec_from_file_location("smoke_marqo", ROOT / "scripts/smoke_marqo.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fake_service(vector):
    encoder = MarqoEncoder(lambda image: vector, device="cpu")
    return MarqoEmbeddingService(ModelManager({MARQO_MODEL_NAME: lambda: encoder}))


def test_matching_reference_saves_one_768_vector_and_report(tmp_path):
    image, reference = FIXTURES / "G001_front_input.png", FIXTURES / "G001_front_reference.npz"
    vector = module.verify_reference(image, reference)
    report = module.run_smoke(
        image, tmp_path / "run", service=fake_service(vector), reference_path=reference
    )
    assert report["status"] == "PASSED" and report["dimension"] == 768
    assert report["reference_cosine"] == pytest.approx(1.0)
    assert report["training_run"] is False and report["classification_run"] is False
    with np.load(tmp_path / "run/embedding.npz", allow_pickle=False) as z:
        assert z["embedding"].shape == (768,)


def test_wrong_embedding_fails_and_writes_failure_report(tmp_path):
    image, reference = FIXTURES / "G001_front_input.png", FIXTURES / "G001_front_reference.npz"
    vector = -module.verify_reference(image, reference)
    with pytest.raises(ValueError, match="regression"):
        module.run_smoke(
            image, tmp_path / "run", service=fake_service(vector), reference_path=reference
        )
    assert json.loads((tmp_path / "run/report.json").read_text())["status"] == "FAILED"
    assert not (tmp_path / "run/embedding.npz").exists()


def test_reference_cannot_be_applied_to_a_different_image(tmp_path):
    changed = tmp_path / "different.png"
    changed.write_bytes(b"different")
    with pytest.raises(ValueError, match="does not match"):
        module.verify_reference(changed, FIXTURES / "G001_front_reference.npz")
