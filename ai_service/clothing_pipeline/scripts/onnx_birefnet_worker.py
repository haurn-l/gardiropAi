"""Isolated worker for the fixed-shape ONNX experiment, never the HTTP service."""

import argparse
import gc
import json
import random
import resource
import time
import traceback
from dataclasses import asdict
from pathlib import Path

import numpy as np
from PIL import Image

from gardirop_ai_clothing.benchmarking import describe
from gardirop_ai_clothing.config import get_settings
from gardirop_ai_clothing.image.io import decode_uploaded_image
from gardirop_ai_clothing.image.segmentation import BiRefNetSegmenter, preprocess_birefnet
from gardirop_ai_clothing.onnx_experiment import (
    CASES,
    INPUT_SHAPE,
    OPSET,
    build_deform_probe,
    pixel_metrics,
    provider_evidence,
    read_rgb,
    register_deform_symbolic,
    save_json,
    sha256,
    validate_fixed_input,
    validate_logits,
)
from gardirop_ai_clothing.pipeline import ClothingImagePipeline, ImagePreparationOptions

ROOT = Path(__file__).resolve().parents[1]


def make_session(path, profile_prefix):
    # PyTorch is imported first so the exact existing CUDA/cuDNN libraries are loaded.
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; no CPU fallback is permitted.")
    import onnxruntime as ort

    ort.disable_telemetry_events()
    if hasattr(ort, "preload_dlls"):
        ort.preload_dlls(cuda=True, cudnn=True)
    if "CUDAExecutionProvider" not in ort.get_available_providers():
        raise RuntimeError("ONNX Runtime CUDA provider is unavailable.")
    options = ort.SessionOptions()
    options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.enable_profiling = True
    options.profile_file_prefix = str(profile_prefix)
    session = ort.InferenceSession(
        str(path), sess_options=options, providers=[("CUDAExecutionProvider", {"device_id": 0})]
    )
    session.disable_fallback()
    if "CUDAExecutionProvider" not in session.get_providers():
        raise RuntimeError("Actual session did not retain its CUDA provider.")
    return session


def end_profile(session):
    path = Path(session.end_profiling())
    evidence = provider_evidence(json.loads(path.read_text()))
    evidence["profile"] = str(path)
    if not evidence["passed"]:
        raise RuntimeError(f"CUDA node execution was not demonstrated: {evidence}")
    return evidence


def tiny_deform_test(output):
    import onnx
    import torch

    register_deform_symbolic()

    rng = np.random.default_rng(20261125)
    rows = []
    for kernel in (1, 3, 7):
        print(f"CUDA DeformConv eşdeğerlik kontrolü: kernel={kernel}", flush=True)
        arrays = [
            (rng.normal(size=(1, 2, 8, 10)) * 0.1).astype(np.float16),
            (rng.normal(size=(3, 2, kernel, kernel)) * 0.1).astype(np.float16),
            (rng.normal(size=(1, 2 * kernel * kernel, 8, 10)) * 0.3).astype(np.float16),
            rng.uniform(0, 2, size=(1, kernel * kernel, 8, 10)).astype(np.float16),
            (rng.normal(size=(3,)) * 0.1).astype(np.float16),
        ]
        values = tuple(torch.from_numpy(value).to("cuda") for value in arrays)
        model = build_deform_probe(kernel)
        path = output / f"tiny_deform_{kernel}.onnx"
        with torch.inference_mode(), torch.autocast("cuda", enabled=False):
            expected = model(*values).float().cpu().numpy()
            torch.onnx.export(
                model,
                values,
                str(path),
                opset_version=OPSET,
                dynamo=False,
                input_names=["x", "weight", "offset", "mask", "bias"],
                output_names=["y"],
                external_data=False,
            )
        onnx.checker.check_model(str(path))
        session = make_session(path, output / f"tiny_profile_{kernel}")
        candidate = session.run(
            None, dict(zip(["x", "weight", "offset", "mask", "bias"], arrays, strict=True))
        )[0].astype(np.float32)
        np.testing.assert_allclose(candidate, expected, atol=0.002, rtol=0.005)
        evidence = end_profile(session)
        rows.append(
            {
                "kernel": kernel,
                "max_abs_error": float(np.abs(candidate - expected).max()),
                "provider_evidence": evidence,
            }
        )
        del session, values, model
        gc.collect()
        torch.cuda.empty_cache()
    return {
        "status": "PASSED",
        "tests": rows,
        "scope": "Fractional offsets, non-unit masks and nonzero bias; FP16 CUDA.",
    }


def options(settings):
    return ImagePreparationOptions(
        use_cleanup=settings.image_use_cleanup,
        auto_align=settings.image_auto_align,
        padding=settings.image_padding,
        square_margin_fraction=settings.image_square_margin_fraction,
    )


def process_cases(output, inputs, runner, backend):
    settings = get_settings()
    captured = {}

    def capture_logits(chw):
        value = validate_logits(runner(chw))
        captured["logits"] = value
        return value

    pipeline = ClothingImagePipeline(
        BiRefNetSegmenter(capture_logits),
        default_options=options(settings),
        include_transparent_webp=False,
    )
    rows = []
    for entry in inputs:
        print(f"{backend}: {entry['name']}", flush=True)
        folder = output / backend / entry["name"]
        folder.mkdir(parents=True, exist_ok=False)
        if sha256(entry["path"]) != entry["sha256"]:
            raise ValueError("An experiment input was changed during the run.")
        prepared = pipeline.prepare_photo(Path(entry["path"]).read_bytes())
        np.save(folder / "logits.npy", captured.pop("logits"), allow_pickle=False)
        Image.fromarray(prepared.raw_alpha).save(folder / "alpha.png")
        prepared.original_cutout.save(folder / "cutout.png")
        (folder / "clean.webp").write_bytes(prepared.delivery_webp)
        save_json(
            folder / "view.json",
            {
                "source_size": prepared.source_size,
                "output_size": prepared.output_size,
                "rotation_degrees": prepared.rotation_degrees,
                "options": asdict(options(settings)),
            },
        )
        row = {
            "name": entry["name"],
            "output_size": list(prepared.output_size),
            "image_sha256": sha256(folder / "clean.webp"),
        }
        if backend != "torch":
            reference = output / "torch" / entry["name"]
            with Image.open(reference / "alpha.png") as mask:
                alpha = np.array(mask)
            expected_logits = np.load(reference / "logits.npy", allow_pickle=False)
            actual_logits = np.load(folder / "logits.npy", allow_pickle=False)
            delta = np.abs(actual_logits - expected_logits)
            row["logits_drift"] = {
                "max_abs_error": float(delta.max()),
                "mean_abs_error": float(delta.mean()),
                "p99_abs_error": float(np.percentile(delta, 99)),
            }
            row["quality"] = pixel_metrics(
                alpha, prepared.raw_alpha, read_rgb(reference / "clean.webp"), prepared.white_rgb
            )
        rows.append(row)
    return rows


def benchmark(inputs, runner, repeats):
    import torch

    arrays = {}
    for entry in inputs:
        chw = preprocess_birefnet(decode_uploaded_image(Path(entry["path"]).read_bytes()))
        validate_fixed_input(chw)
        arrays[entry["name"]] = chw
    for _ in range(3):
        for array in arrays.values():
            runner(array)
    order = list(arrays) * repeats
    random.Random(20261125).shuffle(order)
    samples = []
    for name in order:
        torch.cuda.synchronize()
        started = time.perf_counter()
        value = runner(arrays[name])
        torch.cuda.synchronize()
        elapsed = (time.perf_counter() - started) * 1000
        validate_logits(value)
        samples.append({"name": name, "milliseconds": elapsed})
    return {
        "summary_ms": describe([row["milliseconds"] for row in samples]),
        "by_view_ms": {
            name: describe([row["milliseconds"] for row in samples if row["name"] == name])
            for name in arrays
        },
        "samples": samples,
        "scope": "Normalized CPU float32 CHW -> CUDA FP16 -> CPU float32 logits, synchronized. Includes transfers; excludes decode/postprocessing/HTTP.",
    }


def reference_and_export(output, inputs, repeats, *, export=True, observer=None):
    import onnx
    import torch

    from gardirop_ai_clothing.image.birefnet_local import load_birefnet_model
    from gardirop_ai_clothing.model_specs import BIREFNET_REVISION, SEGMENTATION_PROFILE

    settings = get_settings()
    print("Sabitlenmiş BiRefNet, üretimdeki yükleyiciyle CUDA FP16 olarak açılıyor...", flush=True)
    model, device = load_birefnet_model(settings.model_manifest_path, device="cuda")
    if device != "cuda":
        raise RuntimeError("CUDA required.")

    class LastLogits(torch.nn.Module):
        def __init__(self, network):
            super().__init__()
            self.network = network

        def forward(self, pixels):
            values = self.network(pixels)
            return values[-1] if isinstance(values, (list, tuple)) else values

    wrapper = LastLogits(model).eval().requires_grad_(False)

    def runner(chw):
        validate_fixed_input(chw)
        with torch.inference_mode(), torch.autocast("cuda", enabled=False):
            value = wrapper(torch.from_numpy(chw).unsqueeze(0).to("cuda", dtype=torch.float16))
            return validate_logits(value.detach().float().cpu().numpy())

    cases = process_cases(output, inputs, runner, "torch")
    timing = benchmark(inputs, runner, repeats)
    save_json(
        output / "torch_reference.json", {"status": "COMPLETED", "cases": cases, "timing": timing}
    )
    if not export:
        return {
            "status": "PASSED",
            "reference_timing": timing["summary_ms"],
            "memory_snapshot": observer() if observer is not None else None,
        }
    register_deform_symbolic()
    example = preprocess_birefnet(decode_uploaded_image(Path(inputs[0]["path"]).read_bytes()))
    tensor = torch.from_numpy(example).unsqueeze(0).to("cuda", dtype=torch.float16)
    path = output / "birefnet_1024x704_fp16.onnx"
    print(
        "Sabit boyutlu ONNX export başlıyor; bu işlem fotoğraf işleme süresinden uzundur...",
        flush=True,
    )
    started = time.perf_counter()
    with torch.inference_mode(), torch.autocast("cuda", enabled=False):
        torch.onnx.export(
            wrapper,
            (tensor,),
            str(path),
            input_names=["pixels"],
            output_names=["logits"],
            opset_version=OPSET,
            dynamo=False,
            do_constant_folding=True,
            keep_initializers_as_inputs=False,
            external_data=False,
        )
    onnx.checker.check_model(str(path))
    graph = onnx.load(str(path), load_external_data=False)
    shape = [value.dim_value for value in graph.graph.input[0].type.tensor_type.shape.dim]
    if (
        tuple(shape) != INPUT_SHAPE
        or graph.graph.input[0].type.tensor_type.elem_type != onnx.TensorProto.FLOAT16
    ):
        raise ValueError("Exported graph input shape/dtype differs from the fixed contract.")
    domains = sorted({node.domain for node in graph.graph.node})
    if any(domain not in {"", "ai.onnx"} for domain in domains):
        raise ValueError(f"Unexpected nonstandard operator domains: {domains}")
    deform_count = sum(node.op_type == "DeformConv" for node in graph.graph.node)
    if deform_count == 0:
        raise ValueError("Expected DeformConv nodes are missing from the exported graph.")
    artifact = {
        "status": "EXPORTED",
        "file": path.name,
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "seconds": time.perf_counter() - started,
        "opset": OPSET,
        "input_nchw": list(INPUT_SHAPE),
        "precision": "fp16",
        "revision": BIREFNET_REVISION,
        "preprocessing_profile": SEGMENTATION_PROFILE,
        "exporter": "torchscript_static_with_standard_DeformConv_symbolic",
        "dynamic_shapes_supported": False,
        "deform_conv_nodes": deform_count,
        "domains": domains,
    }
    save_json(output / "artifact.json", artifact)
    return {"status": "PASSED", "artifact": artifact, "reference_timing": timing["summary_ms"]}


def ort_compare(output, inputs, repeats):
    artifact = json.loads((output / "artifact.json").read_text())
    path = output / artifact["file"]
    if sha256(path) != artifact["sha256"]:
        raise ValueError("ONNX artifact checksum mismatch.")
    print("ONNX Runtime CUDA oturumu açılıyor; CPU yürütmesine izin verilmiyor...", flush=True)
    session = make_session(path, output / "ort_profile")
    spec = session.get_inputs()
    if len(spec) != 1 or spec[0].shape != list(INPUT_SHAPE) or spec[0].type != "tensor(float16)":
        raise ValueError("Unexpected ONNX input schema.")

    def runner(chw):
        validate_fixed_input(chw)
        data = np.ascontiguousarray(chw[None], dtype=np.float16)
        return validate_logits(session.run(["logits"], {"pixels": data})[0])

    sample = preprocess_birefnet(decode_uploaded_image(Path(inputs[0]["path"]).read_bytes()))
    runner(sample)
    evidence = end_profile(session)
    cases = process_cases(output, inputs, runner, "ort")
    timing = benchmark(inputs, runner, repeats)
    return {
        "status": "PASSED",
        "provider_evidence": evidence,
        "cases": cases,
        "all_image_gates_passed": all(row["quality"]["passed"] for row in cases),
        "timing": timing,
    }


def downstream(output, inputs, baseline, *, candidate_backend="ort"):
    from gardirop_ai_clothing.analysis import AnalyzedView, create_analysis_service
    from gardirop_ai_clothing.benchmark_comparison import embedding_drift
    from gardirop_ai_clothing.embeddings.marqo import MARQO_MODEL_NAME
    from gardirop_ai_clothing.labeling.color import view_palette
    from gardirop_ai_clothing.schemas import ViewType
    from gardirop_ai_clothing.view_snapshot import StoredGarmentImage

    settings = get_settings().model_copy(update={"device": "cuda", "marqo_precision": "fp16"})
    service = create_analysis_service(settings)
    encoder = service.manager.get_model(MARQO_MODEL_NAME)
    results = {}
    for backend in ("torch", candidate_backend):
        results[backend] = {}
        for item, parent in CASES:
            views = []
            for view in ("front", "back"):
                folder = output / backend / f"{item}_{view}"
                info = json.loads((folder / "view.json").read_text())
                rgb = read_rgb(folder / "clean.webp")
                with Image.open(folder / "cutout.png") as cutout:
                    palette = view_palette(cutout)
                prepared = StoredGarmentImage(
                    source_size=tuple(info["source_size"]),
                    output_size=tuple(info["output_size"]),
                    white_webp=(folder / "clean.webp").read_bytes(),
                    rotation_degrees=info["rotation_degrees"],
                    color_palette=palette,
                )
                views.append(
                    AnalyzedView(
                        view_type=ViewType(view.upper()),
                        prepared=prepared,
                        embedding=encoder.encode(rgb),
                        encoder_precision="fp16",
                        options=ImagePreparationOptions(**info["options"]),
                    )
                )
            pair = service.finish_pair(front=views[0], back=views[1], main_category=parent)
            data = {
                "tags": pair.tags.model_dump(
                    mode="json", include={"sub_category", "color", "season", "has_print"}
                ),
                "classification": asdict(pair.classification),
                "embedding": pair.embedding.tolist(),
            }
            results[backend][item] = data
    rows = {}
    for item, _ in CASES:
        left, right = results["torch"][item], results[candidate_backend][item]
        saved = baseline / "cases" / item
        old = json.loads((saved / "result.json").read_text())
        old_vector = np.asarray(
            json.loads((saved / "embedding.json").read_text())["values"], dtype=np.float32
        )
        # API tag names use camelCase; the internal core uses snake_case.
        expected_tags = {
            "sub_category": old["tags"]["subCategory"],
            "color": old["tags"]["color"],
            "season": old["tags"]["season"],
            "has_print": old["tags"]["hasPrint"],
        }
        reference_ok = left["tags"] == expected_tags and np.array_equal(
            np.asarray(left["embedding"], dtype=np.float32), old_vector
        )
        for view in ("front", "back"):
            reference_ok = reference_ok and np.array_equal(
                read_rgb(saved / f"{view}.webp"),
                read_rgb(output / "torch" / f"{item}_{view}" / "clean.webp"),
            )
        drift = embedding_drift(old_vector.tolist(), right["embedding"])
        # embedding_drift validates 1536D float32 and unit front/back halves.
        rank_left = [a["class_id"] for a in left["classification"]["alternatives"][:3]]
        rank_right = [a["class_id"] for a in right["classification"]["alternatives"][:3]]
        rows[item] = {
            "reference_matches_api_baseline": bool(reference_ok),
            "tags_identical": left["tags"] == right["tags"],
            "top3_identical": rank_left == rank_right,
            "reference_tags": left["tags"],
            "candidate_tags": right["tags"],
            "embedding_drift": drift,
        }
        rows[item]["passed"] = bool(
            reference_ok
            and rows[item]["tags_identical"]
            and rows[item]["top3_identical"]
            and drift["within_tolerance"]
        )
    save_json(output / "downstream_vectors.json", results)
    return {
        "status": "PASSED",
        "cases": rows,
        "all_downstream_gates_passed": all(row["passed"] for row in rows.values()),
        "models_loaded": list(service.manager.loaded_models),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage", choices=["tiny", "reference_export", "ort", "downstream"], required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    allowed = (ROOT / "outputs/onnx_compare").resolve()
    if not output.is_relative_to(allowed) or output == allowed or not output.is_dir():
        parser.error("Output must be an existing isolated run under outputs/onnx_compare.")
    result = {"status": "FAILED", "stage": args.stage}
    import sys

    if Path(sys.prefix).resolve() != (ROOT / ".venv-onnx").resolve():
        parser.error("Run workers only in the prepared .venv-onnx overlay.")
    try:
        import torch

        if not torch.cuda.is_available() or not 1 <= args.repeats <= 30:
            raise ValueError("CUDA and 1..30 repeats are required.")
        inputs = json.loads((output / "inputs.json").read_text())
        if args.stage == "tiny":
            result = tiny_deform_test(output)
        elif args.stage == "reference_export":
            result = reference_and_export(output, inputs, args.repeats)
        elif args.stage == "ort":
            result = ort_compare(output, inputs, args.repeats)
        else:
            result = downstream(output, inputs, args.baseline)
        result["lifetime_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        result["memory_scope"] = (
            "Process RAM peak; ORT GPU allocations are not measured by PyTorch's allocator. Export peak is not steady inference memory."
        )
    except Exception as exc:
        result.update(status="FAILED", error=str(exc), error_type=type(exc).__name__)
        traceback.print_exc()
    save_json(output / f"{args.stage}.json", result)
    print(f"{args.stage}: {result['status']}", flush=True)
    if result["status"] != "PASSED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
