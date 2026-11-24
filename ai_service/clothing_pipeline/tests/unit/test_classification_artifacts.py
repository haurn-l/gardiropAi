"""Tests for verified classifier artifact loading."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from gardirop_ai_clothing.errors import ModelArtifactError
from gardirop_ai_clothing.labeling.legacy_artifacts import (
    CLASSIFIER_MODEL_NAME,
    MARQO_REVISION,
    create_classifier_manager_from_manifest,
    create_classifier_model_manager,
    load_verified_classifier,
)
from gardirop_ai_clothing.labeling.legacy_category import TAXONOMY


@pytest.fixture
def artifact_bundle(tmp_path):
    weights = np.zeros((20, 768), dtype=np.float32)
    bias = np.zeros(20, dtype=np.float32)

    weights[1, 0] = 5.0

    artifact_path = tmp_path / "classifier.npz"

    np.savez_compressed(
        artifact_path,
        weights=weights,
        bias=bias,
        class_ids=np.arange(20),
    )

    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()

    metadata = {
        "schema_version": 1,
        "embedding_dim": 768,
        "num_classes": 20,
        "marqo_revision": MARQO_REVISION,
        "artifact_sha256": digest,
        "taxonomy": [list(item) for item in TAXONOMY],
    }

    metadata_path = tmp_path / "classifier.json"

    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False),
        encoding="utf-8",
    )

    return artifact_path, metadata_path, digest


def test_verified_artifact_loads(artifact_bundle):
    artifact, metadata, digest = artifact_bundle

    model = load_verified_classifier(
        artifact,
        metadata,
        expected_sha256=digest,
    )

    vector = np.zeros(768)
    vector[0] = 1.0

    result = model.classify(vector, "üst")

    assert result.sub_category == "T-shirt"
    assert result.class_id == 1


def test_corrupted_artifact_is_rejected(artifact_bundle):
    artifact, metadata, digest = artifact_bundle

    artifact.write_bytes(b"corrupted data")

    with pytest.raises(ValueError, match="SHA256"):
        load_verified_classifier(
            artifact,
            metadata,
            expected_sha256=digest,
        )


def test_wrong_marqo_revision_is_rejected(artifact_bundle):
    artifact, metadata_path, digest = artifact_bundle

    metadata = json.loads(metadata_path.read_text())
    metadata["marqo_revision"] = "wrong-revision"

    metadata_path.write_text(json.dumps(metadata))

    with pytest.raises(ValueError, match="marqo_revision"):
        load_verified_classifier(
            artifact,
            metadata_path,
            expected_sha256=digest,
        )


def test_wrong_taxonomy_is_rejected(artifact_bundle):
    artifact, metadata_path, digest = artifact_bundle

    metadata = json.loads(metadata_path.read_text())

    metadata["taxonomy"][0], metadata["taxonomy"][1] = (
        metadata["taxonomy"][1],
        metadata["taxonomy"][0],
    )

    metadata_path.write_text(json.dumps(metadata))

    with pytest.raises(ValueError, match="taxonomy"):
        load_verified_classifier(
            artifact,
            metadata_path,
            expected_sha256=digest,
        )


def test_wrong_expected_hash_is_rejected(artifact_bundle):
    artifact, metadata, _ = artifact_bundle

    with pytest.raises(ValueError, match="SHA256"):
        load_verified_classifier(
            artifact,
            metadata,
            expected_sha256="0" * 64,
        )


def test_missing_artifact_is_rejected(artifact_bundle):
    artifact, metadata, digest = artifact_bundle

    artifact.unlink()

    with pytest.raises(FileNotFoundError):
        load_verified_classifier(
            artifact,
            metadata,
            expected_sha256=digest,
        )


def test_classifier_manager_loads_lazily(artifact_bundle):
    """Classifier must load only on first access."""

    artifact, metadata, digest = artifact_bundle

    manager = create_classifier_model_manager(
        artifact_path=artifact,
        metadata_path=metadata,
        expected_sha256=digest,
    )

    assert manager.registered_models == (CLASSIFIER_MODEL_NAME,)

    # Nothing should be loaded during registration.
    assert manager.loaded_models == ()

    first = manager.get_model(CLASSIFIER_MODEL_NAME)

    assert manager.loaded_models == (CLASSIFIER_MODEL_NAME,)

    # Subsequent requests must reuse the same object.
    second = manager.get_model(CLASSIFIER_MODEL_NAME)

    assert first is second

    vector = np.zeros(768)
    vector[0] = 1.0

    result = first.classify(vector, "üst")

    assert result.sub_category == "T-shirt"


def test_classifier_manager_retries_failed_load(
    artifact_bundle,
):
    """Failed initialization must not be cached."""

    artifact, metadata, digest = artifact_bundle

    original_bytes = artifact.read_bytes()

    manager = create_classifier_model_manager(
        artifact_path=artifact,
        metadata_path=metadata,
        expected_sha256=digest,
    )

    # Simulate a temporarily unavailable checkpoint.
    artifact.unlink()

    with pytest.raises(ModelArtifactError):
        manager.get_model(CLASSIFIER_MODEL_NAME)

    assert manager.loaded_models == ()

    # Restore the trusted artifact.
    artifact.write_bytes(original_bytes)

    model = manager.get_model(CLASSIFIER_MODEL_NAME)

    assert model is not None
    assert manager.loaded_models == (CLASSIFIER_MODEL_NAME,)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = PROJECT_ROOT / "configs/model_manifest.yaml"


@pytest.fixture
def ready_manifest(tmp_path, artifact_bundle):
    artifact, metadata, digest = artifact_bundle

    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))

    # Explicit legacy fixture; the active parent LR must never use this loader.
    data["models"].pop("marqo_parent_lr", None)
    data["models"]["marqo_supervised_head"] = {
        "role": "subcategory_classifier",
        "status": "planned",
        "artifacts": [],
    }
    data["pipeline"]["classifier_architecture"] = "legacy_global_lr"
    data["pipeline"]["classifier_input_dimension"] = 768
    head = data["models"]["marqo_supervised_head"]
    head["status"] = "ready"
    head["artifacts"] = [
        {
            "name": "weights",
            "path": str(artifact),
            "sha256": digest,
        },
        {
            "name": "metadata",
            "path": str(metadata),
            "sha256": hashlib.sha256(metadata.read_bytes()).hexdigest(),
        },
    ]

    data["models"]["marqo_fashionsiglip"]["revision"] = MARQO_REVISION

    path = tmp_path / "model_manifest.yaml"
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True),
        encoding="utf-8",
    )

    return path


def test_manifest_manager_loads_and_caches(ready_manifest):
    manager = create_classifier_manager_from_manifest(ready_manifest)

    assert manager.loaded_models == ()

    first = manager.get_model(CLASSIFIER_MODEL_NAME)
    second = manager.get_model(CLASSIFIER_MODEL_NAME)

    assert first is second
    assert manager.loaded_models == (CLASSIFIER_MODEL_NAME,)


def test_planned_classifier_is_rejected():
    manager = create_classifier_manager_from_manifest(MANIFEST)

    with pytest.raises(ModelArtifactError):
        manager.get_model(CLASSIFIER_MODEL_NAME)

    assert manager.loaded_models == ()


def test_manifest_rejects_wrong_marqo_revision(ready_manifest):
    data = yaml.safe_load(ready_manifest.read_text(encoding="utf-8"))

    data["models"]["marqo_fashionsiglip"]["revision"] = "wrong"

    ready_manifest.write_text(
        yaml.safe_dump(data),
        encoding="utf-8",
    )

    manager = create_classifier_manager_from_manifest(ready_manifest)

    with pytest.raises(ModelArtifactError):
        manager.get_model(CLASSIFIER_MODEL_NAME)


def test_manifest_rejects_tampered_metadata(
    ready_manifest,
    artifact_bundle,
):
    _, metadata, _ = artifact_bundle

    metadata.write_text(
        '{"tampered": true}',
        encoding="utf-8",
    )

    manager = create_classifier_manager_from_manifest(ready_manifest)

    with pytest.raises(ModelArtifactError):
        manager.get_model(CLASSIFIER_MODEL_NAME)
