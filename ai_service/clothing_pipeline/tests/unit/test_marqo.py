"""Encoder contracts and a tiny fake torch model; no real model inference."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
import yaml
from PIL import Image

from gardirop_ai_clothing.embeddings import marqo
from gardirop_ai_clothing.errors import (
    ImageProcessingError,
    InferenceError,
    ModelArtifactError,
)
from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256
from gardirop_ai_clothing.model_manager import ModelManager
from gardirop_ai_clothing.model_specs import ENCODERS

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/marqo"


def test_normalize_is_float32_unit_readonly_and_does_not_mutate_input():
    raw = np.arange(1, 769, dtype=np.float32)
    before = raw.copy()
    vector = marqo.normalize_view_embedding(raw)
    assert vector.shape == (768,) and vector.dtype == np.float32
    assert np.linalg.norm(vector) == pytest.approx(1.0)
    np.testing.assert_array_equal(raw, before)
    with pytest.raises(ValueError):
        vector[0] = 1.0


@pytest.mark.parametrize(
    "raw",
    [
        np.zeros(768),
        np.zeros(1536),
        np.ones((1, 768)),
        np.full(768, np.nan),
        np.full(768, np.inf),
        np.ones(768, dtype=np.int32),
    ],
)
def test_bad_vectors_are_rejected(raw):
    with pytest.raises(InferenceError):
        marqo.normalize_view_embedding(raw)


def test_large_finite_float32_values_do_not_overflow_normalization():
    assert np.linalg.norm(
        marqo.normalize_view_embedding(np.full(768, 1e38, dtype=np.float32))
    ) == pytest.approx(1.0)


def test_service_loads_once_and_runs_once_per_image(monkeypatch):
    loads, calls = [], []

    def loader(*args, **kwargs):
        loads.append(1)
        return marqo.MarqoEncoder(
            lambda image: calls.append(image.size) or np.ones(768), device="cpu"
        )

    monkeypatch.setattr(marqo, "load_marqo_encoder", loader)
    service = marqo.create_marqo_service("unused.yaml", device="cpu")
    assert not loads
    image = Image.new("RGB", (30, 60))
    service.encode(image)
    service.encode(image)
    assert loads == [1] and calls == [(30, 60), (30, 60)]


def test_invalid_image_is_rejected_before_loading(monkeypatch):
    def unexpected_load(*args, **kwargs):
        pytest.fail("Invalid image must not load a model")

    monkeypatch.setattr(marqo, "load_marqo_encoder", unexpected_load)
    service = marqo.create_marqo_service("unused.yaml")
    for image in [None, Image.new("RGBA", (10, 10))]:
        with pytest.raises(ImageProcessingError):
            service.encode(image)
    assert service.manager.loaded_models == ()


def test_service_respects_shared_execution_slot():
    manager = ModelManager({marqo.MARQO_MODEL_NAME: lambda: pytest.fail("must not load")})
    service = marqo.MarqoEmbeddingService(manager)
    with manager.gpu_slot():
        with pytest.raises(InferenceError, match="No GPU"):
            service.encode(Image.new("RGB", (8, 8)), timeout_seconds=0)


def test_failed_forward_releases_slot_for_next_attempt():
    calls = []

    def runner(image):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("forward failed")
        return np.ones(768)

    encoder = marqo.MarqoEncoder(runner, device="cpu")
    service = marqo.MarqoEmbeddingService(ModelManager({marqo.MARQO_MODEL_NAME: lambda: encoder}))
    with pytest.raises(InferenceError):
        service.encode(Image.new("RGB", (8, 8)))
    assert service.encode(Image.new("RGB", (8, 8)), timeout_seconds=0).shape == (768,)


def test_explicit_cuda_does_not_silently_fallback():
    cpu_only = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    assert marqo.resolve_device("auto", cpu_only) == "cpu"
    with pytest.raises(ModelArtifactError, match="CUDA was requested"):
        marqo.resolve_device("cuda", cpu_only)


@pytest.fixture
def local_marqo(model_manifest, tmp_path, monkeypatch):
    config = tmp_path / "open_clip_config.json"
    config.write_bytes((FIXTURES / "open_clip_config.json").read_bytes())
    weights = tmp_path / "open_clip_model.safetensors"
    weights.write_bytes(b"synthetic-checkpoint-for-constructor-test")
    spec = dict(ENCODERS[marqo.MARQO_MODEL_NAME])
    spec["weight_sha256"] = file_sha256(weights)
    monkeypatch.setitem(ENCODERS, marqo.MARQO_MODEL_NAME, spec)
    data = yaml.safe_load(model_manifest.read_text())
    data["models"][marqo.MARQO_MODEL_NAME].update(
        status="ready",
        artifacts=[
            {"name": p.name, "path": str(p), "sha256": file_sha256(p)} for p in [config, weights]
        ],
    )
    model_manifest.write_text(yaml.safe_dump(data))
    return model_manifest, config, weights


def test_loader_uses_published_local_config_strict_weights_and_frozen_fp32(
    local_marqo,
    monkeypatch,
):
    path, config, _ = local_marqo
    events = []

    class TinyFakeModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.marker = torch.nn.Parameter(torch.ones(1))

        def encode_image(self, tensor, normalize):
            assert self.training is False and self.marker.requires_grad is False
            assert torch.is_inference_mode_enabled()
            assert not torch.is_autocast_enabled("cpu")
            assert tensor.shape == (1, 3, 224, 224) and tensor.dtype == torch.float32
            assert normalize is False
            return torch.ones((1, 768))

    model = TinyFakeModel()

    def create(name, **kwargs):
        assert name == f"local-dir:{config.parent}"
        assert kwargs == dict(
            load_weights=True,
            require_pretrained=True,
            weights_only=True,
            precision="fp32",
            device="cpu",
            pretrained_image=False,
            pretrained_text=False,
        )
        events.append("create")
        return model, None, lambda image: torch.zeros((3, 224, 224))

    monkeypatch.setitem(
        sys.modules, "open_clip", SimpleNamespace(create_model_and_transforms=create)
    )
    encoder = marqo.load_marqo_encoder(path, device="cpu")
    with torch.autocast(device_type="cpu", dtype=torch.bfloat16):
        vector = encoder.encode(Image.new("RGB", (40, 80)))
    assert events == ["create"]
    assert vector.shape == (768,) and np.linalg.norm(vector) == pytest.approx(1.0)


def test_modified_published_config_is_rejected_even_if_manifest_rehashed(local_marqo):
    path, config, _ = local_marqo
    data = json.loads(config.read_text())
    data["preprocess_cfg"]["resize_mode"] = "shortest"
    config.write_text(json.dumps(data))
    manifest = yaml.safe_load(path.read_text())
    manifest["models"][marqo.MARQO_MODEL_NAME]["artifacts"][0]["sha256"] = file_sha256(config)
    path.write_text(yaml.safe_dump(manifest))
    with pytest.raises(ModelArtifactError, match="configuration SHA256"):
        marqo.load_marqo_encoder(path, device="cpu")


def test_missing_or_unready_weights_fail_before_torch_build(model_manifest):
    with pytest.raises(ModelArtifactError, match="not ready"):
        marqo.load_marqo_encoder(model_manifest, device="cpu")


def test_checkpoint_load_failure_is_not_cached(local_marqo, monkeypatch):
    path, _, _ = local_marqo

    def broken_factory(*args, **kwargs):
        raise RuntimeError("checkpoint key mismatch")

    monkeypatch.setitem(
        sys.modules, "open_clip", SimpleNamespace(create_model_and_transforms=broken_factory)
    )
    service = marqo.create_marqo_service(path, device="cpu")
    with pytest.raises(ModelArtifactError):
        service.encode(Image.new("RGB", (30, 30)))
    assert service.manager.loaded_models == ()
