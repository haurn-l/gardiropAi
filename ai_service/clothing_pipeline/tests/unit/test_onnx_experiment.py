"""Reject misleading ONNX acceptance results without requiring optional ONNX packages."""

import numpy as np
import pytest

from gardirop_ai_clothing.onnx_experiment import (
    build_deform_probe,
    deform_conv_symbolic,
    pixel_metrics,
    provider_evidence,
    validate_fixed_input,
)


def images():
    alpha = np.zeros((32, 32), np.uint8)
    alpha[8:24, 8:24] = 255
    rgb = np.full((40, 40, 3), 255, np.uint8)
    rgb[10:30, 10:30] = [50, 80, 120]
    return alpha, rgb


def test_identical_images_pass_but_empty_foregrounds_do_not():
    alpha, rgb = images()
    assert pixel_metrics(alpha, alpha.copy(), rgb, rgb.copy())["passed"]
    empty = np.zeros_like(alpha)
    result = pixel_metrics(empty, empty, rgb, rgb)
    assert result["alpha_iou_at_127"] == 1
    assert not result["passed"]


def test_missing_garment_region_fails_the_mask_gate():
    alpha, rgb = images()
    damaged = alpha.copy()
    damaged[8:16] = 0
    assert not pixel_metrics(alpha, damaged, rgb, rgb)["passed"]


def test_changed_crop_dimensions_and_nonwhite_background_are_rejected():
    alpha, rgb = images()
    assert not pixel_metrics(alpha, alpha, rgb, rgb[:-1])["passed"]
    altered = rgb.copy()
    altered[0, 0] = 0
    assert not pixel_metrics(alpha, alpha, rgb, altered)["passed"]


def test_mask_error_does_not_wrap_unsigned_bytes():
    alpha, rgb = images()
    changed = alpha.copy()
    changed[8:24, 8:24] = 254
    assert pixel_metrics(alpha, changed, rgb, rgb)["alpha_mae_255"] == pytest.approx(0.25)


def test_static_artifact_rejects_otherwise_valid_model_shapes():
    validate_fixed_input(np.zeros((3, 1024, 704), dtype=np.float32))
    with pytest.raises(ValueError, match="only NCHW"):
        validate_fixed_input(np.zeros((3, 704, 1024), dtype=np.float32))


def test_provider_list_is_not_accepted_as_proof_of_cuda_execution():
    assert not provider_evidence([])["passed"]
    event = {
        "cat": "Node",
        "name": "DeformConv_kernel_time",
        "args": {"provider": "CUDAExecutionProvider", "op_name": "DeformConv"},
    }
    assert provider_evidence([event])["passed"]
    cpu = {
        "cat": "Node",
        "name": "Conv_on_CPU",
        "args": {"provider": "CPUExecutionProvider", "op_name": "Conv"},
    }
    assert not provider_evidence([event, cpu])["passed"]


@pytest.mark.parametrize("mask_enabled", [False, True])
def test_deform_symbolic_preserves_weight_offset_order_and_group_parameters(mask_enabled):
    captured = []

    class Graph:
        def op(self, name, *inputs, **attributes):
            captured.append((name, inputs, attributes))
            return "output"

    result = deform_conv_symbolic(
        Graph(), "image", "weight", "offset", "mask", "bias", 2, 3, 1, 2, 4, 5, 2, 3, mask_enabled
    )
    expected_inputs = ("image", "weight", "offset", "bias") + (("mask",) if mask_enabled else ())
    assert result == "output"
    assert captured == [
        (
            "DeformConv",
            expected_inputs,
            {
                "strides_i": [2, 3],
                "pads_i": [1, 2, 1, 2],
                "dilations_i": [4, 5],
                "group_i": 2,
                "offset_group_i": 3,
            },
        )
    ]


@pytest.mark.parametrize("kernel", [1, 3, 7])
def test_tiny_probe_traces_with_constant_padding_on_cpu(kernel):
    """Regression: deriving padding from traced weight.shape raises a scalar iteration error."""
    import torch

    model = build_deform_probe(kernel)
    generator = torch.Generator().manual_seed(123)
    values = (
        torch.randn((1, 2, 8, 10), generator=generator),
        torch.randn((3, 2, kernel, kernel), generator=generator),
        torch.randn((1, 2 * kernel * kernel, 8, 10), generator=generator) * 0.2,
        torch.rand((1, kernel * kernel, 8, 10), generator=generator) * 2,
        torch.randn((3,), generator=generator),
    )
    assert model.padding == (kernel // 2, kernel // 2)
    assert all(type(value) is int for value in model.padding)
    with torch.inference_mode():
        expected = model(*values)
        traced = torch.jit.trace(model, values, check_trace=True)
        actual = traced(*values)
    torch.testing.assert_close(actual, expected)
    assert actual.shape == (1, 3, 8, 10)
