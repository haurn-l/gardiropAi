"""Real, offline acceptance evidence for the local demo; never trains models."""

import argparse
import hashlib
import io
import json
import resource
from dataclasses import asdict, replace
from pathlib import Path
from time import perf_counter

import numpy as np
from PIL import Image

from gardirop_ai_clothing.analysis import create_analysis_service
from gardirop_ai_clothing.config import get_settings
from gardirop_ai_clothing.embeddings.marqo import MARQO_MODEL_NAME
from gardirop_ai_clothing.image.birefnet_local import BIREFNET_MODEL_NAME
from gardirop_ai_clothing.labeling.artifacts import CLASSIFIER_MODEL_NAME


def validate_delivery(prepared):
    """Check the actual delivered bytes, including fine texture and white corners."""
    with Image.open(io.BytesIO(prepared.delivery_webp)) as image:
        if image.mode != "RGB" or image.width != image.height:
            raise AssertionError("Delivery must be opaque RGB on a square canvas.")
        np.testing.assert_array_equal(image, prepared.white_rgb)
        for point in [
            (0, 0),
            (image.width - 1, 0),
            (0, image.height - 1),
            (image.width - 1, image.height - 1),
        ]:
            if image.getpixel(point) != (255, 255, 255):
                raise AssertionError("Delivery corner is not real white.")
    return {
        "rgb_lossless_roundtrip": True,
        "white_corners": True,
        "source_size": list(prepared.source_size),
        "output_size": list(prepared.white_rgb.size),
        "webp_bytes": len(prepared.delivery_webp),
        "foreground_fraction": float(np.mean(prepared.final_alpha > 127)),
        "rotation_degrees": prepared.rotation_degrees,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    args = parser.parse_args()
    import torch

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable; no silent CPU fallback.")
    args.output.mkdir(parents=True, exist_ok=False)
    settings = get_settings().model_copy(update={"device": args.device})
    service = create_analysis_service(settings)
    cases = json.loads(args.cases.read_text())
    report = {
        "scope": "small functional demo acceptance, not population accuracy or benchmark",
        "training_run": False,
        "backend_connected": False,
        "device": args.device,
        "cases": [],
        "model_load_ms": {},
    }
    started = perf_counter()

    def sync():
        if args.device == "cuda":
            torch.cuda.synchronize()

    try:
        if args.device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        for name in (BIREFNET_MODEL_NAME, MARQO_MODEL_NAME, CLASSIFIER_MODEL_NAME):
            before = perf_counter()
            model = service.manager.get_model(name)
            sync()
            report["model_load_ms"][name] = (perf_counter() - before) * 1000
            report.setdefault("models", {})[name] = {
                "device": getattr(model, "device", "cpu"),
                "precision": getattr(model, "precision", "float64"),
            }
        if args.device == "cuda":
            report["resident_allocated_mib"] = torch.cuda.memory_allocated() / 1024**2
        for case in cases:
            print(f"Processing {case['id']}", flush=True)
            out = args.output / case["id"]
            out.mkdir()
            views, details, times = {}, {}, {}
            pair_start = perf_counter()
            for name in ("front", "back"):
                data = Path(case[name]).read_bytes()
                options = replace(
                    service.images.default_options, manual_rotation=case.get("rotation", 0)
                )
                before = perf_counter()
                view = service.prepare_view(data, view_type=name.upper(), options=options)
                sync()
                times[f"{name}_prepare_ms"] = (perf_counter() - before) * 1000
                np.testing.assert_allclose(np.linalg.norm(view.embedding), 1, atol=1e-6)
                details[name] = {
                    **validate_delivery(view.prepared),
                    "input_sha256": hashlib.sha256(data).hexdigest(),
                }
                (out / f"{name}.webp").write_bytes(view.prepared.delivery_webp)
                view.prepared.white_rgb.save(out / f"{name}.png")
                views[name] = view
            before = perf_counter()
            pair = service.finish_pair(
                front=views["front"], back=views["back"], main_category=case["category"]
            )
            times["fusion_lr_attributes_ms"] = (perf_counter() - before) * 1000
            times["pair_ms"] = (perf_counter() - pair_start) * 1000
            if pair.embedding.shape != (1536,) or pair.embedding.dtype != np.float32:
                raise AssertionError("Invalid stored embedding shape/dtype.")
            np.testing.assert_allclose(np.linalg.norm(pair.embedding), 1, atol=1e-6)
            np.savez_compressed(
                out / "embedding.npz",
                embedding=pair.embedding,
                front=views["front"].embedding,
                back=views["back"].embedding,
            )
            entry = {
                "id": case["id"],
                "origin": case["origin"],
                "timings": times,
                "classification": asdict(pair.classification),
                "expected_visual_subtype": case.get("expected_subtype"),
                "subtype_matches_visual_expectation": pair.classification.sub_category
                == case.get("expected_subtype"),
                "tags": pair.tags.model_dump(mode="json"),
                "views": details,
                "embedding_dimension": 1536,
                "embedding_norm": float(np.linalg.norm(pair.embedding)),
                "diagnostics": pair.diagnostics,
            }
            if args.device == "cuda":
                entry["gpu_allocated_mib"] = torch.cuda.memory_allocated() / 1024**2
            report["cases"].append(entry)
            (out / "report.json").write_text(json.dumps(entry, ensure_ascii=False, indent=2))
            print(
                json.dumps(
                    {"id": entry["id"], "tags": entry["tags"], "ms": times["pair_ms"]},
                    ensure_ascii=False,
                ),
                flush=True,
            )
        report["status"] = "FUNCTIONAL_CHECKS_PASSED"
    except Exception as exc:
        report.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        report["total_seconds"] = perf_counter() - started
        report["process_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        if args.device == "cuda":
            report["gpu"] = {
                "name": torch.cuda.get_device_name(),
                "total_mib": torch.cuda.get_device_properties(0).total_memory / 1024**2,
                "peak_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2,
                "peak_reserved_mib": torch.cuda.max_memory_reserved() / 1024**2,
            }
        (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
