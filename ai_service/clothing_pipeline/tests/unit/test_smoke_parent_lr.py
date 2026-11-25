"""A failing reference check must never print PASSED or export success vectors."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from gardirop_ai_clothing.contracts import FUSION_METHOD, VIEW_ORDER
from gardirop_ai_clothing.labeling.artifacts import CLASSIFIER_MODEL_NAME
from gardirop_ai_clothing.labeling.category import SCORE_KIND, CategoryClassifier
from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256
from gardirop_ai_clothing.labeling.service import ParentClassificationService
from gardirop_ai_clothing.model_manager import ModelManager
from gardirop_ai_clothing.model_specs import MARQO_REVISION

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "smoke_parent_lr", ROOT / "scripts/smoke_parent_lr.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def synthetic_reference(tmp_path, monkeypatch):
    features = tmp_path / "features.npz"
    np.savez_compressed(features, front_back=np.ones((1, 2, 768)), case_ids=np.array(["S001"]))
    sha = "a" * 64
    monkeypatch.setattr(module, "PARENT_HEAD_SHA256", sha)
    reference = {
        "schema_version": 1,
        "classifier_sha256": sha,
        "encoder_revision": MARQO_REVISION,
        "fusion_method": FUSION_METHOD,
        "view_order": list(VIEW_ORDER),
        "score_kind": SCORE_KIND,
        "score_absolute_tolerance": module.SCORE_ATOL,
        "features_sha256": file_sha256(features),
        "cases": [
            {
                "case_id": "S001",
                "selected_parent": "üst",
                "top3": [
                    {"class_id": i, "label": label, "score": 0.0, "score_kind": SCORE_KIND}
                    for i, label in enumerate(["Gömlek", "T-shirt", "Bluz"])
                ],
            }
        ],
    }
    info = tmp_path / "reference.json"
    info.write_text(json.dumps(reference, ensure_ascii=False), encoding="utf-8")
    head = CategoryClassifier(np.zeros((20, 1536)), np.zeros(20), artifact_sha256=sha)
    service = ParentClassificationService(ModelManager({CLASSIFIER_MODEL_NAME: lambda: head}))
    return features, info, service


def test_matching_outputs_are_exported_without_encoder_inference(tmp_path, synthetic_reference):
    features, info, service = synthetic_reference
    report = module.run_smoke(features, info, tmp_path / "run", service=service)
    assert report["status"] == "PASSED"
    assert report["matching_recorded_outputs"] == 1
    assert report["encoder_inference"] is False and report["training_run"] is False
    with np.load(tmp_path / "run/embeddings.npz", allow_pickle=False) as data:
        assert data["embeddings"].shape == (1, 1536)


def test_wrong_recorded_score_writes_failure_report(tmp_path, synthetic_reference):
    features, info, service = synthetic_reference
    data = json.loads(info.read_text())
    data["cases"][0]["top3"][0]["score"] = 10
    info.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="regression"):
        module.run_smoke(features, info, tmp_path / "run", service=service)
    report = json.loads((tmp_path / "run/report.json").read_text())
    assert report["status"] == "FAILED" and report["matching_recorded_outputs"] == 0
    assert (tmp_path / "run/cases.json").is_file()
    assert not (tmp_path / "run/embeddings.npz").exists()


def test_wrong_case_alignment_is_rejected_before_head_loading(tmp_path, synthetic_reference):
    features, info, service = synthetic_reference
    data = json.loads(info.read_text())
    data["cases"][0]["case_id"] = "S002"
    info.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="alignment"):
        module.run_smoke(features, info, tmp_path / "run", service=service)
    assert service.manager.loaded_models == ()


def test_actual_reference_fixture_has_40_aligned_records():
    folder = ROOT / "tests/fixtures/parent_lr"
    views, reference = module.load_reference(
        folder / "recorded_views.npz", folder / "reference.json"
    )
    assert views.shape == (40, 2, 768)
    assert len(reference["cases"]) == 40
    assert reference["cases"][26]["selected_parent"] == "alt"
