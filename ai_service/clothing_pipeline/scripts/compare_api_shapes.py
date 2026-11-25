"""Final local geometry diagnostic: same garments, padded ratios, fresh reference and routed API."""

import argparse
import html
import json
import os
import shutil
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from compare_api_tensorrt import run_measurement

from gardirop_ai_clothing.benchmarking import describe
from gardirop_ai_clothing.onnx_experiment import save_json
from gardirop_ai_clothing.shape_experiment import ITEMS, PROFILES, SHAPES, case_name, prepare_suite

ROOT = Path(__file__).resolve().parents[1]
FIELD = "back_request_start_to_assets_received_seconds"


def ready_memory(report):
    values = [
        row["mib"]
        for row in report["server_gpu_process_samples_mib"]
        if row["event"] == "runtime_ready"
    ]
    return values[0] if len(values) == 1 else None


def summarize(reference, candidate):
    profiles, misses, tags = {}, [], {}
    quality = candidate["quality_comparison"]
    if not quality.get("all_checks_passed") or not all(
        report.get("status") == "COMPLETED"
        and report.get("first_shape_routing_valid")
        and report.get("measured_segmentation_routing_valid")
        for report in (reference, candidate)
    ):
        raise ValueError("Incomplete geometry routing or output-quality evidence.")
    for profile, _ in PROFILES:
        scenarios = {}
        for scenario in ("front_ready_before_back", "back_immediate"):
            left = [
                row
                for row in reference["samples"]
                if row["phase"] == "measured"
                and row["profile"] == profile
                and row["scenario"] == scenario
            ]
            right = [
                row
                for row in candidate["samples"]
                if row["phase"] == "measured"
                and row["profile"] == profile
                and row["scenario"] == scenario
            ]
            a, b = describe([row[FIELD] for row in left]), describe([row[FIELD] for row in right])
            passed = b["max"] < 1
            if not passed:
                misses.append(
                    {
                        "profile": profile,
                        "scenario": scenario,
                        "max_seconds": b["max"],
                        "p95_seconds": b["p95"],
                    }
                )
            scenarios[scenario] = {
                "pytorch_seconds": a,
                "routed_seconds": b,
                "observed_mean_speedup": a["mean"] / b["mean"],
                "all_observed_below_one_second": passed,
            }
        gpu_values = [
            row["gpu_process_sample_after_pair_mib"]
            for row in candidate["samples"]
            if row["profile"] == profile
            and row.get("gpu_process_sample_after_pair_mib") is not None
        ]
        first = next(
            row for row in candidate["samples"] if row["phase"] == f"first_shape/{profile}"
        )
        if first[FIELD] >= 1:
            misses.append({"profile": profile, "scenario": "first_shape", "seconds": first[FIELD]})
        profiles[profile] = {
            "model_input_nchw": list(SHAPES[profile]),
            "selected_backend": "tensorrt" if profile == "p23" else "pytorch",
            "scenarios": scenarios,
            "first_shape_pair": {
                "seconds": first[FIELD],
                "gpu_process_sample_mib": first.get("gpu_process_sample_after_pair_mib"),
                "scope": "First pair of this shape in the fixed sequence; only p34 is the first request after startup cache release.",
            },
            "post_pair_gpu_samples_mib": {"min": min(gpu_values), "max": max(gpu_values)}
            if gpu_values
            else None,
        }
        for item, _, _ in ITEMS:
            name = case_name(item, profile)
            tags[name] = next(
                row["tags"]
                for row in candidate["samples"]
                if row["phase"] == "measured" and row["case"] == name
            )
    first = candidate["samples"][0]
    if first["phase"] != "first_shape/p34" or first["expected_backend"] != "pytorch":
        raise ValueError(
            "The first post-trim request did not exercise the declared PyTorch fallback."
        )
    all_samples = [
        row["gpu_process_sample_after_pair_mib"]
        for row in candidate["samples"]
        if row.get("gpu_process_sample_after_pair_mib") is not None
    ]
    before = ready_memory(candidate)
    maximum = max(all_samples) if all_samples else None
    result = {
        "profiles": profiles,
        "tags_by_case": tags,
        "quality_comparison": quality,
        "routing": candidate["segmentation_forward_counts"],
        "first_shape_routing_valid": candidate["first_shape_routing_valid"],
        "measured_routing_valid": candidate["measured_segmentation_routing_valid"],
        "first_post_trim_pytorch_request_seconds": first[FIELD],
        "ready_gpu_process_mib": before,
        "largest_post_pair_gpu_sample_mib": maximum,
        "first_fallback_gpu_process_mib": first.get("gpu_process_sample_after_pair_mib"),
        "shutdown_gpu_samples_mib": candidate["server_gpu_process_samples_mib"],
        "sampled_gpu_growth_after_startup_mib": maximum - before
        if maximum is not None and before is not None
        else None,
        "all_observed_below_one_second": not misses,
        "latency_target_misses": misses,
        "decision": "KEEP_CURRENT_RUNTIME_FOR_TESTED_PROFILES"
        if not misses
        else "TARGETED_WORK_FOR_LISTED_PROFILES",
        "memory_scope": "Per-PID samples after downloads and at readiness/shutdown, not true GPU peaks. All models remain resident; fallback work can rebuild the Torch cache.",
    }
    return result


def render(output, report, runs, manifest):
    blocks = []
    for case in json.loads(manifest.read_text())["cases"]:
        name = case["name"]
        for view in ("front", "back"):
            paths = [
                (Path(case[view]), "Girdi · yalnız beyaz alan eklendi"),
                (runs["pytorch"] / "cases" / name / f"{view}.webp", "PyTorch FP16"),
                (runs["routed"] / "cases" / name / f"{view}.webp", case["expected_backend"]),
            ]
            if not all(path.is_file() for path, _ in paths):
                continue
            figures = []
            for path, label in paths:
                rel = html.escape(os.path.relpath(path, output), quote=True)
                figures.append(
                    f'<figure><img src="{rel}"><figcaption>{html.escape(label)}</figcaption></figure>'
                )
            blocks.append(f'<h2>{name} / {view}</h2><div class="photos">{"".join(figures)}</div>')
    data = html.escape(json.dumps(report, ensure_ascii=False, indent=2))
    (
        output / "report.html"
    ).write_text(f"""<!doctype html><html lang="tr"><meta charset="utf-8"><title>OPT-06</title>
<style>body{{font:16px system-ui;max-width:1200px;margin:30px auto;padding:15px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}
.photos{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}figure{{margin:0}}img{{width:100%;height:320px;object-fit:contain}}</style>
<h1>OPT-06 · Fotoğraf oranları ve PyTorch geri dönüşü</h1>
<p>Üç ürünün aynı altı fotoğrafına beyaz alan eklendi; görüntü esnetilmedi/kesilmedi. Bu test farklı oranları taklit eder;
yeni kamera görüntüleri veya bağımsız sınıflandırma doğruluk testi değildir. Süreler son fotoğraf isteğinden tüm çıktıların indirilmesine kadardır.
GPU değerleri tepe ölçümü değildir. İlk p34 isteği başlangıç önbelleği temizliğinin hemen arkasındadır.</p>
<pre>{data}</pre>{"".join(blocks)}</html>""")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trt-run", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve() or not 1 <= args.repeats <= 10:
        parser.error("Use make compare-api-shapes; repeats must be 1..10.")
    for port in (7861, 8001, 8002):
        with socket.socket() as probe:
            probe.settimeout(0.2)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                parser.error(f"{port} açık; ilgili API/demo terminalini Ctrl+C ile durdur.")
    trt_run, baseline = args.trt_run.expanduser().resolve(), args.baseline.expanduser().resolve()
    for path, parent in (
        (trt_run, ROOT / "outputs/tensorrt_compare"),
        (baseline, ROOT / "outputs/api_baseline"),
    ):
        if not parent.resolve().is_relative_to(ROOT) or not path.is_relative_to(parent.resolve()):
            parser.error("Choose accepted local engine and API reports inside project outputs.")
    accepted, old = (
        json.loads((trt_run / "report.json").read_text()),
        json.loads((baseline / "report.json").read_text()),
    )
    if (
        accepted.get("status") != "DEMO_GATES_PASSED_REVIEW_REQUIRED"
        or not accepted.get("all_demo_gates_passed")
        or old.get("status") != "COMPLETED"
        or old.get("segmentation_backend_requested") != "tensorrt"
        or not old.get("quality_comparison", {}).get("all_checks_passed")
        or old.get("segmentation_runtime", {}).get("engineSha256")
        != accepted["steps"]["build"]["engine"]["plan_sha256"]
    ):
        parser.error("Accepted engine/API reference mismatch.")
    overlay = ROOT / ".venv-trt"
    if (
        overlay.is_symlink()
        or not overlay.resolve().is_relative_to(ROOT)
        or not (overlay / "bin/python").is_file()
    ):
        parser.error("The prepared .venv-trt is required.")
    if shutil.disk_usage(ROOT).free < 4 * 1024**3:
        parser.error("At least 4 GiB free disk required for diagnostic outputs.")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    output = ROOT / "outputs/api_shape_compare" / stamp
    if not output.resolve().is_relative_to(ROOT):
        parser.error("Unsafe output path.")
    output.mkdir(parents=True, exist_ok=False)
    manifest = prepare_suite(ROOT, output, baseline)
    runs = {
        name: ROOT / "outputs/api_baseline" / f"{stamp}_shapes_{name}"
        for name in ("pytorch", "routed")
    }
    report = {
        "stage": "OPT-06",
        "status": "FAILED",
        "training_run": False,
        "backend_connected": False,
        "production_settings_changed": False,
        "runs": {key: str(value) for key, value in runs.items()},
        "suite": str(manifest),
        "source_baseline": str(baseline),
        "accepted_engine_run": str(trt_run),
        "repeats_per_item_profile_scenario": args.repeats,
        "scope": "Three generated products, four ratios with pixel-preserving padding; loopback single-user HTTP. No phone/Spring/DB and no new engine export/build.",
    }
    print(f"OPT-06 ana rapor klasörü: {output}", flush=True)
    try:
        left = run_measurement(
            sys.executable,
            runs["pytorch"],
            None,
            "pytorch",
            trt_run,
            args.repeats,
            output / "pytorch.log",
            release_warmup_cache=True,
            shape_suite=manifest,
        )
        right = run_measurement(
            overlay / "bin/python",
            runs["routed"],
            runs["pytorch"],
            "tensorrt",
            trt_run,
            args.repeats,
            output / "routed.log",
            release_warmup_cache=True,
            shape_suite=manifest,
        )
        report.update(summarize(left, right))
        report["status"] = "SHAPE_TEST_COMPLETED_REVIEW_REQUIRED"
    except KeyboardInterrupt:
        report["status"] = "INTERRUPTED"
    except Exception as exc:
        report["error"] = str(exc)
    finally:
        save_json(output / "report.json", report)
        render(output, report, runs, manifest)
    terminal = {
        key: report.get(key)
        for key in (
            "status",
            "error",
            "profiles",
            "first_post_trim_pytorch_request_seconds",
            "ready_gpu_process_mib",
            "first_fallback_gpu_process_mib",
            "largest_post_pair_gpu_sample_mib",
            "sampled_gpu_growth_after_startup_mib",
            "routing",
            "first_shape_routing_valid",
            "measured_routing_valid",
            "all_observed_below_one_second",
            "latency_target_misses",
            "decision",
        )
    }
    terminal["quality_checks_passed"] = report.get("quality_comparison", {}).get(
        "all_checks_passed"
    )
    print(json.dumps(terminal, ensure_ascii=False, indent=2))
    print(f"Ana rapor: {output / 'report.json'}")
    print(f"Görsel rapor: {output / 'report.html'}")
    if report["status"] != "SHAPE_TEST_COMPLETED_REVIEW_REQUIRED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
