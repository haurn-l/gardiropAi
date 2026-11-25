"""Opt-in profiling factory. The regular production app is never patched."""

import json
import os
import resource
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from gardirop_ai_clothing.app import create_app
from gardirop_ai_clothing.config import PROJECT_ROOT, get_settings
from gardirop_ai_clothing.embeddings.marqo import MARQO_MODEL_NAME
from gardirop_ai_clothing.errors import ConfigurationError
from gardirop_ai_clothing.image.birefnet_local import BIREFNET_MODEL_NAME
from gardirop_ai_clothing.image_profiling import attach_image_stage_profiling
from gardirop_ai_clothing.jobs import create_draft_service
from gardirop_ai_clothing.runtime_preparation import prepare_runtime


def memory_snapshot():
    torch = sys.modules.get("torch")
    rss = None
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                rss = int(line.split()[1]) / 1024
                break
    except OSError:
        pass
    result = {
        "rss_mib": rss,
        "lifetime_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "cuda_initialized": torch is not None and torch.cuda.is_initialized(),
    }
    if result["cuda_initialized"]:
        result.update(
            gpu_name=torch.cuda.get_device_name(),
            gpu_total_mib=torch.cuda.get_device_properties(0).total_memory / 1024**2,
            allocated_mib=torch.cuda.memory_allocated() / 1024**2,
            reserved_mib=torch.cuda.memory_reserved() / 1024**2,
            peak_allocated_mib=torch.cuda.max_memory_allocated() / 1024**2,
            peak_reserved_mib=torch.cuda.max_memory_reserved() / 1024**2,
        )
    return result


def gpu_process_sample():
    """Sample all CUDA allocations of this server PID, including TensorRT (not a peak)."""
    torch = sys.modules.get("torch")
    if torch is None or not torch.cuda.is_initialized():
        return None
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,used_gpu_memory",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode != 0:
            return None
        rows = [
            float(line.split(",")[1].strip())
            for line in proc.stdout.splitlines()
            if line.split(",")[0].strip() == str(os.getpid())
        ]
        return sum(rows) if rows else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


class Recorder:
    def __init__(self, path):
        self.path, self.lock = path, threading.Lock()

    def emit(self, event):
        event.update(pid=os.getpid(), memory=memory_snapshot())
        if event["event"] in {"runtime_ready", "shutdown"}:
            event["memory"]["gpu_process_sample_mib"] = gpu_process_sample()
        with self.lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, allow_nan=False) + "\n")

    @contextmanager
    def span(self, name, **details):
        start = time.perf_counter_ns()
        success = False
        try:
            yield
            success = True
        finally:
            torch = sys.modules.get("torch")
            if torch is not None and torch.cuda.is_initialized():
                torch.cuda.synchronize()
            end = time.perf_counter_ns()
            self.emit(
                {
                    "event": name,
                    "start_ns": start,
                    "end_ns": end,
                    "elapsed_ms": (end - start) / 1e6,
                    "success": success,
                    **details,
                }
            )


def attach_profiling(service, recorder):
    analysis = service.analysis
    manager = analysis.manager
    get_model = manager.get_model

    def profiled_get_model(name):
        if name in manager.loaded_models:
            return get_model(name)
        start = time.perf_counter_ns()
        model = get_model(name)
        torch = sys.modules.get("torch")
        if torch is not None and torch.cuda.is_initialized():
            torch.cuda.synchronize()
        end = time.perf_counter_ns()
        precision = getattr(model, "precision", None)
        if precision is None and hasattr(model, "weights"):
            precision = str(model.weights.dtype)
        recorder.emit(
            {
                "event": "model_load",
                "model": name,
                "device": getattr(model, "device", "cpu"),
                "precision": precision,
                "runtime_details": getattr(model, "runtime_details", {}),
                "torch": getattr(torch, "__version__", None),
                "cuda_runtime": getattr(getattr(torch, "version", None), "cuda", None),
                "start_ns": start,
                "end_ns": end,
                "elapsed_ms": (end - start) / 1e6,
            }
        )
        if name == BIREFNET_MODEL_NAME:
            original_runner = model._runner

            def run_segmenter(*args, **kwargs):
                shape = (1, *args[0].shape)
                backend = (
                    model.backend_for_shape(shape)
                    if hasattr(model, "backend_for_shape")
                    else "pytorch"
                )
                with recorder.span(
                    "segmentation_forward_and_transfer", backend=backend, input_nchw=shape
                ):
                    return original_runner(*args, **kwargs)

            model._runner = run_segmenter
        if name == MARQO_MODEL_NAME:
            original_encode = model.encode

            def encode(image):
                with recorder.span("marqo_encode"):
                    return original_encode(image)

            model.encode = encode
        return model

    manager.get_model = profiled_get_model
    original_prepare = analysis.prepare_view
    original_image = analysis.images.prepare_photo
    original_finish = analysis.finish_pair

    def image_prepare(*args, **kwargs):
        with recorder.span("image_preparation"):
            return original_image(*args, **kwargs)

    def prepare_view(*args, **kwargs):
        view = str(kwargs["view_type"])
        torch = sys.modules.get("torch")
        if view == "FRONT" and torch is not None and torch.cuda.is_initialized():
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
        with recorder.span("prepare_view", view=view):
            return original_prepare(*args, **kwargs)

    def finish_pair(*args, **kwargs):
        with recorder.span("fusion_lr_attributes"):
            return original_finish(*args, **kwargs)

    analysis.images.prepare_photo = image_prepare
    analysis.prepare_view = prepare_view
    analysis.finish_pair = finish_pair

    for name in ("save_view", "load_view", "save_result"):
        original = getattr(service.repository, name)

        def wrap(original_method, event_name):
            def run(*args, **kwargs):
                with recorder.span(event_name):
                    return original_method(*args, **kwargs)

            return run

        setattr(service.repository, name, wrap(original, name))
    original_close = service.close
    restore_image_stages = attach_image_stage_profiling(analysis.images, recorder)

    def close(*args, **kwargs):
        success = False
        try:
            result = original_close(*args, **kwargs)
            success = True
            return result
        finally:
            restore_image_stages()
            now = time.perf_counter_ns()
            recorder.emit({"event": "shutdown", "start_ns": now, "end_ns": now, "success": success})

    service.close = close
    now = time.perf_counter_ns()
    torch = sys.modules.get("torch")
    recorder.emit(
        {
            "event": "worker_created",
            "start_ns": now,
            "end_ns": now,
            "loaded_models": list(manager.loaded_models),
            "compact_storage": service.repository.compact,
            "include_transparent_webp": analysis.images.include_transparent_webp,
            "torch": getattr(torch, "__version__", None),
        }
    )
    return service


def create_profiled_app():
    settings = get_settings()
    if settings.device != "cuda":
        raise ConfigurationError("CUDA is required for this GPU baseline; no CPU fallback.")
    log_path = Path(os.environ["GARDROPAI_BENCHMARK_LOG"]).resolve()
    allowed = (PROJECT_ROOT / "outputs" / "api_baseline").resolve()
    if not log_path.is_relative_to(allowed):
        raise ConfigurationError("Benchmark log must be inside outputs/api_baseline.")
    recorder = Recorder(log_path)

    def factory(configured):
        service = create_draft_service(configured)
        try:
            return attach_profiling(service, recorder)
        except BaseException:
            service.close()
            raise

    def prepare(service, configured):
        with recorder.span("startup_preparation"):
            result = prepare_runtime(service, configured)
        now = time.perf_counter_ns()
        recorder.emit({"event": "runtime_ready", "start_ns": now, "end_ns": now, "report": result})
        return result

    return create_app(
        processing_enabled=True,
        settings=settings,
        service_factory=factory,
        runtime_preparer=prepare,
    )
