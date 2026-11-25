"""Explicit TensorRT API entrypoint; no environment edits, build or install."""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trt-run", type=Path, required=True)
    parser.add_argument("--release-warmup-cache", action="store_true")
    args = parser.parse_args()
    if Path(sys.prefix).resolve() != (ROOT / ".venv-trt").resolve():
        parser.error("Use make api-trt so TensorRT stays isolated from the base environment.")
    os.environ.update(
        GARDROPAI_API_RELEASE_WARMUP_CACHE="true" if args.release_warmup_cache else "false",
        GARDROPAI_DEVICE="cuda",
        GARDROPAI_SEGMENTATION_BACKEND="tensorrt",
        GARDROPAI_TENSORRT_RUN=str(args.trt_run.expanduser().resolve()),
        GARDROPAI_API_PRELOAD_MODELS="true",
        GARDROPAI_MARQO_PRECISION="fp16",
    )
    from gardirop_ai_clothing.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    import uvicorn

    uvicorn.run("gardirop_ai_clothing.app:app", host=settings.host, port=settings.port, workers=1)


if __name__ == "__main__":
    main()
