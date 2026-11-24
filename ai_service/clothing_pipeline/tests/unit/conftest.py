"""Synthetic parent LR files; no neural models or external downloads."""

import json
from pathlib import Path

import numpy as np
import pytest
import yaml

# Shared test-only service: real image/fusion code, synthetic neural runners.
from gardirop_ai_clothing import analysis as module
from gardirop_ai_clothing.contracts import (
    FUSION_METHOD,
    MAIN_CATEGORIES,
    TAXONOMY,
    TAXONOMY_VERSION,
    class_ids_for_category,
)
from gardirop_ai_clothing.embeddings.marqo import MARQO_MODEL_NAME, MarqoEncoder
from gardirop_ai_clothing.image.birefnet_local import BIREFNET_MODEL_NAME, LocalBiRefNetSegmenter
from gardirop_ai_clothing.labeling.artifacts import CLASSIFIER_MODEL_NAME
from gardirop_ai_clothing.labeling.category import CategoryClassifier
from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256
from gardirop_ai_clothing.model_manager import ModelManager
from gardirop_ai_clothing.model_specs import ENCODERS, MARQO_REVISION, PARENT_HEAD_NAME


@pytest.fixture
def parent_bundle(tmp_path):
    weights = tmp_path / "parent.npz"
    np.savez_compressed(
        weights, weights=np.zeros((20, 1536)), bias=np.zeros(20), class_ids=np.arange(20)
    )
    metadata = {
        "schema_version": 1,
        "model_kind": "parent_logistic_regression",
        "embedding_dim": 1536,
        "num_classes": 20,
        "taxonomy_version": TAXONOMY_VERSION,
        "taxonomy": [list(t) for t in TAXONOMY],
        "marqo_repo_id": ENCODERS["marqo_fashionsiglip"]["repo_id"],
        "marqo_revision": MARQO_REVISION,
        "fusion_method": FUSION_METHOD,
        "view_order": ["FRONT", "BACK"],
        "parent_class_ids": {p: list(class_ids_for_category(p)) for p in sorted(MAIN_CATEGORIES)},
        "artifact_sha256": file_sha256(weights),
    }
    info = tmp_path / "parent.json"
    info.write_text(json.dumps(metadata, ensure_ascii=False))
    return weights, info


@pytest.fixture
def model_manifest(tmp_path, parent_bundle):
    root = Path(__file__).resolve().parents[2]
    data = yaml.safe_load((root / "configs/model_manifest.yaml").read_text())
    for model in data["models"].values():
        model.update(status="planned", artifacts=[])
    weights, info = parent_bundle
    data["models"][PARENT_HEAD_NAME].update(
        status="ready",
        artifacts=[
            {"name": name, "path": str(path), "sha256": file_sha256(path)}
            for name, path in [("weights", weights), ("metadata", info)]
        ],
    )
    configs = tmp_path / "configs"
    configs.mkdir()
    path = configs / "model_manifest.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True))
    return path


def build_synthetic_analysis(**kwargs):
    calls = {"segmentation": 0, "marqo": 0, "seg_load": 0, "marqo_load": 0, "head_load": 0}

    def segment(chw):
        calls["segmentation"] += 1
        logits = np.full((1, 1, 16, 16), -30, dtype=np.float32)
        logits[:, :, 4:12, 4:12] = 30
        return logits

    def encode(image):
        calls["marqo"] += 1
        assert image.mode == "RGB" and image.width == image.height
        assert image.getpixel((0, 0)) == (255, 255, 255)
        index = int(np.argmax(np.asarray(image).mean(axis=(0, 1))))
        vector = np.zeros(768, dtype=np.float32)
        vector[index] = 1
        return vector

    segmenter = LocalBiRefNetSegmenter(segment, device="cpu")
    encoder = MarqoEncoder(encode, device="cpu")
    head = CategoryClassifier(np.zeros((20, 1536)), np.zeros(20), artifact_sha256="a" * 64)

    def loader(name, model):
        calls[name] += 1
        return model

    manager = ModelManager(
        {
            BIREFNET_MODEL_NAME: lambda: loader("seg_load", segmenter),
            MARQO_MODEL_NAME: lambda: loader("marqo_load", encoder),
            CLASSIFIER_MODEL_NAME: lambda: loader("head_load", head),
        }
    )
    return module.ClothingAnalysisService(manager, **kwargs), calls


@pytest.fixture
def analysis_factory():
    return build_synthetic_analysis
