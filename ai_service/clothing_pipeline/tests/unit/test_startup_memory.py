"""Cache policy and acceptance gates with fake CUDA counters; no GPU calls."""

import importlib
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from gardirop_ai_clothing.config import Settings
from gardirop_ai_clothing.startup_memory import release_warmup_cache

MIB = 1024**2


class FakeCuda:
    def __init__(self):
        self.allocated, self.reserved = 300 * MIB, 2048 * MIB
        self.calls = []
        self.initialized = True
        self.change_active = False

    def is_initialized(self):
        return self.initialized

    def synchronize(self):
        self.calls.append("sync")

    def memory_allocated(self):
        return self.allocated

    def memory_reserved(self):
        return self.reserved

    def empty_cache(self):
        self.calls.append("empty")
        self.reserved = self.allocated + 64 * MIB
        if self.change_active:
            self.allocated += MIB


@pytest.mark.parametrize("enabled,device", [(False, "cuda"), (False, "cpu"), (True, "cpu")])
def test_disabled_or_cpu_policy_never_touches_cuda(enabled, device):
    class Forbidden:
        def __getattr__(self, name):
            pytest.fail("No CUDA/allocator access is permitted in this mode.")

    result = release_warmup_cache(enabled=enabled, device=device, torch_module=Forbidden())
    assert not result["applied"]


def test_release_is_synchronized_preserves_active_tensors_and_reports_partial_cache_reclamation():
    cuda = FakeCuda()
    result = release_warmup_cache(
        enabled=True, device="cuda", torch_module=SimpleNamespace(cuda=cuda)
    )
    assert cuda.calls == ["sync", "empty"]
    assert result["applied"] and result["active_allocations_unchanged"]
    assert result["before"]["allocated_bytes"] == result["after"]["allocated_bytes"] == 300 * MIB
    assert result["released_reserved_mib"] == 1684
    assert result["after"]["reserved_bytes"] == 364 * MIB


@pytest.mark.parametrize("failure", ["not_initialized", "active_changed"])
def test_invalid_release_cannot_be_reported_as_success(failure):
    cuda = FakeCuda()
    cuda.initialized = failure != "not_initialized"
    cuda.change_active = failure == "active_changed"
    with pytest.raises(RuntimeError):
        release_warmup_cache(enabled=True, device="cuda", torch_module=SimpleNamespace(cuda=cuda))


def test_preparation_releases_once_inside_gpu_slot_and_keeps_cached_models(
    tmp_path, analysis_factory, monkeypatch
):
    from gardirop_ai_clothing import runtime_preparation as module
    from gardirop_ai_clothing.embeddings.marqo import MARQO_MODEL_NAME
    from gardirop_ai_clothing.jobs import DraftService
    from gardirop_ai_clothing.storage import LocalDraftRepository

    analysis, calls = analysis_factory()
    analysis.manager.get_model(MARQO_MODEL_NAME).device = "cuda"
    service = DraftService(LocalDraftRepository(tmp_path / "store"), analysis)
    cuda = FakeCuda()
    seen = []

    def release(*, enabled, device):
        # The sole inference slot must still be owned by startup preparation.
        assert not analysis.manager._gpu_semaphore.acquire(blocking=False)
        seen.append((enabled, device))
        return release_warmup_cache(
            enabled=enabled, device=device, torch_module=SimpleNamespace(cuda=cuda)
        )

    monkeypatch.setattr(module, "release_warmup_cache", release)
    settings = Settings(_env_file=None, api_release_warmup_cache=True)
    try:
        first = module.prepare_runtime(service, settings)
        previous_calls = calls.copy()
        assert first["startupCacheRelease"]["applied"]
        assert module.prepare_runtime(service, settings) is first
        assert seen == [(True, "cuda")] and calls == previous_calls
        assert cuda.calls == ["sync", "empty"]
        assert len(analysis.manager.loaded_models) == 3
        assert not service.repository.ids()
    finally:
        service.close()


def test_failed_cache_policy_does_not_publish_ready(tmp_path, analysis_factory, monkeypatch):
    from gardirop_ai_clothing import runtime_preparation as module
    from gardirop_ai_clothing.jobs import DraftService
    from gardirop_ai_clothing.storage import LocalDraftRepository

    analysis, _ = analysis_factory()
    service = DraftService(LocalDraftRepository(tmp_path / "store"), analysis)

    def fail(**kwargs):
        raise RuntimeError("synthetic cache failure")

    monkeypatch.setattr(module, "release_warmup_cache", fail)
    try:
        with pytest.raises(RuntimeError, match="cache failure"):
            module.prepare_runtime(service, Settings(_env_file=None, api_release_warmup_cache=True))
        assert service.runtime_preparation["status"] == "FAILED"
    finally:
        service.close()


def summary_inputs():
    field = "back_request_start_to_assets_received_seconds"
    timing = {"n": 15, "min": 0.4, "mean": 0.5, "p50": 0.5, "p95": 0.6, "max": 0.7}
    report = {
        "summary_seconds": {
            name: {field: deepcopy(timing)}
            for name in ("front_ready_before_back", "back_immediate")
        },
        "server_gpu_process_samples_mib": [
            {"event": "runtime_ready", "mib": 4308},
            {"event": "shutdown", "mib": 4318},
        ],
        "samples": [{"phase": "first_ready_request", field: 0.65}],
        "startup_cache_release": {"applied": False, "active_allocations_unchanged": True},
        "quality_comparison": {"all_checks_passed": True},
        "segmentation_forward_counts": {"tensorrt": 69, "pytorch": 4},
        "server_startup_seconds": 8.0,
    }
    left, right = deepcopy(report), deepcopy(report)
    right["server_gpu_process_samples_mib"][0]["mib"] = 2500
    right["server_gpu_process_samples_mib"][1]["mib"] = 2600
    right["startup_cache_release"]["applied"] = True
    return left, right


def comparator(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    return importlib.import_module("compare_trt_memory")


def test_memory_gate_accepts_meaningful_savings_with_unchanged_outputs_and_fast_first_request(
    monkeypatch,
):
    result = comparator(monkeypatch).summarize(*summary_inputs())
    assert result["all_demo_gates_passed"]
    assert result["ready_sample_reduction_mib"] == 1808


@pytest.mark.parametrize(
    "change",
    [
        "quality",
        "missing_sample",
        "regrown_cache",
        "missing_shutdown",
        "small_saving",
        "p95_regression",
        "slow_delivery",
        "slow_first",
        "not_applied",
        "active_changed",
    ],
)
def test_memory_gate_rejects_each_missing_or_regressed_requirement(monkeypatch, change):
    left, right = summary_inputs()
    field = "back_request_start_to_assets_received_seconds"
    if change == "quality":
        right["quality_comparison"]["all_checks_passed"] = False
    elif change == "missing_sample":
        right["server_gpu_process_samples_mib"] = []
    elif change == "regrown_cache":
        right["server_gpu_process_samples_mib"][1]["mib"] = 4318
    elif change == "missing_shutdown":
        right["server_gpu_process_samples_mib"] = right["server_gpu_process_samples_mib"][:1]
    elif change == "small_saving":
        right["server_gpu_process_samples_mib"][0]["mib"] = 4300
    elif change == "p95_regression":
        right["summary_seconds"]["back_immediate"][field]["p95"] = 0.8
    elif change == "slow_delivery":
        right["summary_seconds"]["back_immediate"][field]["max"] = 1.0
    elif change == "slow_first":
        right["samples"][0][field] = 1.0
    elif change == "not_applied":
        right["startup_cache_release"]["applied"] = False
    else:
        right["startup_cache_release"]["active_allocations_unchanged"] = False
    assert not comparator(monkeypatch).summarize(left, right)["all_demo_gates_passed"]


def test_cache_release_is_opt_in_and_environment_override_is_parsed(monkeypatch):
    monkeypatch.delenv("GARDROPAI_API_RELEASE_WARMUP_CACHE", raising=False)
    assert Settings(_env_file=None).api_release_warmup_cache is False
    monkeypatch.setenv("GARDROPAI_API_RELEASE_WARMUP_CACHE", "true")
    assert Settings(_env_file=None).api_release_warmup_cache is True
