"""Fixed-shape experiment policies; ONNX is an optional offline dependency."""

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from gardirop_ai_clothing.image.io import decode_uploaded_image
from gardirop_ai_clothing.image.segmentation import preprocess_birefnet, validate_birefnet_input

INPUT_SHAPE = (1, 3, 1024, 704)
OPSET = 20
POLICY = {
    "id": "birefnet-onnx-fixed-demo-v1",
    "min_alpha_iou": 0.995,
    "max_alpha_mae_255": 0.5,
    "max_rgb_mae_255": 1.0,
    "max_rgb_p99_error_255": 4.0,
    "min_embedding_cosine": 0.9999,
    "max_embedding_abs_error": 0.001,
    "scope": "Six generated demo images; engineering parity, not segmentation accuracy.",
}
CASES = (("tshirt", "üst"), ("jeans", "alt"), ("jacket", "dış"))


def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_fixed_input(chw):
    validate_birefnet_input(chw)
    if (1, *chw.shape) != INPUT_SHAPE:
        raise ValueError("This experimental artifact accepts only NCHW=(1,3,1024,704).")


def validate_logits(value):
    value = np.asarray(value)
    if value.shape != (1, 1, INPUT_SHAPE[2], INPUT_SHAPE[3]) or not np.isfinite(value).all():
        raise ValueError("Invalid or non-finite fixed-shape segmentation logits.")
    return value.astype(np.float32)


def collect_inputs(root, baseline):
    report = json.loads((baseline / "report.json").read_text())
    if report.get("status") != "COMPLETED" or report.get("marqo_precision_requested") != "fp16":
        raise ValueError("A completed FP16 API baseline is required.")
    references = {item["name"]: item for item in report["inputs"]}
    inputs = root / "outputs/step07_completion/inputs/generated"
    rows = []
    for item, parent in CASES:
        for view in ("front", "back"):
            path = inputs / f"{item}_{view}.png"
            digest = sha256(path)
            if digest != references[item][f"{view}_sha256"]:
                raise ValueError(f"Input differs from the verified API baseline: {path.name}")
            rgb = decode_uploaded_image(path.read_bytes())
            validate_fixed_input(preprocess_birefnet(rgb))
            rows.append(
                {
                    "name": f"{item}_{view}",
                    "item": item,
                    "view": view,
                    "parent": parent,
                    "path": str(path),
                    "sha256": digest,
                }
            )
    return rows


def pixel_metrics(reference_alpha, candidate_alpha, reference_rgb, candidate_rgb):
    a, b = np.asarray(reference_alpha), np.asarray(candidate_alpha)
    if a.shape != b.shape or a.dtype != np.uint8 or b.dtype != np.uint8:
        raise ValueError("Masks must be aligned uint8 images at original source resolution.")
    left, right = a > 127, b > 127
    union = np.count_nonzero(left | right)
    iou = float(np.count_nonzero(left & right) / union) if union else 1.0
    alpha_mae = float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())
    x, y = np.asarray(reference_rgb), np.asarray(candidate_rgb)
    if x.dtype != np.uint8 or y.dtype != np.uint8 or x.ndim != 3 or y.ndim != 3:
        raise ValueError("Expected opaque uint8 RGB output images.")
    same_shape = x.shape == y.shape and x.shape[-1] == 3
    delta = np.abs(x.astype(np.int16) - y.astype(np.int16)) if same_shape else None
    corners = [y[0, 0], y[0, -1], y[-1, 0], y[-1, -1]]
    result = {
        "alpha_iou_at_127": iou,
        "alpha_mae_255": alpha_mae,
        "alpha_pixels_identical": bool(np.array_equal(a, b)),
        "nonempty_foregrounds": bool(left.any() and right.any()),
        "same_output_shape": same_shape,
        "rgb_mae_255": float(delta.mean()) if delta is not None else None,
        "rgb_p99_error_255": float(np.percentile(delta, 99)) if delta is not None else None,
        "rgb_max_error_255": int(delta.max()) if delta is not None else None,
        "white_corners": bool(all(np.all(point == 255) for point in corners)),
    }
    result["passed"] = bool(
        result["nonempty_foregrounds"]
        and same_shape
        and result["white_corners"]
        and iou >= POLICY["min_alpha_iou"]
        and alpha_mae <= POLICY["max_alpha_mae_255"]
        and result["rgb_mae_255"] <= POLICY["max_rgb_mae_255"]
        and result["rgb_p99_error_255"] <= POLICY["max_rgb_p99_error_255"]
    )
    return result


def read_rgb(path):
    with Image.open(path) as image:
        image.load()
        if image.mode != "RGB":
            raise ValueError("Delivery must be opaque RGB.")
        return image.copy()


def build_deform_probe(kernel: int):
    """Keep probe geometry as Python constants while JIT traces tensor inputs."""
    import torch
    from torchvision.ops import deform_conv2d

    if type(kernel) is not int or kernel not in (1, 3, 7):
        raise ValueError("The probe supports fixed Python kernel sizes 1, 3 and 7.")

    class Tiny(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.padding = (kernel // 2, kernel // 2)

        def forward(self, x, weight, offset, mask, bias):
            return deform_conv2d(x, offset, weight, bias=bias, padding=self.padding, mask=mask)

    return Tiny().eval().requires_grad_(False)


def deform_conv_symbolic(
    g, input, weight, offset, mask, bias, sh, sw, ph, pw, dh, dw, groups, offset_groups, use_mask
):
    """Preserve torchvision semantics using the standard ONNX DeformConv (opset >=19)."""
    from torch.onnx._internal.torchscript_exporter import symbolic_helper as helper

    numbers = [
        helper._parse_arg(value, "i") for value in (sh, sw, ph, pw, dh, dw, groups, offset_groups)
    ]
    sh, sw, ph, pw, dh, dw, groups, offset_groups = numbers
    masked = helper._parse_arg(use_mask, "b")
    inputs = [input, weight, offset, bias]
    if masked:
        inputs.append(mask)
    result = g.op(
        "DeformConv",
        *inputs,
        strides_i=[sh, sw],
        pads_i=[ph, pw, ph, pw],
        dilations_i=[dh, dw],
        group_i=groups,
        offset_group_i=offset_groups,
    )
    if helper._is_value(input) and helper._is_value(weight):
        shape, kernel = helper._get_tensor_sizes(input), helper._get_tensor_sizes(weight)
        if (
            shape
            and kernel
            and len(shape) == len(kernel) == 4
            and all(v is not None for v in [*shape, *kernel])
        ):
            height = (shape[2] + 2 * ph - dh * (kernel[2] - 1) - 1) // sh + 1
            width = (shape[3] + 2 * pw - dw * (kernel[3] - 1) - 1) // sw + 1
            result.setType(input.type().with_sizes([shape[0], kernel[0], height, width]))
    return result


def register_deform_symbolic():
    import torch

    torch.onnx.register_custom_op_symbolic(
        "torchvision::deform_conv2d", deform_conv_symbolic, OPSET
    )


def provider_evidence(events):
    kernels = [
        item
        for item in events
        if item.get("cat") == "Node" and item.get("args", {}).get("provider")
    ]
    cuda = [item for item in kernels if item["args"]["provider"] == "CUDAExecutionProvider"]
    others = [
        item.get("name", "")
        for item in kernels
        if item["args"]["provider"] != "CUDAExecutionProvider"
    ]
    deform = [item for item in cuda if item["args"].get("op_name") == "DeformConv"]
    return {
        "cuda_kernel_events": len(cuda),
        "cuda_deform_conv_events": len(deform),
        "non_cuda_kernel_names": others,
        "passed": bool(cuda and deform and not others),
    }
