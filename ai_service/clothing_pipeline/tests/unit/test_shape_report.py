"""Final recommendation must expose slow shapes and cache regrowth."""

import importlib.util
from pathlib import Path

import pytest

from gardirop_ai_clothing.shape_experiment import ITEMS, PROFILES, case_name


@pytest.fixture
def diagnostic(monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "shape_report_under_test", scripts / "compare_api_shapes.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report():
    samples = [
        {
            "phase": f"first_shape/{profile}",
            "profile": profile,
            "expected_backend": "pytorch" if profile != "p23" else "tensorrt",
            "gpu_process_sample_after_pair_mib": 3000,
            "back_request_start_to_assets_received_seconds": 0.7,
        }
        for profile, _ in PROFILES
    ]
    for profile, _ in PROFILES:
        for item, _, _ in ITEMS:
            for scenario in ("front_ready_before_back", "back_immediate"):
                samples.append(
                    {
                        "phase": "measured",
                        "profile": profile,
                        "case": case_name(item, profile),
                        "scenario": scenario,
                        "tags": {},
                        "gpu_process_sample_after_pair_mib": 3100,
                        "back_request_start_to_assets_received_seconds": 0.6,
                    }
                )
    return {
        "status": "COMPLETED",
        "samples": samples,
        "quality_comparison": {"all_checks_passed": True},
        "first_shape_routing_valid": True,
        "measured_segmentation_routing_valid": True,
        "segmentation_forward_counts": {},
        "server_gpu_process_samples_mib": [{"event": "runtime_ready", "mib": 2400}],
    }


def test_acceptable_latencies_keep_runtime_and_report_memory_regrowth(diagnostic):
    result = diagnostic.summarize(report(), report())
    assert result["all_observed_below_one_second"]
    assert result["decision"] == "KEEP_CURRENT_RUNTIME_FOR_TESTED_PROFILES"
    assert result["sampled_gpu_growth_after_startup_mib"] == 700


def test_slow_first_fallback_is_not_hidden_by_warm_means(diagnostic):
    candidate = report()
    candidate["samples"][0]["back_request_start_to_assets_received_seconds"] = 1.1
    result = diagnostic.summarize(report(), candidate)
    assert not result["all_observed_below_one_second"]
    assert result["decision"] == "TARGETED_WORK_FOR_LISTED_PROFILES"
    assert result["latency_target_misses"][0]["profile"] == "p34"


def test_quality_failure_prevents_a_keep_decision(diagnostic):
    candidate = report()
    candidate["quality_comparison"]["all_checks_passed"] = False
    with pytest.raises(ValueError, match="quality"):
        diagnostic.summarize(report(), candidate)
