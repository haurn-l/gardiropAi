"""BiRefNet Dynamic preprocessing, alpha generation and inference adapter."""

import math
import re
from collections.abc import Callable

import numpy as np
from PIL import Image

from gardirop_ai_clothing.errors import (
    ConfigurationError,
    ImageProcessingError,
)
from gardirop_ai_clothing.model_specs import BIREFNET_REPO, BIREFNET_REVISION

MODEL_REPO = BIREFNET_REPO
LONG_SIDE = 1024
INPUT_MULTIPLE = 64
MIN_INPUT_SIDE = 256

IMAGENET_MEAN = np.array(
    [0.485, 0.456, 0.406],
    dtype=np.float32,
).reshape(3, 1, 1)

IMAGENET_STD = np.array(
    [0.229, 0.224, 0.225],
    dtype=np.float32,
).reshape(3, 1, 1)

REVISION_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")

# Accepts normalized CHW input and returns segmentation logits.
LogitsRunner = Callable[[np.ndarray], np.ndarray]


def prepare_birefnet_canvas(image: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Match the evaluated Dynamic geometry; preserve ratio, pad with white."""
    if not isinstance(image, Image.Image) or image.mode != "RGB":
        raise ImageProcessingError("BiRefNet preprocessing requires an RGB PIL image.")
    if image.width < 1 or image.height < 1:
        raise ImageProcessingError("BiRefNet input dimensions must be positive.")
    scale = LONG_SIDE / max(image.size)
    width, height = [max(1, round(n * scale)) for n in image.size]
    canvas_size = (
        max(MIN_INPUT_SIDE, math.ceil(width / INPUT_MULTIPLE) * INPUT_MULTIPLE),
        max(MIN_INPUT_SIDE, math.ceil(height / INPUT_MULTIPLE) * INPUT_MULTIPLE),
    )
    left, top = (canvas_size[0] - width) // 2, (canvas_size[1] - height) // 2
    canvas = Image.new("RGB", canvas_size, "white")
    canvas.paste(image.resize((width, height), Image.Resampling.BILINEAR), (left, top))
    return canvas, (left, top, left + width, top + height)


def _normalize_canvas(canvas: Image.Image) -> np.ndarray:
    pixels = np.asarray(canvas, dtype=np.float32) / 255.0
    chw = pixels.transpose(2, 0, 1)
    return np.ascontiguousarray((chw - IMAGENET_MEAN) / IMAGENET_STD, dtype=np.float32)


def preprocess_birefnet(image: Image.Image) -> np.ndarray:
    """Aspect-preserving Dynamic canvas -> ImageNet CHW float32."""
    canvas, _ = prepare_birefnet_canvas(image)
    return _normalize_canvas(canvas)


def validate_birefnet_input(normalized_chw: np.ndarray) -> None:
    if (
        not isinstance(normalized_chw, np.ndarray)
        or normalized_chw.dtype != np.float32
        or normalized_chw.ndim != 3
        or normalized_chw.shape[0] != 3
        or any(
            n < MIN_INPUT_SIDE or n > LONG_SIDE or n % INPUT_MULTIPLE
            for n in normalized_chw.shape[1:]
        )
        or not np.isfinite(normalized_chw).all()
    ):
        raise ImageProcessingError(
            "BiRefNet requires finite float32 CHW input with 256..1024 sides divisible by 64."
        )


def logits_to_alpha(
    logits: np.ndarray,
    original_size: tuple[int, int],
) -> np.ndarray:
    """
    Convert raw segmentation logits into soft uint8 alpha.

    Sigmoid is applied before bilinear resizing, following
    the official inference sequence.
    """
    if len(original_size) != 2 or original_size[0] < 1 or original_size[1] < 1:
        raise ImageProcessingError("Invalid original image size.")

    try:
        values = np.asarray(logits, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise ImageProcessingError("Invalid segmentation logits.") from exc

    # Allow [1,1,H,W], [1,H,W] or [H,W].
    if values.ndim == 4 and values.shape[:2] == (1, 1):
        values = values[0, 0]
    elif values.ndim == 3 and values.shape[0] == 1:
        values = values[0]

    if values.ndim != 2 or not all(values.shape):
        raise ImageProcessingError("Expected single-channel segmentation logits.")

    if not np.isfinite(values).all():
        raise ImageProcessingError("Segmentation logits contain NaN or infinity.")

    # Clipping provides numerical stability for sigmoid.
    values = np.clip(values, -80.0, 80.0)
    probabilities = 1.0 / (1.0 + np.exp(-values))

    probability_image = Image.fromarray(probabilities.astype(np.float32))

    resized = probability_image.resize(
        original_size,
        resample=Image.Resampling.BILINEAR,
    )

    alpha = np.asarray(resized, dtype=np.float32)
    alpha = np.clip(alpha, 0.0, 1.0)

    return np.rint(alpha * 255.0).astype(np.uint8)


class BiRefNetSegmenter:
    """
    Segmentation orchestrator independent of the ML framework.

    A runner may use real PyTorch inference or a synthetic
    function in unit tests.
    """

    def __init__(self, runner: LogitsRunner) -> None:
        if not callable(runner):
            raise ConfigurationError("BiRefNet runner must be callable.")

        self._runner = runner

    def predict_alpha(self, image: Image.Image) -> np.ndarray:
        """Return a soft alpha mask at the original image size."""
        canvas, content_box = prepare_birefnet_canvas(image)
        logits = self._runner(_normalize_canvas(canvas))
        # Restore model canvas first, strip only known padding, then map to source pixels.
        # uint8 quantization at this point matches the approved Colab Dynamic path.
        canvas_alpha = Image.fromarray(logits_to_alpha(logits, original_size=canvas.size))
        restored = canvas_alpha.crop(content_box).resize(image.size, Image.Resampling.BILINEAR)
        return np.asarray(restored, dtype=np.uint8)


def load_huggingface_birefnet_runner(*, revision: str, device: str = "cpu") -> LogitsRunner:
    """Compatibility entrypoint using the same verified offline Dynamic loader.

    Downloading is a separate `make models-prepare` step. This path cannot
    select arbitrary revisions or bypass pinned support-file verification.
    """
    if not REVISION_PATTERN.fullmatch(revision):
        raise ConfigurationError("BiRefNet requires a pinned 40-character revision.")
    if revision != BIREFNET_REVISION:
        raise ConfigurationError("BiRefNet requires the selected Dynamic revision.")
    if device not in {"cpu", "cuda"}:
        raise ConfigurationError("BiRefNet device must be cpu or cuda.")
    # Lazy import avoids a cycle with the framework-independent orchestrator.
    from gardirop_ai_clothing.config import get_settings
    from gardirop_ai_clothing.image.birefnet_local import load_birefnet_segmenter

    return load_birefnet_segmenter(get_settings().model_manifest_path, device=device)._runner
