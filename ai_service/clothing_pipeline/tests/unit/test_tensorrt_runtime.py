"""Synthetic runtime/engine records only; no TensorRT, CUDA or model weights."""

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from pydantic import ValidationError

from gardirop_ai_clothing.config import Settings
from gardirop_ai_clothing.errors import (
    ConfigurationError,
    ImageProcessingError,
    InferenceError,
    ModelArtifactError,
)
from gardirop_ai_clothing.image import birefnet_tensorrt as module
from gardirop_ai_clothing.image.birefnet_local import LocalBiRefNetSegmenter
from gardirop_ai_clothing.model_specs import BIREFNET_REVISION, SEGMENTATION_PROFILE
from gardirop_ai_clothing.onnx_experiment import INPUT_SHAPE, save_json, sha256
from gardirop_ai_clothing.tensorrt_experiment import BUILD_POLICY, cache_key


def routed():
    calls = {"tensorrt": 0, "pytorch": 0}

    def runner(name):
        def run(chw):
            calls[name] += 1
            return np.zeros((1, 1, 8, 8), dtype=np.float32)

        return run

    fallback = LocalBiRefNetSegmenter(runner("pytorch"), device="cuda")
    return module.RoutedBiRefNetSegmenter(runner("tensorrt"), fallback, plan_sha256="a" * 64), calls


@pytest.mark.parametrize(
    "size,backend",
    [
        ((1024, 1536), "tensorrt"),
        ((64, 96), "tensorrt"),
        ((1024, 1024), "pytorch"),
        ((1536, 1024), "pytorch"),
    ],
)
def test_routing_uses_preprocessed_geometry_and_restores_original_size(size, backend):
    segmenter, calls = routed()
    alpha = segmenter.predict_alpha(Image.new("RGB", size, "red"))
    assert alpha.shape == (size[1], size[0]) and alpha.dtype == np.uint8
    assert calls[backend] == 1 and sum(calls.values()) == 1
    assert segmenter.runtime_details["forwardCounts"] == calls


def test_tensor_execution_failure_does_not_silently_retry_pytorch():
    segmenter, calls = routed()

    def fail(chw):
        raise RuntimeError("synthetic native error")

    segmenter.native_runner = fail
    with pytest.raises(InferenceError, match="no automatic retry"):
        segmenter.predict_alpha(Image.new("RGB", (32, 48)))
    assert calls == {"tensorrt": 0, "pytorch": 0}


def test_invalid_input_is_rejected_before_either_backend():
    segmenter, calls = routed()
    with pytest.raises(ImageProcessingError, match="requires finite float32"):
        segmenter._runner(np.zeros((3, 1024, 704), dtype=np.float16))
    assert sum(calls.values()) == 0


def test_default_pytorch_loader_never_looks_up_an_engine(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(module, "load_birefnet_segmenter", lambda *a, **k: sentinel)

    def forbidden():
        pytest.fail("Default backend must not inspect TensorRT/CUDA.")

    monkeypatch.setattr(module, "current_device_identity", forbidden)
    settings = Settings(_env_file=None, segmentation_backend="pytorch", device="cpu")
    assert module.load_configured_segmenter(settings) is sentinel


def test_tensor_backend_rejects_missing_engine_and_explicit_cpu_before_gpu_access():
    with pytest.raises(ConfigurationError, match="requires an accepted"):
        module.load_configured_segmenter(Settings(_env_file=None, segmentation_backend="tensorrt"))
    with pytest.raises(ConfigurationError, match="requires CUDA"):
        module.load_configured_segmenter(
            Settings(_env_file=None, segmentation_backend="tensorrt", device="cpu")
        )
    with pytest.raises(ValidationError):
        Settings(_env_file=None, segmentation_backend="unknown")


@pytest.fixture
def engine_records(tmp_path):
    root = tmp_path / "project"
    adapter = root / "src/gardirop_ai_clothing/tensorrt_experiment.py"
    builder = root / "scripts/tensorrt_birefnet_worker.py"
    for path in (adapter, builder):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic test code")
    source = root / "outputs/onnx_compare/source"
    source.mkdir(parents=True)
    artifact = {
        "revision": BIREFNET_REVISION,
        "preprocessing_profile": SEGMENTATION_PROFILE,
        "precision": "fp16",
        "input_nchw": list(INPUT_SHAPE),
        "sha256": "b" * 64,
    }
    save_json(source / "artifact.json", artifact)
    device = {"gpu": "fake", "driver": "fake"}
    identity = {
        "device": device,
        "build": BUILD_POLICY,
        "onnx_sha256": artifact["sha256"],
        "adapter_sha256": sha256(adapter),
        "builder_sha256": sha256(builder),
    }
    key = cache_key(identity)
    plan = root / "outputs/tensorrt_engines" / key / "model.plan"
    plan.parent.mkdir(parents=True)
    plan.write_bytes(b"synthetic plan; never deserialized")
    record = {
        "identity": identity,
        "cache_key": key,
        "plan_sha256": sha256(plan),
        "plan_bytes": plan.stat().st_size,
        "original_build_seconds": 1.0,
    }
    save_json(plan.parent / "engine.json", record)
    run = root / "outputs/tensorrt_compare/passed"
    run.mkdir(parents=True)
    build = {
        "status": "PASSED",
        "plan": str(plan),
        "engine": {**record, "cache_hit": True, "build_seconds_this_run": 0},
    }
    save_json(run / "build.json", build)
    steps = {
        stage: {"status": "PASSED"}
        for stage in ("tiny", "build", "reference", "infer", "downstream")
    }
    steps["build"] = build
    steps["infer"]["all_image_gates_passed"] = True
    steps["downstream"]["all_downstream_gates_passed"] = True
    report = {
        "stage": "OPT-05C",
        "status": "DEMO_GATES_PASSED_REVIEW_REQUIRED",
        "all_demo_gates_passed": True,
        "input_shape_nchw": list(INPUT_SHAPE),
        "steps": steps,
        "source_onnx_sha256": artifact["sha256"],
        "source_onnx_run": str(source),
    }
    save_json(run / "report.json", report)
    return root, run, device, plan


def test_exact_accepted_engine_is_verified_without_tensor_libraries(engine_records):
    root, run, device, plan = engine_records
    actual, record = module.verified_engine(root, run, device)
    assert actual == plan and record["plan_sha256"] == sha256(plan)


@pytest.mark.parametrize(
    "change", ["device", "plan", "adapter", "builder", "quality", "shape", "source", "path"]
)
def test_unaccepted_or_changed_engine_is_rejected_before_deserialization(engine_records, change):
    root, run, device, plan = engine_records
    report = json.loads((run / "report.json").read_text())
    if change == "device":
        device = {**device, "driver": "changed"}
    elif change == "plan":
        plan.write_bytes(b"changed")
    elif change in {"adapter", "builder"}:
        path = (
            root / "src/gardirop_ai_clothing/tensorrt_experiment.py"
            if change == "adapter"
            else root / "scripts/tensorrt_birefnet_worker.py"
        )
        path.write_text("changed")
    elif change == "quality":
        report["steps"]["infer"]["all_image_gates_passed"] = False
    elif change == "shape":
        report["input_shape_nchw"] = [1, 3, 704, 1024]
    elif change == "source":
        source = Path(report["source_onnx_run"]) / "artifact.json"
        artifact = json.loads(source.read_text())
        artifact["revision"] = "changed"
        save_json(source, artifact)
    else:
        run = root / "elsewhere"
    if change != "path":
        save_json(run / "report.json", report)
    with pytest.raises(ModelArtifactError):
        module.verified_engine(root, run, device)


def test_warmup_exercises_both_routes_before_ready_and_is_idempotent(tmp_path, analysis_factory):
    from gardirop_ai_clothing.embeddings.marqo import MARQO_MODEL_NAME
    from gardirop_ai_clothing.image.birefnet_local import BIREFNET_MODEL_NAME
    from gardirop_ai_clothing.jobs import DraftService
    from gardirop_ai_clothing.runtime_preparation import prepare_runtime
    from gardirop_ai_clothing.storage import LocalDraftRepository

    analysis, _ = analysis_factory()
    segmenter, calls = routed()
    analysis.manager._models[BIREFNET_MODEL_NAME] = segmenter
    analysis.manager.get_model(MARQO_MODEL_NAME).device = "cuda"
    service = DraftService(LocalDraftRepository(tmp_path / "store"), analysis)
    try:
        first = prepare_runtime(service, Settings(_env_file=None))
        before = calls.copy()
        assert first["status"] == "READY" and first["segmentationBackend"] == segmenter.backend
        assert calls["tensorrt"] >= 1 and calls["pytorch"] >= 1
        assert prepare_runtime(service, Settings(_env_file=None)) == first and calls == before
        assert not service.repository.ids()
    finally:
        service.close()


def test_http_readiness_identifies_warmed_routed_backend(tmp_path, analysis_factory):
    from fastapi.testclient import TestClient

    from gardirop_ai_clothing.app import create_app
    from gardirop_ai_clothing.embeddings.marqo import MARQO_MODEL_NAME
    from gardirop_ai_clothing.image.birefnet_local import BIREFNET_MODEL_NAME
    from gardirop_ai_clothing.jobs import DraftService
    from gardirop_ai_clothing.runtime_preparation import prepare_runtime
    from gardirop_ai_clothing.storage import LocalDraftRepository

    analysis, _ = analysis_factory()
    segmenter, calls = routed()
    analysis.manager._models[BIREFNET_MODEL_NAME] = segmenter
    analysis.manager.get_model(MARQO_MODEL_NAME).device = "cuda"

    def factory(configured):
        return DraftService(LocalDraftRepository(configured.draft_root, compact=True), analysis)

    app = create_app(
        processing_enabled=True,
        api_key="synthetic-service-key-for-unit-tests-only",
        settings=Settings(_env_file=None, api_draft_root=tmp_path / "api"),
        service_factory=factory,
        runtime_preparer=prepare_runtime,
    )
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["segmentationBackend"] == "tensorrt_with_pytorch_fallback"
        assert calls["pytorch"] >= 1 and calls["tensorrt"] >= 1
