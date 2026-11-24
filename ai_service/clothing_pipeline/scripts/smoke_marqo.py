"""Single-image implementation smoke check; no segmentation or classification."""

import argparse
import importlib.metadata
import json
from pathlib import Path
from uuid import uuid4

import numpy as np

from gardirop_ai_clothing.config import get_settings
from gardirop_ai_clothing.embeddings.marqo import (
    MARQO_MODEL_NAME,
    MarqoEmbeddingService,
    create_marqo_service,
    normalize_view_embedding,
)
from gardirop_ai_clothing.image.io import decode_uploaded_image
from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256
from gardirop_ai_clothing.model_specs import MARQO_REVISION

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/marqo"


def verify_reference(image_path: Path, reference_path: Path) -> np.ndarray:
    with np.load(reference_path, allow_pickle=False) as data:
        if str(data["encoder_revision"].item()) != MARQO_REVISION:
            raise ValueError("Reference encoder revision mismatch.")
        if str(data["image_sha256"].item()) != file_sha256(image_path):
            raise ValueError("Image does not match the selected reference.")
        return normalize_view_embedding(data["embedding"])


def run_smoke(
    image_path: Path,
    output_dir: Path,
    *,
    service: MarqoEmbeddingService,
    reference_path: Path | None = None,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "status": "STARTED",
        "training_run": False,
        "classification_run": False,
        "segmentation_run": False,
        "encoder_revision": MARQO_REVISION,
        "scope": "One prepared RGB image; not full pipeline or accuracy evaluation.",
        "reference_check": "requested" if reference_path else "not_requested",
    }
    try:
        reference = verify_reference(image_path, reference_path) if reference_path else None
        image = decode_uploaded_image(image_path.read_bytes())
        vector = service.encode(image)
        encoder = service.manager.get_model(MARQO_MODEL_NAME)
        report.update(
            dimension=int(vector.size),
            norm=float(np.linalg.norm(vector)),
            dtype=str(vector.dtype),
            device=encoder.device,
            precision=encoder.precision,
            image_sha256=file_sha256(image_path),
            encoder_forward_count=1,
        )
        if reference is not None:
            left, right = vector.astype(np.float64), reference.astype(np.float64)
            cosine = float(
                np.clip(np.dot(left, right) / (np.linalg.norm(left) * np.linalg.norm(right)), -1, 1)
            )
            report.update(reference_cosine=cosine, reference_threshold=0.999)
            if cosine < 0.999:
                raise ValueError("Encoder regression differs from the saved Colab reference.")
        np.savez_compressed(output_dir / "embedding.npz", embedding=vector)
        report.update(status="PASSED", embedding_file=str(output_dir / "embedding.npz"))
    except Exception as exc:
        report.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        (output_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Use a prepared RGB image, not an unsegmented photo."
    )
    parser.add_argument("--image", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    settings = get_settings()
    image = args.image or FIXTURES / "G001_front_input.png"
    reference = args.reference
    if args.image is None and reference is None:
        reference = FIXTURES / "G001_front_reference.npz"
    service = create_marqo_service(
        settings.model_manifest_path,
        device=args.device or settings.device,
        max_concurrent_gpu_jobs=settings.max_concurrent_gpu_jobs,
    )
    output = args.output_dir or settings.output_dir / "marqo_smoke" / f"run_{uuid4().hex[:10]}"
    print("OpenCLIP:", importlib.metadata.version("open_clip_torch"))
    run_smoke(image, output, service=service, reference_path=reference)


if __name__ == "__main__":
    main()
