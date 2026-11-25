"""One real paired-photo integration check, using pinned local model files."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import numpy as np

from gardirop_ai_clothing.analysis import ClothingAnalysisService, create_analysis_service
from gardirop_ai_clothing.config import get_settings
from gardirop_ai_clothing.contracts import MainCategory
from gardirop_ai_clothing.embeddings.marqo import MARQO_MODEL_NAME
from gardirop_ai_clothing.image.birefnet_local import BIREFNET_MODEL_NAME
from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256
from gardirop_ai_clothing.schemas import ClothingAnalysisResult, ViewType

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/pipeline"


def run_smoke(
    front_path: Path,
    back_path: Path,
    main_category: MainCategory | str,
    output_dir: Path,
    *,
    service: ClothingAnalysisService,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "status": "STARTED",
        "scope": "One paired-photo functional integration; not accuracy or latency benchmarking.",
        "training_run": False,
        "backend_connected": False,
        "confirmation_run": False,
        "expected_forward_counts": {"segmentation": 2, "marqo": 2},
        "gpu_policy": "Single shared execution slot; models remain cached; explicit OOM error, no silent fallback.",
        "co_residency_limit": "This run applies only to this device/input/configuration; not a general VRAM guarantee.",
    }
    started = perf_counter()
    try:
        parent = MainCategory(main_category)
        report["selected_parent"] = parent.value
        report["source_sha256"] = {"FRONT": file_sha256(front_path), "BACK": file_sha256(back_path)}
        front = service.prepare_view(front_path.read_bytes(), view_type=ViewType.FRONT)
        front_done = perf_counter()
        back = service.prepare_view(back_path.read_bytes(), view_type=ViewType.BACK)
        back_done = perf_counter()
        pair = service.finish_pair(front=front, back=back, main_category=parent)
        pair_done = perf_counter()
        # Validate the full existing result contract before writing success artifacts.
        result = ClothingAnalysisResult(
            item_session_id=f"smoke-{output_dir.name}",
            draft_revision=1,
            category=parent,
            front_image_ref="front.webp",
            back_image_ref="back.webp",
            tags=pair.tags,
            embedding_model="Marqo/marqo-fashionSigLIP",
            versions=pair.versions,
            embedding=tuple(float(v) for v in pair.embedding),
        )
        view_details = {}
        for name, view in (("front", front), ("back", back)):
            prepared = view.prepared
            (output_dir / f"{name}.webp").write_bytes(prepared.delivery_webp)
            prepared.white_rgb.save(output_dir / f"{name}_white.png")
            view_details[name] = {
                "source_size": prepared.source_size,
                "white_size": prepared.white_rgb.size,
                "image_output_profile": prepared.delivery_profile,
                "cutout_size": prepared.aligned_rgba.size,
                "options": asdict(view.options),
                "orientation_method": prepared.orientation_method,
                "rotation_degrees": prepared.rotation_degrees,
                "cleanup_reason": prepared.cleanup_reason,
                "view_dimension": int(view.embedding.size),
                "view_norm": float(np.linalg.norm(view.embedding)),
            }
        np.savez_compressed(
            output_dir / "embedding.npz",
            embedding=pair.embedding,
            front=front.embedding,
            back=back.embedding,
            view_order=np.array(["FRONT", "BACK"]),
        )
        models = {}
        for name in (BIREFNET_MODEL_NAME, MARQO_MODEL_NAME):
            model = service.manager.get_model(name)
            models[name] = {
                "device": model.device,
                "precision": model.precision,
                "revision": model.revision,
            }
        report.update(
            dimension=int(pair.embedding.size),
            norm=float(np.linalg.norm(pair.embedding)),
            classification=asdict(pair.classification),
            tags=pair.tags.model_dump(mode="json"),
            versions=pair.versions.model_dump(mode="json"),
            models=models,
            views=view_details,
            loaded_models=service.manager.loaded_models,
            timings_ms={
                "front_with_lazy_load": (front_done - started) * 1000,
                "back_warm": (back_done - front_done) * 1000,
                "fusion_and_lr_with_lazy_load": (pair_done - back_done) * 1000,
            },
        )
        import torch

        if any(model["device"] == "cuda" for model in models.values()):
            report["cuda_memory"] = {
                "device_name": torch.cuda.get_device_name(),
                "peak_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2,
                "peak_reserved_mib": torch.cuda.max_memory_reserved() / 1024**2,
                "currently_allocated_mib": torch.cuda.memory_allocated() / 1024**2,
            }
        else:
            report["cuda_memory"] = None
        (output_dir / "result.json").write_text(
            result.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        report.update(
            status="PASSED", result_file=str(output_dir / "result.json"), output_dir=str(output_dir)
        )
    except Exception as exc:
        report.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        report["total_ms"] = (perf_counter() - started) * 1000
        (output_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Use two raw garment photos and the user's parent category."
    )
    parser.add_argument("--front", type=Path)
    parser.add_argument("--back", type=Path)
    parser.add_argument("--category", choices=[p.value for p in MainCategory], default="üst")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if (args.front is None) != (args.back is None):
        parser.error("Provide --front and --back together.")
    settings = get_settings()
    if args.device:
        settings = settings.model_copy(update={"device": args.device})
    import torch

    if settings.device != "cpu" and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    print(
        "Pinned local files only. Two raw photos; default rotation is zero. First load can take time.",
        flush=True,
    )
    if args.front is None:
        print(
            "Bundled G001 raw dataset photos are sideways; no dataset-specific 90-degree rule is applied.",
            flush=True,
        )
    service = create_analysis_service(settings)
    output = args.output_dir or settings.output_dir / "pipeline_smoke" / f"run_{uuid4().hex[:10]}"
    run_smoke(
        args.front or FIXTURES / "G001_front_raw.jpg",
        args.back or FIXTURES / "G001_back_raw.jpg",
        args.category,
        output,
        service=service,
    )


if __name__ == "__main__":
    main()
