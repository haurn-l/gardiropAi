"""Opt-in cached TensorRT segmenter with an eagerly loaded PyTorch shape fallback."""

import importlib.metadata
import json
import shutil
import subprocess
from pathlib import Path

from gardirop_ai_clothing.errors import ConfigurationError, InferenceError, ModelArtifactError
from gardirop_ai_clothing.image.birefnet_local import (
    LocalBiRefNetSegmenter,
    load_birefnet_segmenter,
)
from gardirop_ai_clothing.image.segmentation import validate_birefnet_input
from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256
from gardirop_ai_clothing.model_specs import BIREFNET_REVISION, SEGMENTATION_PROFILE
from gardirop_ai_clothing.onnx_experiment import INPUT_SHAPE, sha256
from gardirop_ai_clothing.tensorrt_experiment import (
    BUILD_POLICY,
    TRT_PACKAGES,
    TensorRTRunner,
    cache_key,
    native_trt,
)


def current_device_identity():
    """Match the OPT-05C cache fingerprint without importing its build worker."""
    import torch

    if not torch.cuda.is_available():
        raise ModelArtifactError("The selected TensorRT backend requires CUDA.")
    for requirement in TRT_PACKAGES:
        name, version = requirement.split("==")
        if importlib.metadata.version(name) != version:
            raise ModelArtifactError(
                f"TensorRT SDK version differs from the accepted engine: {name}"
            )
    prop = torch.cuda.get_device_properties(0)
    smi = shutil.which("nvidia-smi")
    if not smi:
        raise ModelArtifactError(
            "nvidia-smi is required to verify the accepted GPU/driver identity."
        )
    query = subprocess.check_output(
        [smi, "--query-gpu=uuid,driver_version", "--format=csv,noheader"], text=True, timeout=10
    )
    return {
        "name": prop.name,
        "compute_capability": [prop.major, prop.minor],
        "total_memory": prop.total_memory,
        "torch_cuda": torch.version.cuda,
        "torch": torch.__version__,
        "tensorrt_binding": native_trt().__version__,
        "sdk_packages": {
            p.split("==")[0]: importlib.metadata.version(p.split("==")[0]) for p in TRT_PACKAGES
        },
        "gpu_driver_inventory": query.strip().splitlines(),
    }


def verified_engine(root: Path, run: Path, device_identity: dict):
    """Verify a locally generated plan; checksums are not third-party signatures.

    No build, conversion, download or engine search is performed here.
    """
    root, run = root.resolve(), run.expanduser().resolve()
    allowed_runs = (root / "outputs/tensorrt_compare").resolve()
    if (
        not allowed_runs.is_relative_to(root)
        or run == allowed_runs
        or not run.is_relative_to(allowed_runs)
    ):
        raise ModelArtifactError(
            "Select an accepted local OPT-05C run inside outputs/tensorrt_compare."
        )
    report = json.loads((run / "report.json").read_text())
    if (
        report.get("stage") != "OPT-05C"
        or report.get("status") != "DEMO_GATES_PASSED_REVIEW_REQUIRED"
        or report.get("all_demo_gates_passed") is not True
        or report.get("input_shape_nchw") != list(INPUT_SHAPE)
    ):
        raise ModelArtifactError("The selected TensorRT experiment has not passed its demo gates.")
    for stage in ("tiny", "build", "reference", "infer", "downstream"):
        if report["steps"][stage].get("status") != "PASSED":
            raise ModelArtifactError("An accepted TensorRT experiment stage is missing.")
    if (
        report["steps"]["infer"].get("all_image_gates_passed") is not True
        or report["steps"]["downstream"].get("all_downstream_gates_passed") is not True
    ):
        raise ModelArtifactError("TensorRT image/downstream quality was not accepted.")
    build = json.loads((run / "build.json").read_text())
    if build.get("status") != "PASSED" or build["engine"] != report["steps"]["build"]["engine"]:
        raise ModelArtifactError("TensorRT build record differs from its accepted report.")
    plan = Path(build["plan"]).resolve()
    allowed = (root / "outputs/tensorrt_engines").resolve()
    if (
        not allowed.is_relative_to(root)
        or plan.name != "model.plan"
        or not plan.is_relative_to(allowed)
    ):
        raise ModelArtifactError("TensorRT plan is outside the trusted local engine cache.")
    record = json.loads((plan.parent / "engine.json").read_text())
    for key, value in record.items():
        if build["engine"].get(key) != value:
            raise ModelArtifactError("TensorRT engine cache and experiment records differ.")
    identity = record["identity"]
    if (
        identity["device"] != device_identity
        or identity["build"] != BUILD_POLICY
        or identity["onnx_sha256"] != report["source_onnx_sha256"]
        or identity["adapter_sha256"]
        != sha256(root / "src/gardirop_ai_clothing/tensorrt_experiment.py")
        or identity["builder_sha256"] != sha256(root / "scripts/tensorrt_birefnet_worker.py")
        or record["cache_key"] != cache_key(identity)
        or plan.parent.name != record["cache_key"]
    ):
        raise ModelArtifactError("TensorRT engine fingerprint differs from this model/runtime.")
    source = Path(report["source_onnx_run"]).resolve()
    onnx_root = (root / "outputs/onnx_compare").resolve()
    if not onnx_root.is_relative_to(root) or not source.is_relative_to(onnx_root):
        raise ModelArtifactError("Unexpected accepted ONNX source path.")
    artifact = json.loads((source / "artifact.json").read_text())
    if (
        artifact.get("revision") != BIREFNET_REVISION
        or artifact.get("preprocessing_profile") != SEGMENTATION_PROFILE
        or artifact.get("precision") != "fp16"
        or artifact.get("input_nchw") != list(INPUT_SHAPE)
        or artifact.get("sha256") != identity["onnx_sha256"]
    ):
        raise ModelArtifactError("TensorRT source does not match the pinned Dynamic model/profile.")
    if plan.stat().st_size != record["plan_bytes"] or file_sha256(plan) != record["plan_sha256"]:
        raise ModelArtifactError("TensorRT plan checksum/length mismatch.")
    return plan, record


class RoutedBiRefNetSegmenter(LocalBiRefNetSegmenter):
    """The ModelManager GPU slot serializes both eagerly loaded execution paths."""

    backend = "tensorrt_with_pytorch_fallback"

    def __init__(self, native_runner, fallback, *, plan_sha256):
        if fallback.device != "cuda" or fallback.precision != "fp16":
            raise ModelArtifactError(
                "TensorRT shape fallback must be the existing CUDA FP16 model."
            )
        self.native_runner, self.fallback = native_runner, fallback
        self.runtime_details = {
            "backend": self.backend,
            "tensorRTInputNCHW": list(INPUT_SHAPE),
            "engineSha256": plan_sha256,
            "pytorchFallbackLoaded": True,
            "engineBuildAllowed": False,
            "forwardCounts": {"tensorrt": 0, "pytorch": 0},
        }
        super().__init__(self._dispatch, device="cuda")

    @staticmethod
    def backend_for_shape(shape):
        return "tensorrt" if tuple(shape) == INPUT_SHAPE else "pytorch"

    def _dispatch(self, chw):
        validate_birefnet_input(chw)
        backend = self.backend_for_shape((1, *chw.shape))
        try:
            result = (
                self.native_runner(chw) if backend == "tensorrt" else self.fallback._runner(chw)
            )
        except Exception as exc:
            raise InferenceError(
                f"BiRefNet {backend} inference failed; no automatic retry was performed."
            ) from exc
        self.runtime_details["forwardCounts"][backend] += 1
        return result


def load_configured_segmenter(settings):
    if settings.segmentation_backend == "pytorch":
        return load_birefnet_segmenter(settings.model_manifest_path, device=settings.device)
    if settings.device == "cpu":
        raise ConfigurationError("TensorRT mode requires CUDA; use the PyTorch backend on CPU.")
    if settings.tensorrt_run is None:
        raise ConfigurationError("TensorRT mode requires an accepted local tensorrt_run.")
    try:
        from gardirop_ai_clothing.config import PROJECT_ROOT

        plan, record = verified_engine(
            PROJECT_ROOT, settings.tensorrt_run, current_device_identity()
        )
        native = TensorRTRunner(plan, {"pixels": INPUT_SHAPE})
        if tuple(native.buffers[native.output_name].shape) != (1, 1, 1024, 704):
            raise ModelArtifactError("Unexpected TensorRT segmentation output shape.")
        fallback = load_birefnet_segmenter(settings.model_manifest_path, device="cuda")
        return RoutedBiRefNetSegmenter(native, fallback, plan_sha256=record["plan_sha256"])
    except (ConfigurationError, ModelArtifactError):
        raise
    except Exception as exc:
        raise ModelArtifactError(
            "Accepted TensorRT runtime could not be loaded. No engine was built."
        ) from exc
