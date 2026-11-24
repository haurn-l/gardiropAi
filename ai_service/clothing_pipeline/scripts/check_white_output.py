"""Check actual white WebP bytes using a recorded mask; no neural inference."""

import argparse
import io
import json
from pathlib import Path
from uuid import uuid4

import numpy as np
from PIL import Image

from gardirop_ai_clothing.config import get_settings
from gardirop_ai_clothing.image.io import WHITE_OUTPUT_PROFILE
from gardirop_ai_clothing.labeling.parent_artifacts import file_sha256
from gardirop_ai_clothing.pipeline import ClothingImagePipeline

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/dynamic"


class RecordedMask:
    def __init__(self, alpha):
        self.alpha = alpha

    def predict_alpha(self, image):
        if self.alpha.shape != (image.height, image.width):
            raise ValueError("Recorded mask and original photo have different dimensions.")
        return self.alpha.copy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    provenance = json.loads((FIXTURES / "provenance.json").read_text())
    for filename, expected in provenance["files_sha256"].items():
        if file_sha256(FIXTURES / filename) != expected:
            raise ValueError(f"Recorded fixture changed: {filename}")
    with Image.open(FIXTURES / "PANTOLON_FRONT_colab_alpha.png") as image:
        alpha = np.asarray(image.convert("L"))
    prepared = ClothingImagePipeline(RecordedMask(alpha)).prepare_photo(
        (FIXTURES / "PANTOLON_FRONT.jpg").read_bytes()
    )
    with Image.open(io.BytesIO(prepared.delivery_webp)) as decoded:
        assert decoded.format == "WEBP" and decoded.mode == "RGB"
        np.testing.assert_array_equal(decoded, prepared.white_rgb)
        corners = [
            (0, 0),
            (decoded.width - 1, 0),
            (0, decoded.height - 1),
            (decoded.width - 1, decoded.height - 1),
        ]
        assert all(decoded.getpixel(point) == (255, 255, 255) for point in corners)
    output = (
        args.output_dir
        or get_settings().output_dir / "white_output_smoke" / f"run_{uuid4().hex[:10]}"
    )
    output.mkdir(parents=True, exist_ok=False)
    (output / "clean.webp").write_bytes(prepared.delivery_webp)
    prepared.white_rgb.save(output / "white_reference.png")
    report = {
        "status": "PASSED",
        "scope": "Recorded Colab mask -> primary white WebP; no neural inference or accuracy claim.",
        "segmentation_inference": False,
        "encoder_inference": False,
        "training_run": False,
        "backend_connected": False,
        "image_output": WHITE_OUTPUT_PROFILE,
        "image_size": list(prepared.white_rgb.size),
        "decoded_rgb_exactly_matches_white_reference": True,
        "corners_white": True,
        "has_alpha": False,
        "webp_bytes": len(prepared.delivery_webp),
        "white_png_bytes": (output / "white_reference.png").stat().st_size,
        "output_file": str(output / "clean.webp"),
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
