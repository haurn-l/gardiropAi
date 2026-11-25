"""Launch the local clothing demo through the shared application service."""

import argparse
import logging
import os

from gardirop_ai_clothing.config import get_settings
from gardirop_ai_clothing.demo_controller import DemoController
from gardirop_ai_clothing.jobs import create_draft_service
from gardirop_ai_clothing.labeling.attribute_bank import load_bank
from gardirop_ai_clothing.local_demo import build_demo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"])
    args = parser.parse_args()
    settings = get_settings()
    if args.device:
        settings = settings.model_copy(update={"device": args.device})
    os.environ.setdefault("GRADIO_TEMP_DIR", str(settings.output_dir / "demo_cache"))
    os.environ.setdefault("HF_MODULES_CACHE", str(settings.output_dir / "hf_modules"))
    load_bank(settings.attribute_bank_dir)
    logging.basicConfig(level=logging.INFO)
    service = create_draft_service(settings)
    try:
        controller = DemoController(service, settings.demo_export_dir)
        demo = build_demo(controller)
        demo.launch(
            server_name="127.0.0.1",
            server_port=args.port or settings.demo_port,
            share=False,
            inbrowser=False,
            allowed_paths=[str(settings.demo_export_dir.resolve())],
            max_file_size=settings.max_upload_mb * 1024 * 1024,
            enable_monitoring=False,
            footer_links=[],
        )
    finally:
        service.close(timeout=60)


if __name__ == "__main__":
    main()
