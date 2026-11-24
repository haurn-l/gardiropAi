"""Test preparation transaction with small fake downloads, not real encoders."""

import importlib.util
from pathlib import Path

import pytest
import yaml

from gardirop_ai_clothing.errors import ModelArtifactError
from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256
from gardirop_ai_clothing.model_specs import ENCODERS

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("prepare_script", ROOT / "scripts/prepare_models.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def mock_downloader(tmp_path, monkeypatch):
    paths = {}
    for name, original in list(ENCODERS.items()):
        spec = dict(original)
        if "files_sha256" in spec:
            spec["files_sha256"] = dict(spec["files_sha256"])
        for filename in spec["files"]:
            local = tmp_path / name / filename
            local.parent.mkdir(exist_ok=True)
            local.write_bytes((name + filename).encode())
            paths[(spec["repo_id"], filename)] = local
            if "files_sha256" in spec:
                spec["files_sha256"][filename] = file_sha256(local)
            if filename.endswith(".safetensors"):
                spec["weight_sha256"] = file_sha256(local)
        monkeypatch.setitem(ENCODERS, name, spec)
    calls = []

    def download(**kwargs):
        expected = next(s for s in ENCODERS.values() if s["repo_id"] == kwargs["repo_id"])
        assert kwargs["revision"] == expected["revision"]
        calls.append(kwargs)
        return paths[(kwargs["repo_id"], kwargs["filename"])]

    return download, calls


def test_prepare_pins_revisions_supports_offline_and_commits_once(
    model_manifest,
    parent_bundle,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(module, "PARENT_HEAD_SHA256", file_sha256(parent_bundle[0]))
    download, calls = mock_downloader(tmp_path, monkeypatch)
    states = module.prepare(model_manifest, offline=True, downloader=download)
    assert len(calls) == 6
    assert all(c["local_files_only"] is True for c in calls)
    assert all(s.startswith("READY:") for s in states)
    assert all(
        m["status"] == "ready"
        for m in yaml.safe_load(model_manifest.read_text())["models"].values()
    )


def test_failed_download_preserves_previous_manifest(model_manifest, parent_bundle, monkeypatch):
    monkeypatch.setattr(module, "PARENT_HEAD_SHA256", file_sha256(parent_bundle[0]))
    previous = model_manifest.read_bytes()

    def fail(**kwargs):
        raise OSError("download interrupted")

    with pytest.raises(OSError, match="interrupted"):
        module.prepare(model_manifest, downloader=fail)
    assert model_manifest.read_bytes() == previous


def test_wrong_cached_weight_does_not_mark_models_ready(
    model_manifest,
    parent_bundle,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(module, "PARENT_HEAD_SHA256", file_sha256(parent_bundle[0]))
    download, _ = mock_downloader(tmp_path, monkeypatch)
    ENCODERS["marqo_fashionsiglip"]["weight_sha256"] = "0" * 64
    previous = model_manifest.read_bytes()
    with pytest.raises(ModelArtifactError, match="pinned weights"):
        module.prepare(model_manifest, downloader=download)
    assert model_manifest.read_bytes() == previous
    assert list(model_manifest.parent.glob("tmp*.yaml")) == []


def test_rehashed_modified_dynamic_code_cannot_be_marked_ready(
    model_manifest, parent_bundle, tmp_path, monkeypatch
):
    monkeypatch.setattr(module, "PARENT_HEAD_SHA256", file_sha256(parent_bundle[0]))
    download, _ = mock_downloader(tmp_path, monkeypatch)
    from gardirop_ai_clothing.model_specs import BIREFNET_MODEL_NAME

    code = tmp_path / BIREFNET_MODEL_NAME / "birefnet.py"
    code.write_bytes(b"unexpected source despite new self-recorded hash")
    previous = model_manifest.read_bytes()
    with pytest.raises(ModelArtifactError, match="pinned file"):
        module.prepare(model_manifest, downloader=download)
    assert model_manifest.read_bytes() == previous
