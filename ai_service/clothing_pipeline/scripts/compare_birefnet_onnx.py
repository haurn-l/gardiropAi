"""Sequential CUDA parity experiment; never change the production segmentation backend."""

import argparse
import html
import importlib.metadata
import json
import os
import shutil
import socket
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from gardirop_ai_clothing.onnx_experiment import INPUT_SHAPE, POLICY, collect_inputs, save_json

ROOT = Path(__file__).resolve().parents[1]


def render_report(output, report, inputs):
    blocks = []
    for entry in inputs:
        name = entry["name"]
        left = output / "torch" / name / "clean.webp"
        right = output / "ort" / name / "clean.webp"
        if not left.is_file() or not right.is_file():
            continue
        blocks.append(f"""<h2>{html.escape(name)}</h2><div class="photos">
<figure><img src="torch/{name}/clean.webp"><figcaption>PyTorch FP16</figcaption></figure>
<figure><img src="ort/{name}/clean.webp"><figcaption>ONNX Runtime CUDA FP16</figcaption></figure>
<figure><img src="torch/{name}/alpha.png"><figcaption>PyTorch maskesi</figcaption></figure>
<figure><img src="ort/{name}/alpha.png"><figcaption>ONNX maskesi</figcaption></figure></div>""")
    text = html.escape(json.dumps(report, ensure_ascii=False, indent=2))
    (output / "report.html").write_text(f"""<!doctype html><html lang="tr"><meta charset="utf-8">
<title>GardropAI OPT-05B</title><style>
body{{font:16px system-ui;max-width:1400px;margin:30px auto;padding:0 20px;background:#f4f4f4;color:#111}}
.photos{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}figure{{margin:0;background:white;padding:8px}}
img{{width:100%;height:360px;object-fit:contain}}figcaption{{text-align:center}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}
@media(max-width:800px){{.photos{{grid-template-columns:repeat(2,1fr)}}}}</style>
<h1>OPT-05B · Sabit boyutlu ONNX karşılaştırması</h1>
<p>Yalnız 3 ürün / 6 üretilmiş fotoğraf. Görsel inceleme gereklidir. API segmentasyonu değiştirilmedi.
Bu süreler segmentasyon ve aktarım içindir; HTTP uçtan uca süreleri değildir.</p>
<p>Durum: <b>{html.escape(report["status"])}</b></p>{"".join(blocks)}<h2>Ölçümler ve kontroller</h2><pre>{text}</pre></html>""")


def run_stage(python, stage, output, baseline, repeats, env):
    command = [
        str(python),
        str(ROOT / "scripts/onnx_birefnet_worker.py"),
        "--stage",
        stage,
        "--output",
        str(output),
        "--baseline",
        str(baseline),
        "--repeats",
        str(repeats),
    ]
    print(f"\nAşama başlıyor: {stage}", flush=True)
    process = None
    with (output / f"{stage}.log").open("w") as log:
        try:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in process.stdout:
                log.write(line)
                log.flush()
                print(line, end="", flush=True)
            code = process.wait()
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    path = output / f"{stage}.json"
    data = json.loads(path.read_text()) if path.is_file() else {}
    if code != 0 or data.get("status") != "PASSED":
        raise RuntimeError(f"{stage} tamamlanamadı. Kayıt: {output / f'{stage}.log'}")
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 30:
        parser.error("repeats must be 1..30.")
    for port in (7861, 8001, 8002):
        with socket.socket() as probe:
            probe.settimeout(0.2)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                parser.error(f"{port} açık. API/demo terminalini Ctrl+C ile durdur.")
    overlay = ROOT / ".venv-onnx"
    if overlay.is_symlink() or not overlay.resolve().is_relative_to(ROOT):
        parser.error("Unsafe overlay path.")
    state = json.loads((ROOT / "outputs/onnx_environment/state.json").read_text())
    if state.get("status") != "READY":
        parser.error("Run make onnx-env first.")
    for name in ("torch", "torchvision", "numpy", "pillow", "transformers", "nvidia-cudnn-cu13"):
        if importlib.metadata.version(name) != state["base_versions"].get(name):
            parser.error(f"Base dependency changed since overlay preparation: {name}")
    if shutil.disk_usage(ROOT).free < 8 * 1024**3:
        parser.error("At least 8 GiB free disk is required for experiment artifacts.")
    baseline = args.baseline.expanduser().resolve()
    inputs = collect_inputs(ROOT, baseline)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    parent = ROOT / "outputs/onnx_compare"
    if not parent.resolve().is_relative_to(ROOT):
        parser.error("Unsafe output folder.")
    output = parent / stamp
    output.mkdir(parents=True, exist_ok=False)
    save_json(output / "inputs.json", inputs)
    env = os.environ.copy()
    env.update(
        PYTHONPATH=str(ROOT / "src"),
        PYTHONDONTWRITEBYTECODE="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_MODULES_CACHE=str(ROOT / "outputs/hf_modules"),
        GRADIO_ANALYTICS_ENABLED="False",
        TMPDIR=str(output / "tmp"),
        TORCH_HOME=str(output / "torch_cache"),
        TRITON_CACHE_DIR=str(output / "triton_cache"),
        CUDA_CACHE_PATH=str(output / "cuda_cache"),
        XDG_CACHE_HOME=str(output / "cache"),
        GARDROPAI_DEVICE="cuda",
        GARDROPAI_MARQO_PRECISION="fp16",
    )
    (output / "tmp").mkdir()
    report = {
        "status": "FAILED",
        "stage": "OPT-05B",
        "training_run": False,
        "backend_connected": False,
        "production_backend_changed": False,
        "input_shape_nchw": list(INPUT_SHAPE),
        "dynamic_shapes_supported": False,
        "policy": POLICY,
        "baseline": str(baseline),
        "steps": {},
        "scope": "Six generated demo images. Local segmentation microbenchmark; not HTTP latency, production concurrency or population accuracy.",
        "environment": state["details"],
    }
    print(f"OPT-05B sonuç klasörü: {output}", flush=True)
    try:
        for stage in ("tiny", "reference_export", "ort", "downstream"):
            report["steps"][stage] = run_stage(
                overlay / "bin/python", stage, output, baseline, args.repeats, env
            )
            save_json(output / "report.json", report)
        left = report["steps"]["reference_export"]["reference_timing"]
        right = report["steps"]["ort"]["timing"]["summary_ms"]
        report["segmentation_ms"] = {
            "pytorch_fp16": left,
            "onnxruntime_cuda_fp16": right,
            "mean_speedup": left["mean"] / right["mean"],
        }
        report["all_demo_gates_passed"] = bool(
            report["steps"]["ort"]["all_image_gates_passed"]
            and report["steps"]["downstream"]["all_downstream_gates_passed"]
        )
        report["status"] = (
            "DEMO_GATES_PASSED_REVIEW_REQUIRED"
            if report["all_demo_gates_passed"]
            else "QUALITY_REJECTED"
        )
        report["decision"] = (
            "Record candidate only. Visual review and API integration timing remain separate steps."
        )
    except KeyboardInterrupt:
        report["status"] = "INTERRUPTED"
    except Exception as exc:
        report["error"] = str(exc)
    finally:
        save_json(output / "report.json", report)
        render_report(output, report, inputs)
    print(
        json.dumps(
            {
                key: report.get(key)
                for key in (
                    "status",
                    "error",
                    "all_demo_gates_passed",
                    "segmentation_ms",
                    "production_backend_changed",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"Ana rapor: {output / 'report.json'}")
    print(f"Görsel rapor: {output / 'report.html'}")
    if report["status"] != "DEMO_GATES_PASSED_REVIEW_REQUIRED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
