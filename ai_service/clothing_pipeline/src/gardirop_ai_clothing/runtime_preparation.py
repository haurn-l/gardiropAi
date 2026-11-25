"""Load once and exercise real neural adapters before accepting photo requests."""

import time

import numpy as np
from PIL import Image, ImageDraw

from gardirop_ai_clothing.contracts import MainCategory
from gardirop_ai_clothing.embeddings.marqo import MARQO_MODEL_NAME
from gardirop_ai_clothing.image.birefnet_local import BIREFNET_MODEL_NAME
from gardirop_ai_clothing.labeling.artifacts import CLASSIFIER_MODEL_NAME
from gardirop_ai_clothing.startup_memory import release_warmup_cache

WARMUP_SIZES = ((1024, 1024), (768, 1024), (1024, 768), (704, 1024), (1024, 704))


def prepare_runtime(service, settings):
    previous = getattr(service, "runtime_preparation", None)
    if previous is not None and previous.get("status") == "READY":
        return previous
    started = time.perf_counter()
    analysis = service.analysis
    manager = analysis.manager
    service.runtime_preparation = {"status": "PREPARING"}
    try:
        with manager.gpu_slot(timeout_seconds=settings.draft_queue_timeout_seconds):
            segmenter = manager.get_model(BIREFNET_MODEL_NAME)
            encoder = manager.get_model(MARQO_MODEL_NAME)
            head = manager.get_model(CLASSIFIER_MODEL_NAME)
            device = encoder.device
            sizes = WARMUP_SIZES if device == "cuda" else WARMUP_SIZES[:1]
            for size in sizes:
                image = Image.new("RGB", size, "white")
                ImageDraw.Draw(image).rectangle(
                    (size[0] // 4, size[1] // 4, size[0] * 3 // 4, size[1] * 3 // 4),
                    fill=(180, 40, 40),
                )
                alpha = segmenter.predict_alpha(image)
                if alpha.shape != (size[1], size[0]) or alpha.dtype != np.uint8:
                    raise ValueError("Warmup segmenter returned an invalid alpha.")
            if getattr(segmenter, "backend", None) == "tensorrt_with_pytorch_fallback":
                counts = segmenter.runtime_details["forwardCounts"]
                if not all(counts.get(name, 0) > 0 for name in ("tensorrt", "pytorch")):
                    raise ValueError(
                        "Both TensorRT and PyTorch routes must be warmed before readiness."
                    )
            vector = encoder.encode(Image.new("RGB", (384, 384), "white"))
            if vector.shape != (768,) or not np.isfinite(vector).all():
                raise ValueError("Warmup encoder returned an invalid vector.")
            analysis.classifier.analyze_views(
                front=vector, back=vector, main_category=MainCategory.UPPER
            )
            if analysis.attributes is not None:
                analysis.attributes.prepare()
            cache_release = release_warmup_cache(
                enabled=settings.api_release_warmup_cache, device=device
            )
        result = {
            "status": "READY",
            "device": device,
            "startupPreparationSeconds": time.perf_counter() - started,
            "loadedModels": list(manager.loaded_models),
            "warmupSizes": [list(size) for size in sizes],
            "segmentationPrecision": segmenter.precision,
            "segmentationBackend": getattr(segmenter, "backend", "pytorch"),
            "segmentationRuntime": getattr(segmenter, "runtime_details", {}),
            "embeddingPrecision": encoder.precision,
            "classifierSha256": head.artifact_sha256,
            "startupCacheRelease": cache_release,
        }
        service.runtime_preparation = result
        return result
    except BaseException:
        service.runtime_preparation = {"status": "FAILED"}
        raise
