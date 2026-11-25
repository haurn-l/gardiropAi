"""Exercise the local adapter with a tiny fake model, never real weights."""

import json

import numpy as np
import pytest
import torch
from PIL import Image
from transformers import AutoModelForImageSegmentation

from gardirop_ai_clothing.errors import ModelArtifactError
from gardirop_ai_clothing.image import birefnet_local as module
from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256


@pytest.fixture
def local_model(tmp_path, monkeypatch):
    config = {
        "bb_pretrained": False,
        "auto_map": {
            "AutoConfig": "BiRefNet_config.BiRefNetConfig",
            "AutoModelForImageSegmentation": "birefnet.BiRefNet",
        },
    }
    files = {}
    for name, content in {
        "config.json": json.dumps(config).encode(),
        "BiRefNet_config.py": b"# fake config",
        "birefnet.py": b"# fake model",
        "model.safetensors": b"fake weights never opened",
    }.items():
        path = tmp_path / name
        path.write_bytes(content)
        files[name] = path
    monkeypatch.setattr(module, "verified_model_files", lambda path, name: files)
    monkeypatch.setattr(
        module, "SUPPORT_SHA256", {n: file_sha256(files[n]) for n in module.SUPPORT_SHA256}
    )
    calls = []

    class TinyModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.parameter = torch.nn.Parameter(torch.zeros(1))

        def forward(self, tensor):
            assert not self.training and not self.parameter.requires_grad
            assert torch.is_inference_mode_enabled() and not torch.is_grad_enabled()
            assert not torch.is_autocast_enabled("cpu")
            assert tensor.shape == (1, 3, 1024, 704) and tensor.dtype == torch.float32
            return [torch.zeros((1, 1, 4, 4))]

    model = TinyModel()

    def load(path, **kwargs):
        calls.append((path, kwargs))
        return model, {
            "missing_keys": [],
            "unexpected_keys": [],
            "mismatched_keys": [],
            "error_msgs": [],
        }

    monkeypatch.setattr(AutoModelForImageSegmentation, "from_pretrained", load)
    return files, calls, model


def test_local_loader_is_frozen_offline_and_restores_original_mask_size(local_model, tmp_path):
    files, calls, _ = local_model
    segmenter = module.load_birefnet_segmenter(tmp_path / "unused.yaml", device="cpu")
    alpha = segmenter.predict_alpha(Image.new("RGB", (32, 48)))
    assert alpha.shape == (48, 32) and alpha.dtype == np.uint8
    assert np.all(alpha == 128) and segmenter.device == "cpu" and segmenter.precision == "fp32"
    assert calls == [
        (
            str(files["config.json"].parent),
            {
                "trust_remote_code": True,
                "local_files_only": True,
                "use_safetensors": True,
                "output_loading_info": True,
            },
        )
    ]


def test_changed_local_code_rejected_before_model_factory(local_model, tmp_path):
    files, calls, _ = local_model
    files["birefnet.py"].write_bytes(b"changed")
    with pytest.raises(ModelArtifactError, match="pinned support file"):
        module.load_birefnet_segmenter(tmp_path / "unused.yaml", device="cpu")
    assert calls == []


def test_scattered_files_rejected_before_model_factory(local_model, tmp_path):
    files, calls, _ = local_model
    other = tmp_path / "other/model.safetensors"
    other.parent.mkdir()
    other.write_bytes(b"other")
    files["model.safetensors"] = other
    with pytest.raises(ModelArtifactError, match="share"):
        module.load_birefnet_segmenter(tmp_path / "unused.yaml", device="cpu")
    assert calls == []


@pytest.mark.parametrize(
    "key", ["missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs"]
)
def test_partial_weight_loading_is_never_accepted(local_model, tmp_path, monkeypatch, key):
    _, _, model = local_model
    monkeypatch.setattr(
        AutoModelForImageSegmentation, "from_pretrained", lambda *a, **kw: (model, {key: ["bad"]})
    )
    with pytest.raises(ModelArtifactError) as error:
        module.load_birefnet_segmenter(tmp_path / "unused.yaml", device="cpu")
    assert "fully match" in str(error.value.__cause__)


def test_shared_export_loader_uses_the_same_verified_frozen_model(local_model, tmp_path):
    _, calls, model = local_model
    loaded, device = module.load_birefnet_model(tmp_path / "unused.yaml", device="cpu")
    assert loaded is model and device == "cpu"
    assert not loaded.training and not loaded.parameter.requires_grad
    assert len(calls) == 1
