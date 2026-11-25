"""Read-only OPT-05 prerequisites; never load models or alter dependencies."""

import ast
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from PIL import Image

from gardirop_ai_clothing.embeddings.marqo import resolve_precision
from gardirop_ai_clothing.image.segmentation import prepare_birefnet_canvas
from gardirop_ai_clothing.model_manifest import verified_model_files
from gardirop_ai_clothing.model_specs import (
    BIREFNET_FILE_SHA256,
    BIREFNET_MODEL_NAME,
    BIREFNET_REVISION,
    SEGMENTATION_PROFILE,
)
from gardirop_ai_clothing.runtime_preparation import WARMUP_SIZES

PACKAGES = (
    "torch",
    "torchvision",
    "transformers",
    "open-clip-torch",
    "numpy",
    "Pillow",
    "onnx",
    "onnxscript",
    "onnx-ir",
    "onnxruntime",
    "onnxruntime-gpu",
    "tensorrt",
    "tensorrt-cu12",
    "tensorrt-cu13",
    "tensorrt-cu12-bindings",
    "tensorrt-cu13-bindings",
    "nvidia-cudnn-cu13",
    "nvidia-cudnn-cu12",
    "nvidia-cublas-cu13",
    "nvidia-cublas-cu12",
)
TORCH_PROBE = """
import json
import torch
available = torch.cuda.is_available()
data = {"version": torch.__version__, "cuda_runtime": torch.version.cuda,
        "cudnn_version": torch.backends.cudnn.version(), "cuda_available": available,
        "devices": [], "neural_inference": False}
if available:
    for index in range(torch.cuda.device_count()):
        prop = torch.cuda.get_device_properties(index)
        data["devices"].append({"index": index, "name": prop.name,
            "capability": [prop.major, prop.minor],
            "total_memory_mib": prop.total_memory / 1024**2})
print(json.dumps(data))
"""
ORT_PROBE = """
import json
import torch
import onnxruntime as ort
print(json.dumps({"version": ort.__version__, "available_providers": ort.get_available_providers(),
    "cuda_session_tested": False, "neural_inference": False}))
"""
TRT_PROBE = """
import json
import tensorrt as trt
print(json.dumps({"version": trt.__version__, "engine_built": False}))
"""


def package_versions():
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def probe_json(code, *, timeout=45):
    """Bound native imports to a child; never expose environment or raw native logs."""
    env = os.environ.copy()
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONDONTWRITEBYTECODE="1")
    try:
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=timeout, env=env
        )
        if result.returncode != 0:
            return {"probe_status": "FAILED", "exit_code": result.returncode}
        value = json.loads(result.stdout.strip().splitlines()[-1])
        if not isinstance(value, dict):
            raise ValueError("Expected an object.")
        return {"probe_status": "OK", **value}
    except subprocess.TimeoutExpired:
        return {"probe_status": "TIMEOUT", "timeout_seconds": timeout}
    except (OSError, ValueError, IndexError):
        return {"probe_status": "FAILED", "reason": "Could not run/parse the isolated probe."}


def shape_cast_sites(source):
    """Flag Python integer conversion around tensor shapes; not an export verdict."""
    sites = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id not in {"int", "float", "bool"}:
            continue
        if any(
            isinstance(child, ast.Attribute) and child.attr in {"shape", "size"}
            for child in ast.walk(node)
        ):
            sites.append({"line": node.lineno, "conversion": node.func.id})
    return sorted(sites, key=lambda item: item["line"])


def source_summary(manifest_path):
    # Integrity check only: this hashes bytes, without importing checkpoint source.
    files = verified_model_files(Path(manifest_path), BIREFNET_MODEL_NAME)
    for name, digest in BIREFNET_FILE_SHA256.items():
        if name not in files:
            raise ValueError(f"Missing pinned BiRefNet file: {name}")
        if name != "model.safetensors":
            if hashlib.sha256(files[name].read_bytes()).hexdigest() != digest:
                raise ValueError(f"Pinned source mismatch: {name}")
    source = files["birefnet.py"].read_text(encoding="utf-8")
    return {
        "model": BIREFNET_MODEL_NAME,
        "revision": BIREFNET_REVISION,
        "preprocessing_profile": SEGMENTATION_PROFILE,
        "artifact_integrity_verified": True,
        "weights_bytes": files["model.safetensors"].stat().st_size,
        "source_python_shape_casts": shape_cast_sites(source),
        "exportability_established": False,
        "source_modified": False,
    }


def demo_shapes(root):
    cases, shapes = [], set()
    inputs = root / "outputs" / "step07_completion" / "inputs" / "generated"
    for item in ("tshirt", "jeans", "jacket"):
        for view in ("front", "back"):
            path = inputs / f"{item}_{view}.png"
            with Image.open(path) as original:
                if original.width * original.height > 24_000_000:
                    raise ValueError("Demo input exceeds the project pixel limit.")
                source_size = original.size
                # Uses the real preprocessing function, not an approximate formula.
                canvas, box = prepare_birefnet_canvas(original.convert("RGB"))
            width, height = canvas.size
            shape = (1, 3, height, width)
            shapes.add(shape)
            cases.append(
                {
                    "file": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "source_size_wh": list(source_size),
                    "input_nchw": list(shape),
                    "content_box": list(box),
                }
            )
    return {
        "cases": cases,
        "observed_shapes_nchw": [list(value) for value in sorted(shapes)],
        "warmup_shapes_nchw": [[1, 3, height, width] for width, height in WARMUP_SIZES],
        "batch_size": 1,
        "valid_side_multiple": 64,
        "valid_min_side": 256,
        "long_side": 1024,
        "dynamic_shape_validated": False,
        "plan": "Keep aspect geometry. Validate each actual shape; do not assume traced axes are dynamic.",
    }


def visible_servers():
    ports = []
    for port in (7861, 8001, 8002):
        with socket.socket() as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                ports.append(port)
    return ports


def collect_report(settings, root, *, progress=print):
    versions = package_versions()
    report = {
        "stage": "OPT-05A_ENVIRONMENT_AND_EXPORT_PREFLIGHT",
        "status": "ENVIRONMENT_RECORDED",
        "training_run": False,
        "neural_inference": False,
        "dependencies_installed": False,
        "model_exported": False,
        "engine_built": False,
        "backend_connected": False,
        "python": platform.python_version(),
        "platform": platform.system(),
        "machine": platform.machine(),
        "python_executable": sys.executable,
        "packages": versions,
        "disk_free_gib": shutil.disk_usage(root).free / 1024**3,
        "configured_device": settings.device,
        "configured_marqo_precision": settings.marqo_precision,
        "listening_local_ports": visible_servers(),
        "errors": [],
        "notes": [],
    }
    progress("PyTorch/CUDA/cuDNN bilgisi okunuyor; model yüklenmeyecek...", flush=True)
    report["torch"] = probe_json(TORCH_PROBE)
    torch = report["torch"]
    if torch.get("probe_status") != "OK":
        report["errors"].append("PyTorch/CUDA environment probe failed.")
    elif not torch.get("cuda_available"):
        report["errors"].append("CUDA is unavailable; GPU optimization cannot be measured.")
    else:
        device = "cpu" if settings.device == "cpu" else "cuda"
        report["effective_marqo_precision"] = resolve_precision(settings.marqo_precision, device)
        if device != "cuda" or report["effective_marqo_precision"] != "fp16":
            report["errors"].append("Active settings override the accepted CUDA FP16 policy.")
    for key, code, present in (
        ("onnxruntime", ORT_PROBE, versions["onnxruntime-gpu"] or versions["onnxruntime"]),
        ("tensorrt", TRT_PROBE, any(versions[n] for n in PACKAGES if n.startswith("tensorrt"))),
    ):
        if present:
            progress(f"Kurulu {key} paketi ayrı süreçte kontrol ediliyor...", flush=True)
            report[key] = probe_json(code)
        else:
            report[key] = {"probe_status": "NOT_INSTALLED"}
    try:
        progress(
            "Sabitlenmiş BiRefNet dosyaları doğrulanıyor; kod çalıştırılmayacak...", flush=True
        )
        report["segmentation"] = source_summary(settings.model_manifest_path)
    except Exception as exc:
        report["errors"].append(f"BiRefNet artifacts could not be verified: {type(exc).__name__}")
    try:
        report["shapes"] = demo_shapes(root)
    except Exception as exc:
        report["errors"].append(f"Demo input geometry could not be read: {type(exc).__name__}")
    if versions["onnxruntime"] and versions["onnxruntime-gpu"]:
        report["notes"].append(
            "CPU and GPU ORT distributions coexist; use a clean isolated environment."
        )
    missing = [n for n in ("onnx", "onnxscript", "onnxruntime-gpu") if not versions[n]]
    report["missing_export_runtime_packages"] = missing
    report["tools"] = {name: shutil.which(name) for name in ("uv", "nvcc", "trtexec")}
    report["references"] = [
        "https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html",
        "https://docs.pytorch.org/docs/2.12/onnx.html",
        "https://docs.nvidia.com/deeplearning/tensorrt/latest/installing-tensorrt/installing.html",
    ]
    report["notes"].extend(
        [
            "Missing ONNX/TensorRT packages are expected here; this command does not install anything.",
            "Provider enumeration does not prove that a CUDA inference session can run.",
            "PyTorch CUDA runtime and nvidia-smi CUDA capability are different measurements.",
            "OPT-05B uses an isolated environment; base Torch, driver and uv.lock stay unchanged.",
            "Export last segmentation logits only; keep sigmoid/alpha/crop/white WebP code unchanged.",
            "Compare PyTorch FP16 vs ORT CUDA, then TensorRT FP16; do not change production segmenter yet.",
        ]
    )
    executable = shutil.which("nvidia-smi")
    report["nvidia_smi"] = {"available": executable is not None}
    if executable:
        try:
            result = subprocess.run(
                [
                    executable,
                    "--query-gpu=index,name,driver_version,memory.total,memory.used",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            report["nvidia_smi"].update(exit_code=result.returncode)
            if result.returncode == 0:
                report["nvidia_smi"]["devices_csv"] = result.stdout.strip().splitlines()
        except (OSError, subprocess.TimeoutExpired):
            report["nvidia_smi"]["probe_status"] = "FAILED"
    if report["errors"]:
        report["status"] = "ACTION_REQUIRED"
    return report
