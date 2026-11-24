"""Verified lazy CPU head; no neural loading or GPU slot for LR."""

import numpy as np
import pytest

from gardirop_ai_clothing.embeddings.fusion import fuse_views
from gardirop_ai_clothing.errors import InferenceError, ModelArtifactError
from gardirop_ai_clothing.labeling.artifacts import (
    CLASSIFIER_MODEL_NAME,
    create_classifier_model_manager,
    load_verified_classifier,
)
from gardirop_ai_clothing.labeling.category import CategoryClassifier
from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256
from gardirop_ai_clothing.labeling.service import ParentClassificationService, create_parent_service
from gardirop_ai_clothing.model_manager import ModelManager


def test_verified_active_loader_requires_both_checksums(parent_bundle):
    weights, info = parent_bundle
    args = dict(expected_sha256=file_sha256(weights), expected_metadata_sha256=file_sha256(info))
    classifier = load_verified_classifier(weights, info, **args)
    assert classifier.weights.shape == (20, 1536)
    assert classifier.artifact_sha256 == args["expected_sha256"]
    info.write_bytes(info.read_bytes() + b" ")
    with pytest.raises(ValueError, match="SHA256"):
        load_verified_classifier(weights, info, **args)


def test_direct_manager_is_lazy_and_detects_changed_weights(parent_bundle):
    weights, info = parent_bundle
    manager = create_classifier_model_manager(
        weights,
        info,
        expected_sha256=file_sha256(weights),
        expected_metadata_sha256=file_sha256(info),
    )
    assert manager.loaded_models == ()
    weights.write_bytes(b"changed")
    with pytest.raises(ModelArtifactError):
        manager.get_model(CLASSIFIER_MODEL_NAME)
    assert manager.loaded_models == ()


def test_active_manifest_loads_only_small_head_even_with_neural_models_planned(model_manifest):
    service = create_parent_service(model_manifest)
    assert service.manager.loaded_models == ()
    result = service.analyze_views(front=np.ones(768), back=np.ones(768), main_category="üst")
    assert result.embedding.shape == (1536,)
    assert result.classification.class_id == 0
    assert service.manager.loaded_models == (CLASSIFIER_MODEL_NAME,)
    first = service.manager.get_model(CLASSIFIER_MODEL_NAME)
    assert service.manager.get_model(CLASSIFIER_MODEL_NAME) is first


def test_category_change_reuses_embedding_and_one_head_without_a_gpu_slot(monkeypatch):
    loaded = []

    def load():
        loaded.append(True)
        return CategoryClassifier(np.zeros((20, 1536)), np.zeros(20))

    manager = ModelManager({CLASSIFIER_MODEL_NAME: load})

    def forbidden(**kwargs):
        pytest.fail("CPU classifier must not reserve the GPU.")

    monkeypatch.setattr(manager, "gpu_slot", forbidden)
    service = ParentClassificationService(manager)
    pair = service.analyze_views(front=np.ones(768), back=np.ones(768), main_category="üst")
    original = pair.embedding.copy()
    changed = service.classify(pair.embedding, "alt")
    assert pair.classification.class_id == 0 and changed.class_id == 9
    assert len(loaded) == 1
    np.testing.assert_array_equal(pair.embedding, original)


@pytest.mark.parametrize(
    "front,back,parent",
    [
        (None, np.ones(768), "üst"),
        (np.ones(768), None, "üst"),
        (np.ones(768), np.ones(768), "invalid"),
    ],
)
def test_invalid_pair_never_loads_a_model(model_manifest, front, back, parent):
    service = create_parent_service(model_manifest)
    with pytest.raises(ValueError):
        service.analyze_views(front=front, back=back, main_category=parent)
    assert service.manager.loaded_models == ()


def test_legacy_model_object_cannot_accidentally_become_active():
    service = ParentClassificationService(ModelManager({CLASSIFIER_MODEL_NAME: object}))
    vector = fuse_views(front=np.ones(768), back=np.ones(768))
    with pytest.raises(InferenceError, match="1536D"):
        service.classify(vector, "üst")
