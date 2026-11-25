"""Record FP16 policy and OPT-05 prerequisites without installing or loading models."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from gardirop_ai_clothing.config import get_settings
from gardirop_ai_clothing.optimization_preflight import collect_report

ROOT = Path(__file__).resolve().parents[1]


def main():
    parent = ROOT / "outputs" / "optimization_preflight"
    if not parent.resolve().is_relative_to(ROOT):
        raise SystemExit("Report folder must remain inside clothing_pipeline.")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    directory = parent / stamp
    directory.mkdir(parents=True, exist_ok=False)
    report = {"status": "ACTION_REQUIRED", "errors": []}
    try:
        report = collect_report(get_settings(), ROOT)
    except Exception as exc:
        report["errors"].append(f"Preflight failed: {type(exc).__name__}")
    path = directory / "report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
    summary = {
        key: report.get(key)
        for key in (
            "status",
            "configured_device",
            "configured_marqo_precision",
            "effective_marqo_precision",
            "torch",
            "packages",
            "onnxruntime",
            "tensorrt",
            "disk_free_gib",
            "missing_export_runtime_packages",
            "errors",
        )
    }
    summary["segmentation"] = report.get("segmentation")
    summary["observed_shapes_nchw"] = report.get("shapes", {}).get("observed_shapes_nchw")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"OPT-05A raporu: {path}")
    print("Paket kurulmadı; model yüklenmedi; çıkarım, ONNX export ve engine derlemesi yapılmadı.")
    if report["status"] != "ENVIRONMENT_RECORDED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
