"""Benchmark the shared clothing image pipeline on real photographs."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import torch
from PIL import Image

from gardirop_ai_clothing.evaluation import (
    image_diagnostics,
    summarize_timings_ms,
)
from gardirop_ai_clothing.image.io import decode_uploaded_image
from gardirop_ai_clothing.image.segmentation import (
    BiRefNetSegmenter,
    load_huggingface_birefnet_runner,
)
from gardirop_ai_clothing.model_specs import BIREFNET_REVISION, SEGMENTATION_PROFILE
from gardirop_ai_clothing.pipeline import (
    ClothingImagePipeline,
    ImagePreparationOptions,
)

MODEL_REVISION = BIREFNET_REVISION


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark the GardropAI image preparation pipeline.",
    )
    parser.add_argument(
        "--images",
        type=Path,
        nargs="+",
        required=True,
        help="One or more original garment photographs.",
    )
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda"],
        default="cuda",
    )
    parser.add_argument("--a15", action="store_true")
    parser.add_argument("--auto-align", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/benchmarks"),
    )
    return parser.parse_args()


def synchronize(device: str) -> None:
    if device == "cuda":
        torch.cuda.synchronize()


def main() -> None:
    args = parse_args()

    if args.repeats < 1 or args.warmup < 0:
        raise ValueError("Repeats must be >= 1 and warmup must be >= 0.")

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available.")

    # Validate all photographs before downloading/loading a model.
    for path in args.images:
        if not path.is_file():
            raise FileNotFoundError(f"Image not found: {path}")

        decode_uploaded_image(path.read_bytes())

    args.output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Loading pinned BiRefNet Dynamic...")
    load_start = time.perf_counter()

    runner = load_huggingface_birefnet_runner(
        revision=MODEL_REVISION,
        device=args.device,
    )

    synchronize(args.device)
    model_load_seconds = time.perf_counter() - load_start

    pipeline = ClothingImagePipeline(BiRefNetSegmenter(runner))

    options = ImagePreparationOptions(
        use_cleanup=args.a15,
        auto_align=args.auto_align,
    )

    records = []

    for index, path in enumerate(args.images, start=1):
        print(f"\n[{index}/{len(args.images)}] {path.name}")

        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()

        # Warmup is excluded from measured latency.
        for _ in range(args.warmup):
            pipeline.prepare_photo(data, options=options)
            synchronize(args.device)

        timings = []
        peaks_allocated = []
        peaks_reserved = []
        last_result = None

        for _ in range(args.repeats):
            synchronize(args.device)

            if args.device == "cuda":
                torch.cuda.reset_peak_memory_stats()

            start = time.perf_counter()

            last_result = pipeline.prepare_photo(
                data,
                options=options,
            )

            synchronize(args.device)
            elapsed_ms = (time.perf_counter() - start) * 1000

            timings.append(elapsed_ms)

            if args.device == "cuda":
                peaks_allocated.append(torch.cuda.max_memory_allocated() / (1024**2))
                peaks_reserved.append(torch.cuda.max_memory_reserved() / (1024**2))

        assert last_result is not None

        folder = args.output_dir / f"{index:02d}_{digest[:10]}"
        folder.mkdir(parents=True, exist_ok=True)

        white_path = folder / "white.png"
        webp_path = folder / "white.webp"
        mask_path = folder / "mask.png"

        last_result.white_rgb.save(white_path)
        webp_path.write_bytes(last_result.delivery_webp)

        Image.fromarray(last_result.final_alpha).save(mask_path)

        record = {
            "image": str(path),
            "input_sha256": digest,
            "latency_ms": summarize_timings_ms(timings),
            "samples_ms": [round(v, 2) for v in timings],
            "gpu_peak_allocated_mib": (round(max(peaks_allocated), 2) if peaks_allocated else None),
            "gpu_peak_reserved_mib": (round(max(peaks_reserved), 2) if peaks_reserved else None),
            "diagnostics": image_diagnostics(last_result),
            "outputs": {
                "white_png": str(white_path),
                "white_webp": str(webp_path),
                "mask_png": str(mask_path),
            },
        }

        records.append(record)

        print(
            f"P50: {record['latency_ms']['p50']} ms | "
            f"P95: {record['latency_ms']['p95']} ms | "
            f"GPU peak: {record['gpu_peak_allocated_mib']} MiB"
        )

    report = {
        "model": "ZhengPeng7/BiRefNet_dynamic",
        "revision": MODEL_REVISION,
        "segmentation_profile": SEGMENTATION_PROFILE,
        "device": args.device,
        "precision": "float16" if args.device == "cuda" else "float32",
        "model_load_seconds": round(model_load_seconds, 2),
        "repeats": args.repeats,
        "warmup": args.warmup,
        "a15_enabled": args.a15,
        "auto_align_enabled": args.auto_align,
        "measurement_scope": (
            "In-memory decode, segmentation, mask processing, "
            "orientation, white canvas and WebP encoding. "
            "Excludes source disk reads, output disk writes and "
            "model loading. GPU peaks are PyTorch allocator "
            "measurements, not total system VRAM."
        ),
        "images": records,
    }

    report_path = args.output_dir / "benchmark_report.json"

    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
