"""Native TensorRT build/compare worker. Runs only in .venv-trt, never the API."""

import argparse
import fcntl
import gc
import importlib.metadata
import json
import os
import resource
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

import numpy as np
from onnx_birefnet_worker import benchmark, downstream, process_cases, reference_and_export

from gardirop_ai_clothing.onnx_experiment import INPUT_SHAPE, build_deform_probe, save_json, sha256
from gardirop_ai_clothing.tensorrt_experiment import (
    BUILD_POLICY,
    TRT_PACKAGES,
    TensorRTRunner,
    cache_key,
    native_trt,
)

ROOT = Path(__file__).resolve().parents[1]


def memory_snapshot():
    import torch

    result = {
        "torch_allocated_mib": torch.cuda.memory_allocated() / 1024**2,
        "torch_reserved_mib": torch.cuda.memory_reserved() / 1024**2,
        "lifetime_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "gpu_process_sample_mib": None,
        "scope": "One process-memory sample with models resident after warmup; not a true VRAM peak. TensorRT allocations are outside the Torch allocator.",
    }
    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            proc = subprocess.run(
                [smi, "--query-compute-apps=pid,used_gpu_memory", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0:
                matches = [
                    float(line.split(",")[1].strip())
                    for line in proc.stdout.splitlines()
                    if line.split(",")[0].strip() == str(os.getpid())
                ]
                if matches:
                    result["gpu_process_sample_mib"] = sum(matches)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    return result


def device_identity():
    import torch

    prop = torch.cuda.get_device_properties(0)
    identity = {
        "name": prop.name,
        "compute_capability": [prop.major, prop.minor],
        "total_memory": prop.total_memory,
        "torch_cuda": torch.version.cuda,
        "torch": torch.__version__,
        "tensorrt_binding": native_trt().__version__,
        "sdk_packages": {
            p.split("==")[0]: importlib.metadata.version(p.split("==")[0]) for p in TRT_PACKAGES
        },
    }
    smi = shutil.which("nvidia-smi")
    if not smi:
        raise RuntimeError(
            "nvidia-smi is required to fingerprint driver/GPU for this engine cache."
        )
    query = subprocess.check_output(
        [smi, "--query-gpu=uuid,driver_version", "--format=csv,noheader"], text=True, timeout=10
    )
    identity["gpu_driver_inventory"] = query.strip().splitlines()
    return identity


def build_plan(onnx_file, *, label):
    import torch

    trt = native_trt()
    logger = trt.Logger(trt.Logger.WARNING)
    if not trt.init_libnvinfer_plugins(logger, ""):
        raise RuntimeError("TensorRT plugin initialization failed.")
    builder = trt.Builder(logger)
    if builder is None:
        raise RuntimeError("TensorRT Builder initialization failed.")
    flags = 1 << int(trt.NetworkDefinitionCreationFlag.STRONGLY_TYPED)
    network = builder.create_network(flags)
    parser = trt.OnnxParser(network, logger)
    print(f"TensorRT ONNX ayrıştırma: {label}", flush=True)
    if not parser.parse_from_file(str(onnx_file)):
        errors = [str(parser.get_error(index)) for index in range(parser.num_errors)]
        raise RuntimeError("TensorRT ONNX parse failed:\n" + "\n".join(errors))
    for index in range(network.num_inputs):
        tensor = network.get_input(index)
        if tensor.dtype != trt.float16 or any(value < 1 for value in tensor.shape):
            raise RuntimeError("Only static FP16 inputs are accepted in this experiment.")
        tensor.allowed_formats = 1 << int(trt.TensorFormat.LINEAR)
    for index in range(network.num_outputs):
        network.get_output(index).allowed_formats = 1 << int(trt.TensorFormat.LINEAR)
    config = builder.create_builder_config()
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, BUILD_POLICY["workspace_bytes"])
    config.builder_optimization_level = BUILD_POLICY["optimization_level"]
    config.max_aux_streams = BUILD_POLICY["max_aux_streams"]
    config.profiling_verbosity = trt.ProfilingVerbosity.DETAILED
    # Strong typing preserves the FP16 ONNX tensor types/casts; no blanket precision rewrite.
    started = time.perf_counter()
    stop = threading.Event()

    def heartbeat():
        while not stop.wait(15):
            print(
                f"{label}: motor oluşturuluyor... {time.perf_counter() - started:.0f} sn",
                flush=True,
            )

    monitor = threading.Thread(target=heartbeat, daemon=True)
    monitor.start()
    try:
        print(
            f"{label}: motor oluşturma başladı; çalışma alanı üst sınırı 1 GiB (toplam bellek sınırı değildir).",
            flush=True,
        )
        blob = builder.build_serialized_network(network, config)
        if blob is None:
            raise RuntimeError("TensorRT engine build failed. Review native messages above.")
        result = bytes(blob)
        torch.cuda.synchronize()
        return result, time.perf_counter() - started
    finally:
        stop.set()
        monitor.join(timeout=1)


def cached_plan(source, *, label):
    identity = {
        "onnx_sha256": sha256(source),
        "device": device_identity(),
        "build": BUILD_POLICY,
        "adapter_sha256": sha256(ROOT / "src/gardirop_ai_clothing/tensorrt_experiment.py"),
        "builder_sha256": sha256(Path(__file__)),
    }
    fingerprint = cache_key(identity)
    parent = ROOT / "outputs/tensorrt_engines"
    if not parent.resolve().is_relative_to(ROOT):
        raise RuntimeError("Unsafe TensorRT engine cache.")
    folder = parent / fingerprint
    folder.mkdir(parents=True, exist_ok=True)
    plan, manifest = folder / "model.plan", folder / "engine.json"
    with (folder / "build.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if plan.is_file() and manifest.is_file():
            record = json.loads(manifest.read_text())
            if record["identity"] != identity or sha256(plan) != record["plan_sha256"]:
                raise RuntimeError("Cached TensorRT engine identity/checksum mismatch.")
            print(f"Doğrulanmış motor cache'den açılacak: {label}", flush=True)
            return plan, {**record, "cache_hit": True, "build_seconds_this_run": 0.0}
        blob, seconds = build_plan(source, label=label)
        temporary = folder / "model.plan.tmp"
        temporary.write_bytes(blob)
        os.replace(temporary, plan)
        record = {
            "identity": identity,
            "cache_key": fingerprint,
            "plan_sha256": sha256(plan),
            "plan_bytes": len(blob),
            "original_build_seconds": seconds,
        }
        tmp_manifest = folder / "engine.json.tmp"
        save_json(tmp_manifest, record)
        os.replace(tmp_manifest, manifest)
        return plan, {**record, "cache_hit": False, "build_seconds_this_run": seconds}


def tiny_test(output, source):
    import onnx
    import torch
    from onnx import numpy_helper

    rng = np.random.default_rng(20261125)
    rows = []
    for kernel in (1, 3, 7):
        print(f"TensorRT DeformConv kontrolü: kernel={kernel}", flush=True)
        arrays = [
            (rng.normal(size=(1, 2, 8, 10)) * 0.1).astype(np.float16),
            (rng.normal(size=(3, 2, kernel, kernel)) * 0.1).astype(np.float16),
            (rng.normal(size=(1, 2 * kernel * kernel, 8, 10)) * 0.3).astype(np.float16),
            rng.uniform(0, 2, size=(1, kernel * kernel, 8, 10)).astype(np.float16),
            (rng.normal(size=(3,)) * 0.1).astype(np.float16),
        ]
        model = build_deform_probe(kernel)
        with torch.inference_mode():
            expected = (
                model(*(torch.from_numpy(v).to("cuda") for v in arrays)).float().cpu().numpy()
            )
        del model
        gc.collect()
        torch.cuda.empty_cache()
        names = ["x", "weight", "offset", "mask", "bias"]
        values = dict(zip(names, arrays, strict=True))
        # BiRefNet has fixed learned weights/bias. Freeze only these two probe
        # arguments to mirror that contract, retaining fractional offsets/masks.
        graph = onnx.load(str(source / f"tiny_deform_{kernel}.onnx"))
        retained = [entry for entry in graph.graph.input if entry.name not in {"weight", "bias"}]
        del graph.graph.input[:]
        graph.graph.input.extend(retained)
        for name in ("weight", "bias"):
            graph.graph.initializer.append(numpy_helper.from_array(values.pop(name), name=name))
        onnx.checker.check_model(graph)
        frozen = output / f"tiny_constant_weights_{kernel}.onnx"
        onnx.save(graph, str(frozen))
        plan, record = cached_plan(frozen, label=f"tiny_{kernel}")
        runner = TensorRTRunner(plan, {name: tuple(value.shape) for name, value in values.items()})
        actual = runner.run_arrays(values)
        np.testing.assert_allclose(actual, expected, atol=0.002, rtol=0.005)
        rows.append(
            {
                "kernel": kernel,
                "max_abs_error": float(np.abs(actual - expected).max()),
                "engine": record,
            }
        )
        del runner
        gc.collect()
        torch.cuda.empty_cache()
    return {"status": "PASSED", "cases": rows}


def build_full(source):
    artifact = json.loads((source / "artifact.json").read_text())
    model = source / artifact["file"]
    if sha256(model) != artifact["sha256"]:
        raise RuntimeError("Source ONNX artifact SHA256 mismatch.")
    plan, record = cached_plan(model, label="BiRefNet Dynamic FP16")
    return {"status": "PASSED", "plan": str(plan), "engine": record}


def infer(output, inputs, repeats):
    record = json.loads((output / "build.json").read_text())
    plan = Path(record["plan"])
    allowed = (ROOT / "outputs/tensorrt_engines").resolve()
    if (
        not plan.resolve().is_relative_to(allowed)
        or sha256(plan) != record["engine"]["plan_sha256"]
    ):
        raise RuntimeError("Unrecognized or modified TensorRT plan.")
    runner = TensorRTRunner(plan, {"pixels": INPUT_SHAPE})
    if tuple(runner.buffers[runner.output_name].shape) != (1, 1, 1024, 704):
        raise RuntimeError("Unexpected TensorRT segmentation output shape.")
    cases = process_cases(output, inputs, runner, "trt")
    timing = benchmark(inputs, runner, repeats)
    (output / "engine_inspector.json").write_text(runner.inspector_json())
    return {
        "status": "PASSED",
        "cases": cases,
        "timing": timing,
        "all_image_gates_passed": all(row["quality"]["passed"] for row in cases),
        "memory_snapshot": memory_snapshot(),
        "context_device_memory_bytes": runner.context_device_memory_bytes,
        "context_memory_scope": "Execution context workspace/activations only; not total VRAM or engine weights.",
        "io_buffers_bytes": sum(v.numel() * v.element_size() for v in runner.buffers.values()),
        "execution": "Native TensorRT execute_async_v3 on a CUDA stream; synchronized. No ORT/CPU execution provider.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage", choices=["tiny", "build", "reference", "infer", "downstream"], required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()
    output = args.output.resolve()
    allowed = (ROOT / "outputs/tensorrt_compare").resolve()
    if output == allowed or not output.is_relative_to(allowed) or not output.is_dir():
        parser.error("Output must be an isolated run under outputs/tensorrt_compare.")
    if Path(sys.prefix).resolve() != (ROOT / ".venv-trt").resolve():
        parser.error("Use only the prepared .venv-trt interpreter.")
    result = {"status": "FAILED", "stage": args.stage}
    try:
        import torch

        if not torch.cuda.is_available() or not 1 <= args.repeats <= 30:
            raise RuntimeError("CUDA and 1..30 repeats are required.")
        for requirement in TRT_PACKAGES:
            name, version = requirement.split("==")
            if importlib.metadata.version(name) != version:
                raise RuntimeError(f"Unexpected TensorRT SDK version: {name}")
        inputs = json.loads((output / "inputs.json").read_text())
        if args.stage == "tiny":
            result = tiny_test(output, args.source)
        elif args.stage == "build":
            result = build_full(args.source)
        elif args.stage == "reference":
            result = reference_and_export(
                output, inputs, args.repeats, export=False, observer=memory_snapshot
            )
        elif args.stage == "infer":
            result = infer(output, inputs, args.repeats)
        else:
            result = downstream(output, inputs, args.baseline, candidate_backend="trt")
        result["lifetime_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception as exc:
        result.update(status="FAILED", error=str(exc), error_type=type(exc).__name__)
        traceback.print_exc()
    save_json(output / f"{args.stage}.json", result)
    print(f"{args.stage}: {result['status']}", flush=True)
    if result["status"] != "PASSED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
