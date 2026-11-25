"""Two fresh TensorRT API runs differing only in startup cache release."""

import argparse
import html
import json
import os
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from compare_api_tensorrt import run_measurement

from gardirop_ai_clothing.onnx_experiment import save_json

ROOT = Path(__file__).resolve().parents[1]
POLICY = {
    "id": "trt-startup-cache-demo-v1",
    "min_resident_sample_reduction_mib": 128,
    "max_p95_increase_seconds": 0.1,
    "max_observed_delivery_seconds": 1.0,
    "scope": "Two sequential local runs; descriptive demo gates, not a concurrency or true VRAM-peak guarantee.",
}


def gpu_sample(report, event):
    values = [
        row["mib"] for row in report["server_gpu_process_samples_mib"] if row["event"] == event
    ]
    return values[0] if len(values) == 1 else None


def summarize(left, right):
    field = "back_request_start_to_assets_received_seconds"
    scenarios = {}
    for scenario in ("front_ready_before_back", "back_immediate"):
        a, b = left["summary_seconds"][scenario][field], right["summary_seconds"][scenario][field]
        scenarios[scenario] = {
            "keep_cache_seconds": a,
            "release_cache_seconds": b,
            "p95_delta_ms": (b["p95"] - a["p95"]) * 1000,
            "latency_gate_passed": b["p95"] <= a["p95"] + POLICY["max_p95_increase_seconds"]
            and b["max"] < POLICY["max_observed_delivery_seconds"],
        }
    samples = {
        role: {event: gpu_sample(report, event) for event in ("runtime_ready", "shutdown")}
        for role, report in (("keep", left), ("release", right))
    }
    before, after = samples["keep"]["runtime_ready"], samples["release"]["runtime_ready"]
    reduction = before - after if before is not None and after is not None else None
    end_before, end_after = samples["keep"]["shutdown"], samples["release"]["shutdown"]
    end_reduction = (
        end_before - end_after if end_before is not None and end_after is not None else None
    )
    first_requests = {
        role: next(row for row in report["samples"] if row["phase"] == "first_ready_request")[field]
        for role, report in (("keep", left), ("release", right))
    }
    release = right["startup_cache_release"]
    quality_ok = right["quality_comparison"]["all_checks_passed"]
    memory_ok = (
        reduction is not None
        and reduction >= POLICY["min_resident_sample_reduction_mib"]
        and end_reduction is not None
        and end_reduction >= POLICY["min_resident_sample_reduction_mib"]
        and release.get("applied") is True
        and release.get("active_allocations_unchanged") is True
    )
    latency_ok = (
        all(row["latency_gate_passed"] for row in scenarios.values())
        and first_requests["release"] < POLICY["max_observed_delivery_seconds"]
    )
    return {
        "scenarios": scenarios,
        "gpu_process_samples_mib": samples,
        "ready_sample_reduction_mib": reduction,
        "shutdown_sample_reduction_mib": end_reduction,
        "startup_cache_release": release,
        "first_ready_request_delivery_seconds": first_requests,
        "startup_seconds": {
            "keep": left["server_startup_seconds"],
            "release": right["server_startup_seconds"],
        },
        "quality_comparison": right["quality_comparison"],
        "routing": right["segmentation_forward_counts"],
        "memory_gate_passed": memory_ok,
        "latency_gate_passed": latency_ok,
        "quality_gate_passed": quality_ok,
        "all_demo_gates_passed": bool(memory_ok and latency_ok and quality_ok),
    }


def render(output, report, runs):
    blocks = []
    for item in ("tshirt", "jeans", "jacket"):
        for view in ("front", "back"):
            figures = []
            for role, label in (
                ("keep", "TensorRT · mevcut önbellek"),
                ("release", "TensorRT · başlangıç önbelleği bırakıldı"),
            ):
                path = runs[role] / "cases" / item / f"{view}.webp"
                if path.is_file():
                    relative = html.escape(os.path.relpath(path, output), quote=True)
                    figures.append(
                        f'<figure><img src="{relative}"><figcaption>{label}</figcaption></figure>'
                    )
            if len(figures) == 2:
                blocks.append(f'<h2>{item} / {view}</h2><div class="pair">{"".join(figures)}</div>')
    data = html.escape(json.dumps(report, ensure_ascii=False, indent=2))
    (
        output / "report.html"
    ).write_text(f"""<!doctype html><html lang="tr"><meta charset="utf-8"><title>OPT-05E</title>
<style>body{{font:16px system-ui;max-width:1100px;margin:30px auto;padding:15px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:15px}}figure{{margin:0}}img{{width:100%;height:360px;object-fit:contain}}</style>
<h1>OPT-05E · Başlangıç GPU önbelleği karşılaştırması</h1>
<p>İki koşuda da TensorRT, CUDA FP16 PyTorch fallback ve Marqo bellekte kalır. Yalnız başlangıç sonrası boş önbellek politikası değişir.
GPU sayıları hazır olma/kapanış anlarındaki süreç örnekleridir; tepe değildir. Sonraki PyTorch görüntü boyutları önbelleği tekrar büyütebilir.</p>
<pre>{data}</pre>{"".join(blocks)}</html>""")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trt-run", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve() or not 1 <= args.repeats <= 20:
        parser.error("Use make compare-trt-memory from .venv; repeats must be 1..20.")
    for port in (7861, 8001, 8002):
        with socket.socket() as probe:
            probe.settimeout(0.2)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                parser.error(f"{port} açık; ilgili API/demo terminalini Ctrl+C ile durdur.")
    trt_run, baseline = args.trt_run.expanduser().resolve(), args.baseline.expanduser().resolve()
    if not trt_run.is_relative_to((ROOT / "outputs/tensorrt_compare").resolve()):
        parser.error("Choose an accepted local OPT-05C engine run.")
    if not baseline.is_relative_to((ROOT / "outputs/api_baseline").resolve()):
        parser.error("Choose a completed local TensorRT HTTP baseline.")
    accepted = json.loads((trt_run / "report.json").read_text())
    old = json.loads((baseline / "report.json").read_text())
    if (
        accepted.get("status") != "DEMO_GATES_PASSED_REVIEW_REQUIRED"
        or accepted.get("all_demo_gates_passed") is not True
        or old.get("status") != "COMPLETED"
        or old.get("segmentation_backend_requested") != "tensorrt"
        or not old.get("quality_comparison", {}).get("all_checks_passed")
        or old.get("segmentation_runtime", {}).get("engineSha256")
        != accepted["steps"]["build"]["engine"]["plan_sha256"]
    ):
        parser.error("Accepted engine and completed TensorRT API reference do not agree.")
    overlay = ROOT / ".venv-trt"
    if (
        overlay.is_symlink()
        or not overlay.resolve().is_relative_to(ROOT)
        or not (overlay / "bin/python").is_file()
    ):
        parser.error("The existing .venv-trt environment is required.")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    output = ROOT / "outputs/api_memory_compare" / stamp
    if not output.resolve().is_relative_to(ROOT):
        parser.error("Unsafe output folder.")
    output.mkdir(parents=True, exist_ok=False)
    runs = {
        role: ROOT / "outputs/api_baseline" / f"{stamp}_cache_{role}"
        for role in ("keep", "release")
    }
    report = {
        "stage": "OPT-05E",
        "status": "FAILED",
        "policy": POLICY,
        "training_run": False,
        "backend_connected": False,
        "default_cache_policy_changed": False,
        "baseline": str(baseline),
        "accepted_engine_run": str(trt_run),
        "runs": {key: str(value) for key, value in runs.items()},
        "scope": "Single-user loopback HTTP; no phone network/Spring/DB. Memory samples are not peaks. All loaded models and fallback remain resident.",
    }
    print(f"OPT-05E ana rapor klasörü: {output}", flush=True)
    try:
        left = run_measurement(
            overlay / "bin/python",
            runs["keep"],
            baseline,
            "tensorrt",
            trt_run,
            args.repeats,
            output / "keep.log",
            comparison_mode="strict",
        )
        right = run_measurement(
            overlay / "bin/python",
            runs["release"],
            runs["keep"],
            "tensorrt",
            trt_run,
            args.repeats,
            output / "release.log",
            comparison_mode="strict",
            release_warmup_cache=True,
        )
        report.update(summarize(left, right))
        report["status"] = (
            "MEMORY_DEMO_GATES_PASSED_REVIEW_REQUIRED"
            if report["all_demo_gates_passed"]
            else "MEMORY_OR_LATENCY_GATE_REJECTED"
        )
    except KeyboardInterrupt:
        report["status"] = "INTERRUPTED"
    except Exception as exc:
        report["error"] = str(exc)
    finally:
        save_json(output / "report.json", report)
        render(output, report, runs)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Ana rapor: {output / 'report.json'}")
    print(f"Görsel rapor: {output / 'report.html'}")
    if report["status"] != "MEMORY_DEMO_GATES_PASSED_REVIEW_REQUIRED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
