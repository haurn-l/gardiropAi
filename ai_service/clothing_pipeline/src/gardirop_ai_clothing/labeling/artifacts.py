"""Active parent LR loaders. Legacy 768D loading lives in legacy_artifacts.py."""

from pathlib import Path

from gardirop_ai_clothing.labeling.category import CategoryClassifier
from gardirop_ai_clothing.labeling.parent_artifacts import load_parent_parameters
from gardirop_ai_clothing.model_manager import ModelManager
from gardirop_ai_clothing.model_manifest import (
    artifact_entries,
    load_manifest,
    verified_model_files,
)
from gardirop_ai_clothing.model_specs import PARENT_HEAD_NAME

CLASSIFIER_MODEL_NAME = PARENT_HEAD_NAME


def load_verified_classifier(
    artifact_path: str | Path,
    metadata_path: str | Path,
    *,
    expected_sha256: str,
    expected_metadata_sha256: str,
) -> CategoryClassifier:
    parameters = load_parent_parameters(
        Path(artifact_path),
        Path(metadata_path),
        weights_sha256=expected_sha256,
        metadata_sha256=expected_metadata_sha256,
    )
    return CategoryClassifier(parameters.weights, parameters.bias, artifact_sha256=expected_sha256)


def load_classifier_from_manifest(manifest_path: str | Path) -> CategoryClassifier:
    path = Path(manifest_path).expanduser().resolve()
    data = load_manifest(path)
    declared = artifact_entries(data["models"][CLASSIFIER_MODEL_NAME], path.parent.parent)
    verified = verified_model_files(path, CLASSIFIER_MODEL_NAME)
    return load_verified_classifier(
        verified["weights"],
        verified["metadata"],
        expected_sha256=declared["weights"][1],
        expected_metadata_sha256=declared["metadata"][1],
    )


def create_classifier_model_manager(
    artifact_path: str | Path,
    metadata_path: str | Path,
    *,
    expected_sha256: str,
    expected_metadata_sha256: str,
) -> ModelManager:
    return ModelManager(
        {
            CLASSIFIER_MODEL_NAME: lambda: load_verified_classifier(
                artifact_path,
                metadata_path,
                expected_sha256=expected_sha256,
                expected_metadata_sha256=expected_metadata_sha256,
            )
        }
    )


def create_classifier_manager_from_manifest(manifest_path: str | Path) -> ModelManager:
    path = Path(manifest_path).expanduser().resolve()
    return ModelManager({CLASSIFIER_MODEL_NAME: lambda: load_classifier_from_manifest(path)})
