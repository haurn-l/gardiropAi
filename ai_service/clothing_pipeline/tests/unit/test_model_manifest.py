"""Model declarations must reflect the selected architecture and exact revisions."""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from gardirop_ai_clothing.errors import ConfigurationError, ModelArtifactError
from gardirop_ai_clothing.model_manifest import verify_manifest
from gardirop_ai_clothing.model_specs import PARENT_HEAD_NAME

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate_checkpoints.py"


def test_manifest_cli_validates_synthetic_parent_without_neural_weights(model_manifest):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", str(model_manifest)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Manifest structure: VALID" in result.stdout
    assert "Model readiness: INCOMPLETE" in result.stdout
    assert f"READY: {PARENT_HEAD_NAME}" in result.stdout


def test_require_ready_rejects_missing_encoders(model_manifest):
    with pytest.raises(ModelArtifactError, match="not ready"):
        verify_manifest(model_manifest, require_ready=True)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("revision", "main"),
        ("revision", "0" * 40),
        ("repo_id", "wrong/model"),
        ("role", "labeling_backbone"),
        ("source", "local"),
    ],
)
def test_even_planned_encoders_require_exact_identity(model_manifest, field, bad):
    data = yaml.safe_load(model_manifest.read_text())
    data["models"]["marqo_fashionsiglip"][field] = bad
    model_manifest.write_text(yaml.safe_dump(data))
    with pytest.raises(ConfigurationError):
        verify_manifest(model_manifest)


@pytest.mark.parametrize("change", ["old18", "legacy_model", "wrong_feature", "reversed_views"])
def test_obsolete_architecture_is_rejected(model_manifest, change):
    data = yaml.safe_load(model_manifest.read_text())
    if change == "old18":
        data["pipeline"]["subcategory_count"] = 18
    elif change == "legacy_model":
        data["models"]["dinov2_heads"] = {}
    elif change == "wrong_feature":
        data["pipeline"]["classifier_input_dimension"] = 768
    else:
        data["pipeline"]["view_order"] = ["BACK", "FRONT"]
    model_manifest.write_text(yaml.safe_dump(data))
    with pytest.raises(ConfigurationError):
        verify_manifest(model_manifest)


def test_missing_parent_file_is_rejected(model_manifest, parent_bundle):
    parent_bundle[0].unlink()
    with pytest.raises(OSError):
        verify_manifest(model_manifest)


def test_duplicate_or_missing_named_artifacts_are_rejected(model_manifest):
    data = yaml.safe_load(model_manifest.read_text())
    head = data["models"][PARENT_HEAD_NAME]
    head["artifacts"].append(head["artifacts"][0])
    model_manifest.write_text(yaml.safe_dump(data))
    with pytest.raises(ConfigurationError, match="duplicate"):
        verify_manifest(model_manifest)


def test_corrupted_parent_is_rejected(model_manifest, parent_bundle):
    parent_bundle[0].write_bytes(b"corrupt")
    with pytest.raises(ModelArtifactError, match="SHA256"):
        verify_manifest(model_manifest)
