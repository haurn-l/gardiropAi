"""Protect sample grouping and percentile interpretation without model loading."""

import pytest

from gardirop_ai_clothing.benchmarking import LATENCY_FIELDS, describe, summarize_samples


def test_percentiles_report_count_and_linear_interpolation():
    result = describe([1, 2, 3, 4, 5])
    assert result["n"] == 5 and result["p50"] == 3 and result["mean"] == 3
    assert result["p95"] == pytest.approx(4.8)


@pytest.mark.parametrize("values", [[], [-1], [float("nan")], [float("inf")]])
def test_invalid_timings_are_not_reported_as_successful_measurements(values):
    with pytest.raises(ValueError):
        describe(values)


def test_cold_and_warmup_are_excluded_and_scenarios_are_not_mixed():
    def row(phase, case, scenario, value):
        return {
            "phase": phase,
            "case": case,
            "scenario": scenario,
            **{key: value for key in LATENCY_FIELDS},
        }

    rows = [
        row("cold", "tshirt", "back_immediate", 100),
        row("warmup", "tshirt", "back_immediate", 50),
        row("measured", "tshirt", "back_immediate", 3),
        row("measured", "jeans", "back_immediate", 1),
        row("measured", "tshirt", "front_ready_before_back", 0.5),
    ]
    summary = summarize_samples(rows)
    key = LATENCY_FIELDS[0]
    assert summary["back_immediate"][key]["n"] == 2
    assert summary["back_immediate"][key]["p50"] == 2
    assert summary["front_ready_before_back"][key]["n"] == 1
    assert summary["tshirt/back_immediate"][key]["p50"] == 3
    assert "cold" not in summary and "warmup" not in summary
