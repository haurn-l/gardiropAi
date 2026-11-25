"""Isolated real HTTP baseline: one cold pair, warmup, then two capture scenarios."""

import argparse
import hashlib
import importlib.metadata
import io
import json
import os
import random
import shutil
import signal
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

import numpy as np
from PIL import Image

from gardirop_ai_clothing.api_auth import load_api_key
from gardirop_ai_clothing.benchmark_comparison import compare_delivery_runs
from gardirop_ai_clothing.benchmarking import describe, summarize_samples
from gardirop_ai_clothing.config import get_settings
from gardirop_ai_clothing.embeddings.marqo import resolve_precision
from gardirop_ai_clothing.shape_experiment import load_suite, routing_valid, sample_process_gpu

ROOT = Path(__file__).resolve().parents[1]


def save(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8"
    )


def listening(port):
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def multipart(fields, data):
    boundary = "baseline-" + uuid4().hex
    output = bytearray()
    for key, value in fields.items():
        output.extend(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        )
    output.extend(
        f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="image.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
    )
    output.extend(data)
    output.extend(f"\r\n--{boundary}--\r\n".encode())
    return bytes(output), f"multipart/form-data; boundary={boundary}"


def nvidia_snapshot():
    try:
        process = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return process.stdout.strip() if process.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument(
        "--prepared", action="store_true", help="Load/warm models before HTTP becomes available."
    )
    parser.add_argument(
        "--compare", type=Path, help="Earlier completed baseline directory (read-only)."
    )
    parser.add_argument("--marqo-precision", choices=("fp32", "fp16"))
    parser.add_argument(
        "--segmentation-backend", choices=("pytorch", "tensorrt"), default="pytorch"
    )
    parser.add_argument("--tensorrt-run", type=Path)
    parser.add_argument("--comparison-mode", choices=("strict", "fp16", "trt"), default="strict")
    parser.add_argument("--output", type=Path, help="New directory inside outputs/api_baseline.")
    parser.add_argument(
        "--release-warmup-cache", action=argparse.BooleanOptionalAction, default=False
    )
    parser.add_argument("--shape-suite", type=Path)
    args = parser.parse_args()
    if args.compare is not None and not (args.compare / "report.json").is_file():
        parser.error("Reference report.json is missing.")
    if not 1 <= args.repeats <= 20 or not 1024 <= args.port <= 65535:
        parser.error("repeats must be 1..20; port must be 1024..65535.")
    for port in {8001, 7861, args.port}:
        if listening(port):
            raise SystemExit(
                f"{port} portu açık. API/demo terminalini Ctrl+C ile durdur; ölçümü yeniden başlat."
            )
    if args.release_warmup_cache and not args.prepared:
        parser.error("Startup cache release requires --prepared.")
    settings = get_settings()
    # This diagnostic explicitly requests CUDA for its isolated worker.
    precision = resolve_precision(args.marqo_precision or settings.marqo_precision, "cuda")
    if args.comparison_mode == "fp16" and (precision != "fp16" or args.compare is None):
        parser.error("FP16 comparison requires FP16 precision and a reference run.")
    if args.segmentation_backend == "tensorrt" and (
        args.tensorrt_run is None
        or not args.prepared
        or precision != "fp16"
        or args.compare is None
        or args.comparison_mode not in {"trt", "strict"}
    ):
        parser.error(
            "TensorRT measurement requires prepared FP16, an accepted engine and reference comparison."
        )
    if args.comparison_mode == "trt" and args.segmentation_backend != "tensorrt":
        parser.error("TRT parity mode requires the TensorRT backend.")
    if args.segmentation_backend == "tensorrt" and args.comparison_mode == "strict":
        reference_report = json.loads((args.compare / "report.json").read_text())
        if (
            reference_report.get("status") != "COMPLETED"
            or reference_report.get("segmentation_backend_requested") != "tensorrt"
        ):
            parser.error("Strict TensorRT comparison requires a completed TensorRT API reference.")
    secret = load_api_key(settings).get_secret_value()
    input_root = ROOT / "outputs" / "step07_completion" / "inputs" / "generated"
    if args.shape_suite is not None:
        if not args.prepared or not args.release_warmup_cache:
            parser.error("Shape suite requires prepared models and explicit warmup cache release.")
        cases = load_suite(args.shape_suite, ROOT, settings.max_upload_mb * 1024**2)
    else:
        cases = []
        for name, category, expected in (
            ("tshirt", "UST_GIYIM", "T-shirt"),
            ("jeans", "ALT_GIYIM", "Jean"),
            ("jacket", "DIS_GIYIM", "Kot ceket"),
        ):
            case = {"name": name, "category": category, "expected_subtype": expected}
            for view in ("front", "back"):
                path = input_root / f"{name}_{view}.png"
                data = path.read_bytes()
                if not 0 < len(data) <= settings.max_upload_mb * 1024**2:
                    raise ValueError("Input exceeds the configured upload limit.")
                case[view] = data
            cases.append(case)
    required_gib = max(2, (args.repeats * 2 + 4) // 5)
    if shutil.disk_usage(ROOT).free < required_gib * 1024**3:
        raise SystemExit(
            f"Ölçümün geçici dosyaları için en az {required_gib} GiB boş alan gerekli."
        )
    output = (
        ROOT
        / "outputs"
        / "api_baseline"
        / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8])
    )
    if args.output is not None:
        output = args.output.expanduser().resolve()
        allowed = (ROOT / "outputs" / "api_baseline").resolve()
        if output == allowed or not output.is_relative_to(allowed):
            parser.error("Output must be a new directory inside outputs/api_baseline.")
    output.mkdir(parents=True, exist_ok=False)
    events_path = output / "runtime_events.jsonl"
    environment = os.environ.copy()
    environment.update(
        GARDROPAI_API_RELEASE_WARMUP_CACHE="true" if args.release_warmup_cache else "false",
        GARDROPAI_SEGMENTATION_BACKEND=args.segmentation_backend,
        GARDROPAI_DEVICE="cuda",
        GARDROPAI_MARQO_PRECISION=precision,
        GARDROPAI_API_COMPACT_STORAGE="true",
        GARDROPAI_API_PRELOAD_MODELS="true" if args.prepared else "false",
        GARDROPAI_API_DRAFT_ROOT=str(output / "store"),
        GARDROPAI_BENCHMARK_LOG=str(events_path),
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_MODULES_CACHE=str(ROOT / "outputs" / "hf_modules"),
        PYTHONDONTWRITEBYTECODE="1",
    )
    if args.tensorrt_run is not None:
        environment["GARDROPAI_TENSORRT_RUN"] = str(args.tensorrt_run.expanduser().resolve())
    base = f"http://127.0.0.1:{args.port}"
    opener = build_opener(ProxyHandler({}))
    report = {
        "status": "FAILED",
        "training_run": False,
        "backend_connected": False,
        "runtime_optimization_applied": True,
        "models_prepared_before_first_request": args.prepared,
        "comparison_baseline": str(args.compare.resolve()) if args.compare is not None else None,
        "device_requested": "cuda",
        "marqo_precision_requested": precision,
        "segmentation_backend_requested": args.segmentation_backend,
        "startup_cache_release_requested": args.release_warmup_cache,
        "comparison_mode": args.comparison_mode,
        "repeats_per_case_per_scenario": args.repeats,
        "poll_interval_seconds": 0.1,
        "shape_suite": str(args.shape_suite.resolve()) if args.shape_suite is not None else None,
        "samples": [],
        "nvidia_before": nvidia_snapshot(),
        "inputs": [
            {
                "name": case["name"],
                "category": case["category"],
                "expected_subtype": case["expected_subtype"],
                **(
                    {
                        key: case[key]
                        for key in ("profile", "item", "expected_input_nchw", "expected_backend")
                    }
                    if args.shape_suite is not None
                    else {}
                ),
                "origin": "generated_images_not_population_accuracy_data",
                "front_sha256": hashlib.sha256(case["front"]).hexdigest(),
                "back_sha256": hashlib.sha256(case["back"]).hexdigest(),
            }
            for case in cases
        ],
        "limits": [
            "Loopback HTTP only; excludes mobile camera/network, Spring Boot and database services.",
            "Ready observation includes up to one polling interval and status-request latency.",
            "Cold is the first request in a new API process with lazy models, not a reboot/disk-cold cache.",
            "Internal spans overlap and include profiling overhead; never add model-load and parent-span durations.",
            "GPU allocated/reserved are overlapping PyTorch allocator metrics, not total process/desktop VRAM.",
            "RAM comes from the server child process; client allocations are excluded.",
            "Small repeated demo set. Percentiles are descriptive; this is not concurrent-user throughput.",
        ],
    }
    try:
        git_environment = os.environ.copy()
        git_environment["GIT_OPTIONAL_LOCKS"] = "0"
        report["git_head"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            env=git_environment,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        report["git_head"] = None
    report["source_sha256"] = {
        name: hashlib.sha256(
            (ROOT / "src" / "gardirop_ai_clothing" / name).read_bytes()
        ).hexdigest()
        for name in (
            "analysis.py",
            "jobs.py",
            "pipeline.py",
            "app.py",
            "model_manager.py",
            "embeddings/marqo.py",
            "image/birefnet_local.py",
            "image/birefnet_tensorrt.py",
            "tensorrt_experiment.py",
            "image/mask_postprocess.py",
            "image/canonical_view.py",
            "image/io.py",
            "image_profiling.py",
            "storage.py",
            "compact_storage.py",
            "runtime_preparation.py",
            "startup_memory.py",
            "shape_experiment.py",
            "labeling/attributes.py",
        )
    }
    references = {}
    report["python"] = sys.version
    report["package_versions"] = {
        name: importlib.metadata.version(name)
        for name in (
            "torch",
            "torchvision",
            "open-clip-torch",
            "transformers",
            "fastapi",
            "uvicorn",
            "numpy",
            "Pillow",
        )
    }

    def request(path, *, method="GET", body=None, headers=None):
        req = Request(
            base + path, data=body, method=method, headers={"X-API-Key": secret, **(headers or {})}
        )
        try:
            with opener.open(req, timeout=30) as response:
                payload, content_type = response.read(), response.headers.get("Content-Type", "")
        except HTTPError as error:
            raise RuntimeError(f"HTTP {error.code} on {method} {path}") from error
        return json.loads(payload) if "application/json" in content_type else payload

    def wait_state(path, *, front_only=False):
        deadline = time.monotonic() + 300
        while True:
            state = request(path)
            if state["status"] in {"FAILED", "CANCELLED"}:
                raise RuntimeError(f"Photo job failed: {state.get('error')}")
            if (
                front_only and state.get("views", {}).get("FRONT", {}).get("status") == "READY"
            ) or (not front_only and state["status"] == "READY"):
                return state
            if time.monotonic() >= deadline:
                raise TimeoutError("Benchmark job did not complete within 300 seconds.")
            time.sleep(0.1)

    def sample(case, scenario, phase):
        body, content_type = multipart(
            {"category": case["category"], "captureId": uuid4().hex}, case["front"]
        )
        start_ns = time.perf_counter_ns()
        created = request(
            "/v1/clothing/jobs",
            method="POST",
            body=body,
            headers={"Content-Type": content_type, "Idempotency-Key": uuid4().hex},
        )
        front_accepted_ns = time.perf_counter_ns()
        job_path = f"/v1/clothing/jobs/{created['jobId']}"
        state = (
            wait_state(job_path, front_only=True)
            if scenario == "front_ready_before_back"
            else request(job_path)
        )
        body, content_type = multipart(
            {"captureId": uuid4().hex, "expectedRevision": state["revision"]}, case["back"]
        )
        back_started_ns = time.perf_counter_ns()
        request(
            job_path + "/views/BACK",
            method="PUT",
            body=body,
            headers={"Content-Type": content_type},
        )
        back_accepted_ns = time.perf_counter_ns()
        ready = wait_state(job_path)
        ready_ns = time.perf_counter_ns()
        metadata = request(ready["resultUrl"])
        images = {view: request(info["url"]) for view, info in metadata["images"].items()}
        embedding = request(metadata["embedding"]["url"])
        assets_ns = time.perf_counter_ns()
        vector = np.asarray(embedding["values"], dtype=np.float32)
        if (
            vector.shape != (1536,)
            or not np.isfinite(vector).all()
            or abs(float(np.linalg.norm(vector)) - 1) > 1e-3
        ):
            raise ValueError("Invalid embedding contract.")
        if embedding["viewOrder"] != ["FRONT", "BACK"]:
            raise ValueError("Invalid view order.")
        for half in (vector[:768], vector[768:]):
            if abs(float(np.linalg.norm(half)) - 1 / np.sqrt(2)) > 1e-3:
                raise ValueError("Invalid embedding half norm.")
        hashes = {}
        for view, data in images.items():
            info = metadata["images"][view]
            digest = hashlib.sha256(data).hexdigest()
            if digest != info["sha256"] or len(data) != info["byteLength"]:
                raise ValueError("Image checksum/length mismatch.")
            hashes[view] = digest
            with Image.open(io.BytesIO(data)) as image:
                if image.mode != "RGB" or image.format != "WEBP":
                    raise ValueError("Delivery is not RGB WebP.")
                image.load()
                if list(image.size) != [info["width"], info["height"]]:
                    raise ValueError("Image dimensions do not match their descriptor.")
                corners = (
                    (0, 0),
                    (image.width - 1, 0),
                    (0, image.height - 1),
                    (image.width - 1, image.height - 1),
                )
                if any(image.getpixel(point) != (255, 255, 255) for point in corners):
                    raise ValueError("Delivery background is not white.")
        row = {
            "phase": phase,
            "case": case["name"],
            "scenario": scenario,
            "job_id": created["jobId"],
            "start_ns": start_ns,
            "ready_ns": ready_ns,
            "assets_ns": assets_ns,
            "front_status_observed_before_back": state["views"]["FRONT"]["status"],
            "capture_gap_seconds": (back_started_ns - front_accepted_ns) / 1e9,
            "back_request_start_to_ready_seconds": (ready_ns - back_started_ns) / 1e9,
            "back_request_start_to_assets_received_seconds": (assets_ns - back_started_ns) / 1e9,
            "back_accepted_to_ready_seconds": (ready_ns - back_accepted_ns) / 1e9,
            "back_accepted_to_assets_received_seconds": (assets_ns - back_accepted_ns) / 1e9,
            "front_request_start_to_ready_seconds": (ready_ns - start_ns) / 1e9,
            "front_request_start_to_assets_received_seconds": (assets_ns - start_ns) / 1e9,
            "tags": metadata["tags"],
            "image_sha256": hashes,
            **(
                {
                    "profile": case["profile"],
                    "expected_input_nchw": case["expected_input_nchw"],
                    "expected_backend": case["expected_backend"]
                    if args.segmentation_backend == "tensorrt"
                    else "pytorch",
                    "gpu_process_sample_after_pair_mib": sample_process_gpu(process.pid),
                }
                if args.shape_suite is not None
                else {}
            ),
            "subtype_matches_visual_expectation": metadata["tags"]["subCategory"]
            == case["expected_subtype"],
        }
        if phase == "measured":
            if case["name"] not in references:
                directory = output / "cases" / case["name"]
                directory.mkdir(parents=True)
                for view, data in images.items():
                    (directory / f"{view.lower()}.webp").write_bytes(data)
                save(directory / "result.json", metadata)
                save(directory / "embedding.json", embedding)
                references[case["name"]] = {
                    "hashes": hashes,
                    "vector": vector.copy(),
                    "tags": metadata["tags"],
                }
            reference = references[case["name"]]
            row.update(
                same_image_bytes_as_first_measured=hashes == reference["hashes"],
                same_embedding_values_as_first_measured=np.array_equal(vector, reference["vector"]),
                embedding_cosine_to_first_measured=float(
                    np.dot(vector.astype(np.float64), reference["vector"].astype(np.float64))
                    / (
                        np.linalg.norm(vector.astype(np.float64))
                        * np.linalg.norm(reference["vector"].astype(np.float64))
                    )
                ),
                same_tags_as_first_measured=metadata["tags"] == reference["tags"],
            )
        report["samples"].append(row)
        save(output / "report.json", report)
        request(job_path + f"?expectedRevision={ready['revision']}", method="DELETE")
        print(
            f"{phase}: {case['name']} / {scenario}: arka kabulü → hazır {row['back_accepted_to_ready_seconds']:.3f} sn; indirmeler {row['back_accepted_to_assets_received_seconds']:.3f} sn",
            flush=True,
        )

    process = None
    server_log = (output / "server.log").open("w")
    print(f"Ölçüm klasörü: {output}", flush=True)
    try:
        launch_ns = time.perf_counter_ns()
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "gardirop_ai_clothing.benchmark_runtime:create_profiled_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(args.port),
                "--workers",
                "1",
                "--log-level",
                "warning",
            ],
            cwd=ROOT,
            env=environment,
            stdout=server_log,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 120
        while True:
            if process.poll() is not None:
                raise RuntimeError("Ölçüm sunucusu açılamadı; server.log dosyasına bak.")
            try:
                if request("/health/live").get("photoProcessingAvailable"):
                    break
            except (URLError, TimeoutError):
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError("Ölçüm sunucusu 120 saniyede başlayamadı.")
            time.sleep(0.25)
        report["server_startup_seconds"] = (time.perf_counter_ns() - launch_ns) / 1e9
        if args.prepared:
            readiness = request("/health/ready")
            if readiness["status"] != "READY" or not readiness["modelsWarmed"]:
                raise RuntimeError("Server was not warmed before the first request.")
            expected_runtime = (
                "tensorrt_with_pytorch_fallback"
                if args.segmentation_backend == "tensorrt"
                else "pytorch"
            )
            if readiness.get("segmentationBackend") != expected_runtime:
                raise RuntimeError("Readiness reports the wrong segmentation backend.")
            report["readiness_before_first_request"] = readiness
        if args.shape_suite is not None:
            for case in cases:
                if case["item"] == "tshirt":
                    sample(case, "back_immediate", f"first_shape/{case['profile']}")
        else:
            sample(cases[0], "back_immediate", "first_ready_request" if args.prepared else "cold")
        for case in cases:
            sample(case, "back_immediate", "warmup")
        plan = [
            (case, scenario)
            for _ in range(args.repeats)
            for case in cases
            for scenario in ("back_immediate", "front_ready_before_back")
        ]
        random.Random(0).shuffle(plan)
        for index, (case, scenario) in enumerate(plan, 1):
            print(f"Ölçüm {index}/{len(plan)}", flush=True)
            sample(case, scenario, "measured")
        report["summary_seconds"] = summarize_samples(report["samples"])
        if args.compare is not None:
            report["quality_comparison"] = compare_delivery_runs(
                args.compare,
                output,
                mode=args.comparison_mode,
                case_names=tuple(case["name"] for case in cases),
            )
            repeat_consistent = all(
                row["same_image_bytes_as_first_measured"]
                and row["same_tags_as_first_measured"]
                and row["same_embedding_values_as_first_measured"]
                for row in report["samples"]
                if row["phase"] == "measured"
            )
            report["quality_comparison"]["all_repeats_identical"] = repeat_consistent
            report["quality_comparison"]["all_checks_passed"] &= repeat_consistent
            if not report["quality_comparison"]["all_checks_passed"]:
                raise ValueError(
                    "Reference comparison differed; inspect quality_comparison before accepting this optimization."
                )
        if args.shape_suite is not None:
            report["suite_repeats_identical"] = all(
                row["same_image_bytes_as_first_measured"]
                and row["same_tags_as_first_measured"]
                and row["same_embedding_values_as_first_measured"]
                for row in report["samples"]
                if row["phase"] == "measured"
            )
            if not report["suite_repeats_identical"]:
                raise ValueError("Shape suite outputs changed between repeats.")
        report["status"] = "COMPLETED"
    except Exception as error:
        report["error"] = str(error)
    finally:
        report["forced_shutdown"] = False
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                report["forced_shutdown"] = True
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        server_log.close()
        report["server_exit_code"] = process.returncode if process is not None else None
        if events_path.exists():
            try:
                events = [
                    json.loads(line)
                    for line in events_path.read_text().splitlines()
                    if line.strip()
                ]
                report["model_loads"] = [
                    event for event in events if event["event"] == "model_load"
                ]
                memories = [event["memory"] for event in events]
                report["server_memory_max_mib"] = {
                    key: max(
                        (item[key] for item in memories if key in item and item[key] is not None),
                        default=None,
                    )
                    for key in (
                        "lifetime_peak_rss_mib",
                        "allocated_mib",
                        "reserved_mib",
                        "peak_allocated_mib",
                        "peak_reserved_mib",
                    )
                }
                report["server_gpu_process_samples_mib"] = [
                    {"event": event["event"], "mib": event["memory"]["gpu_process_sample_mib"]}
                    for event in events
                    if event["memory"].get("gpu_process_sample_mib") is not None
                ]
                report["gpu_memory_scope"] = (
                    "Per-PID total GPU memory at readiness/shutdown, not a peak; PyTorch allocator counters exclude native TensorRT allocations."
                )
                report["segmentation_runtime"] = next(
                    (
                        event.get("runtime_details", {})
                        for event in report["model_loads"]
                        if event["model"] == "birefnet_dynamic"
                    ),
                    {},
                )
                # Load-time routing counters are zero; actual successful routing
                # evidence is recorded independently for each measured forward.
                report["segmentation_runtime"] = dict(report["segmentation_runtime"])
                report["segmentation_runtime"].pop("forwardCounts", None)
                forwards = [
                    event
                    for event in events
                    if event["event"] == "segmentation_forward_and_transfer"
                ]
                report["segmentation_forward_counts"] = {
                    backend: sum(event.get("backend") == backend for event in forwards)
                    for backend in ("pytorch", "tensorrt")
                }
                measured_windows = [row for row in report["samples"] if row["phase"] == "measured"]
                report["measured_segmentation_routing_valid"] = routing_valid(
                    measured_windows, forwards, cases, args.segmentation_backend
                )
                if args.shape_suite is not None:
                    first_windows = [
                        row for row in report["samples"] if row["phase"].startswith("first_shape/")
                    ]
                    report["first_shape_routing_valid"] = routing_valid(
                        first_windows, forwards, cases, args.segmentation_backend
                    )
                    if not report["first_shape_routing_valid"]:
                        report.update(
                            status="FAILED",
                            routing_error="First post-trim shape routing was not demonstrated.",
                        )
                if not report["measured_segmentation_routing_valid"]:
                    report.update(
                        status="FAILED",
                        routing_error="Measured demo photos did not all use the requested segmenter.",
                    )
                ready_events = [event for event in events if event["event"] == "runtime_ready"]
                report["startup_cache_release"] = (
                    ready_events[0]["report"].get("startupCacheRelease", {})
                    if len(ready_events) == 1
                    else {}
                )
                if (
                    args.prepared
                    and report["startup_cache_release"].get("applied")
                    is not args.release_warmup_cache
                ):
                    report.update(
                        status="FAILED",
                        cache_release_error="Requested startup cache policy was not applied.",
                    )
                report["runtime_event_count"] = len(events)
                loads = report["model_loads"]
                expected_models = {"birefnet_dynamic", "marqo_fashionsiglip", "marqo_parent_lr"}
                if len(loads) != 3 or {item["model"] for item in loads} != expected_models:
                    report.update(
                        status="FAILED",
                        event_parse_error="Expected exactly one load per pinned model.",
                    )
                marqo_loads = [item for item in loads if item["model"] == "marqo_fashionsiglip"]
                if len(marqo_loads) != 1 or marqo_loads[0]["precision"] != precision:
                    report.update(
                        status="FAILED",
                        event_parse_error="Actual Marqo precision differs from the requested precision.",
                    )
                report["marqo_runtime"] = (
                    marqo_loads[0].get("runtime_details", {}) if marqo_loads else {}
                )
                shutdowns = [event for event in events if event["event"] == "shutdown"]
                if len(shutdowns) != 1 or not shutdowns[0]["success"] or report["forced_shutdown"]:
                    report.update(
                        status="FAILED", event_parse_error="Worker did not close gracefully."
                    )
                report["stage_summary_ms"] = {}
                phases = ["cold", "first_ready_request", "warmup", "measured"]
                if args.shape_suite is not None:
                    phases.extend(
                        sorted(
                            {
                                row["phase"]
                                for row in report["samples"]
                                if row["phase"].startswith("first_shape/")
                            }
                        )
                    )
                for phase in phases:
                    windows = [row for row in report["samples"] if row["phase"] == phase]
                    selected = [
                        event
                        for event in events
                        if "elapsed_ms" in event
                        and any(
                            row["start_ns"]
                            <= event["start_ns"]
                            <= event["end_ns"]
                            <= row["assets_ns"]
                            for row in windows
                        )
                    ]
                    report["stage_summary_ms"][phase] = {
                        name: describe(
                            [event["elapsed_ms"] for event in selected if event["event"] == name]
                        )
                        for name in sorted({event["event"] for event in selected})
                    }
                first_start = report["samples"][0]["start_ns"] if report["samples"] else 0
                if args.prepared and (
                    len(loads) != 3 or any(item["end_ns"] >= first_start for item in loads)
                ):
                    report.update(
                        status="FAILED",
                        event_parse_error="A model loaded during/after the first prepared request.",
                    )
                starts = [event for event in events if event["event"] == "worker_created"]
                if len(starts) != 1 or starts[0]["loaded_models"]:
                    report.update(
                        status="FAILED",
                        event_parse_error="Worker was not created with lazy unloaded models.",
                    )
            except (ValueError, KeyError) as error:
                report.update(status="FAILED", event_parse_error=str(error))
        else:
            report.update(status="FAILED", event_parse_error="No runtime events were recorded.")
        report["nvidia_after"] = nvidia_snapshot()
        if report["status"] == "COMPLETED" and report["server_exit_code"] == 0:
            store = output / "store"
            if store.is_dir() and store.resolve().is_relative_to(output.resolve()):
                shutil.rmtree(store)
            report["temporary_store_removed"] = True
        elif report["status"] == "COMPLETED":
            report["status"] = "FAILED"
        save(output / "report.json", report)
    terminal_summary = {
        key: report.get(key)
        for key in (
            "status",
            "error",
            "event_parse_error",
            "server_startup_seconds",
            "server_memory_max_mib",
            "readiness_before_first_request",
            "quality_comparison",
            "marqo_precision_requested",
            "marqo_runtime",
            "segmentation_backend_requested",
            "segmentation_runtime",
            "segmentation_forward_counts",
            "measured_segmentation_routing_valid",
            "server_gpu_process_samples_mib",
            "routing_error",
            "startup_cache_release",
            "first_shape_routing_valid",
            "cache_release_error",
        )
    }
    terminal_summary["image_stage_mean_ms"] = {
        name: values["mean"]
        for name, values in report.get("stage_summary_ms", {}).get("measured", {}).items()
        if name
        in {
            "image_decode",
            "segmentation_with_prepost",
            "segmentation_forward_and_transfer",
            "mask_cleanup",
            "foreground_crop",
            "canonicalize_and_white",
            "transparent_webp_encoding",
            "white_webp_encoding",
            "image_preparation",
        }
    }
    terminal_summary["warm_scenarios_seconds"] = {
        name: {
            field: values[field]
            for field in (
                "back_request_start_to_ready_seconds",
                "back_request_start_to_assets_received_seconds",
                "back_accepted_to_ready_seconds",
                "back_accepted_to_assets_received_seconds",
            )
        }
        for name, values in report.get("summary_seconds", {}).items()
        if "/" not in name
    }
    print(json.dumps(terminal_summary, ensure_ascii=False, indent=2))
    print(f"Ana rapor: {output / 'report.json'}")
    print(f"Aşama kayıtları: {events_path}")
    if report["status"] != "COMPLETED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
