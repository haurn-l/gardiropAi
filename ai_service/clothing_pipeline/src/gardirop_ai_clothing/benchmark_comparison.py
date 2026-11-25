"""Compare the three demo deliveries against a completed earlier baseline."""

import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

FP16_MIN_COSINE = 0.9999
FP16_MAX_ABS_ERROR = 0.001


def embedding_drift(reference, current):
    """Fixed engineering gates for this demo, not calibrated accuracy metrics."""
    left, right = np.asarray(reference, dtype=np.float64), np.asarray(current, dtype=np.float64)
    valid = (
        left.shape == right.shape == (1536,)
        and np.isfinite(left).all()
        and np.isfinite(right).all()
    )
    if not valid:
        return {"contract_valid": False, "within_tolerance": False}
    half_norm = 1 / np.sqrt(2)
    valid = all(abs(float(np.linalg.norm(v)) - 1) <= 1e-3 for v in (left, right))
    valid &= all(
        abs(float(np.linalg.norm(v)) - half_norm) <= 1e-3
        for v in (left[:768], left[768:], right[:768], right[768:])
    )
    metrics = {}
    for name, a, b in (
        ("fused", left, right),
        ("front", left[:768] * np.sqrt(2), right[:768] * np.sqrt(2)),
        ("back", left[768:] * np.sqrt(2), right[768:] * np.sqrt(2)),
    ):
        denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
        cosine = float(np.clip(np.dot(a, b) / denominator, -1, 1)) if denominator > 0 else None
        error = float(np.max(np.abs(a - b)))
        metrics[name] = {"cosine": cosine, "max_abs_error": error}
    passed = bool(valid) and all(
        row["cosine"] is not None
        and row["cosine"] >= FP16_MIN_COSINE
        and row["max_abs_error"] <= FP16_MAX_ABS_ERROR
        for row in metrics.values()
    )
    return {
        "contract_valid": bool(valid),
        "within_tolerance": passed,
        "float32_identical": np.array_equal(left.astype(np.float32), right.astype(np.float32)),
        "metrics": metrics,
    }


def classification_details(reference, current):
    old = reference.get("modelDiagnostics", {}).get("classification", {}).get("alternatives", [])
    new = current.get("modelDiagnostics", {}).get("classification", {}).get("alternatives", [])
    old_ids, new_ids = [r["class_id"] for r in old[:3]], [r["class_id"] for r in new[:3]]
    old_scores = {r["class_id"]: r["score"] for r in old}
    differences = [
        abs(r["score"] - old_scores[r["class_id"]]) for r in new if r["class_id"] in old_scores
    ]
    return {
        "top3_ids_identical": len(old_ids) == len(new_ids) == 3 and old_ids == new_ids,
        "reference_top3": old_ids,
        "current_top3": new_ids,
        "max_abs_margin_change": max(differences) if differences else None,
    }


def delivery_pixel_drift(reference, current):
    """HTTP-delivered RGB parity; original-resolution mask parity was checked in OPT-05C."""
    a, b = np.asarray(reference), np.asarray(current)
    valid = (
        reference.mode == current.mode == "RGB"
        and a.shape == b.shape
        and a.ndim == 3
        and a.shape[2] == 3
    )
    if not valid:
        return {"passed": False, "same_rgb_shape": False}
    delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
    white = all(
        tuple(b[y, x]) == (255, 255, 255)
        for y, x in (
            (0, 0),
            (0, b.shape[1] - 1),
            (b.shape[0] - 1, 0),
            (b.shape[0] - 1, b.shape[1] - 1),
        )
    )
    mean, p99 = float(delta.mean()), float(np.percentile(delta, 99))
    return {
        "passed": white and mean <= 1.0 and p99 <= 4.0,
        "same_rgb_shape": True,
        "mae_255": mean,
        "p99_error_255": p99,
        "max_error_255": int(delta.max()),
        "white_corners": white,
        "pixels_identical": np.array_equal(a, b),
    }


def compare_delivery_runs(
    baseline, candidate, *, mode="strict", case_names=("tshirt", "jeans", "jacket")
):
    if mode not in {"strict", "fp16", "trt"}:
        raise ValueError("Unknown comparison mode.")
    case_names = tuple(case_names)
    if (
        not case_names
        or any(
            not isinstance(name, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name) is None
            for name in case_names
        )
        or len(set(case_names)) != len(case_names)
    ):
        raise ValueError("Invalid comparison case names.")
    baseline, candidate = Path(baseline), Path(candidate)
    reference_report = json.loads((baseline / "report.json").read_text())
    if reference_report.get("status") != "COMPLETED":
        raise ValueError("Reference baseline was not completed.")
    result, numerical, classification, pixels = {}, {}, {}, {}
    for name in case_names:
        old, new = baseline / "cases" / name, candidate / "cases" / name
        reference = json.loads((old / "result.json").read_text())
        current = json.loads((new / "result.json").read_text())
        left = np.asarray(
            json.loads((old / "embedding.json").read_text())["values"], dtype=np.float32
        )
        right = np.asarray(
            json.loads((new / "embedding.json").read_text())["values"], dtype=np.float32
        )
        checks = {
            "tags_identical": reference["tags"] == current["tags"],
            "producer_versions_identical": reference["versions"] == current["versions"],
            "embedding_float32_identical": np.array_equal(left, right),
        }
        if mode in {"fp16", "trt"}:
            numerical[name] = embedding_drift(left, right)
            classification[name] = classification_details(reference, current)
            old_precision = (
                reference.get("modelDiagnostics", {})
                .get("embedding", {})
                .get("encoder_precision", "fp32")
            )
            new_precision = (
                current.get("modelDiagnostics", {})
                .get("embedding", {})
                .get("encoder_precision", "fp32")
            )
            del checks["embedding_float32_identical"]
            checks.update(
                embedding_within_tolerance=numerical[name]["within_tolerance"],
                classification_top3_identical=classification[name]["top3_ids_identical"],
                runtime_precision_transition_valid=(
                    old_precision == ("fp32" if mode == "fp16" else "fp16")
                    and new_precision == "fp16"
                ),
            )
        for view in ("front", "back"):
            with Image.open(old / f"{view}.webp") as a, Image.open(new / f"{view}.webp") as b:
                if mode == "trt":
                    pixels[f"{name}_{view}"] = delivery_pixel_drift(a, b)
                    checks[f"{view}_pixels_within_tolerance"] = pixels[f"{name}_{view}"]["passed"]
                else:
                    checks[f"{view}_pixels_identical"] = (
                        a.mode == b.mode == "RGB"
                        and a.size == b.size
                        and np.array_equal(np.asarray(a), np.asarray(b))
                    )
        result[name] = checks
    response = {
        "all_checks_passed": all(all(row.values()) for row in result.values()),
        "cases": result,
    }
    if mode in {"fp16", "trt"}:
        response.update(
            mode=mode,
            embedding_drift=numerical,
            classification_drift=classification,
            policy={
                "id": "tensorrt-http-demo-v1" if mode == "trt" else "marqo-fp16-demo-v1",
                "min_cosine": FP16_MIN_COSINE,
                "max_abs_error": FP16_MAX_ABS_ERROR,
                "scope": "Three demo products only; not independent accuracy or retrieval evaluation.",
            },
        )
    if mode == "trt":
        response["delivery_pixels"] = pixels
        response["policy"].update(max_rgb_mae_255=1.0, max_rgb_p99_error_255=4.0)
    return response
