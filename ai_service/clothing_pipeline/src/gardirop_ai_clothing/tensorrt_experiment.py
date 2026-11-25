"""Native TensorRT experiment utilities; no import or change to the HTTP runtime."""

import hashlib
import importlib
import json
from pathlib import Path

import numpy as np

from gardirop_ai_clothing.onnx_experiment import INPUT_SHAPE, validate_fixed_input, validate_logits

TRT_VERSION = "10.13.3.9.post1"
TRT_PACKAGES = (f"tensorrt-cu13-bindings=={TRT_VERSION}", f"tensorrt-cu13-libs=={TRT_VERSION}")
BUILD_POLICY = {
    "id": "birefnet-native-trt-strong-fp16-static-v1",
    "workspace_bytes": 1024**3,
    "optimization_level": 3,
    "max_aux_streams": 0,
    "strongly_typed": True,
    "input_shape_nchw": list(INPUT_SHAPE),
    "precision": "explicit_ONNX_FP16_types_preserving_casts",
    "linear_io": True,
}


def cache_key(identity):
    serialized = json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(serialized.encode()).hexdigest()


def check_static_specs(specs, expected_inputs):
    """Never bind a buffer with the wrong name, type, shape or storage location."""
    if len({s["name"] for s in specs}) != len(specs) or any(
        s["mode"] not in {"INPUT", "OUTPUT"} for s in specs
    ):
        raise ValueError("Duplicate tensor names or invalid TensorRT I/O modes.")
    inputs = {s["name"]: tuple(s["shape"]) for s in specs if s["mode"] == "INPUT"}
    outputs = [s for s in specs if s["mode"] == "OUTPUT"]
    if inputs != expected_inputs or len(outputs) != 1:
        raise ValueError("TensorRT engine input/output names or shapes differ from the contract.")
    for spec in specs:
        if spec["dtype"] != "float16" or spec["location"] != "DEVICE" or spec["format"] != "LINEAR":
            raise ValueError("TensorRT experiment requires device-resident, linear FP16 I/O.")
        if not spec["shape"] or any(type(n) is not int or n < 1 for n in spec["shape"]):
            raise ValueError("Only fully static positive TensorRT I/O shapes are accepted.")
    return outputs[0]["name"]


def native_trt():
    # NVIDIA's tensorrt frontend re-exports this bindings module. Installing
    # the two official binary wheels avoids source/stub installers entirely.
    return importlib.import_module("tensorrt_bindings")


def engine_specs(engine, trt):
    specs = []
    for index in range(engine.num_io_tensors):
        name = engine.get_tensor_name(index)
        dtype = engine.get_tensor_dtype(name)
        specs.append(
            {
                "name": name,
                "mode": "INPUT"
                if engine.get_tensor_mode(name) == trt.TensorIOMode.INPUT
                else "OUTPUT",
                "shape": list(engine.get_tensor_shape(name)),
                "dtype": "float16" if dtype == trt.float16 else str(dtype),
                "location": "DEVICE"
                if engine.get_tensor_location(name) == trt.TensorLocation.DEVICE
                else "HOST",
                "format": "LINEAR"
                if engine.get_tensor_format(name) == trt.TensorFormat.LINEAR
                else str(engine.get_tensor_format(name)),
            }
        )
    return specs


class TensorRTRunner:
    """One execution context/stream, reusable I/O buffers, no CPU inference fallback."""

    def __init__(self, plan: Path, expected_inputs):
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError("TensorRT experiment requires CUDA.")
        trt = native_trt()
        self.logger = trt.Logger(trt.Logger.WARNING)
        if not trt.init_libnvinfer_plugins(self.logger, ""):
            raise RuntimeError("TensorRT plugin initialization failed.")
        self.runtime = trt.Runtime(self.logger)
        self.engine = self.runtime.deserialize_cuda_engine(plan.read_bytes())
        if self.engine is None:
            raise RuntimeError("TensorRT engine could not be deserialized.")
        self.specs = engine_specs(self.engine, trt)
        self.output_name = check_static_specs(self.specs, expected_inputs)
        self.expected_inputs = expected_inputs
        self.context = self.engine.create_execution_context()
        if self.context is None:
            raise RuntimeError("TensorRT execution context creation failed.")
        self.stream = torch.cuda.Stream()
        self.stream.wait_stream(torch.cuda.current_stream())
        self.buffers = {
            s["name"]: torch.empty(tuple(s["shape"]), device="cuda", dtype=torch.float16)
            for s in self.specs
        }
        for name, tensor in self.buffers.items():
            if not self.context.set_tensor_address(name, tensor.data_ptr()):
                raise RuntimeError(f"TensorRT buffer binding failed: {name}")
        self.context_device_memory_bytes = int(self.engine.device_memory_size_v2)

    def run_arrays(self, values):
        import torch

        if set(values) != set(self.expected_inputs):
            raise ValueError("Unexpected TensorRT input names.")
        for name, shape in self.expected_inputs.items():
            value = values[name]
            if (
                value.dtype != np.float16
                or tuple(value.shape) != shape
                or not np.isfinite(value).all()
            ):
                raise ValueError("Invalid TensorRT FP16 array shape/type/value.")
        with torch.inference_mode(), torch.cuda.stream(self.stream):
            for name, value in values.items():
                self.buffers[name].copy_(torch.from_numpy(np.ascontiguousarray(value)))
            if not self.context.execute_async_v3(self.stream.cuda_stream):
                raise RuntimeError("Native TensorRT CUDA execution failed.")
        self.stream.synchronize()
        return (
            self.buffers[self.output_name]
            .detach()
            .to(device="cpu", dtype=torch.float32)
            .numpy()
            .copy()
        )

    def __call__(self, chw):
        validate_fixed_input(chw)
        data = np.ascontiguousarray(chw[None], dtype=np.float16)
        return validate_logits(self.run_arrays({"pixels": data}))

    def inspector_json(self):
        trt = native_trt()
        inspector = self.engine.create_engine_inspector()
        inspector.execution_context = self.context
        return inspector.get_engine_information(trt.LayerInformationFormat.JSON)
