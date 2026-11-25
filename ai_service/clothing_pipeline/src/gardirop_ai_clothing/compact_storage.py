"""Versioned, hashed pair-analysis snapshots, without diagnostic PNG/alpha copies."""

import hashlib
import json
import math
from dataclasses import asdict

import numpy as np

from gardirop_ai_clothing.analysis import AnalyzedView
from gardirop_ai_clothing.contracts import NORM_ABS_TOLERANCE
from gardirop_ai_clothing.errors import LocalStorageError
from gardirop_ai_clothing.image.io import DEFAULT_MAX_PIXELS, WHITE_OUTPUT_PROFILE
from gardirop_ai_clothing.labeling.color import COLOR_PALETTE_VERSION, PALETTE, view_palette
from gardirop_ai_clothing.pipeline import ImagePreparationOptions
from gardirop_ai_clothing.schemas import ViewType
from gardirop_ai_clothing.view_snapshot import StoredGarmentImage

COMPACT_PROFILE = "pair-analysis-v1"
COMPACT_FILES = {"clean.webp", "features.json"}


def write_compact(folder, view):
    prepared = view.prepared
    if prepared.white_webp is None:
        raise LocalStorageError("Compact storage requires a white RGB delivery image.")
    palette = (
        prepared.color_palette
        if isinstance(prepared, StoredGarmentImage)
        else view_palette(prepared.original_cutout)
    )
    features = {
        "embedding": view.embedding.tolist(),
        "color_palette": palette,
        "color_palette_version": COLOR_PALETTE_VERSION,
    }
    (folder / "clean.webp").write_bytes(prepared.delivery_webp)
    (folder / "features.json").write_text(
        json.dumps(features, allow_nan=False, separators=(",", ":")), encoding="utf-8"
    )
    return {
        "storage_profile": COMPACT_PROFILE,
        "view_type": view.view_type.value,
        "options": asdict(view.options),
        "preprocessing_version": view.preprocessing_version,
        "embedding_revision": view.embedding_revision,
        "segmentation_revision": view.segmentation_revision,
        "encoder_precision": view.encoder_precision,
        "image_output": dict(WHITE_OUTPUT_PROFILE),
        "image": {
            "source_size": list(prepared.source_size),
            "output_size": list(prepared.output_size),
            "rotation_degrees": prepared.rotation_degrees,
        },
        "files": {
            name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
            for name in sorted(COMPACT_FILES)
        },
    }


def _size(value):
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(n) is not int or n < 1 for n in value)
        or value[0] * value[1] > DEFAULT_MAX_PIXELS
    ):
        raise ValueError("Invalid image dimensions.")
    return tuple(value)


def read_compact(folder, record):
    try:
        if (
            record["storage_profile"] != COMPACT_PROFILE
            or record["image_output"] != WHITE_OUTPUT_PROFILE
            or set(record["files"]) != COMPACT_FILES
        ):
            raise ValueError("Invalid compact storage profile/files.")
        payloads = {}
        for name, expected in record["files"].items():
            data = (folder / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise LocalStorageError("Stored compact view SHA256 mismatch.")
            payloads[name] = data
        if record.get("encoder_precision", "fp32") not in {"fp32", "fp16"}:
            raise ValueError("Unsupported encoder precision.")
        features = json.loads(payloads["features.json"])
        vector = np.asarray(features["embedding"], dtype=np.float32)
        if (
            vector.shape != (768,)
            or not np.isfinite(vector).all()
            or not np.isclose(np.linalg.norm(vector), 1, atol=NORM_ABS_TOLERANCE, rtol=0)
        ):
            raise ValueError("Invalid stored view embedding.")
        if features["color_palette_version"] != COLOR_PALETTE_VERSION:
            raise ValueError("Unsupported palette producer.")
        palette = features["color_palette"]
        if palette is not None:
            if (
                not isinstance(palette, dict)
                or set(palette) != set(PALETTE)
                or any(
                    type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
                    for v in palette.values()
                )
                or not math.isclose(sum(palette.values()), 1, abs_tol=1e-6)
            ):
                raise ValueError("Invalid stored color palette.")
        image = record["image"]
        rotation = image["rotation_degrees"]
        if type(rotation) not in (int, float) or not math.isfinite(rotation):
            raise ValueError("Invalid stored rotation.")
        vector.setflags(write=False)
        return AnalyzedView(
            view_type=ViewType(record["view_type"]),
            prepared=StoredGarmentImage(
                source_size=_size(image["source_size"]),
                output_size=_size(image["output_size"]),
                white_webp=payloads["clean.webp"],
                rotation_degrees=rotation,
                color_palette=palette,
            ),
            embedding=vector,
            options=ImagePreparationOptions(**record["options"]),
            preprocessing_version=record["preprocessing_version"],
            embedding_revision=record["embedding_revision"],
            segmentation_revision=record["segmentation_revision"],
            encoder_precision=record.get("encoder_precision", "fp32"),
        )
    except LocalStorageError:
        raise
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        raise LocalStorageError("Cannot read compact analysis snapshot.") from exc
