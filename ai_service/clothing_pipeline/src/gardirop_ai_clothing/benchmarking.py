"""Descriptive benchmark summaries; cold and warmup samples remain separate."""

from collections import defaultdict

import numpy as np

LATENCY_FIELDS = (
    "back_request_start_to_ready_seconds",
    "back_request_start_to_assets_received_seconds",
    "back_accepted_to_ready_seconds",
    "back_accepted_to_assets_received_seconds",
    "front_request_start_to_ready_seconds",
    "front_request_start_to_assets_received_seconds",
)


def describe(values):
    data = np.asarray(values, dtype=np.float64)
    if data.ndim != 1 or not data.size or not np.isfinite(data).all() or (data < 0).any():
        raise ValueError("Timing samples must be a non-empty finite non-negative sequence.")
    return {
        "n": int(data.size),
        "min": float(data.min()),
        "mean": float(data.mean()),
        "p50": float(np.percentile(data, 50)),
        "p95": float(np.percentile(data, 95)),
        "max": float(data.max()),
    }


def summarize_samples(samples):
    groups = defaultdict(list)
    for sample in samples:
        if sample["phase"] != "measured":
            continue
        groups[sample["scenario"]].append(sample)
        groups[f"{sample['case']}/{sample['scenario']}"].append(sample)
    return {
        name: {field: describe([sample[field] for sample in rows]) for field in LATENCY_FIELDS}
        for name, rows in sorted(groups.items())
    }
