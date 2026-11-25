"""Fresh sequential PyTorch/TensorRT loopback HTTP comparison with all assets downloaded."""

import argparse
import html
import json
import os
import signal
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from gardirop_ai_clothing.onnx_experiment import save_json

ROOT = Path(__file__).resolve().parents[1]


def run_measurement(
    python,
    output,
    reference,
    backend,
    trt_run,
    repeats,
    log,
    *,
    comparison_mode=None,
    release_warmup_cache=False,
    shape_suite=None,
):
    command = [
        str(python),
        str(ROOT / "scripts/benchmark_api.py"),
        "--prepared",
        "--marqo-precision",
        "fp16",
        "--repeats",
        str(repeats),
        "--segmentation-backend",
        backend,
        "--output",
        str(output),
        "--comparison-mode",
        comparison_mode or ("trt" if backend == "tensorrt" else "strict"),
        "--release-warmup-cache" if release_warmup_cache else "--no-release-warmup-cache",
    ]
    if reference is not None:
        command.extend(["--compare", str(reference)])
    if shape_suite is not None:
        command.extend(["--shape-suite", str(shape_suite)])
    if backend == "tensorrt":
        command.extend(["--tensorrt-run", str(trt_run)])
    env = os.environ.copy()
    env.update(
        PYTHONPATH=str(ROOT / "src"),
        PYTHONDONTWRITEBYTECODE="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        GRADIO_ANALYTICS_ENABLED="False",
    )
    process = None
    print(f"\nHTTP ölçümü: {backend}; startup cache release: {release_warmup_cache}", flush=True)
    with log.open("w") as stream:
        try:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=env,
                start_new_session=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in process.stdout:
                stream.write(line)
                stream.flush()
                print(line, end="", flush=True)
            code = process.wait()
        finally:
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
    path = output / "report.json"
    report = json.loads(path.read_text()) if path.is_file() else {}
    if code != 0 or report.get("status") != "COMPLETED":
        raise RuntimeError(
            f"{backend} measurement failed; inspect {log} and {output / 'server.log'}."
        )
    if not report.get("measured_segmentation_routing_valid"):
        raise RuntimeError("Real measured backend routing was not demonstrated.")
    return report


def render(output, report, runs):
    blocks = []
    for item in ("tshirt", "jeans", "jacket"):
        for view in ("front", "back"):
            paths = [
                runs[backend] / "cases" / item / f"{view}.webp"
                for backend in ("pytorch", "tensorrt")
            ]
            if not all(path.is_file() for path in paths):
                continue
            figures = []
            for backend, path in zip(("PyTorch FP16", "TensorRT FP16"), paths, strict=True):
                relative = os.path.relpath(path, output)
                figures.append(
                    f'<figure><img src="{html.escape(relative, quote=True)}"><figcaption>{backend}</figcaption></figure>'
                )
            blocks.append(f'<h2>{item} / {view}</h2><div class="pair">{"".join(figures)}</div>')
    data = html.escape(json.dumps(report, ensure_ascii=False, indent=2))
    (output / "report.html").write_text(f"""<!doctype html><html lang="tr"><meta charset="utf-8">
<title>GardropAI OPT-05D</title><style>body{{font:16px system-ui;max-width:1100px;margin:30px auto;padding:15px}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:15px}}figure{{margin:0}}img{{width:100%;height:380px;object-fit:contain}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere}}</style><h1>OPT-05D · Yerel HTTP karşılaştırması</h1>
<p>Ön fotoğraf hazırken ve arka fotoğraf hemen gönderildiğinde: son fotoğraf isteğinden tüm çıktıların indirilmesine kadar.
Telefon ağı, Spring Boot, veritabanı ve eşzamanlı kullanıcılar ölçüme dahil değildir. GPU bellek örnekleri tepe ölçümü değildir.</p>
<pre>{data}</pre>{"".join(blocks)}</html>""")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trt-run", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        parser.error("Use make compare-api-trt from the base environment.")
    if not 1 <= args.repeats <= 20:
        parser.error("repeats must be 1..20.")
    for port in (7861, 8001, 8002):
        with socket.socket() as probe:
            probe.settimeout(0.2)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                parser.error(f"{port} açık; ilgili API/demo terminalini Ctrl+C ile durdur.")
    trt_run = args.trt_run.expanduser().resolve()
    allowed = (ROOT / "outputs/tensorrt_compare").resolve()
    if not trt_run.is_relative_to(allowed):
        parser.error("Choose a local accepted OPT-05C run.")
    accepted = json.loads((trt_run / "report.json").read_text())
    if (
        accepted.get("status") != "DEMO_GATES_PASSED_REVIEW_REQUIRED"
        or accepted.get("all_demo_gates_passed") is not True
    ):
        parser.error("The TensorRT experiment did not pass its demo quality gates.")
    reference = Path(accepted["baseline"]).resolve()
    if not reference.is_relative_to((ROOT / "outputs/api_baseline").resolve()):
        parser.error("Unexpected original API baseline path.")
    overlay = ROOT / ".venv-trt"
    if (
        overlay.is_symlink()
        or not overlay.resolve().is_relative_to(ROOT)
        or not (overlay / "bin/python").is_file()
    ):
        parser.error("The prepared .venv-trt is required.")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    output = ROOT / "outputs/api_tensorrt_compare" / stamp
    if not output.resolve().is_relative_to(ROOT):
        parser.error("Unsafe output directory.")
    output.mkdir(parents=True, exist_ok=False)
    runs = {
        name: ROOT / "outputs/api_baseline" / f"{stamp}_{name}" for name in ("pytorch", "tensorrt")
    }
    report = {
        "stage": "OPT-05D",
        "status": "FAILED",
        "training_run": False,
        "backend_connected": False,
        "default_backend_changed": False,
        "accepted_engine_run": str(trt_run),
        "runs": {k: str(v) for k, v in runs.items()},
        "scope": "Sequential single-user loopback HTTP. Includes polling and downloading metadata, both images and embedding. Excludes phone/Spring/network/DB. Native GPU memory samples are not peaks.",
    }
    print(f"OPT-05D ana rapor klasörü: {output}", flush=True)
    try:
        left = run_measurement(
            sys.executable,
            runs["pytorch"],
            reference,
            "pytorch",
            trt_run,
            args.repeats,
            output / "pytorch.log",
        )
        right = run_measurement(
            overlay / "bin/python",
            runs["tensorrt"],
            runs["pytorch"],
            "tensorrt",
            trt_run,
            args.repeats,
            output / "tensorrt.log",
        )
        report["scenarios"] = {}
        for scenario in ("front_ready_before_back", "back_immediate"):
            field = "back_request_start_to_assets_received_seconds"
            a, b = (
                left["summary_seconds"][scenario][field],
                right["summary_seconds"][scenario][field],
            )
            report["scenarios"][scenario] = {
                "pytorch_seconds": a,
                "tensorrt_seconds": b,
                "mean_speedup": a["mean"] / b["mean"],
                "tensorrt_observed_p95_below_one_second": b["p95"] < 1,
            }
        report["startup_seconds"] = {
            "pytorch": left["server_startup_seconds"],
            "tensorrt": right["server_startup_seconds"],
        }
        report["gpu_process_samples_mib"] = {
            "pytorch": left["server_gpu_process_samples_mib"],
            "tensorrt": right["server_gpu_process_samples_mib"],
        }
        report["server_memory_max_mib"] = {
            "pytorch": left["server_memory_max_mib"],
            "tensorrt": right["server_memory_max_mib"],
        }
        report["quality_comparison"] = right["quality_comparison"]
        report["routing"] = right["segmentation_forward_counts"]
        report["status"] = "HTTP_DEMO_GATES_PASSED_REVIEW_REQUIRED"
    except KeyboardInterrupt:
        report["status"] = "INTERRUPTED"
    except Exception as exc:
        report["error"] = str(exc)
    finally:
        save_json(output / "report.json", report)
        render(output, report, runs)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Ana rapor: {output / 'report.json'}")
    print(f"Görsel rapor: {output / 'report.html'}")
    if report["status"] != "HTTP_DEMO_GATES_PASSED_REVIEW_REQUIRED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
