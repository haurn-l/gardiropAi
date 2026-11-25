"""Historical 768D artifact loaders, isolated from active parent LR."""

import hashlib
import hmac
import json
import re
from pathlib import Path

import yaml

from gardirop_ai_clothing.config import PROJECT_ROOT
from gardirop_ai_clothing.labeling.legacy_category import (
    EMBEDDING_DIM,
    NUM_CLASSES,
    TAXONOMY,
    CategoryClassifier,
)
from gardirop_ai_clothing.model_manager import ModelManager
from gardirop_ai_clothing.model_specs import MARQO_REVISION

SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def calculate_sha256(path: Path) -> str:
    """Calculate SHA256 without reading the whole artifact at once."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def load_verified_classifier(
    artifact_path: str | Path,
    metadata_path: str | Path,
    *,
    expected_sha256: str,
) -> CategoryClassifier:
    """Load classifier only after artifact and metadata checks."""

    artifact_path = Path(artifact_path)
    metadata_path = Path(metadata_path)

    if not SHA256_PATTERN.fullmatch(expected_sha256):
        raise ValueError("Invalid expected SHA256.")

    if not artifact_path.is_file():
        raise FileNotFoundError(f"Classifier artifact not found: {artifact_path}")

    if not metadata_path.is_file():
        raise FileNotFoundError(f"Classifier metadata not found: {metadata_path}")

    actual_hash = calculate_sha256(artifact_path)

    if not hmac.compare_digest(
        actual_hash.lower(),
        expected_sha256.lower(),
    ):
        raise ValueError("Classifier artifact SHA256 mismatch.")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    if not isinstance(metadata, dict):
        raise ValueError("Invalid classifier metadata.")

    expected_fields = {
        "schema_version": 1,
        "embedding_dim": EMBEDDING_DIM,
        "num_classes": NUM_CLASSES,
        "marqo_revision": MARQO_REVISION,
    }

    for key, expected_value in expected_fields.items():
        if metadata.get(key) != expected_value:
            raise ValueError(f"Classifier metadata mismatch: {key}")

    metadata_hash = metadata.get("artifact_sha256")

    if not isinstance(metadata_hash, str):
        raise ValueError("Missing artifact SHA256 in metadata.")

    if not hmac.compare_digest(
        metadata_hash.lower(),
        expected_sha256.lower(),
    ):
        raise ValueError("Metadata SHA256 mismatch.")

    expected_taxonomy = [list(item) for item in TAXONOMY]

    if metadata.get("taxonomy") != expected_taxonomy:
        raise ValueError("Classifier taxonomy mismatch.")

    # Existing loader also verifies weight/bias dimensions
    # and the class ID sequence inside the NPZ file.
    return CategoryClassifier.from_npz(artifact_path)


CLASSIFIER_MODEL_NAME = "marqo_supervised_head"


def create_classifier_model_manager(
    artifact_path: str | Path,
    metadata_path: str | Path,
    *,
    expected_sha256: str,
) -> ModelManager:
    """Register a verified classifier with the existing ModelManager.

    The classifier is not loaded until its first use.
    """

    artifact_path = Path(artifact_path).expanduser()
    metadata_path = Path(metadata_path).expanduser()

    def load_classifier() -> CategoryClassifier:
        return load_verified_classifier(
            artifact_path=artifact_path,
            metadata_path=metadata_path,
            expected_sha256=expected_sha256,
        )

    return ModelManager(
        loaders={
            CLASSIFIER_MODEL_NAME: load_classifier,
        },
    )


def create_classifier_manager_from_manifest(
    manifest_path: str | Path,
) -> ModelManager:
    """Register a lazily loaded classifier using a model manifest."""

    manifest_path = Path(manifest_path).expanduser()

    def load_from_manifest() -> CategoryClassifier:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

        if not isinstance(manifest, dict):
            raise ValueError("Invalid model manifest.")

        pipeline = manifest.get("pipeline", {})

        if not isinstance(pipeline, dict) or (
            pipeline.get("embedding_dimension_per_view") != 768
            or pipeline.get("combined_embedding_dimension") != 1536
            or pipeline.get("subcategory_count") != 20
        ):
            raise ValueError("Incompatible pipeline architecture.")

        models = manifest.get("models", {})

        if not isinstance(models, dict):
            raise ValueError("Invalid model definitions.")

        if "marqo_parent_lr" in models:
            raise ValueError("The 1536D parent LR requires the parent artifact loader.")

        head = models.get(CLASSIFIER_MODEL_NAME, {})
        marqo = models.get("marqo_fashionsiglip", {})

        if not isinstance(head, dict) or not isinstance(marqo, dict):
            raise ValueError("Invalid model configuration.")

        if head.get("status") != "ready":
            raise ValueError("Classifier is not ready.")

        if head.get("role") != "subcategory_classifier":
            raise ValueError("Unexpected classifier role.")

        if marqo.get("repo_id") != "Marqo/marqo-fashionSigLIP":
            raise ValueError("Unexpected Marqo model.")

        if marqo.get("revision") != MARQO_REVISION:
            raise ValueError("Marqo revision mismatch.")

        artifact_entries = head.get("artifacts")

        if not isinstance(artifact_entries, list):
            raise ValueError("Invalid artifact definitions.")

        entries = {}

        for entry in artifact_entries:
            if not isinstance(entry, dict):
                raise ValueError("Invalid artifact entry.")

            name = entry.get("name")

            if name not in {"weights", "metadata"} or name in entries:
                raise ValueError("Unexpected or duplicate artifact.")

            entries[name] = entry

        if set(entries) != {"weights", "metadata"}:
            raise ValueError("Classifier requires weights and metadata.")

        def resolve_entry(name: str) -> tuple[Path, str]:
            entry = entries[name]
            path_value = entry.get("path")
            sha256 = entry.get("sha256")

            if not isinstance(path_value, str) or not path_value.strip():
                raise ValueError(f"Invalid path: {name}")

            if not isinstance(sha256, str) or not SHA256_PATTERN.fullmatch(sha256):
                raise ValueError(f"Invalid SHA256: {name}")

            path = Path(path_value).expanduser()

            if not path.is_absolute():
                path = PROJECT_ROOT / path

            return path, sha256

        weights_path, weights_hash = resolve_entry("weights")
        metadata_path, metadata_hash = resolve_entry("metadata")

        # The existing classifier loader verifies the weights.
        # Verify the metadata file independently as well.
        actual_metadata_hash = calculate_sha256(metadata_path)

        if not hmac.compare_digest(
            actual_metadata_hash.lower(),
            metadata_hash.lower(),
        ):
            raise ValueError("Classifier metadata SHA256 mismatch.")

        return load_verified_classifier(
            artifact_path=weights_path,
            metadata_path=metadata_path,
            expected_sha256=weights_hash,
        )

    return ModelManager(
        loaders={
            CLASSIFIER_MODEL_NAME: load_from_manifest,
        },
    )
