"""Two fresh sequential GPU runs; no production precision setting is changed."""

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from gardirop_ai_clothing.config import get_settings

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20:
        parser.error("repeats must be 1..20.")
    baseline = args.baseline.expanduser().resolve()
    reference = json.loads((baseline / "report.json").read_text())
    if (
        reference.get("status") != "COMPLETED"
        or reference.get("marqo_precision_requested", "fp32") != "fp32"
    ):
        parser.error("A completed FP32 baseline is required.")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    output = ROOT / "outputs" / "marqo_precision_comparison" / stamp
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "status": "FAILED",
        "default_precision": get_settings().marqo_precision,
        "production_setting_changed": False,
        "training_run": False,
        "backend_connected": False,
        "baseline": str(baseline),
        "runs": {},
        "scope": "Three repeated demo products; not a general accuracy or retrieval evaluation.",
    }
    print(f"FP32/FP16 karşılaştırma klasörü: {output}", flush=True)
    try:
        for precision in ("fp32", "fp16"):
            directory = ROOT / "outputs" / "api_baseline" / f"{stamp}_{precision}"
            comparison = (
                baseline if precision == "fp32" else Path(report["runs"]["fp32"]["directory"])
            )
            print(
                f"\nBaşlıyor: yeni {precision.upper()} sunucusu; diğer sunucu kapalı olmalı.",
                flush=True,
            )
            process = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "benchmark_api.py"),
                    "--prepared",
                    "--repeats",
                    str(args.repeats),
                    "--marqo-precision",
                    precision,
                    "--comparison-mode",
                    "strict" if precision == "fp32" else "fp16",
                    "--compare",
                    str(comparison),
                    "--output",
                    str(directory),
                ],
                cwd=ROOT,
            )
            path = directory / "report.json"
            result = json.loads(path.read_text()) if path.is_file() else {}
            report["runs"][precision] = {
                "directory": str(directory),
                "exit_code": process.returncode,
                "status": result.get("status"),
                "report": str(path),
            }
            save(output / "report.json", report)
            if process.returncode != 0 or result.get("status") != "COMPLETED":
                raise RuntimeError(
                    f"{precision.upper()} ölçümü/kabul kontrolü tamamlanmadı. Ayrıntı: {path}"
                )
        old = json.loads(Path(report["runs"]["fp32"]["report"]).read_text())
        new = json.loads(Path(report["runs"]["fp16"]["report"]).read_text())
        if old["inputs"] != new["inputs"]:
            raise RuntimeError("FP32 and FP16 runs used different input files/categories.")
        report["quality_comparison"] = new["quality_comparison"]
        report["model_parameters_mib"] = {
            "fp32": old["marqo_runtime"]["parameter_mib"],
            "fp16": new["marqo_runtime"]["parameter_mib"],
        }
        report["server_memory_max_mib"] = {
            "fp32": old["server_memory_max_mib"],
            "fp16": new["server_memory_max_mib"],
        }
        report["encoder_mean_ms"] = {
            "fp32": old["stage_summary_ms"]["measured"]["marqo_encode"]["mean"],
            "fp16": new["stage_summary_ms"]["measured"]["marqo_encode"]["mean"],
        }
        report["end_to_end_seconds"] = {
            scenario: {
                precision: run["summary_seconds"][scenario][
                    "back_request_start_to_assets_received_seconds"
                ]
                for precision, run in (("fp32", old), ("fp16", new))
            }
            for scenario in ("back_immediate", "front_ready_before_back")
        }
        report["candidate_passed_demo_gates"] = new["quality_comparison"]["all_checks_passed"]
        report["decision"] = "Experiment recorded; configured production policy was not changed."
        report["status"] = "COMPLETED"
    except Exception as error:
        report["error"] = str(error)
    finally:
        save(output / "report.json", report)
    terminal = {
        key: report.get(key)
        for key in (
            "status",
            "error",
            "default_precision",
            "production_setting_changed",
            "candidate_passed_demo_gates",
            "model_parameters_mib",
            "encoder_mean_ms",
            "server_memory_max_mib",
        )
    }
    terminal["latency_p95_seconds"] = {
        scenario: {precision: values["p95"] for precision, values in rows.items()}
        for scenario, rows in report.get("end_to_end_seconds", {}).items()
    }
    print(json.dumps(terminal, ensure_ascii=False, indent=2))
    print(f"Karşılaştırma raporu: {output / 'report.json'}")
    if report["status"] != "COMPLETED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
