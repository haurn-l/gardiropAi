"""Lazy frozen Marqo image encoding from verified local files."""

import hmac
import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
from PIL import Image

from gardirop_ai_clothing.contracts import NORM_ABS_TOLERANCE, VIEW_EMBEDDING_DIMENSION
from gardirop_ai_clothing.errors import (
    ClothingPipelineError,
    ConfigurationError,
    ImageProcessingError,
    InferenceError,
    ModelArtifactError,
)
from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256
from gardirop_ai_clothing.model_manager import ModelManager
from gardirop_ai_clothing.model_manifest import verified_model_files
from gardirop_ai_clothing.model_specs import MARQO_CONFIG_SHA256, MARQO_IMAGE_SIZE, MARQO_REVISION

MARQO_MODEL_NAME = "marqo_fashionsiglip"
ImageRunner = Callable[[Image.Image], np.ndarray]


def validate_image(image: Image.Image) -> None:
    if not isinstance(image, Image.Image) or image.mode != "RGB":
        raise ImageProcessingError("Marqo requires a prepared RGB PIL image.")
    if image.width < 1 or image.height < 1:
        raise ImageProcessingError("Marqo image dimensions must be positive.")


def normalize_view_embedding(raw: np.ndarray) -> np.ndarray:
    array = np.asarray(raw)
    if array.shape != (VIEW_EMBEDDING_DIMENSION,) or array.dtype.kind != "f":
        raise InferenceError("Marqo must return one floating-point 768D vector.")
    if not np.isfinite(array).all():
        raise InferenceError("Marqo returned NaN or Infinity.")
    vector = array.astype(np.float64)
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm <= 0:
        raise InferenceError("Marqo returned an invalid vector norm.")
    result = np.array(vector / norm, dtype=np.float32, order="C", copy=True)
    if not np.isclose(np.linalg.norm(result), 1.0, atol=NORM_ABS_TOLERANCE, rtol=0):
        raise InferenceError("Marqo output normalization failed.")
    result.setflags(write=False)
    return result


class MarqoEncoder:
    """Low-level encoder. The service below provides shared execution coordination."""

    revision = MARQO_REVISION
    input_size = MARQO_IMAGE_SIZE
    precision = "fp32"

    def __init__(
        self,
        runner: ImageRunner,
        *,
        device: str,
        text_runner=None,
        precision: str = "fp32",
        runtime_details: dict | None = None,
    ) -> None:
        if not callable(runner) or device not in {"cpu", "cuda"}:
            raise ConfigurationError("Invalid Marqo runner or resolved device.")
        validate_precision(precision, device)
        self.precision = precision
        self.runtime_details = dict(runtime_details or {})
        self._runner = runner
        self.device = device
        self.text_runner = text_runner

    def encode(self, image: Image.Image) -> np.ndarray:
        validate_image(image)
        try:
            raw = self._runner(image)
        except ClothingPipelineError:
            raise
        except Exception as exc:
            raise InferenceError("Marqo image inference failed.") from exc
        return normalize_view_embedding(raw)


def resolve_device(requested: str, torch_module) -> str:
    if requested not in {"auto", "cpu", "cuda"}:
        raise ConfigurationError("Marqo device must be auto, cpu or cuda.")
    if requested == "cpu":
        return "cpu"
    available = torch_module.cuda.is_available()
    if requested == "cuda" and not available:
        raise ModelArtifactError("CUDA was requested but is unavailable; no CPU fallback was used.")
    return "cuda" if available else "cpu"


def validate_precision(precision: str, device: str):
    if precision not in {"fp32", "fp16"}:
        raise ConfigurationError("Marqo precision must be fp32 or fp16.")
    if precision == "fp16" and device != "cuda":
        raise ConfigurationError("Marqo FP16 requires CUDA; no precision/CPU fallback is allowed.")


def resolve_precision(requested: str, resolved_device: str) -> str:
    """Resolve the configured policy; explicit FP16 still requires CUDA."""
    if resolved_device not in {"cpu", "cuda"}:
        raise ConfigurationError("Precision requires a resolved cpu/cuda device.")
    if requested == "auto":
        return "fp16" if resolved_device == "cuda" else "fp32"
    validate_precision(requested, resolved_device)
    return requested


def model_runtime_details(model, precision):
    parameters = {}
    for value in model.parameters():
        name = str(value.dtype)
        parameters[name] = parameters.get(name, 0) + value.numel() * value.element_size()
    return {
        "precision_policy": "open_clip_fp16_mixed" if precision == "fp16" else "fp32",
        "parameter_mib": sum(parameters.values()) / 1024**2,
        "parameter_mib_by_dtype": {name: size / 1024**2 for name, size in parameters.items()},
        "buffer_mib": sum(value.numel() * value.element_size() for value in model.buffers())
        / 1024**2,
    }


def load_marqo_encoder(
    manifest_path: str | Path, *, device: str = "auto", precision: str = "fp32"
) -> MarqoEncoder:
    """Load the exact checkpoint once; no Hub calls, tokenizer, or model fitting."""
    if precision not in {"auto", "fp32", "fp16"}:
        raise ConfigurationError("Marqo precision must be auto, fp32 or fp16.")
    if device == "cpu":
        resolve_precision(precision, "cpu")
    files = verified_model_files(Path(manifest_path), MARQO_MODEL_NAME)
    config_path = files["open_clip_config.json"]
    if not hmac.compare_digest(file_sha256(config_path), MARQO_CONFIG_SHA256):
        raise ModelArtifactError("Marqo published configuration SHA256 mismatch.")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if (
        config.get("model_cfg", {}).get("embed_dim") != VIEW_EMBEDDING_DIMENSION
        or config["model_cfg"].get("vision_cfg", {}).get("image_size") != MARQO_IMAGE_SIZE
    ):
        raise ModelArtifactError("Unexpected Marqo feature dimension or input size.")
    # OpenCLIP's pinned local-dir loader chooses this exact preferred filename.
    # Reject a manifest pointing elsewhere before invoking the factory.
    if (config_path.parent / "open_clip_model.safetensors").resolve() != files[
        "open_clip_model.safetensors"
    ].resolve():
        raise ModelArtifactError(
            "Marqo config and checkpoint must share the prepared local folder."
        )
    if config_path.name != "open_clip_config.json":
        raise ModelArtifactError("Unexpected local Marqo config filename.")
    try:
        import open_clip
        import torch
    except ImportError as exc:
        raise ModelArtifactError("PyTorch and OpenCLIP must be installed.") from exc
    resolved = resolve_device(device, torch)
    precision = resolve_precision(precision, resolved)
    input_dtype = torch.float16 if precision == "fp16" else torch.float32
    try:
        # OpenCLIP 3.3 loads the verified preferred checkpoint with strict=True.
        # require_pretrained prevents returning an encoder with random weights.
        model, _, transform = open_clip.create_model_and_transforms(
            f"local-dir:{config_path.absolute().parent}",
            load_weights=True,
            require_pretrained=True,
            weights_only=True,
            precision=precision,
            device="cpu",
            pretrained_image=False,
            pretrained_text=False,
        )
        model.eval()
        model.requires_grad_(False)
        if precision == "fp32":
            model.to(device=resolved, dtype=torch.float32)
        else:
            # OpenCLIP constructs the mixed FP16 policy, preserving LayerNormFp32.
            # A blanket dtype conversion here would undo that policy.
            model.to(device=resolved)
    except Exception as exc:
        raise ModelArtifactError("Frozen Marqo could not be initialized from local files.") from exc

    def run(image: Image.Image) -> np.ndarray:
        with torch.inference_mode(), torch.autocast(device_type=resolved, enabled=False):
            tensor = transform(image)
            if tensor.shape != (3, MARQO_IMAGE_SIZE, MARQO_IMAGE_SIZE):
                raise InferenceError("Published Marqo transform returned an unexpected shape.")
            tensor = tensor.unsqueeze(0).to(device=resolved, dtype=input_dtype)
            features = model.encode_image(tensor, normalize=False)
            if features.shape != (1, VIEW_EMBEDDING_DIMENSION):
                raise InferenceError("Marqo returned an unexpected feature shape.")
            return features.detach().to(device="cpu", dtype=torch.float32).numpy()[0]

    def run_text(prompts, tokenizer_directory):
        from open_clip.tokenizer import HFTokenizer

        tokenizer = HFTokenizer(
            str(tokenizer_directory), context_length=64, clean="canonicalize", local_files_only=True
        )
        with torch.inference_mode(), torch.autocast(device_type=resolved, enabled=False):
            tokens = tokenizer(prompts).to(device=resolved)
            vectors = model.encode_text(tokens, normalize=True)
            return vectors.detach().to(device="cpu", dtype=torch.float32).numpy()

    return MarqoEncoder(
        run,
        device=resolved,
        text_runner=run_text,
        precision=precision,
        runtime_details=model_runtime_details(model, precision),
    )


class MarqoEmbeddingService:
    """Create once per application; share its manager with later pipeline stages."""

    def __init__(self, manager: ModelManager) -> None:
        self.manager = manager

    def encode(self, image: Image.Image, *, timeout_seconds: float | None = None) -> np.ndarray:
        validate_image(image)
        # Includes first-load initialization, so GPU allocation is also coordinated.
        with self.manager.gpu_slot(timeout_seconds=timeout_seconds):
            encoder = self.manager.get_model(MARQO_MODEL_NAME)
            if not isinstance(encoder, MarqoEncoder):
                raise InferenceError("Registered Marqo model is not a MarqoEncoder.")
            return encoder.encode(image)


def create_marqo_service(
    manifest_path: str | Path,
    *,
    device: str = "auto",
    max_concurrent_gpu_jobs: int = 1,
    precision: str = "fp32",
) -> MarqoEmbeddingService:
    path = Path(manifest_path).expanduser().resolve()
    manager = ModelManager(
        {MARQO_MODEL_NAME: lambda: load_marqo_encoder(path, device=device, precision=precision)},
        max_concurrent_gpu_jobs=max_concurrent_gpu_jobs,
    )
    return MarqoEmbeddingService(manager)
