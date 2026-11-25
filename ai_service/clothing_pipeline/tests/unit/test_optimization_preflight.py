"""Keep the export preflight diagnostic; never imply untested runtime readiness."""

import json
import subprocess
from types import SimpleNamespace

import pytest
from PIL import Image

from gardirop_ai_clothing import optimization_preflight as module


def test_shape_cast_scan_is_static_and_reports_relevant_conversions():
    source = 'raise RuntimeError("must never execute")\nx = int(windows.shape[0] / 4)\ny = int(3)'
    assert module.shape_cast_sites(source) == [{"line": 2, "conversion": "int"}]


@pytest.mark.parametrize("failure", ["exit", "timeout", "invalid_json"])
def test_native_probe_failures_do_not_claim_success_or_dump_native_logs(monkeypatch, failure):
    def run(*args, **kwargs):
        assert kwargs["timeout"] == 45
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        if failure == "timeout":
            raise subprocess.TimeoutExpired("probe", 45)
        return SimpleNamespace(
            returncode=1 if failure == "exit" else 0,
            stdout="private raw native text",
            stderr="private raw logs",
        )

    monkeypatch.setattr(module.subprocess, "run", run)
    result = module.probe_json("synthetic")
    assert result["probe_status"] in {"FAILED", "TIMEOUT"}
    assert "private" not in json.dumps(result)


def test_demo_shapes_keep_actual_portrait_and_landscape_geometry(tmp_path):
    folder = tmp_path / "outputs/step07_completion/inputs/generated"
    folder.mkdir(parents=True)
    for item in ("tshirt", "jeans", "jacket"):
        for view, size in (("front", (400, 800)), ("back", (800, 400))):
            Image.new("RGB", size).save(folder / f"{item}_{view}.png")
    record = module.demo_shapes(tmp_path)
    assert record["observed_shapes_nchw"] == [[1, 3, 512, 1024], [1, 3, 1024, 512]]
    assert not record["dynamic_shape_validated"]
    assert len(record["cases"]) == 6


@pytest.mark.parametrize(
    "cuda,policy,expected",
    [
        (True, "auto", "ENVIRONMENT_RECORDED"),
        (False, "auto", "ACTION_REQUIRED"),
        (True, "fp32", "ACTION_REQUIRED"),
    ],
)
def test_preflight_distinguishes_missing_optional_tools_from_missing_gpu(
    tmp_path, monkeypatch, cuda, policy, expected
):
    settings = SimpleNamespace(
        device="auto", marqo_precision=policy, model_manifest_path=tmp_path / "unused.yaml"
    )
    monkeypatch.setattr(module, "package_versions", lambda: dict.fromkeys(module.PACKAGES))
    monkeypatch.setattr(module, "visible_servers", lambda: [])
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        module, "source_summary", lambda path: {"artifact_integrity_verified": True}
    )
    monkeypatch.setattr(module, "demo_shapes", lambda root: {"cases": []})
    monkeypatch.setattr(
        module,
        "probe_json",
        lambda code: {"probe_status": "OK", "cuda_available": cuda, "cuda_runtime": "13.0"},
    )
    report = module.collect_report(settings, tmp_path, progress=lambda *args, **kwargs: None)
    assert report["status"] == expected
    assert report["onnxruntime"]["probe_status"] == "NOT_INSTALLED"
    assert not report["dependencies_installed"] and not report["model_exported"]
    assert not report["neural_inference"] and not report["engine_built"]
    if cuda and policy == "auto":
        assert report["effective_marqo_precision"] == "fp16"
