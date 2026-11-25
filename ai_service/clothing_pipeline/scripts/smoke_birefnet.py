"""One local Dynamic inference and optional Colab agreement; no other models."""

import argparse
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import numpy as np
from PIL import Image

from gardirop_ai_clothing.config import get_settings
from gardirop_ai_clothing.image.birefnet_local import load_birefnet_segmenter
from gardirop_ai_clothing.image.io import decode_uploaded_image, encode_white_webp
from gardirop_ai_clothing.image.segmentation import prepare_birefnet_canvas
from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256
from gardirop_ai_clothing.model_specs import (
    BIREFNET_MODEL_NAME,
    BIREFNET_REVISION,
)

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/dynamic"


def run_smoke(image_path, output_dir, *, segmenter, reference_path=None, reference_threshold=0.98):
    output_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "status": "STARTED",
        "scope": "One local segmentation; not accuracy, full pipeline or GPU capacity approval.",
        "training_run": False,
        "classification_run": False,
        "encoder_inference": False,
        "backend_connected": False,
        "model": BIREFNET_MODEL_NAME,
        "revision": segmenter.revision,
        "segmentation_profile": segmenter.preprocessing_profile,
        "device": segmenter.device,
        "precision": segmenter.precision,
        "image_sha256": file_sha256(image_path),
        "cleanup_enabled": False,
    }
    try:
        image = decode_uploaded_image(image_path.read_bytes())
        canvas, box = prepare_birefnet_canvas(image)
        started = perf_counter()
        alpha = segmenter.predict_alpha(image)
        if alpha.shape != (image.height, image.width) or alpha.dtype != np.uint8:
            raise ValueError("Alpha shape/dtype does not match the source photo.")
        if not np.any(alpha > 127) or not np.any(alpha < 127):
            raise ValueError("Expected both foreground and background in this garment photo.")
        rgba = image.convert("RGBA")
        rgba.putalpha(Image.fromarray(alpha))
        report["inference_and_rgba_ms"] = (perf_counter() - started) * 1000
        Image.fromarray(alpha).save(output_dir / "alpha.png")
        rgba.save(output_dir / "cutout.png")
        white = Image.alpha_composite(Image.new("RGBA", rgba.size, "white"), rgba).convert("RGB")
        (output_dir / "cutout.webp").write_bytes(encode_white_webp(white))
        white.save(output_dir / "white.png")
        report["output_image"] = {
            "background": "#FFFFFF",
            "mode": "RGB",
            "format": "WEBP",
            "lossless": True,
            "layout": "original_size_segmentation_diagnostic",
        }
        report.update(
            source_size=list(image.size), model_input_wh=list(canvas.size), content_box=list(box)
        )
        if reference_path is not None:
            with Image.open(reference_path) as ref:
                reference = np.asarray(ref.convert("L"))
            if reference.shape != alpha.shape:
                raise ValueError("Reference mask size mismatch.")
            a, b = alpha > 127, reference > 127
            union = int(np.count_nonzero(a | b))
            iou = int(np.count_nonzero(a & b)) / union if union else 1.0
            report["colab_reference"] = {
                "agreement_iou": iou,
                "minimum_agreement": reference_threshold,
                "is_accuracy_measurement": False,
                "note": "Reference is the same model's CPU result, not a ground-truth mask.",
            }
            if iou < reference_threshold:
                raise ValueError(
                    "Dynamic mask differs from the saved Colab implementation reference."
                )
        report["cuda_memory"] = None
        if segmenter.device == "cuda":
            import torch

            report["cuda_memory"] = {
                "device_name": torch.cuda.get_device_name(),
                "peak_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2,
                "peak_reserved_mib": torch.cuda.max_memory_reserved() / 1024**2,
                "scope": "This isolated segmentation process, including model loading; Marqo absent.",
            }
        report["status"] = "PASSED"
    except Exception as exc:
        report.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        (output_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description="Run the pinned local BiRefNet Dynamic only.")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--revision", default=BIREFNET_REVISION)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--no-clean", action="store_true", help="Compatibility flag; cleanup is always off here."
    )
    args = parser.parse_args()
    if args.revision != BIREFNET_REVISION:
        parser.error("Use the selected Dynamic revision; Lite is no longer the active model.")
    image_path = args.image or FIXTURES / "PANTOLON_FRONT.jpg"
    reference = None
    if args.image is None:
        provenance = json.loads((FIXTURES / "provenance.json").read_text())
        for filename, expected in provenance["files_sha256"].items():
            if file_sha256(FIXTURES / filename) != expected:
                raise ValueError(f"Smoke fixture integrity mismatch: {filename}")
        reference = FIXTURES / "PANTOLON_FRONT_colab_alpha.png"
    settings = get_settings()
    print(
        "BiRefNet Dynamic only; pinned local files; no download, training or Marqo. First load can take time.",
        flush=True,
    )
    import torch

    requested_device = args.device or settings.device
    if requested_device != "cpu" and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    segmenter = load_birefnet_segmenter(
        settings.model_manifest_path, device=args.device or settings.device
    )
    output = args.output_dir or settings.output_dir / "dynamic_smoke" / f"run_{uuid4().hex[:10]}"
    run_smoke(image_path, output, segmenter=segmenter, reference_path=reference)


if __name__ == "__main__":
    main()
