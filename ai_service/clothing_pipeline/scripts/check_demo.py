"""Construct the real UI without opening a port or loading neural models."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

import gradio as gr

from gardirop_ai_clothing.config import get_settings
from gardirop_ai_clothing.demo_controller import DemoController
from gardirop_ai_clothing.jobs import create_draft_service
from gardirop_ai_clothing.local_demo import build_demo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    settings = get_settings()
    output = args.output_dir or settings.output_dir / "demo_check" / f"run_{uuid4().hex[:10]}"
    output.mkdir(parents=True, exist_ok=False)
    settings = settings.model_copy(update={"draft_root": output / "store"})
    report = {
        "status": "STARTED",
        "scope": "UI construction only; no server or neural inference.",
        "training_run": False,
        "encoder_inference": False,
        "backend_connected": False,
    }
    try:
        with create_draft_service(settings) as service:
            app = build_demo(DemoController(service, output / "exports"))
            dependencies = app.config["dependencies"]
            if not dependencies or any(d["api_visibility"] != "private" for d in dependencies):
                raise ValueError("UI event visibility mismatch.")
            if service.analysis.manager.loaded_models:
                raise ValueError("UI construction unexpectedly loaded models.")
            report.update(
                status="UI_READY",
                gradio_version=gr.__version__,
                event_handlers=len(dependencies),
                models_loaded=[],
                launch_command="make demo",
                local_url=f"http://127.0.0.1:{settings.demo_port}",
            )
    except Exception as exc:
        report.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        (output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
