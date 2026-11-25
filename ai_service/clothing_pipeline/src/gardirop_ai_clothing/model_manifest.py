"""Validate selected model identities and local artifact integrity."""

import hmac
import re
from pathlib import Path

import yaml

from gardirop_ai_clothing.errors import ConfigurationError, ModelArtifactError
from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256, load_parent_parameters
from gardirop_ai_clothing.model_specs import ENCODERS, PARENT_HEAD_NAME, PIPELINE_CONTRACT

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def load_manifest(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError("Invalid manifest YAML.") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ConfigurationError("Unsupported manifest schema version.")
    pipeline = data.get("pipeline")
    if not isinstance(pipeline, dict):
        raise ConfigurationError("Missing pipeline configuration.")
    for key, expected in PIPELINE_CONTRACT.items():
        if type(pipeline.get(key)) is not type(expected) or pipeline[key] != expected:
            raise ConfigurationError(f"Pipeline contract mismatch: {key}")
    models = data.get("models")
    if not isinstance(models, dict) or set(models) != {*ENCODERS, PARENT_HEAD_NAME}:
        raise ConfigurationError("Model entries differ from the selected architecture.")
    return data


def artifact_entries(model: dict, root: Path) -> dict[str, tuple[Path, str]]:
    entries = model.get("artifacts")
    if not isinstance(entries, list):
        raise ConfigurationError("Artifacts must be a list.")
    result = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ConfigurationError("Invalid artifact entry.")
        name, path, digest = entry.get("name"), entry.get("path"), entry.get("sha256")
        if not isinstance(name, str) or not name or name in result:
            raise ConfigurationError("Missing or duplicate artifact name.")
        if not isinstance(path, str) or not path.strip():
            raise ConfigurationError("Invalid artifact path.")
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise ConfigurationError("Invalid artifact SHA256.")
        local = Path(path).expanduser()
        result[name] = (local if local.is_absolute() else root / local, digest)
    return result


def _verify_model(name: str, model: dict, root: Path, *, require_ready: bool):
    if not isinstance(model, dict):
        raise ConfigurationError(f"{name}: invalid model entry.")
    if name in ENCODERS:
        spec = ENCODERS[name]
        for key in ("role", "repo_id", "revision"):
            if model.get(key) != spec[key]:
                raise ConfigurationError(f"{name}: unexpected {key}.")
        expected_source = "huggingface"
    else:
        spec = None
        if model.get("role") != "subcategory_classifier":
            raise ConfigurationError("Unexpected parent LR role.")
        expected_source = "local"
    if model.get("source") != expected_source:
        raise ConfigurationError(f"{name}: unexpected source.")
    status = model.get("status")
    if status not in {"planned", "ready"}:
        raise ConfigurationError(f"{name}: invalid status.")
    entries = artifact_entries(model, root)
    if status == "planned":
        if require_ready:
            raise ModelArtifactError(f"{name}: model artifacts are not ready.")
        return f"PLANNED: {name}", entries
    required = set(spec["files"]) if spec else {"weights", "metadata"}
    if set(entries) != required:
        raise ModelArtifactError(f"{name}: required artifact set mismatch.")
    for artifact_path, digest in entries.values():
        if not hmac.compare_digest(file_sha256(artifact_path), digest):
            raise ModelArtifactError(f"{name}: SHA256 mismatch: {artifact_path.name}")
    if spec:
        for filename, expected in spec.get("files_sha256", {}).items():
            if entries[filename][1] != expected:
                raise ModelArtifactError(f"{name}: pinned file SHA256 mismatch: {filename}")
        weight_name = next(n for n in spec["files"] if n.endswith(".safetensors"))
        if entries[weight_name][1] != spec["weight_sha256"]:
            raise ModelArtifactError(f"{name}: pinned weights SHA256 mismatch.")
    else:
        try:
            load_parent_parameters(
                entries["weights"][0],
                entries["metadata"][0],
                weights_sha256=entries["weights"][1],
                metadata_sha256=entries["metadata"][1],
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise ModelArtifactError(f"Invalid parent LR package: {exc}") from exc
    return f"READY: {name} ({len(entries)} verified files)", entries


def verified_model_files(path: Path, name: str) -> dict[str, Path]:
    """Verify only the requested ready model before loading it."""
    manifest = load_manifest(path)
    if name not in manifest["models"]:
        raise ConfigurationError(f"Unknown model: {name}")
    _, entries = _verify_model(
        name,
        manifest["models"][name],
        path.resolve().parent.parent,
        require_ready=True,
    )
    return {key: value[0] for key, value in entries.items()}


def verify_manifest(path: Path, *, require_ready: bool = False) -> list[str]:
    manifest = load_manifest(path)
    return [
        _verify_model(name, model, path.resolve().parent.parent, require_ready=require_ready)[0]
        for name, model in manifest["models"].items()
    ]
