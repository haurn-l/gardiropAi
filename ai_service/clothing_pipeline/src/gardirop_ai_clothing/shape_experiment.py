"""Deterministic padded test inputs and per-case routing evidence; no model calls."""

import hashlib
import io
import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from gardirop_ai_clothing.image.segmentation import prepare_birefnet_canvas
from gardirop_ai_clothing.onnx_experiment import INPUT_SHAPE, save_json, sha256

# First submitted shape must exercise the fallback immediately after startup trimming.
PROFILES = (("p34", (3, 4)), ("p23", (2, 3)), ("square", (1, 1)), ("l43", (4, 3)))
ITEMS = (
    ("tshirt", "UST_GIYIM", "T-shirt"),
    ("jeans", "ALT_GIYIM", "Jean"),
    ("jacket", "DIS_GIYIM", "Kot ceket"),
)
SHAPES = {
    "p34": (1, 3, 1024, 768),
    "p23": INPUT_SHAPE,
    "square": (1, 3, 1024, 1024),
    "l43": (1, 3, 768, 1024),
}


def case_name(item, profile):
    return item if profile == "p23" else f"{item}_{profile}"


def pad_to_ratio(image, ratio):
    if image.mode != "RGB" or len(ratio) != 2 or any(type(n) is not int or n < 1 for n in ratio):
        raise ValueError("RGB image and positive integer ratio required.")
    multiple = max(math.ceil(image.width / ratio[0]), math.ceil(image.height / ratio[1]))
    size = (multiple * ratio[0], multiple * ratio[1])
    offset = ((size[0] - image.width) // 2, (size[1] - image.height) // 2)
    canvas = Image.new("RGB", size, "white")
    canvas.paste(image, offset)
    return canvas, offset


def shape_of(image):
    canvas, _ = prepare_birefnet_canvas(image)
    return (1, 3, canvas.height, canvas.width)


def prepare_suite(root, output, baseline):
    reference = json.loads((baseline / "report.json").read_text())
    if (
        reference.get("status") != "COMPLETED"
        or reference.get("segmentation_backend_requested") != "tensorrt"
    ):
        raise ValueError("A completed accepted TensorRT API baseline is required.")
    originals = {row["name"]: row for row in reference["inputs"]}
    target = output / "inputs"
    target.mkdir()
    rows, sources = [], []
    for item, category, expected in ITEMS:
        images, paths = {}, {}
        for view in ("front", "back"):
            path = root / "outputs/step07_completion/inputs/generated" / f"{item}_{view}.png"
            if sha256(path) != originals[item][f"{view}_sha256"]:
                raise ValueError("Original demo photo differs from the accepted API baseline.")
            with Image.open(path) as image:
                if image.mode != "RGB":
                    raise ValueError("Expected original RGB demo photo.")
                images[view] = image.copy()
            paths[view] = path
            sources.append({"item": item, "view": view, "path": str(path), "sha256": sha256(path)})
        for profile, ratio in PROFILES:
            row = {
                "name": case_name(item, profile),
                "item": item,
                "profile": profile,
                "category": category,
                "expected_subtype": expected,
                "expected_input_nchw": list(SHAPES[profile]),
                "expected_backend": "tensorrt" if profile == "p23" else "pytorch",
            }
            for view in ("front", "back"):
                original = images[view]
                if profile == "p23":
                    path, canvas, offset = paths[view], original, (0, 0)
                else:
                    canvas, offset = pad_to_ratio(original, ratio)
                    path = target / f"{row['name']}_{view}.png"
                    canvas.save(path, format="PNG")
                box = (
                    offset[0],
                    offset[1],
                    offset[0] + original.width,
                    offset[1] + original.height,
                )
                if not np.array_equal(np.asarray(canvas.crop(box)), np.asarray(original)):
                    raise ValueError("Padding altered original garment pixels.")
                if shape_of(canvas) != SHAPES[profile]:
                    raise ValueError(
                        "Prepared image does not produce the declared normalized model shape."
                    )
                row[view], row[f"{view}_sha256"] = str(path), sha256(path)
                row[f"{view}_source_size"] = list(original.size)
                row[f"{view}_input_size"] = list(canvas.size)
                row[f"{view}_padding_offset"] = list(offset)
            rows.append(row)
    manifest = output / "shape_suite.json"
    save_json(
        manifest,
        {
            "schema_version": 1,
            "sources": sources,
            "cases": rows,
            "scope": "Same six generated photos with pixel-preserving white padding. Not new photographs or independent accuracy data.",
        },
    )
    return manifest


def load_suite(path, root, max_bytes):
    path, root = Path(path).resolve(), Path(root).resolve()
    allowed = (root / "outputs/api_shape_compare").resolve()
    if not allowed.is_relative_to(root) or not path.is_relative_to(allowed):
        raise ValueError("Shape suite must be under outputs/api_shape_compare.")
    data = json.loads(path.read_text())
    expected = [
        (case_name(item, profile), item, profile, category, subtype)
        for item, category, subtype in ITEMS
        for profile, _ in PROFILES
    ]
    rows = data.get("cases", [])
    if data.get("schema_version") != 1 or len(rows) != len(expected):
        raise ValueError("Incomplete shape suite.")
    result = []
    for row, (name, item, profile, category, subtype) in zip(rows, expected, strict=True):
        if (row["name"], row["item"], row["profile"], row["category"], row["expected_subtype"]) != (
            name,
            item,
            profile,
            category,
            subtype,
        ):
            raise ValueError("Unexpected shape suite case identity/order.")
        backend = "tensorrt" if profile == "p23" else "pytorch"
        if (
            row["expected_input_nchw"] != list(SHAPES[profile])
            or row["expected_backend"] != backend
        ):
            raise ValueError("Invalid shape/backend declaration.")
        case = dict(row)
        for view in ("front", "back"):
            image_path = Path(row[view]).resolve()
            if not image_path.is_relative_to((root / "outputs").resolve()):
                raise ValueError("Shape image escaped the project output folder.")
            raw = image_path.read_bytes()
            if (
                not 0 < len(raw) <= max_bytes
                or hashlib.sha256(raw).hexdigest() != row[f"{view}_sha256"]
            ):
                raise ValueError("Shape input checksum or upload-size mismatch.")
            with Image.open(io.BytesIO(raw)) as image:
                if image.mode != "RGB" or shape_of(image) != SHAPES[profile]:
                    raise ValueError("Shape input dimensions/profile changed.")
            case[view] = raw
        result.append(case)
    return result


def routing_valid(windows, forwards, cases, backend):
    if not windows:
        return False
    by_name = {row["name"]: row for row in cases}
    for window in windows:
        case = by_name[window["case"]]
        expected = case.get("expected_backend", "tensorrt") if backend == "tensorrt" else "pytorch"
        shape = case.get("expected_input_nchw")
        selected = [
            event
            for event in forwards
            if window["start_ns"] <= event["start_ns"] <= event["end_ns"] <= window["assets_ns"]
        ]
        if len(selected) != 2 or any(
            event.get("backend") != expected
            or not event.get("success")
            or (shape is not None and event.get("input_nchw") != shape)
            for event in selected
        ):
            return False
    return True


def sample_process_gpu(pid):
    """Client-side sample after downloads, outside the measured interval; not a peak."""
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,used_gpu_memory",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode != 0:
            return None
        values = [
            float(line.split(",")[1].strip())
            for line in proc.stdout.splitlines()
            if line.split(",")[0].strip() == str(pid)
        ]
        return sum(values) if values else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
