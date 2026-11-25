"""Frozen BiRefNet Dynamic from verified local code and safetensors only."""

import json
from pathlib import Path

import numpy as np

from gardirop_ai_clothing.embeddings.marqo import resolve_device
from gardirop_ai_clothing.errors import (
    ClothingPipelineError,
    ImageProcessingError,
    InferenceError,
    ModelArtifactError,
)
from gardirop_ai_clothing.image.segmentation import BiRefNetSegmenter, validate_birefnet_input
from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256
from gardirop_ai_clothing.model_manifest import verified_model_files
from gardirop_ai_clothing.model_specs import (
    BIREFNET_FILE_SHA256,
    BIREFNET_MODEL_NAME,
    BIREFNET_REVISION,
    SEGMENTATION_PROFILE,
)

SUPPORT_SHA256 = {n: h for n, h in BIREFNET_FILE_SHA256.items() if n != "model.safetensors"}


class LocalBiRefNetSegmenter(BiRefNetSegmenter):
    revision = BIREFNET_REVISION
    preprocessing_profile = SEGMENTATION_PROFILE

    def __init__(self, runner, *, device: str):
        super().__init__(runner)
        self.device = device
        self.precision = "fp16" if device == "cuda" else "fp32"


def load_birefnet_model(manifest_path: str | Path, *, device: str = "auto"):
    """Shared frozen checkpoint construction for production and offline export."""
    files = verified_model_files(Path(manifest_path), BIREFNET_MODEL_NAME)
    folder = files["config.json"].absolute().parent
    for name, file in files.items():
        if (folder / name).resolve() != file.resolve():
            raise ModelArtifactError("BiRefNet files must share the prepared local folder.")
    for name, expected in SUPPORT_SHA256.items():
        if file_sha256(files[name]) != expected:
            raise ModelArtifactError(f"BiRefNet pinned support file SHA256 mismatch: {name}")
    config = json.loads(files["config.json"].read_text(encoding="utf-8"))
    if config.get("bb_pretrained") is not False or config.get("auto_map") != {
        "AutoConfig": "BiRefNet_config.BiRefNetConfig",
        "AutoModelForImageSegmentation": "birefnet.BiRefNet",
    }:
        raise ModelArtifactError("Unexpected BiRefNet local configuration.")
    try:
        import torch
        from transformers import AutoModelForImageSegmentation
    except ImportError as exc:
        raise ModelArtifactError("PyTorch and Transformers are required for BiRefNet.") from exc
    resolved = resolve_device(device, torch)
    dtype = torch.float16 if resolved == "cuda" else torch.float32
    try:
        model, info = AutoModelForImageSegmentation.from_pretrained(
            str(folder),
            trust_remote_code=True,
            local_files_only=True,
            use_safetensors=True,
            output_loading_info=True,
        )
        if any(
            info.get(key)
            for key in ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")
        ):
            raise ModelArtifactError("BiRefNet checkpoint did not fully match its architecture.")
        model.eval()
        model.requires_grad_(False)
        model.to(device=resolved, dtype=dtype)
    except Exception as exc:
        raise ModelArtifactError(
            "Frozen BiRefNet could not be initialized from local files."
        ) from exc

    return model, resolved


def load_birefnet_segmenter(
    manifest_path: str | Path, *, device: str = "auto"
) -> LocalBiRefNetSegmenter:
    model, resolved = load_birefnet_model(manifest_path, device=device)
    import torch

    dtype = torch.float16 if resolved == "cuda" else torch.float32

    def run(normalized_chw: np.ndarray) -> np.ndarray:
        validate_birefnet_input(normalized_chw)
        try:
            with torch.inference_mode(), torch.autocast(device_type=resolved, enabled=False):
                tensor = (
                    torch.from_numpy(normalized_chw).unsqueeze(0).to(device=resolved, dtype=dtype)
                )
                outputs = model(tensor)
                logits = outputs[-1] if isinstance(outputs, (tuple, list)) else outputs
                if not torch.is_tensor(logits) or logits.ndim != 4 or logits.shape[:2] != (1, 1):
                    raise ImageProcessingError("BiRefNet returned invalid logit dimensions.")
                return logits.detach().to(device="cpu", dtype=torch.float32).numpy()
        except ClothingPipelineError:
            raise
        except Exception as exc:
            raise InferenceError("BiRefNet image inference failed.") from exc

    return LocalBiRefNetSegmenter(run, device=resolved)
